"""
MCP Protocol Server Implementation

Lightweight TCP server that streams search results to LLM clients using MCP framing.
Handles back-pressure and graceful shutdown.
"""

import asyncio
import logging
import signal
from contextlib import asynccontextmanager
from typing import Optional, Set

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

# Writers of active connections
active_connections: Set[asyncio.StreamWriter] = set()
# Track running client handler tasks to await during shutdown
_client_tasks: Set[asyncio.Task[None]] = set()


async def _handle_client_wrapper(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    """Wrapper that registers the client task for shutdown coordination."""
    task = asyncio.current_task()
    if task:
        _client_tasks.add(task)
        try:
            await handle_client(reader, writer)
        finally:
            _client_tasks.discard(task)


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

        # Use shared service to parse and validate parameters
        from readwise_vector_db.mcp.search_service import SearchService

        try:
            search_params = SearchService.parse_mcp_params(request.params)
        except ValueError as e:
            error_msg = create_error_response(
                JSONRPCErrorCodes.INVALID_PARAMS,
                str(e),
                request.id,
            )
            await write_mcp_message(writer, error_msg)
            return

        # Execute search using shared service
        async for result in SearchService.execute_search(
            search_params, stream=True, client_id=client_id
        ):
            # Check if client is still connected
            if reader.at_eof():
                logger.info(f"Client {client_id} disconnected, stopping stream")
                break

            # Send result to client using MCP framing
            response = create_response(
                {"id": result["id"], "text": result["text"], "score": result["score"]},
                str(request.id) if request.id is not None else "null",
            )
            await write_mcp_message(writer, response)

        logger.info(f"Completed streaming search for client {client_id}")

    except (MCPFramingError, MCPProtocolError) as e:
        # Framing or protocol errors — differentiate for correct JSON-RPC code
        # ↳ because JSON-RPC 2.0 defines -32700 for parse errors (invalid JSON)
        #    and -32600 for other invalid requests / protocol violations.
        logger.error(f"Protocol error with client {client_id}: {str(e)}")

        if isinstance(e, MCPFramingError):
            code = JSONRPCErrorCodes.PARSE_ERROR
        else:
            code = JSONRPCErrorCodes.INVALID_REQUEST

        try:
            error_msg = create_error_response(code, str(e))  # id will be null
            await write_mcp_message(writer, error_msg)
        except Exception:
            pass  # If we can't send the error, simply drop the connection

    except ConnectionError as e:
        logger.info(f"Connection closed by client {client_id}: {str(e)}")

    except Exception as e:
        # Unexpected, internal server errors
        logger.exception(f"Error processing request from client {client_id}: {str(e)}")
        try:
            # If we managed to parse a request we can echo its id back, otherwise null
            req_id = (
                request.id if "request" in locals() and hasattr(request, "id") else None
            )
            error_msg = create_error_response(
                JSONRPCErrorCodes.INTERNAL_ERROR,
                "Internal server error",
                req_id,
            )
            await write_mcp_message(writer, error_msg)
        except Exception:
            pass  # Fall through to connection cleanup

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
        self.server = await asyncio.start_server(
            _handle_client_wrapper, self.host, self.port
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

            # Wait for in-flight client tasks to finish gracefully before closing writers
            if _client_tasks:
                logger.info("Waiting for %d in-flight client tasks", len(_client_tasks))
                await asyncio.gather(*_client_tasks, return_exceptions=True)

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
                        logger.warning(
                            "Some connections did not close gracefully; aborting"
                        )

                        # Force-abort any writers that are still open to avoid
                        # hanging the shutdown sequence forever. We access the
                        # private transport only as a last resort.
                        for w in active_connections:
                            try:
                                transport = (
                                    w.transport if hasattr(w, "transport") else None
                                )
                                if transport and not w.is_closing():  # type: ignore[attr-defined]
                                    transport.abort()
                            except Exception:
                                pass

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
