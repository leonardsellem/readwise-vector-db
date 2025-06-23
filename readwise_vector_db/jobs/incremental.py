import os
from typing import List, Optional

import httpx
import openai

from readwise_vector_db.core.embedding import embed
from readwise_vector_db.core.readwise import ReadwiseClient
from readwise_vector_db.db.database import AsyncSessionLocal
from readwise_vector_db.db.upsert import (
    get_sync_state,
    update_sync_state,
    upsert_highlights,
)
from readwise_vector_db.jobs.parser import parse_highlight
from readwise_vector_db.models import Highlight

BATCH_SIZE = 100
SERVICE_NAME = "readwise"


async def run_incremental_sync(since: Optional[str] = None) -> None:
    """
    Runs the incremental sync process to fetch, embed, and upsert highlights.
    """
    readwise_token = os.environ.get("READWISE_TOKEN")
    if not readwise_token:
        raise ValueError("READWISE_TOKEN environment variable not set.")

    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set.")

    openai_client = openai.AsyncClient(api_key=openai_api_key)

    async with AsyncSessionLocal() as session:
        if since is None:
            sync_state = await get_sync_state(SERVICE_NAME, session)
            if sync_state and sync_state.last_synced_at:
                since = sync_state.last_synced_at.isoformat()
                print(f"No 'since' date provided. Syncing since last sync: {since}")
            else:
                print(
                    "No last sync state found. Please run a full backfill first or provide a 'since' date."
                )
                return

        async with httpx.AsyncClient() as client:
            readwise_client = ReadwiseClient(token=readwise_token, client=client)

            print(f"Starting incremental sync for highlights since {since}...")

            batch: List[Highlight] = []
            highlights_count = 0
            async for highlight_data in readwise_client.export(updated_after=since):
                parsed = parse_highlight(highlight_data)
                embedding = await embed(
                    openai_client, f"{parsed.text} {parsed.note or ''}"
                )
                parsed.embedding = embedding
                batch.append(parsed)

                if len(batch) >= BATCH_SIZE:
                    await upsert_highlights(batch, session)
                    highlights_count += len(batch)
                    print(
                        f"Upserted batch of {len(batch)} highlights. Total: {highlights_count}"
                    )
                    batch = []

            if batch:
                await upsert_highlights(batch, session)
                highlights_count += len(batch)
                print(
                    f"Upserted final batch of {len(batch)} highlights. Total: {highlights_count}"
                )

            await update_sync_state(SERVICE_NAME, session)
            print("Incremental sync complete.")
