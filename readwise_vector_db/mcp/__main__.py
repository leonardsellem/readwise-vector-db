#!/usr/bin/env python3
"""
Command-line entry point for the MCP Server.
Allows running the server as:
  python -m readwise_vector_db.mcp [--host HOST] [--port PORT]
"""

import argparse
import logging
import sys

from readwise_vector_db.mcp.server import run_server


def main() -> int:
    """Parse command line arguments and start the MCP server."""
    parser = argparse.ArgumentParser(
        description="Run the MCP Protocol Server for streaming Readwise vector search results."
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", type=int, default=8375, help="Port to listen on (default: 8375)"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Log startup info
    logger = logging.getLogger("mcp")
    logger.info(f"Starting MCP server on {args.host}:{args.port}")

    try:
        # Run the server
        run_server(args.host, args.port)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        return 0
    except Exception as e:
        logger.exception(f"Server error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
