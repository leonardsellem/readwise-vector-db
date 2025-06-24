import json

import pytest

from readwise_vector_db.mcp.server import handle_client


class _Reader:
    """Minimal async reader returning provided bytes then EOF."""

    def __init__(self, first: bytes):
        self._first = first
        self._consumed = False

    async def readline(self):  # noqa: D401
        if self._consumed:
            return b""  # EOF
        self._consumed = True
        return self._first

    def at_eof(self):  # noqa: D401
        return self._consumed


class _Writer:
    """Capture writes in-memory for assertions."""

    def __init__(self):
        self.written: list[bytes] = []
        self.closed = False

    def write(self, data):  # noqa: D401
        self.written.append(data)

    async def drain(self):
        pass  # No back-pressure simulation

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass

    def get_extra_info(self, key):
        if key == "peername":
            return ("127.0.0.1", 55555)
        return None


@pytest.mark.asyncio
async def test_parse_error_results_in_jsonrpc_parse_error():
    """Send malformed JSON and expect a -32700 PARSE_ERROR response with id=null."""

    reader = _Reader(b"not-json\n")
    writer = _Writer()

    await handle_client(reader, writer)

    # One error response should have been written
    assert len(writer.written) == 1

    msg_json = json.loads(writer.written[0].decode().rstrip("\n"))

    assert msg_json["jsonrpc"] == "2.0"
    assert msg_json["id"] is None  # null in JSON
    assert msg_json["error"]["code"] == -32700  # PARSE_ERROR
    assert (
        "Invalid JSON" in msg_json["error"]["message"]
        or "Failed" in msg_json["error"]["message"]
    )
