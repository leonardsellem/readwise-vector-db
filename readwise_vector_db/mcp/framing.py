"""
MCP Protocol Framing and Message Handling

Implements JSON-RPC 2.0 message framing for the Model Context Protocol (MCP)
over TCP connections using newline-delimited JSON (NDJSON).
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class MCPMessage:
    """Represents an MCP JSON-RPC 2.0 message"""

    jsonrpc: str = "2.0"
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = {"jsonrpc": self.jsonrpc}

        if self.method is not None:
            data["method"] = self.method
        if self.params is not None:
            data["params"] = self.params
        if self.id is not None:
            data["id"] = self.id
        if self.result is not None:
            data["result"] = self.result
        if self.error is not None:
            data["error"] = self.error

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPMessage":
        """Create MCPMessage from dictionary"""
        return cls(
            jsonrpc=str(data.get("jsonrpc", "2.0")),
            method=data.get("method"),
            params=data.get("params"),
            id=data.get("id"),
            result=data.get("result"),
            error=data.get("error"),
        )


class MCPFramingError(Exception):
    """Raised when MCP message framing fails"""

    pass


class MCPProtocolError(Exception):
    """Raised when MCP protocol is violated"""

    pass


def pack_mcp_message(message: MCPMessage) -> bytes:
    """
    Pack an MCP message into NDJSON format for TCP transmission.

    Args:
        message: MCPMessage to pack

    Returns:
        UTF-8 encoded bytes with newline delimiter

    Raises:
        MCPFramingError: If JSON serialization fails
    """
    try:
        json_str = json.dumps(message.to_dict(), separators=(",", ":"))
        # ↳ because we want compact JSON and NDJSON needs newline delimiter
        return (json_str + "\n").encode("utf-8")
    except (TypeError, ValueError) as e:
        raise MCPFramingError(f"Failed to serialize MCP message: {e}") from e


def create_request(
    method: str,
    params: Optional[Dict[str, Any]] = None,
    request_id: Optional[Union[str, int]] = None,
) -> MCPMessage:
    """
    Create an MCP request message.

    Args:
        method: JSON-RPC method name
        params: Optional parameters
        request_id: Request ID (if None, creates a notification)

    Returns:
        MCPMessage configured as request
    """
    return MCPMessage(method=method, params=params, id=request_id)


def create_response(result: Any, request_id: Union[str, int]) -> MCPMessage:
    """
    Create an MCP response message.

    Args:
        result: The result data
        request_id: ID from the original request

    Returns:
        MCPMessage configured as response
    """
    return MCPMessage(result=result, id=request_id)


def create_error_response(
    error_code: int,
    error_message: str,
    request_id: Optional[Union[str, int]] = None,
    error_data: Optional[Any] = None,
) -> MCPMessage:
    """
    Create an MCP error response message.

    Args:
        error_code: JSON-RPC error code
        error_message: Human-readable error message
        request_id: ID from the original request (if any)
        error_data: Optional additional error data

    Returns:
        MCPMessage configured as error response
    """
    error_obj = {"code": error_code, "message": error_message}
    if error_data is not None:
        error_obj["data"] = error_data

    return MCPMessage(error=error_obj, id=request_id)


async def read_mcp_message(
    reader: asyncio.StreamReader, max_line_length: int = 1024 * 1024
) -> MCPMessage:
    """
    Read and parse a single MCP message from TCP stream.

    Args:
        reader: asyncio StreamReader
        max_line_length: Maximum allowed line length to prevent DoS

    Returns:
        Parsed MCPMessage

    Raises:
        MCPFramingError: If line is too long or JSON parsing fails
        MCPProtocolError: If message violates JSON-RPC 2.0 spec
        ConnectionError: If connection is closed
    """
    try:
        # Read one line (NDJSON format)
        line_bytes = await reader.readline()

        if not line_bytes:
            raise ConnectionError("Connection closed by client")

        if len(line_bytes) > max_line_length:
            raise MCPFramingError(f"Message too long: {len(line_bytes)} bytes")

        # Decode and parse JSON
        line_str = line_bytes.decode("utf-8").rstrip("\n\r")
        if not line_str:
            raise MCPFramingError("Empty message received")

        data = json.loads(line_str)

        # Validate basic JSON-RPC 2.0 structure
        if not isinstance(data, dict):
            raise MCPProtocolError("Message must be a JSON object")

        if data.get("jsonrpc") != "2.0":
            raise MCPProtocolError("Invalid or missing jsonrpc version")

        return MCPMessage.from_dict(data)

    except json.JSONDecodeError as e:
        raise MCPFramingError(f"Invalid JSON: {e}") from e
    except UnicodeDecodeError as e:
        raise MCPFramingError(f"Invalid UTF-8 encoding: {e}") from e


async def write_mcp_message(writer: asyncio.StreamWriter, message: MCPMessage) -> None:
    """
    Write an MCP message to TCP stream with back-pressure handling.

    Args:
        writer: asyncio StreamWriter
        message: MCPMessage to send

    Raises:
        MCPFramingError: If message serialization fails
        ConnectionError: If connection is closed
    """
    try:
        data = pack_mcp_message(message)
        writer.write(data)
        await writer.drain()  # ↳ because we need back-pressure control

    except ConnectionResetError as e:
        raise ConnectionError("Connection closed by client") from e
    except BrokenPipeError as e:
        raise ConnectionError("Connection broken") from e


async def read_mcp_messages(
    reader: asyncio.StreamReader, max_messages: Optional[int] = None
) -> AsyncIterator[MCPMessage]:
    """
    Read multiple MCP messages from stream until EOF or limit reached.

    Args:
        reader: asyncio StreamReader
        max_messages: Optional limit on number of messages to read

    Yields:
        MCPMessage instances

    Raises:
        MCPFramingError: If message parsing fails
        MCPProtocolError: If protocol is violated
    """
    count = 0

    while max_messages is None or count < max_messages:
        try:
            if reader.at_eof():
                logger.debug("Stream EOF reached")
                break

            message = await read_mcp_message(reader)
            yield message
            count += 1

        except ConnectionError:
            logger.debug("Connection closed, stopping message reading")
            break
        except (MCPFramingError, MCPProtocolError) as e:
            logger.warning(f"Message parsing error: {e}")
            # Continue reading despite individual message errors
            continue


# JSON-RPC 2.0 standard error codes
class JSONRPCErrorCodes:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    # Custom application errors should use codes -32099 to -32000
    SERVER_ERROR_RANGE = range(-32099, -31999)  # ↳ because range end is exclusive
