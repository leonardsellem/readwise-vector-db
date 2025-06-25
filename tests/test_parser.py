from datetime import datetime, timezone

import pytest

from readwise_vector_db.jobs.parser import parse_highlight, parse_iso_datetime


@pytest.mark.parametrize(
    "input_str, expected",
    [
        (
            "2022-09-13T16:41:53.186Z",
            datetime(2022, 9, 13, 16, 41, 53, 186000, tzinfo=timezone.utc),
        ),
        (
            "2022-09-13T16:41:53+00:00",
            datetime(2022, 9, 13, 16, 41, 53, tzinfo=timezone.utc),
        ),
        (None, None),
        ("not-a-date", None),
    ],
)
# The parse_iso_datetime helper should gracefully parse common ISO 8601 formats or return None
def test_parse_iso_datetime(input_str, expected):
    assert parse_iso_datetime(input_str) == expected


def test_parse_highlight_basic():
    """parse_highlight should map nested Readwise JSON into a Highlight model."""
    raw = {
        "id": 42,
        "text": "Hello world",
        "url": "https://example.com/highlight/42",
        "tags": [{"name": "python"}, {"name": "testing"}],
        "highlighted_at": "2022-09-13T16:41:53.186Z",
        "updated_at": "2022-09-14T12:00:00.000Z",
        "book": {
            "id": 7,
            "title": "Effective Testing",
            "author": "T. Pytester",
            "category": "book",
            "source_url": "https://example.com/book/7",
        },
    }

    h = parse_highlight(raw)

    # Check direct mappings
    assert h.id == 42
    assert h.text == "Hello world"
    assert (
        h.url == "https://example.com/highlight/42"
    )  # url field takes precedence over book.source_url
    # Check nested book mapping
    assert h.source_type == "book"
    assert h.source_id == "7"  # Book id coerced to str
    assert h.title == "Effective Testing"
    assert h.author == "T. Pytester"
    # Tags extraction should flatten to list[str]
    assert h.tags == ["python", "testing"]
    # Dates parsed into aware datetimes
    assert h.highlighted_at.tzinfo is not None
    assert h.updated_at.tzinfo is not None
    # Embedding placeholder should be an empty list ready for later population
    assert h.embedding == []
