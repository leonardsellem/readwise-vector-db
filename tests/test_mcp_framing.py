"""
Unit tests for MCP Protocol Framing and Message Handling
"""

import json
from io import BytesIO

import pytest

from readwise_vector_db.mcp.framing import (
    JSONRPCErrorCodes,
    MCPFramingError,
    MCPMessage,
    MCPProtocolError,
    create_error_response,
    create_request,
    create_response,
    pack_mcp_message,
    read_mcp_message,
    read_mcp_messages,
    write_mcp_message,
)


class TestMCPMessage:
    """Test MCPMessage dataclass functionality"""

    def test_create_basic_message(self):
        """Test creating a basic MCP message"""
        msg = MCPMessage(method="search", params={"q": "test"}, id="123")

        assert msg.jsonrpc == "2.0"
        assert msg.method == "search"
        assert msg.params == {"q": "test"}
        assert msg.id == "123"

    def test_to_dict(self):
        """Test converting message to dictionary"""
        msg = MCPMessage(method="search", params={"q": "test"}, id="123")
        data = msg.to_dict()

        expected = {
            "jsonrpc": "2.0",
            "method": "search",
            "params": {"q": "test"},
            "id": "123",
        }
        assert data == expected

    def test_to_dict_minimal(self):
        """Test converting minimal message (no optional fields)"""
        msg = MCPMessage()
        data = msg.to_dict()

        assert data == {"jsonrpc": "2.0"}

    def test_from_dict(self):
        """Test creating message from dictionary"""
        data = {
            "jsonrpc": "2.0",
            "method": "search",
            "params": {"q": "test"},
            "id": "123",
        }
        msg = MCPMessage.from_dict(data)

        assert msg.jsonrpc == "2.0"
        assert msg.method == "search"
        assert msg.params == {"q": "test"}
        assert msg.id == "123"

    def test_from_dict_defaults(self):
        """Test creating message from minimal dictionary"""
        data = {"method": "ping"}
        msg = MCPMessage.from_dict(data)

        assert msg.jsonrpc == "2.0"  # ↳ because default should be set
        assert msg.method == "ping"
        assert msg.params is None


class TestMessagePacking:
    """Test MCP message packing functionality"""

    def test_pack_basic_message(self):
        """Test packing a basic message"""
        msg = MCPMessage(method="search", params={"q": "test"}, id="123")
        packed = pack_mcp_message(msg)

        # Should be JSON with newline
        expected_json = (
            '{"jsonrpc":"2.0","method":"search","params":{"q":"test"},"id":"123"}\n'
        )
        assert packed == expected_json.encode("utf-8")

    def test_pack_unicode_message(self):
        """Test packing message with unicode characters"""
        msg = MCPMessage(method="search", params={"q": "café"}, id="123")
        packed = pack_mcp_message(msg)

        # Should handle unicode properly
        assert packed.decode("utf-8").endswith("\n")
        unpacked = json.loads(packed.decode("utf-8").rstrip("\n"))
        assert unpacked["params"]["q"] == "café"

    def test_pack_with_non_serializable_data(self):
        """Test packing message with non-serializable data raises error"""
        # Create a message with non-serializable data
        msg = MCPMessage(result=object())  # object() can't be serialized

        with pytest.raises(MCPFramingError, match="Failed to serialize"):
            pack_mcp_message(msg)


class TestMessageCreation:
    """Test helper functions for creating different message types"""

    def test_create_request(self):
        """Test creating a request message"""
        msg = create_request("search", {"q": "test", "k": 10}, "req-123")

        assert msg.method == "search"
        assert msg.params == {"q": "test", "k": 10}
        assert msg.id == "req-123"
        assert msg.result is None
        assert msg.error is None

    def test_create_notification(self):
        """Test creating a notification (request without ID)"""
        msg = create_request("ping")

        assert msg.method == "ping"
        assert msg.id is None  # ↳ because notifications have no ID

    def test_create_response(self):
        """Test creating a response message"""
        result_data = [{"text": "result 1"}, {"text": "result 2"}]
        msg = create_response(result_data, "req-123")

        assert msg.result == result_data
        assert msg.id == "req-123"
        assert msg.method is None
        assert msg.error is None

    def test_create_error_response(self):
        """Test creating an error response"""
        msg = create_error_response(
            JSONRPCErrorCodes.INVALID_PARAMS,
            "Missing required parameter 'q'",
            "req-123",
            {"param": "q"},
        )

        assert msg.error == {
            "code": JSONRPCErrorCodes.INVALID_PARAMS,
            "message": "Missing required parameter 'q'",
            "data": {"param": "q"},
        }
        assert msg.id == "req-123"
        assert msg.result is None

    def test_create_error_response_minimal(self):
        """Test creating minimal error response"""
        msg = create_error_response(JSONRPCErrorCodes.INTERNAL_ERROR, "Server error")

        assert msg.error == {
            "code": JSONRPCErrorCodes.INTERNAL_ERROR,
            "message": "Server error",
        }
        assert msg.id is None


