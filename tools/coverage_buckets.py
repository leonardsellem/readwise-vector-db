"""
Coverage bucket definitions for targeted testing strategy.

This module defines which modules require different levels of test coverage:
- Core modules: 90% coverage (business-critical logic)
- High-priority modules: 75% coverage (important but stable)
- Standard modules: 60% coverage (supportive or volatile)
"""

from pathlib import Path
from typing import List

# ↳ Core modules containing business-critical logic - require 90% coverage
CORE_MODULES: List[str] = [
    "readwise_vector_db/core",  # embedding.py, search.py, readwise.py
    "readwise_vector_db/db",  # database.py, upsert.py, supabase_ops.py
    "readwise_vector_db/models",  # all model files
]

# ↳ High-priority modules that are important but stable - require 75% coverage
HIGH_PRIORITY_MODULES: List[str] = [
    "readwise_vector_db/api",  # FastAPI routes and main
    "readwise_vector_db/jobs",  # sync jobs (backfill, incremental)
]

# ↳ Standard modules for supportive or volatile components - require 60% coverage
STANDARD_MODULES: List[str] = [
    "readwise_vector_db/mcp",  # MCP server implementation
    "readwise_vector_db/config",  # configuration management
    "readwise_vector_db/main",  # CLI entry points
]

# ↳ Coverage thresholds for each bucket
COVERAGE_THRESHOLDS = {
    "core": 90,  # Business-critical modules
    "high_priority": 75,  # Important but stable modules
    "standard": 60,  # Supportive or volatile modules
}


def normalize_module_path(module_path: str) -> str:
    """
    Normalize a module path to use forward slashes consistently.

    This ensures compatibility across different operating systems and
    consistent matching with coverage report paths.
    """
    return str(Path(module_path).as_posix())


def get_module_bucket(file_path: str) -> str:
    """
    Determine which coverage bucket a file belongs to.

    Args:
        file_path: Path to the source file (e.g., "readwise_vector_db/core/embedding.py")

    Returns:
        Bucket name: "core", "high_priority", "standard", or "unknown"
    """
    normalized_path = normalize_module_path(file_path)

    # Check each bucket in priority order
    for module in CORE_MODULES:
        if normalized_path.startswith(normalize_module_path(module)):
            return "core"

    for module in HIGH_PRIORITY_MODULES:
        if normalized_path.startswith(normalize_module_path(module)):
            return "high_priority"

    for module in STANDARD_MODULES:
        if normalized_path.startswith(normalize_module_path(module)):
            return "standard"

    return "unknown"


def get_threshold_for_file(file_path: str) -> int:
    """
    Get the coverage threshold for a specific file.

    Args:
        file_path: Path to the source file

    Returns:
        Coverage threshold percentage (90, 75, 60, or 70 for unknown)
    """
    bucket = get_module_bucket(file_path)
    return COVERAGE_THRESHOLDS.get(bucket, 70)  # Default 70% for unknown files
