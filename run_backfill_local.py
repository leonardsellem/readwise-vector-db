#!/usr/bin/env python3
"""
Local backfill script that bypasses connection issues.

This script runs the backfill process locally using the exact same logic
as the API but with proper environment variable loading.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables
try:
    from dotenv import load_dotenv

    load_dotenv()
    print("✅ Loaded .env file")
except ImportError:
    print("⚠️  dotenv not available, using system environment")

# Import after environment is loaded  # noqa: E402
from sqlalchemy import text  # noqa: E402

from readwise_vector_db.config import settings  # noqa: E402
from readwise_vector_db.db.database import AsyncSessionLocal  # noqa: E402
from readwise_vector_db.jobs.backfill import run_backfill  # noqa: E402


async def check_database_connection():
    """Test database connection and show current state."""
    try:
        async with AsyncSessionLocal() as session:
            # Test basic connection
            await session.execute(text("SELECT 1"))
            print("✅ Database connection successful")

            # Check if tables exist
            try:
                result = await session.execute(text("SELECT COUNT(*) FROM highlight"))
                count = result.fetchone()[0]
                print(f"📊 Current highlights in database: {count}")
                return True
            except Exception as e:
                print(f"❌ Tables not found or inaccessible: {e}")
                return False

    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


async def main():
    """Run the backfill process with proper error handling."""
    print("🚀 Starting Readwise Vector DB Backfill")
    print(f"📍 Database backend: {settings.db_backend}")

    # Check required environment variables
    required_vars = ["READWISE_TOKEN", "OPENAI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]

    if missing_vars:
        print(f"❌ Missing required environment variables: {missing_vars}")
        return False

    print("✅ Required environment variables found")

    # Test database connection
    print("\n🔍 Testing database connection...")
    if not await check_database_connection():
        print("\n❌ Cannot proceed without database connection")
        return False

    # Run backfill
    print("\n📚 Starting backfill process...")
    try:
        await run_backfill()
        print("\n✅ Backfill completed successfully!")

        # Show final count
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM highlight"))
            count = result.fetchone()[0]
            print(f"🎉 Total highlights now in database: {count}")

        return True

    except Exception as e:
        print(f"\n❌ Backfill failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
