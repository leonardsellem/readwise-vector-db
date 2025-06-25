"""Shared search service for MCP protocol implementations.

This module provides a unified interface for processing search parameters
and invoking semantic search, used by both TCP and HTTP SSE MCP endpoints.
"""

import logging
from datetime import date
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from readwise_vector_db.core.search import semantic_search

logger = logging.getLogger(__name__)


class SearchParams:
    """Validated search parameters for MCP requests."""

    def __init__(
        self,
        query: str,
        k: int = 20,
        source_type: Optional[str] = None,
        author: Optional[str] = None,
        tags: Optional[List[str]] = None,
        highlighted_at_range: Optional[Tuple[date, date]] = None,
    ):
        self.query = query
        self.k = k
        self.source_type = source_type
        self.author = author
        self.tags = tags
        self.highlighted_at_range = highlighted_at_range

    def __str__(self) -> str:
        """String representation for logging."""
        return f"SearchParams(query='{self.query}', k={self.k}, filters={self._filter_summary()})"

    def _filter_summary(self) -> str:
        """Create a summary of active filters for logging."""
        filters = []
        if self.source_type:
            filters.append(f"source_type={self.source_type}")
        if self.author:
            filters.append(f"author={self.author}")
        if self.tags:
            filters.append(f"tags={len(self.tags)} items")
        if self.highlighted_at_range:
            filters.append(
                f"date_range={self.highlighted_at_range[0]} to {self.highlighted_at_range[1]}"
            )
        return "{" + ", ".join(filters) + "}" if filters else "none"


class SearchService:
    """Shared service for processing MCP search requests."""

    @staticmethod
    def parse_mcp_params(params: Dict[str, Any]) -> SearchParams:
        """Parse and validate MCP protocol search parameters.

        Args:
            params: Raw parameters dict from MCP request

        Returns:
            Validated SearchParams object

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Validate required query parameter
        query = params.get("q")
        if not query or not isinstance(query, str):
            raise ValueError("Missing or invalid 'q' parameter")

        # Extract and validate k parameter
        k = params.get("k", 20)
        if not isinstance(k, int) or k <= 0:
            k = 20  # Default to 20 if invalid

        # Extract filter parameters
        source_type = params.get("source_type")
        author = params.get("author")
        tags = params.get("tags")

        # Parse date range if provided
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

        return SearchParams(
            query=query,
            k=k,
            source_type=source_type,
            author=author,
            tags=tags,
            highlighted_at_range=highlighted_at_range,
        )

    @staticmethod
    def parse_http_params(
        query: str,
        k: int = 20,
        source_type: Optional[str] = None,
        author: Optional[str] = None,
        tags: Optional[List[str]] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> SearchParams:
        """Parse and validate HTTP query parameters.

        Args:
            query: Search query string
            k: Number of results to return
            source_type: Filter by source type
            author: Filter by author
            tags: Filter by tags
            from_date: Start date as ISO string
            to_date: End date as ISO string

        Returns:
            Validated SearchParams object

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        if not query or not isinstance(query, str):
            raise ValueError("Missing or invalid 'q' parameter")

        # Validate k parameter
        if not isinstance(k, int) or k <= 0:
            k = 20

        # Parse date range if both dates provided
        highlighted_at_range = None
        if from_date and to_date:
            try:
                start = date.fromisoformat(from_date) if from_date else None
                end = date.fromisoformat(to_date) if to_date else None
                if start and end:
                    highlighted_at_range = (start, end)
            except (ValueError, TypeError):
                logger.warning(f"Invalid date range: {from_date} to {to_date}")

        return SearchParams(
            query=query,
            k=k,
            source_type=source_type,
            author=author,
            tags=tags,
            highlighted_at_range=highlighted_at_range,
        )

    @staticmethod
    async def execute_search(
        search_params: SearchParams,
        stream: bool = True,
        client_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute semantic search with the given parameters.

        Args:
            search_params: Validated search parameters
            stream: Whether to stream results
            client_id: Optional client identifier for logging

        Yields:
            Search result dictionaries
        """
        if client_id:
            logger.info(f"Client {client_id} searching: {search_params}")
        else:
            logger.info(f"Executing search: {search_params}")

        # Call semantic_search with validated parameters
        results_generator = await semantic_search(
            search_params.query,
            search_params.k,
            search_params.source_type,
            search_params.author,
            search_params.tags,
            search_params.highlighted_at_range,
            stream=stream,
        )

        # Stream results
        result_count = 0
        if hasattr(results_generator, "__aiter__"):
            # Stream mode
            async for result in results_generator:
                yield result
                result_count += 1
        else:
            # Non-stream mode - results_generator is a list
            for result in results_generator:
                yield result
                result_count += 1

        if client_id:
            logger.info(f"Sent {result_count} results to client {client_id}")
        else:
            logger.info(f"Search completed: {result_count} results")


# Legacy compatibility function for existing code
async def execute_mcp_search(
    params: Dict[str, Any],
    stream: bool = True,
    client_id: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Legacy wrapper for backward compatibility.

    Args:
        params: Raw MCP parameters dict
        stream: Whether to stream results
        client_id: Optional client identifier for logging

    Yields:
        Search result dictionaries
    """
    search_params = SearchService.parse_mcp_params(params)
    async for result in SearchService.execute_search(search_params, stream, client_id):
        yield result
