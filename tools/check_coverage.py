#!/usr/bin/env python3
"""
Coverage checker script for targeted testing strategy.

This script reads coverage JSON and validates that each module bucket
meets its required coverage threshold:
- Core modules: 90% coverage
- High-priority modules: 75% coverage
- Standard modules: 60% coverage

Usage:
    python tools/check_coverage.py

Exits with code 1 if any bucket fails to meet its threshold.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

# Import our bucket definitions
try:
    from coverage_buckets import COVERAGE_THRESHOLDS, get_module_bucket
except ImportError:
    # Handle case where script is run from tools/ directory
    import sys

    sys.path.insert(0, str(Path(__file__).parent))
    from coverage_buckets import COVERAGE_THRESHOLDS, get_module_bucket


# ANSI color codes for output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def colorize(text: str, color: str) -> str:
    """Add color to text if stdout supports it."""
    if sys.stdout.isatty():
        return f"{color}{text}{Colors.RESET}"
    return text


def load_coverage_data(coverage_file: str = ".coverage.json") -> Dict[str, Any]:
    """Load coverage data from JSON file."""
    try:
        with open(coverage_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Coverage file {coverage_file} not found!")
        print(
            "💡 Run 'poetry run coverage json' first to generate the coverage report."
        )
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing coverage JSON: {e}")
        sys.exit(1)


def calculate_bucket_coverage(
    coverage_data: Dict[str, Any]
) -> Dict[str, Dict[str, int]]:
    """
    Calculate coverage statistics for each bucket.

    Returns:
        Dict with bucket names as keys, each containing:
        - 'covered': number of covered lines
        - 'total': total number of lines
        - 'percentage': coverage percentage
    """
    # Initialize counters for each bucket
    bucket_stats = {
        "core": {"covered": 0, "total": 0},
        "high_priority": {"covered": 0, "total": 0},
        "standard": {"covered": 0, "total": 0},
    }

    # Get file coverage data
    files = coverage_data.get("files", {})

    for file_path, file_data in files.items():
        bucket = get_module_bucket(file_path)

        # Only count files that belong to our defined buckets
        if bucket in bucket_stats:
            # executed_lines is a list of line numbers, so we need its length
            executed_lines_list = file_data.get("executed_lines", [])
            covered_lines = (
                len(executed_lines_list)
                if isinstance(executed_lines_list, list)
                else executed_lines_list
            )

            total_lines = file_data.get("num_statements", 0)

            bucket_stats[bucket]["covered"] += covered_lines
            bucket_stats[bucket]["total"] += total_lines

    # Calculate percentages
    for _bucket, stats in bucket_stats.items():
        if stats["total"] > 0:
            stats["percentage"] = round((stats["covered"] / stats["total"]) * 100, 1)
        else:
            stats["percentage"] = 100.0  # No code = 100% coverage

    return bucket_stats


def print_coverage_report(bucket_stats: Dict[str, Dict[str, int]]) -> bool:
    """
    Print a formatted coverage report and return whether all thresholds are met.

    Returns:
        True if all buckets meet their thresholds, False otherwise
    """
    print("🔍 Checking per-module coverage thresholds...")
    print()
    print("📊 Targeted Coverage Report")
    print("=" * 50)

    all_passed = True

    # Define display names and expected order
    bucket_info = [
        ("core", "CORE", COVERAGE_THRESHOLDS["core"]),
        ("high_priority", "HIGH", COVERAGE_THRESHOLDS["high_priority"]),
        ("standard", "STANDARD", COVERAGE_THRESHOLDS["standard"]),
    ]

    for bucket_key, display_name, threshold in bucket_info:
        stats = bucket_stats[bucket_key]
        percentage = stats["percentage"]
        covered = stats["covered"]
        total = stats["total"]

        # Determine pass/fail status
        passed = percentage >= threshold
        status = "✅" if passed else "❌"

        if not passed:
            all_passed = False

        print(
            f"{status} {display_name}: {percentage}% (target {threshold}%) - {covered}/{total} lines"
        )

    print("=" * 50)

    if all_passed:
        print("🎉 All coverage targets met!")
    else:
        print("💥 Some coverage targets failed!")

    return all_passed


def main():
    """Main entry point for the coverage checker."""
    coverage_data = load_coverage_data()
    bucket_stats = calculate_bucket_coverage(coverage_data)
    all_passed = print_coverage_report(bucket_stats)

    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
