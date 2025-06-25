#!/bin/bash
# =============================================================================
# Supabase Migration Script for Readwise Vector DB
# =============================================================================
# This script runs Alembic migrations against a Supabase PostgreSQL database.
# It ensures the pgvector extension is available and applies all schema changes.
#
# Prerequisites:
# - SUPABASE_DB_URL environment variable must be set
# - Alembic must be installed and configured
# - Network access to your Supabase project
#
# Usage:
#   export SUPABASE_DB_URL="postgresql://postgres:password@project.supabase.co:6543/postgres?options=project%3Dproject"
#   ./scripts/run_migrations_supabase.sh
#
# Or use the Makefile target:
#   make migrate-supabase

set -euo pipefail  # ↳ Exit on error, undefined vars, and pipe failures

# -----------------------------------------------------------------------------
# Configuration & Validation
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Starting Supabase migration process..."
echo "📍 Project root: $PROJECT_ROOT"

# Validate required environment variables
if [[ -z "${SUPABASE_DB_URL:-}" ]]; then
    echo "❌ Error: SUPABASE_DB_URL environment variable is required"
    echo "💡 Get your connection string from: Supabase Dashboard → Settings → Database"
    echo "📝 Format: postgresql://postgres:[PASSWORD]@[PROJECT_REF].supabase.co:6543/postgres?options=project%3D[PROJECT_REF]"
    exit 1
fi

# Validate Alembic is available
if ! command -v alembic &> /dev/null; then
    echo "❌ Error: Alembic is not installed or not in PATH"
    echo "💡 Install with: poetry install or pip install alembic"
    exit 1
fi

# -----------------------------------------------------------------------------
# Pre-Migration Checks
# -----------------------------------------------------------------------------
echo "🔍 Validating Supabase connection..."

# Test database connectivity
if ! python -c "
import asyncpg
import asyncio

async def test_connection():
    try:
        conn = await asyncpg.connect('$SUPABASE_DB_URL')
        await conn.close()
        print('✅ Connection successful')
    except Exception as e:
        print(f'❌ Connection failed: {e}')
        exit(1)

asyncio.run(test_connection())
" 2>/dev/null; then
    echo "❌ Failed to connect to Supabase database"
    echo "💡 Check your SUPABASE_DB_URL and network connectivity"
    exit 1
fi

# -----------------------------------------------------------------------------
# Rate Limiting & Connection Notes
# -----------------------------------------------------------------------------
echo "⏱️  Note: Supabase has rate limits - migrations will run with conservative timing"
echo "🔗 Connection pooling via PgBouncer is automatically used"
echo "📊 Monitor your usage at: https://supabase.com/dashboard/project/[PROJECT]/settings/usage"

# -----------------------------------------------------------------------------
# Migration Execution
# -----------------------------------------------------------------------------
echo "🗄️  Checking current migration state..."

# Change to project root for Alembic
cd "$PROJECT_ROOT"

# Set the database URL for Alembic
export DATABASE_URL="$SUPABASE_DB_URL"

# Show current revision
CURRENT_REV=$(alembic current 2>/dev/null || echo "none")
echo "📍 Current revision: $CURRENT_REV"

# Show target revision
TARGET_REV=$(alembic heads 2>/dev/null || echo "unknown")
echo "🎯 Target revision: $TARGET_REV"

# Run migrations
echo "🚀 Running migrations..."
if alembic upgrade head; then
    echo "✅ Migrations completed successfully"
else
    echo "❌ Migration failed"
    exit 1
fi

# -----------------------------------------------------------------------------
# Post-Migration Verification
# -----------------------------------------------------------------------------
echo "🔬 Verifying migration results..."

# Verify pgvector extension is enabled
python -c "
import asyncpg
import asyncio

async def verify_setup():
    conn = await asyncpg.connect('$SUPABASE_DB_URL')
    try:
        # Check pgvector extension
        result = await conn.fetchval(
            'SELECT 1 FROM pg_extension WHERE extname = \$1', 'vector'
        )
        if result:
            print('✅ pgvector extension is enabled')
        else:
            print('❌ pgvector extension not found')
            return False

        # Check tables exist
        tables = await conn.fetch('''
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('highlight', 'syncstate')
        ''')

        table_names = [row['table_name'] for row in tables]
        if 'highlight' in table_names and 'syncstate' in table_names:
            print('✅ Required tables (highlight, syncstate) are present')
        else:
            print(f'❌ Missing tables. Found: {table_names}')
            return False

        # Check highlight table has vector column
        vector_col = await conn.fetchval('''
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'highlight' AND column_name = 'embedding'
        ''')
        if vector_col:
            print('✅ Embedding vector column is configured')
        else:
            print('❌ Embedding vector column not found')
            return False

        print('�� All verifications passed!')
        return True
    finally:
        await conn.close()

import sys
if not asyncio.run(verify_setup()):
    sys.exit(1)
"

if [[ $? -eq 0 ]]; then
    echo ""
    echo "🎉 Supabase migration completed successfully!"
    echo "🔗 Your database is ready for the Readwise Vector DB application"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Update your .env file with SUPABASE_DB_URL"
    echo "   2. Set DB_BACKEND=supabase in your environment"
    echo "   3. Test your setup with: poetry run python -c 'from readwise_vector_db.config import Settings; print(Settings())'"
    echo ""
else
    echo "❌ Post-migration verification failed"
    exit 1
fi
