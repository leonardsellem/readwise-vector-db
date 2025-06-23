import os
from typing import List

import httpx
import openai

from readwise_vector_db.core.embedding import embed
from readwise_vector_db.core.readwise import ReadwiseClient
from readwise_vector_db.db.database import AsyncSessionLocal
from readwise_vector_db.db.upsert import upsert_highlights
from readwise_vector_db.jobs.parser import parse_highlight
from readwise_vector_db.models import Highlight

BATCH_SIZE = 100


async def run_backfill():
    """
    Runs the backfill process to fetch, embed, and upsert all legacy highlights.
    """
    readwise_token = os.environ.get("READWISE_TOKEN")
    if not readwise_token:
        raise ValueError("READWISE_TOKEN environment variable not set.")

    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set.")

    openai_client = openai.AsyncClient(api_key=openai_api_key)

    async with httpx.AsyncClient() as http_client:
        readwise_client = ReadwiseClient(token=readwise_token, client=http_client)

        print("Starting backfill to retrieve, embed, and upsert legacy highlights...")

        batch: List[Highlight] = []
        async with AsyncSessionLocal() as session:
            async for raw_highlight in readwise_client.export():
                print(
                    f"Processing highlight: {raw_highlight.get('id')}, Text: {raw_highlight.get('text')[:50]}..."
                )

                embedding = await embed(raw_highlight["text"], openai_client)

                parsed_highlight = parse_highlight(raw_highlight)
                parsed_highlight.embedding = embedding

                batch.append(parsed_highlight)

                if len(batch) >= BATCH_SIZE:
                    print(f"Upserting batch of {len(batch)} highlights...")
                    await upsert_highlights(session, batch)
                    batch.clear()

            if batch:
                print(f"Upserting final batch of {len(batch)} highlights...")
                await upsert_highlights(session, batch)

        print("\nBackfill complete.")
