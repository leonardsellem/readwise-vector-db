"""
Unit tests for the MCP Protocol Server.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from readwise_vector_db.mcp.framing import create_request, pack_mcp_message
from readwise_vector_db.mcp.server import MCPServer, active_connections, handle_client


class MockStreamReader:
    def __init__(self, messages=None):
        self.messages = messages or []
        self.message_idx = 0
        self._at_eof = False

    async def readline(self):
        if self._at_eof or self.message_idx >= len(self.messages):
            self._at_eof = True
            return b""

        msg = self.messages[self.message_idx]
        self.message_idx += 1
        return msg

    def at_eof(self):
        return self._at_eof

    def set_eof(self, is_eof=True):
        self._at_eof = is_eof


class MockStreamWriter:
    def __init__(self):
        self.written = []
        self.closed = False
        self._drain_delay = 0  # seconds
        self.drain_called = 0

    def write(self, data):
        self.written.append(data)

    async def drain(self):
        self.drain_called += 1
        if self._drain_delay:
            await asyncio.sleep(self._drain_delay)

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass

    def get_extra_info(self, key):
        if key == "peername":
            return ("127.0.0.1", 12345)
        return None

    def set_drain_delay(self, seconds):
        self._drain_delay = seconds


@pytest.mark.asyncio
class TestMCPServer:
    """Tests for the MCP Server"""

    def setup_method(self):
        # Clear active connections between tests
        active_connections.clear()

    async def test_handle_client_search(self):
        """Test handling a basic search request"""
        # Prepare a search request
        search_msg = create_request("search", {"q": "test query", "k": 5}, "123")
        search_bytes = pack_mcp_message(search_msg)

        # Setup mocks
        reader = MockStreamReader([search_bytes])
        writer = MockStreamWriter()

        # Mock the semantic_search function
        mock_results = [
            {"id": "1", "text": "Test result 1", "score": 0.9},
            {"id": "2", "text": "Test result 2", "score": 0.8},
        ]

        # Create mock that returns appropriate objects based on stream parameter
        def create_mock_semantic_search():
            def mock_semantic_search(*args, **kwargs):
                stream = kwargs.get("stream", False)
                if stream:
                    # Return async generator for streaming
                    async def async_gen():
                        for result in mock_results:
                            yield result

                    return async_gen()
                else:
                    # Return async function that returns list for non-streaming
                    async def async_list():
                        return mock_results

                    return async_list()

            return mock_semantic_search

        with patch(
            "readwise_vector_db.mcp.search_service.semantic_search",
            side_effect=create_mock_semantic_search(),
        ) as mock_search:
            # Process the client request
            await handle_client(reader, writer)

            # Check search was called correctly
            mock_search.assert_called_once_with(
                "test query", 5, None, None, None, None, stream=True
            )

            # Check the responses
            assert len(writer.written) == 2  # Two search results
            assert writer.closed is True

            # Verify response data
            responses = []
            for data in writer.written:
                response_json = json.loads(data.decode().strip())
                responses.append(response_json)

            # Check first response
            assert responses[0]["jsonrpc"] == "2.0"
            assert responses[0]["id"] == "123"
            assert responses[0]["result"]["id"] == "1"
            assert responses[0]["result"]["text"] == "Test result 1"
            assert responses[0]["result"]["score"] == 0.9

            # Check second response
            assert responses[1]["jsonrpc"] == "2.0"
            assert responses[1]["id"] == "123"
            assert responses[1]["result"]["id"] == "2"
            assert responses[1]["result"]["text"] == "Test result 2"
            assert responses[1]["result"]["score"] == 0.8

    async def test_handle_client_invalid_method(self):
        """Test handling invalid method requests"""
        # Prepare an invalid method request
        invalid_msg = create_request("invalid_method", {"q": "test"}, "123")
        invalid_bytes = pack_mcp_message(invalid_msg)

        # Setup mocks
        reader = MockStreamReader([invalid_bytes])
        writer = MockStreamWriter()

        # Process the client request
        await handle_client(reader, writer)

        # Check the response (should be an error)
        assert len(writer.written) == 1
        assert writer.closed is True

        # Parse response
        response_json = json.loads(writer.written[0].decode().strip())

        # Verify error
        assert response_json["jsonrpc"] == "2.0"
        assert response_json["id"] == "123"
        assert "error" in response_json
        assert response_json["error"]["code"] == -32601  # Method not found
        assert "Method not supported" in response_json["error"]["message"]

    async def test_handle_client_missing_params(self):
        """Test handling requests with missing parameters"""
        # Create request with empty params
        empty_params_msg = create_request("search", {}, "123")
        empty_params_bytes = pack_mcp_message(empty_params_msg)

        # Setup mocks
        reader = MockStreamReader([empty_params_bytes])
        writer = MockStreamWriter()

        # Process the client request
        await handle_client(reader, writer)

        # Check the response (should be an error)
        assert len(writer.written) == 1
        assert writer.closed is True

        # Parse response
        response_json = json.loads(writer.written[0].decode().strip())

        # Verify error
        assert response_json["jsonrpc"] == "2.0"
        assert response_json["id"] == "123"
        assert "error" in response_json
        assert response_json["error"]["code"] == -32602  # Invalid params
        assert "Missing or invalid 'q' parameter" in response_json["error"]["message"]

    async def test_handle_client_no_results(self):
        """Test handling a search with no results"""
        # Prepare a search request
        search_msg = create_request("search", {"q": "test query", "k": 5}, "123")
        search_bytes = pack_mcp_message(search_msg)

        # Setup mocks
        reader = MockStreamReader([search_bytes])
        writer = MockStreamWriter()

        # Create mock that returns empty results
        def create_mock_semantic_search():
            def mock_semantic_search(*args, **kwargs):
                stream = kwargs.get("stream", False)
                if stream:
                    # Return async generator for streaming
                    async def async_gen():
                        if (
                            False
                        ):  # This condition is never true, so the generator yields nothing
                            yield {}

                    return async_gen()
                else:
                    # Return async function that returns empty list for non-streaming
                    async def async_list():
                        return []

                    return async_list()

            return mock_semantic_search

        with patch(
            "readwise_vector_db.mcp.search_service.semantic_search",
            side_effect=create_mock_semantic_search(),
        ) as mock_search:
            # Process the client request
            await handle_client(reader, writer)

            # Check search was called
            mock_search.assert_called_once()

            # Check the empty response
            assert len(writer.written) == 1
            assert writer.closed is True

            # Verify response data
            response = json.loads(writer.written[0].decode().strip())
            assert response["jsonrpc"] == "2.0"
            assert response["id"] == "123"
            assert response["result"] == []

    async def test_handle_client_disconnection(self):
        """Test handling client disconnection during streaming"""
        # Prepare a search request
        search_msg = create_request("search", {"q": "test query", "k": 5}, "123")
        search_bytes = pack_mcp_message(search_msg)

        # Setup mocks
        reader = MockStreamReader([search_bytes])
        writer = MockStreamWriter()

        # Create results (more than we'll send)
        mock_results = [
            {"id": "1", "text": "Result 1", "score": 0.9},
            {"id": "2", "text": "Result 2", "score": 0.8},
            {"id": "3", "text": "Result 3", "score": 0.7},
        ]

        # Set reader to disconnect after first result
        reader.set_eof(False)  # Make sure it's not EOF to start

        # Create an async generator
        async def results_generator():
            # Wait a little to simulate work
            await asyncio.sleep(0.1)
            # Set EOF after the first result
            reader.set_eof(True)
            # Only yield the first result before client disconnects
            yield mock_results[0]
            # These would be sent if client hadn't disconnected
            yield mock_results[1]
            yield mock_results[2]

        mock_search = AsyncMock(return_value=results_generator())

        with patch(
            "readwise_vector_db.mcp.search_service.semantic_search", mock_search
        ):
            # Process the client request
            await handle_client(reader, writer)

            # Check search was called
            mock_search.assert_called_once()

            # Should have written only one result before detecting EOF
            assert len(writer.written) <= 1
            assert writer.closed is True

    async def test_back_pressure(self):
        """Test back-pressure handling with slow client"""
        # Prepare a search request
        search_msg = create_request("search", {"q": "test query", "k": 5}, "123")
        search_bytes = pack_mcp_message(search_msg)

        # Setup mocks
        reader = MockStreamReader([search_bytes])
        writer = MockStreamWriter()

        # Set a delay in the writer's drain method to simulate back-pressure
        writer.set_drain_delay(0.05)  # 50ms delay

        # Create some test results
        mock_results = [
            {"id": "1", "text": "Result 1", "score": 0.9},
            {"id": "2", "text": "Result 2", "score": 0.8},
            {"id": "3", "text": "Result 3", "score": 0.7},
        ]

        # Create mock that handles streaming
        def create_mock_semantic_search():
            def mock_semantic_search(*args, **kwargs):
                stream = kwargs.get("stream", False)
                if stream:
                    # Return async generator for streaming
                    async def async_gen():
                        for result in mock_results:
                            yield result

                    return async_gen()
                else:
                    # Return async function that returns list for non-streaming
                    async def async_list():
                        return mock_results

                    return async_list()

            return mock_semantic_search

        with patch(
            "readwise_vector_db.mcp.search_service.semantic_search",
            side_effect=create_mock_semantic_search(),
        ):
            # Process the client request
            await handle_client(reader, writer)

            # Check drain was called once per result for back-pressure
            assert writer.drain_called == 3

            # Verify we sent all results
            assert len(writer.written) == 3
            assert writer.closed is True

    async def test_active_connections_tracking(self):
        """Test that connections are properly tracked in active_connections"""
        # Clear the active_connections set at the beginning
        active_connections.clear()

        # Prepare a search request
        search_msg = create_request("search", {"q": "test"}, "123")
        search_bytes = pack_mcp_message(search_msg)

        # Setup mocks
        reader = MockStreamReader([search_bytes])
        writer = MockStreamWriter()

        # Manually add to active connections (this is what we're testing)
        active_connections.add(writer)
        assert len(active_connections) == 1
        assert writer in active_connections

        # Mock the semantic_search function and handle the client (which should remove the connection)
        with patch(
            "readwise_vector_db.mcp.search_service.semantic_search", return_value=[]
        ):
            # Process the client request
            await handle_client(reader, writer)

            # Verify connection was removed after handling
            assert len(active_connections) == 0
            assert writer not in active_connections

    @pytest.mark.asyncio
    async def test_server_start_stop(self):
        """Test server startup and shutdown"""
        # Create a mock server
        with patch("asyncio.start_server") as mock_start_server:
            server_mock = AsyncMock()
            mock_start_server.return_value = server_mock

            # Specify the behavior for close and wait_closed
            server_mock.close.return_value = None
            server_mock.wait_closed.return_value = None

            # Create a socket mock
            socket_mock = MagicMock()
            socket_mock.getsockname.return_value = ("127.0.0.1", 8375)
            server_mock.sockets = [socket_mock]

            # Initialize server
            server = MCPServer("127.0.0.1", 8375)

            # Start the server
            await server.start()

            # Check server was started with correct params
            # The server should now register the internal wrapper that tracks
            # client handler tasks instead of the raw ``handle_client``
            from readwise_vector_db.mcp.server import (
                _handle_client_wrapper,  # pylint: disable=import-error
            )

            mock_start_server.assert_called_once_with(
                _handle_client_wrapper, "127.0.0.1", 8375
            )

            # Shutdown the server
            await server.shutdown()

            # Verify server was closed
            server_mock.close.assert_called_once()
            server_mock.wait_closed.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_in_background(self):
        """Test the server's run_in_background context manager"""
        with (
            patch.object(MCPServer, "start") as mock_start,
            patch.object(MCPServer, "shutdown") as mock_shutdown,
        ):

            server = MCPServer()
            async with server.run_in_background():
                # Inside the context block, server should be started
                mock_start.assert_called_once()
                mock_shutdown.assert_not_called()

                # Do some work inside the context
                await asyncio.sleep(0.1)

            # After exiting context block, server should be shut down
            mock_shutdown.assert_called_once()


