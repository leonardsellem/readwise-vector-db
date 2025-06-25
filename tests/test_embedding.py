import asyncio
import warnings
from unittest.mock import AsyncMock, patch

import openai
import pytest
import respx

from readwise_vector_db.core.embedding import (
    MAX_TOKENS,
    embed,
    num_tokens_from_string,
    truncate_text_to_tokens,
)


def test_num_tokens_from_string():
    text = "This is a test."
    assert num_tokens_from_string(text) == 5


def test_truncate_text_to_tokens():
    long_text = "test " * 10000
    truncated = truncate_text_to_tokens(long_text)
    assert num_tokens_from_string(truncated) <= MAX_TOKENS


@pytest.mark.asyncio
@respx.mock
async def test_embed_truncation():
    long_text = "test " * 10000
    mock_client = AsyncMock(spec=openai.AsyncClient)
    mock_response = AsyncMock()
    mock_response.data = [AsyncMock(embedding=[0.1, 0.2, 0.3])]
    mock_client.embeddings.create.return_value = asyncio.Future()
    mock_client.embeddings.create.return_value.set_result(mock_response)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = await embed(long_text, mock_client)
        assert len(w) == 1
        assert "truncated" in str(w[0].message).lower()

    assert result == [0.1, 0.2, 0.3]
    # Check that the text passed to the client was truncated
    called_with_text = mock_client.embeddings.create.call_args[1]["input"][0]
    assert num_tokens_from_string(called_with_text) <= MAX_TOKENS


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_embed_retry_logic(mock_sleep):
    mock_client = AsyncMock(spec=openai.AsyncClient)

    future1 = asyncio.Future()
    future1.set_exception(
        openai.RateLimitError("Rate limit exceeded", response=AsyncMock(), body=None)
    )
    future2 = asyncio.Future()
    mock_response = AsyncMock()
    mock_response.data = [AsyncMock(embedding=[0.4, 0.5, 0.6])]
    future2.set_result(mock_response)

    mock_client.embeddings.create.side_effect = [future1, future2]

    with warnings.catch_warnings(record=True) as w:
        result = await embed("test text", mock_client)
        assert len(w) == 1
        assert "rate limit exceeded" in str(w[0].message).lower()

    assert result == [0.4, 0.5, 0.6]
    assert mock_client.embeddings.create.call_count == 2
    mock_sleep.assert_called_once()


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_embed_max_retries_exhausted(mock_sleep):
    """Test that embed raises exception when all retries are exhausted."""
    mock_client = AsyncMock(spec=openai.AsyncClient)

    # ↳ Create multiple rate limit errors for all retry attempts
    rate_limit_error = openai.RateLimitError(
        "Rate limit exceeded", response=AsyncMock(), body=None
    )

    # ↳ Mock all retries to fail with rate limit error
    futures = []
    for _ in range(5):  # MAX_RETRIES = 5
        future = asyncio.Future()
        future.set_exception(rate_limit_error)
        futures.append(future)

    mock_client.embeddings.create.side_effect = futures

    # ↳ Should raise exception after all retries are exhausted
    with pytest.raises(
        Exception, match="Failed to get embedding after multiple retries"
    ):
        await embed("test text", mock_client)

    # ↳ Verify all retries were attempted
    assert mock_client.embeddings.create.call_count == 5
    # ↳ Verify sleep was called for each retry
    assert mock_sleep.call_count == 5
