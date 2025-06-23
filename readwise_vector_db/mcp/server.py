"""
MCP Protocol Server Implementation

Lightweight TCP server that streams search results to LLM clients using MCP framing.
Handles back-pressure and graceful shutdown.
"""

import asyncio
import logging
import signal
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional, Set

from readwise_vector_db.core.search import semantic_search
from readwise_vector_db.mcp.framing import (
    JSONRPCErrorCodes,
    MCPFramingError,
    MCPProtocolError,
    create_error_response,
    create_response,
    read_mcp_message,
    write_mcp_message,
)

logger = logging.getLogger(__name__)

# Tracking active connections for graceful shutdown
active_connections: Set[asyncio.StreamWriter] = set()


async def handle_client(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    """
    Handle an individual client connection.

    Args:
        reader: Stream reader for receiving client data
        writer: Stream writer for sending responses

    This function processes incoming MCP messages, performs searches, and streams results.
    """
    peer_info = writer.get_extra_info("peername")
    client_id = f"{peer_info[0]}:{peer_info[1]}" if peer_info else "unknown"
    logger.info(f"Client connected: {client_id}")

    # Track connection for graceful shutdown
    active_connections.add(writer)

    # Give asyncio a chance to update the set
    await asyncio.sleep(0)

    try:
        # Read the search request
        request = await read_mcp_message(reader)
        if not request.method or request.method != "search":
            error_msg = create_error_response(
                JSONRPCErrorCodes.METHOD_NOT_FOUND,
                f"Method not supported: {request.method}",
                request.id,
            )
            await write_mcp_message(writer, error_msg)
            return

        # Extract parameters
        if not request.params:
            error_msg = create_error_response(
                JSONRPCErrorCodes.INVALID_PARAMS,
                "Missing or invalid 'q' parameter",
                request.id,
            )
            await write_mcp_message(writer, error_msg)
            return

        # Extract search query and parameters
        params = request.params
        query = params.get("q")
        if not query or not isinstance(query, str):
            error_msg = create_error_response(
                JSONRPCErrorCodes.INVALID_PARAMS,
                "Missing or invalid 'q' parameter",
                request.id,
            )
            await write_mcp_message(writer, error_msg)
            return

        # Extract optional parameters
        k = params.get("k", 20)
        if not isinstance(k, int) or k <= 0:
            k = 20  # Default to 20 if invalid

        # Extract filter parameters
        source_type = params.get("source_type")
        author = params.get("author")
        tags = params.get("tags")
        highlighted_at_range = None

        if params.get("highlighted_at_range") and isinstance(
            params["highlighted_at_range"], list
        ):
            try:
                range_data = params["highlighted_at_range"]
                if len(range_data) >= 2:
                    start = date.fromisoformat(range_data[0]) if range_data[0] else None
                    end = date.fromisoformat(range_data[1]) if range_data[1] else None
                    if start and end:
                        highlighted_at_range = (start, end)
            except (ValueError, TypeError):
                logger.warning(
                    f"Invalid date range: {params.get('highlighted_at_range')}"
                )

        logger.info(f"Client {client_id} searching for: {query} (k={k})")

        # Perform semantic search
        results = await semantic_search(
            query, k, source_type, author, tags, highlighted_at_range
        )

        # Stream results back to client
        result_count = 0
        for result in results:
            # Check for client disconnect
            if reader.at_eof():
                logger.info(f"Client {client_id} disconnected during streaming")
                break

            # Send each result as a separate response
            response = create_response(
                {"id": result["id"], "text": result["text"], "score": result["score"]},
                str(request.id) if request.id is not None else "null",
            )
            await write_mcp_message(writer, response)
            result_count += 1

        logger.info(f"Sent {result_count} results to client {client_id}")

        # Send empty response to indicate end of stream if no results
        if result_count == 0:
            empty_response = create_response(
                [], str(request.id) if request.id is not None else "null"
            )
            await write_mcp_message(writer, empty_response)

    except (MCPFramingError, MCPProtocolError) as e:
        # Protocol errors
        logger.error(f"Protocol error with client {client_id}: {str(e)}")
        try:
            error_msg = create_error_response(JSONRPCErrorCodes.INVALID_REQUEST, str(e))
            await write_mcp_message(writer, error_msg)
        except Exception:
            pass  # If we can't send the error, just close the connection

    except ConnectionError as e:
        logger.info(f"Connection closed by client {client_id}: {str(e)}")

    except Exception as e:
        # Unexpected errors
        logger.exception(f"Error processing request from client {client_id}: {str(e)}")
        try:
            error_msg = create_error_response(
                JSONRPCErrorCodes.INTERNAL_ERROR,
                "Internal server error",
            )
            await write_mcp_message(writer, error_msg)
        except Exception:
            pass  # If we can't send the error, just close the connection

    finally:
        # Clean up the connection
        try:
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            logger.error(f"Error closing connection to {client_id}: {str(e)}")

        # Remove from active connections
        active_connections.discard(writer)
        logger.info(f"Client disconnected: {client_id}")


class MCPServer:
    """
    MCP Protocol Server that accepts TCP connections and streams search results.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8375):
        """
        Initialize the MCP server.

        Args:
            host: Host address to bind the server to
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self.server: Optional[asyncio.Server] = None

    async def start(self) -> None:
        """
        Start the MCP server.
        """
        logger.info(f"Starting MCP server on {self.host}:{self.port}")

        # Register signal handlers for graceful shutdown
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_event_loop().add_signal_handler(
                sig, lambda: asyncio.create_task(self.shutdown())
            )

        # Start the server
        self.server: asyncio.Server = await asyncio.start_server(
            handle_client, self.host, self.port
        )

        # Get actual socket information
        if self.server and self.server.sockets:
            for sock in self.server.sockets:
                addr = sock.getsockname()
                logger.info(f"Server listening on {addr[0]}:{addr[1]}")

    async def shutdown(self) -> None:
        """
        Gracefully shut down the server, closing all active connections.
        """
        logger.info("Shutting down MCP server...")

        if self.server:
            # Stop accepting new connections
            self.server.close()
            await self.server.wait_closed()

            # Close all active connections
            if active_connections:
                logger.info(f"Closing {len(active_connections)} active connections")
                close_tasks = []
                for writer in active_connections:
                    try:
                        # Try to send a final message (optional)
                        try:
                            error_msg = create_error_response(
                                JSONRPCErrorCodes.SERVER_ERROR_RANGE.start,  # Custom code
                                "Server shutting down",
                            )
                            await write_mcp_message(writer, error_msg)
                        except Exception:
                            pass  # OK if this fails

                        writer.close()
                        close_tasks.append(writer.wait_closed())
                    except Exception:
                        pass

                # Wait for all connections to close with a timeout
                if close_tasks:
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*close_tasks), timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning("Some connections did not close gracefully")

            # Clear the set in case the server is restarted
            active_connections.clear()
            logger.info("MCP server shutdown complete")

    @asynccontextmanager
    async def run_in_background(self):
        """
        Context manager for running the server in the background.

        Example:
            ```
            async with server.run_in_background():
                # Server is running in background here
                await other_tasks()
            # Server is shut down here
            ```
        """
        try:
            await self.start()
            yield self
        finally:
            await self.shutdown()

    async def run_forever(self) -> None:
        """
        Run the server until interrupted.
        """
        await self.start()
        try:
            # Run forever
            await asyncio.Future()
        finally:
            await self.shutdown()


# Helper function to run the server
def run_server(host: str = "127.0.0.1", port: int = 8375) -> None:
    """
    Run the MCP server until interrupted.

    Args:
        host: Host address to bind to
        port: Port to listen on
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create and run server
    server = MCPServer(host, port)
    asyncio.run(server.run_forever())