class TestServerIntegration:
    """Integration tests that test multiple components together"""

    @pytest.mark.asyncio
    async def test_search_integration(self):
        """Integration test for search functionality through server handling"""
        # Create a real search request
        request_msg = create_request(
            "search", {"q": "test query", "k": 5, "source_type": "book"}, "test-id-123"
        )
        request_bytes = pack_mcp_message(request_msg)

        # Mock components
        reader = MockStreamReader([request_bytes])
        writer = MockStreamWriter()

        # Create fake search results
        mock_results = [
            {
                "id": "highlight-1",
                "text": "This is a test highlight",
                "source_type": "book",
                "source_id": "book-123",
                "title": "Test Book",
                "author": "Test Author",
                "tags": ["test", "example"],
                "score": 0.95,
            }
        ]

        # Create mock that returns appropriate objects based on stream parameter
        def create_mock_semantic_search():
            def mock_semantic_search(*args, **kwargs):
                stream = kwargs.get("stream", False)
                if stream:
                    # Return async generator for streaming
                    async def async_gen():
                        for result in mock_results:
                            yield result

                    return async_gen()
                else:
                    # Return async function that returns list for non-streaming
                    async def async_list():
                        return mock_results

                    return async_list()

            return mock_semantic_search

        # Patch the semantic search function
        with patch(
            "readwise_vector_db.mcp.search_service.semantic_search",
            side_effect=create_mock_semantic_search(),
        ):

            # Run the client handler
            await handle_client(reader, writer)

            # Verify we got a response
            assert len(writer.written) == 1

            # Parse response
            response_data = writer.written[0].decode().strip()
            response = json.loads(response_data)

            # Check core response structure
            assert response["jsonrpc"] == "2.0"
            assert response["id"] == "test-id-123"

            # Check result content
            assert "result" in response
            assert response["result"]["id"] == "highlight-1"
            assert response["result"]["text"] == "This is a test highlight"
            assert response["result"]["score"] == 0.95