class AsyncReaderWriter:
    """Mock async reader/writer for testing"""

    def __init__(self, data: bytes = b""):
        self.data = data
        self.position = 0
        self.written = BytesIO()
        self.closed = False

    async def readline(self) -> bytes:
        """Read a line from the data"""
        if self.position >= len(self.data):
            return b""

        start = self.position
        newline_pos = self.data.find(b"\n", start)

        if newline_pos == -1:
            # No newline found, return rest of data
            line = self.data[start:]
            self.position = len(self.data)
        else:
            # Include the newline
            line = self.data[start : newline_pos + 1]
            self.position = newline_pos + 1

        return line

    def at_eof(self) -> bool:
        """Check if at end of stream"""
        return self.position >= len(self.data)

    def write(self, data: bytes) -> None:
        """Write data"""
        self.written.write(data)

    async def drain(self) -> None:
        """Mock drain"""
        pass

    def close(self) -> None:
        """Mock close"""
        self.closed = True

    async def wait_closed(self) -> None:
        """Mock wait closed"""
        pass


class TestMessageReading:
    """Test reading MCP messages from streams"""

    @pytest.mark.asyncio
    async def test_read_valid_message(self):
        """Test reading a valid MCP message"""
        json_data = (
            '{"jsonrpc":"2.0","method":"search","params":{"q":"test"},"id":"123"}\n'
        )
        reader = AsyncReaderWriter(json_data.encode("utf-8"))

        msg = await read_mcp_message(reader)

        assert msg.jsonrpc == "2.0"
        assert msg.method == "search"
        assert msg.params == {"q": "test"}
        assert msg.id == "123"

    @pytest.mark.asyncio
    async def test_read_empty_connection(self):
        """Test reading from closed connection"""
        reader = AsyncReaderWriter(b"")

        with pytest.raises(ConnectionError, match="Connection closed"):
            await read_mcp_message(reader)

    @pytest.mark.asyncio
    async def test_read_invalid_json(self):
        """Test reading invalid JSON"""
        invalid_json = '{"jsonrpc":"2.0","method":"search"\n'  # Missing closing brace
        reader = AsyncReaderWriter(invalid_json.encode("utf-8"))

        with pytest.raises(MCPFramingError, match="Invalid JSON"):
            await read_mcp_message(reader)

    @pytest.mark.asyncio
    async def test_read_invalid_protocol(self):
        """Test reading non-JSON-RPC message"""
        invalid_protocol = '{"version":"1.0","method":"search"}\n'
        reader = AsyncReaderWriter(invalid_protocol.encode("utf-8"))

        with pytest.raises(MCPProtocolError, match="Invalid or missing jsonrpc"):
            await read_mcp_message(reader)

    @pytest.mark.asyncio
    async def test_read_non_object(self):
        """Test reading non-object JSON"""
        non_object = '"just a string"\n'
        reader = AsyncReaderWriter(non_object.encode("utf-8"))

        with pytest.raises(MCPProtocolError, match="Message must be a JSON object"):
            await read_mcp_message(reader)

    @pytest.mark.asyncio
    async def test_read_too_long_message(self):
        """Test reading message that exceeds length limit"""
        long_data = '{"jsonrpc":"2.0","data":"' + "x" * 2000 + '"}\n'
        reader = AsyncReaderWriter(long_data.encode("utf-8"))

        with pytest.raises(MCPFramingError, match="Message too long"):
            await read_mcp_message(reader, max_line_length=1000)

    @pytest.mark.asyncio
    async def test_read_empty_line(self):
        """Test reading empty line"""
        reader = AsyncReaderWriter(b"\n")

        with pytest.raises(MCPFramingError, match="Empty message"):
            await read_mcp_message(reader)

    @pytest.mark.asyncio
    async def test_read_invalid_utf8(self):
        """Test reading invalid UTF-8"""
        invalid_utf8 = b'{"jsonrpc":"2.0","data":"\xff\xfe"}\n'
        reader = AsyncReaderWriter(invalid_utf8)

        with pytest.raises(MCPFramingError, match="Invalid UTF-8"):
            await read_mcp_message(reader)


