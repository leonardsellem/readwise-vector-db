import asyncio
from typing import Any, AsyncGenerator, Dict, Optional

import httpx


class ReadwiseClient:
    BASE_URL = "https://readwise.io"

    def __init__(self, token: str, client: httpx.AsyncClient, delay_seconds: int = 3):
        self._token = token
        self._client = client
        self._headers = {"Authorization": f"Token {self._token}"}
        self._delay_seconds = delay_seconds

    async def _get_paged_items(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Handles pagination for Readwise API endpoints."""
        next_page_cursor = None
        while True:
            if params is None:
                params = {}
            if next_page_cursor:
                params["pageCursor"] = next_page_cursor

            response = await self._client.get(
                f"{self.BASE_URL}{url}", headers=self._headers, params=params
            )
            response.raise_for_status()
            data = response.json()
            yield data

            next_page_cursor = data.get("nextPageCursor")
            if not next_page_cursor:
                break

            await asyncio.sleep(self._delay_seconds)

    async def export(
        self, updated_after: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Fetches all highlights from the Readwise export API.
        This method iterates through all books and their highlights.
        """
        params = {}
        if updated_after:
            params["updatedAfter"] = updated_after

        async for page in self._get_paged_items("/api/v2/export/", params):
            for book in page["results"]:
                for highlight in book.get("highlights", []):
                    # Add book info to each highlight for context
                    highlight_with_context = highlight.copy()
                    highlight_with_context["book"] = {
                        "id": book.get("user_book_id"),
                        "title": book.get("title"),
                        "author": book.get("author"),
                        "category": book.get("category"),
                        "source": book.get("source"),
                        "source_url": book.get("source_url"),
                    }
                    yield highlight_with_context

    async def reader_list(
        self, updated_after: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Fetches all documents from the Reader v3 list API."""
        params = {}
        if updated_after:
            params["updated__gt"] = updated_after

        async for page in self._get_paged_items("/api/v3/list/", params):
            for item in page["results"]:
                yield item
