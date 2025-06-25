#!/bin/bash
set -euo pipefail

# Vercel build script for optimized serverless deployment
# This script handles Poetry caching, dependency installation, and build optimization

echo "🚀 Starting Vercel build process..."

# Environment detection
if [[ "${VERCEL:-}" == "1" ]]; then
    echo "📡 Running on Vercel"
    IS_VERCEL=true
else
    echo "🏠 Running locally"
    IS_VERCEL=false
fi

# Cache directory detection
if [[ "$IS_VERCEL" == "true" ]]; then
    CACHE_DIR="${VERCEL_CACHE_DIR:-/tmp/cache}"
else
    CACHE_DIR="${VERCEL_CACHE_DIR:-$(python3 -m pip cache dir)}"
fi
echo "📦 Using cache directory: $CACHE_DIR"

# Poetry cache setup for Vercel
if [[ "$IS_VERCEL" == "true" ]]; then
    export POETRY_CACHE_DIR="$CACHE_DIR/poetry"
    export POETRY_VENV_IN_PROJECT=true
    export POETRY_NO_INTERACTION=1
    export POETRY_INSTALLER_PARALLEL=true

    echo "🎯 Poetry cache configured for Vercel at: $POETRY_CACHE_DIR"
else
    echo "🏠 Using local Poetry configuration"
fi

# Ensure Poetry is available
if ! command -v poetry &> /dev/null; then
    echo "📚 Poetry not found, installing..."
    pip3 install poetry

    # Add Poetry to PATH for this session
    export PATH="$HOME/.local/bin:$PATH"

    # Define poetry function as fallback
    if ! command -v poetry &> /dev/null; then
        echo "⚠️ Poetry still not found in PATH, creating function wrapper"
        poetry() {
            python3 -m poetry "$@"
        }
        export -f poetry
    fi
else
    echo "✅ Poetry found: $(poetry --version)"
fi

# Configure Poetry for serverless optimization
poetry config virtualenvs.create true
poetry config virtualenvs.in-project true
echo "⚙️ Poetry configured for in-project virtual environment"

# Install dependencies (production only for deployment)
if [[ "$IS_VERCEL" == "true" ]]; then
    echo "📥 Installing production dependencies..."
    poetry install --only=main --no-root
else
    echo "📥 Installing all dependencies (including dev)..."
    poetry install
fi

# Verify critical imports work (fail fast if issues)
echo "🔍 Verifying application imports..."
if poetry run python3 -c "
import sys
sys.path.insert(0, '.')

try:
    # Test core application imports
    from readwise_vector_db.api import get_application
    print('✅ API module imports successfully')

    # Test database imports (critical for runtime)
    from readwise_vector_db.db import get_pool
    print('✅ Database module imports successfully')

    # Test creating the app (LifespanManager needs async context)
    from readwise_vector_db.api.main import create_app
    app = create_app()
    print('✅ FastAPI app creation works')

    print('🎉 All critical imports verified')

except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
except Exception as e:
    print(f'❌ Application error: {e}')
    sys.exit(1)
"; then
    echo "✅ Import verification passed"
else
    echo "❌ Import verification failed"
    exit 1
fi

# Migration support for Vercel (if database migrations are needed)
if [[ "$IS_VERCEL" == "true" && "${VERCEL_ENV:-}" == "production" ]]; then
    echo "🗄️ Running database migrations..."
    if [[ -n "${DATABASE_URL:-}" ]] || [[ -n "${SUPABASE_DB_URL:-}" ]]; then
        poetry run alembic upgrade head || echo "⚠️ Migration failed or not configured"
    else
        echo "⚠️ No database URL configured, skipping migrations"
    fi
fi

# Build cleanup for smaller deployment
if [[ "$IS_VERCEL" == "true" ]]; then
    echo "🧹 Aggressive cleanup for Vercel size limits..."

    # Remove unnecessary files to reduce deployment size
    find . -name "*.pyc" -delete 2>/dev/null || true
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true

    # Remove test files and dev artifacts
    rm -rf tests/ 2>/dev/null || true
    rm -rf .pytest_cache/ 2>/dev/null || true
    rm -rf .coverage 2>/dev/null || true
    rm -rf htmlcov/ 2>/dev/null || true

    # Aggressive virtual environment cleanup
    if [[ -d ".venv" ]]; then
        echo "🗑️ Cleaning virtual environment..."

        # Remove test directories in packages
        find .venv -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true
        find .venv -name "test" -type d -exec rm -rf {} + 2>/dev/null || true
        find .venv -name "*tests*" -type d -exec rm -rf {} + 2>/dev/null || true

        # Remove documentation and examples
        find .venv -name "docs" -type d -exec rm -rf {} + 2>/dev/null || true
        find .venv -name "examples" -type d -exec rm -rf {} + 2>/dev/null || true
        find .venv -name "*.md" -delete 2>/dev/null || true
        find .venv -name "*.rst" -delete 2>/dev/null || true
        find .venv -name "*.txt" -delete 2>/dev/null || true

        # Remove development tools (not needed in production)
        rm -rf .venv/lib/python*/site-packages/pip* 2>/dev/null || true
        rm -rf .venv/lib/python*/site-packages/setuptools* 2>/dev/null || true
        rm -rf .venv/lib/python*/site-packages/wheel* 2>/dev/null || true

        # Remove .pyc and cache files in venv
        find .venv -name "*.pyc" -delete 2>/dev/null || true
        find .venv -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

        # Remove source files for compiled packages (keep only .so files)
        find .venv -name "*.c" -delete 2>/dev/null || true
        find .venv -name "*.h" -delete 2>/dev/null || true
        find .venv -name "*.pyx" -delete 2>/dev/null || true

        echo "✅ Virtual environment cleaned"
    fi

    # Remove heavy packages we don't need in production
    rm -rf .venv/lib/python*/site-packages/cryptography/hazmat/bindings/_rust* 2>/dev/null || true

    echo "✅ Aggressive cleanup completed"
fi

# Build statistics and size reporting
if command -v du &> /dev/null; then
    TOTAL_SIZE=$(du -sh . 2>/dev/null | cut -f1 || echo "unknown")
    echo "📊 Total deployment size: $TOTAL_SIZE"
fi

# Virtual environment size (for monitoring)
if [[ -d ".venv" ]]; then
    VENV_SIZE=$(du -sh .venv 2>/dev/null | cut -f1 || echo "unknown")
    echo "📦 Virtual environment size: $VENV_SIZE"
fi

echo "🎉 Vercel build completed successfully!"

# Show key environment info for debugging
echo "
📋 Build Summary:
- Environment: ${VERCEL_ENV:-development}
- Python: $(python3 --version 2>&1)
- Poetry: $(poetry --version 2>&1)
- Cache dir: $CACHE_DIR
- Is Vercel: $IS_VERCEL
"