class TestMessageWriting:
    """Test writing MCP messages to streams"""

    @pytest.mark.asyncio
    async def test_write_valid_message(self):
        """Test writing a valid message"""
        writer = AsyncReaderWriter()
        msg = MCPMessage(method="search", params={"q": "test"}, id="123")

        await write_mcp_message(writer, msg)

        written_data = writer.written.getvalue()
        expected = (
            '{"jsonrpc":"2.0","method":"search","params":{"q":"test"},"id":"123"}\n'
        )
        assert written_data == expected.encode("utf-8")


class TestMessageStreaming:
    """Test streaming multiple messages"""

    @pytest.mark.asyncio
    async def test_read_multiple_messages(self):
        """Test reading multiple messages from stream"""
        messages = [
            '{"jsonrpc":"2.0","method":"search","id":"1"}\n',
            '{"jsonrpc":"2.0","result":{"data":"test1"},"id":"1"}\n',
            '{"jsonrpc":"2.0","result":{"data":"test2"},"id":"1"}\n',
        ]
        data = "".join(messages).encode("utf-8")
        reader = AsyncReaderWriter(data)

        received_messages = []
        async for msg in read_mcp_messages(reader):
            received_messages.append(msg)

        assert len(received_messages) == 3
        assert received_messages[0].method == "search"
        assert received_messages[1].result == {"data": "test1"}
        assert received_messages[2].result == {"data": "test2"}

    @pytest.mark.asyncio
    async def test_read_messages_with_limit(self):
        """Test reading messages with a limit"""
        messages = [
            '{"jsonrpc":"2.0","method":"search","id":"1"}\n',
            '{"jsonrpc":"2.0","result":{"data":"test1"},"id":"1"}\n',
            '{"jsonrpc":"2.0","result":{"data":"test2"},"id":"1"}\n',
        ]
        data = "".join(messages).encode("utf-8")
        reader = AsyncReaderWriter(data)

        received_messages = []
        async for msg in read_mcp_messages(reader, max_messages=2):
            received_messages.append(msg)

        assert len(received_messages) == 2  # ↳ because we limited to 2

    @pytest.mark.asyncio
    async def test_read_messages_with_errors(self):
        """Test reading messages when some are malformed"""
        messages = [
            '{"jsonrpc":"2.0","method":"search","id":"1"}\n',
            "invalid json\n",  # This should be skipped
            '{"jsonrpc":"2.0","result":{"data":"test"},"id":"1"}\n',
        ]
        data = "".join(messages).encode("utf-8")
        reader = AsyncReaderWriter(data)

        received_messages = []
        async for msg in read_mcp_messages(reader):
            received_messages.append(msg)

        # Should receive 2 valid messages, skipping the invalid one
        assert len(received_messages) == 2
        assert received_messages[0].method == "search"
        assert received_messages[1].result == {"data": "test"}


class TestJSONRPCErrorCodes:
    """Test JSON-RPC error code constants"""

    def test_standard_error_codes(self):
        """Test that standard error codes are defined correctly"""
        assert JSONRPCErrorCodes.PARSE_ERROR == -32700
        assert JSONRPCErrorCodes.INVALID_REQUEST == -32600
        assert JSONRPCErrorCodes.METHOD_NOT_FOUND == -32601
        assert JSONRPCErrorCodes.INVALID_PARAMS == -32602
        assert JSONRPCErrorCodes.INTERNAL_ERROR == -32603

    def test_server_error_range(self):
        """Test server error range"""
        assert -32099 in JSONRPCErrorCodes.SERVER_ERROR_RANGE
        assert -32000 in JSONRPCErrorCodes.SERVER_ERROR_RANGE
        assert -32100 not in JSONRPCErrorCodes.SERVER_ERROR_RANGE
        assert -31999 not in JSONRPCErrorCodes.SERVER_ERROR_RANGE
