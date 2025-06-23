import asyncio
import warnings

import openai
import tiktoken

# Constants
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_ENCODING = "cl100k_base"
MAX_TOKENS = 8191
MAX_RETRIES = 5
INITIAL_DELAY_SECONDS = 1.0
BACKOFF_FACTOR = 2.0


def num_tokens_from_string(string: str, encoding_name: str = EMBEDDING_ENCODING) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens


def truncate_text_to_tokens(
    string: str, max_tokens: int = MAX_TOKENS, encoding_name: str = EMBEDDING_ENCODING
) -> str:
    """Truncates a text string to a maximum number of tokens."""
    encoding = tiktoken.get_encoding(encoding_name)
    encoded_string = encoding.encode(string)
    truncated_tokens = encoded_string[:max_tokens]
    return encoding.decode(truncated_tokens)


def _exponential_backoff(retries: int, initial_delay: float, factor: float):
    """Generator for exponential backoff delays."""
    delay = initial_delay
    for _ in range(retries):
        yield delay
        delay *= factor


async def embed(text: str, client: openai.AsyncClient) -> list[float]:
    """
    Generates an embedding for the given text using OpenAI's API.
    Truncates the text if it exceeds the model's token limit and retries on rate limit errors.
    """
    token_count = num_tokens_from_string(text)
    if token_count > MAX_TOKENS:
        warnings.warn(
            f"Text truncated from {token_count} to {MAX_TOKENS} tokens.", stacklevel=2
        )
        text = truncate_text_to_tokens(text)

    async def get_embedding_with_backoff():
        for attempt in _exponential_backoff(
            MAX_RETRIES, INITIAL_DELAY_SECONDS, BACKOFF_FACTOR
        ):
            try:
                response = await client.embeddings.create(
                    input=[text], model=EMBEDDING_MODEL
                )
                return response.data[0].embedding
            except openai.RateLimitError:
                warnings.warn(
                    f"Rate limit exceeded. Retrying in {attempt} seconds...",
                    stacklevel=2,
                )
                await asyncio.sleep(attempt)
        raise Exception("Failed to get embedding after multiple retries.")

    return await get_embedding_with_backoff()
