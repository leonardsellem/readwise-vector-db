from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from readwise_vector_db.core.readwise import ReadwiseClient


@pytest.mark.asyncio
@respx.mock
async def test_readwise_client_export_pagination(respx_mock):
    # Mock the API responses for two pages
    respx_mock.get("https://readwise.io/api/v2/export/").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "user_book_id": 1,
                            "title": "Book 1",
                            "highlights": [{"text": "h1"}],
                        }
                    ],
                    "nextPageCursor": "page2",
                },
            ),
            httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "user_book_id": 2,
                            "title": "Book 2",
                            "highlights": [{"text": "h2"}],
                        }
                    ],
                    "nextPageCursor": None,
                },
            ),
        ]
    )

    client = ReadwiseClient(token="test", client=httpx.AsyncClient(), delay_seconds=0)
    results = [item async for item in client.export()]

    assert len(results) == 2
    assert results[0]["book"]["id"] == 1
    assert results[1]["book"]["id"] == 2


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_readwise_client_respects_delay(mock_sleep, respx_mock):
    respx_mock.get("https://readwise.io/api/v2/export/").mock(
        side_effect=[
            httpx.Response(
                200,
                json={"results": [], "nextPageCursor": "page2"},
            ),
            httpx.Response(
                200,
                json={"results": [], "nextPageCursor": None},
            ),
        ]
    )

    client = ReadwiseClient(token="test", client=httpx.AsyncClient(), delay_seconds=5)
    _ = [item async for item in client.export()]

    mock_sleep.assert_called_once_with(5)
