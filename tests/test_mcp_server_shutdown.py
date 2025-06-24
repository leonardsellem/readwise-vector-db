import asyncio

import pytest

from readwise_vector_db.mcp.server import MCPServer, _client_tasks, active_connections


class _DummyWriter:
    def __init__(self):
        self.closed = False
        self._closed_fut = asyncio.Future()

    def write(self, _):
        pass

    async def drain(self):
        pass

    def close(self):
        self.closed = True
        self._closed_fut.set_result(None)

    async def wait_closed(self):
        await self._closed_fut

    def get_extra_info(self, key):
        return ("127.0.0.1", 12345) if key == "peername" else None


@pytest.mark.asyncio
async def test_shutdown_closes_active_connections(monkeypatch):
    """MCPServer.shutdown closes writers and waits for tasks."""
    server = MCPServer()

    # Monkeypatch start_server to no-op so we can call start()
    async def _fake_start(*_args, **_kwargs):
        class _FakeServer:
            sockets = []

            def close(self):
                pass

            async def wait_closed(self):
                pass

        return _FakeServer()

    monkeypatch.setattr(asyncio, "start_server", _fake_start)

    await server.start()

    # Simulate active client task and writer
    writer = _DummyWriter()
    active_connections.add(writer)

    async def _dummy_task():
        await asyncio.sleep(0.05)

    task = asyncio.create_task(_dummy_task())
    _client_tasks.add(task)

    await server.shutdown()

    assert writer.closed, "Writer should be closed during shutdown"
    assert task.done(), "Client handler task should complete before shutdown returns"
