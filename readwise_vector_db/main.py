import asyncio
import json
from typing import Optional

import typer
from typing_extensions import Annotated

from readwise_vector_db.core.search import semantic_search
from readwise_vector_db.jobs.backfill import run_backfill
from readwise_vector_db.jobs.incremental import run_incremental_sync

app = typer.Typer()


@app.command()  # type: ignore
def sync(
    backfill: Annotated[
        bool,
        typer.Option(
            "--backfill",
            help="Backfill all legacy highlights from Readwise.",
        ),
    ] = False,
    since: Annotated[
        Optional[str],
        typer.Option(
            "--since",
            help="Run an incremental sync of highlights updated since a specific ISO 8601 date.",
        ),
    ] = None,
) -> None:
    """
    Sync highlights from Readwise.
    """
    if backfill and since:
        print("Error: --backfill and --since are mutually exclusive.")
        raise typer.Exit(code=1)

    if backfill:
        print("Starting Readwise backfill sync...")
        asyncio.run(run_backfill())
        print("Backfill sync complete.")
    elif since:
        asyncio.run(run_incremental_sync(since=since))
    else:
        # In the future, this will default to running an incremental sync
        # from the last sync date stored in the database.
        print("Starting incremental sync...")
        # For now, we'll just show the message.
        # asyncio.run(run_incremental_sync(since=None))
        print("Incremental sync (default) not yet fully implemented.")


@app.command()  # type: ignore
def search(
    q: Annotated[
        str,
        typer.Argument(
            ...,  # Ellipsis means the argument is required
            help="The search query.",
        ),
    ],
    k: Annotated[
        int,
        typer.Option(
            "--k",
            help="The number of results to return.",
        ),
    ] = 20,
) -> None:
    """
    Performs a semantic search for the given query.
    """
    print(f"Searching for: '{q}'...")
    results = asyncio.run(semantic_search(q, k))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    app()
