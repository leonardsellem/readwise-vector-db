from unittest.mock import AsyncMock

import pytest

from readwise_vector_db.db.upsert import upsert_highlights
from readwise_vector_db.models import Highlight


@pytest.mark.asyncio
async def test_upsert_highlights():
    mock_session = AsyncMock()
    highlights = [
        Highlight(id="1", text="test1", source_type="article", embedding=[0.1]),
        Highlight(id="2", text="test2", source_type="book", embedding=[0.2]),
    ]

    await upsert_highlights(highlights, mock_session)

    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_highlights_no_highlights():
    mock_session = AsyncMock()
    await upsert_highlights([], mock_session)
    mock_session.execute.assert_not_called()
