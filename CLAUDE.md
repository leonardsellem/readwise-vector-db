# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Commands

### Development Workflow
```bash
# Setup and installation
poetry install --with dev                        # Install all dependencies
poetry run pre-commit install                    # Setup code quality hooks

# Core development commands
poetry run uvicorn readwise_vector_db.api:app --reload  # Run dev server (localhost:8000)
docker compose up -d db                          # Start PostgreSQL with pgvector
docker compose up -d api                         # Start API container

# CLI operations
poetry run rwv sync --backfill                   # Initial full sync from Readwise
poetry run rwv sync --since $(date -Idate -d 'yesterday')  # Incremental sync

# Database management
poetry run alembic upgrade head                  # Run migrations
make migrate-supabase                            # Migrate Supabase database
```

### Testing and Quality
```bash
# Testing
poetry run pytest                               # Run test suite
make cov                                        # Run tests with targeted coverage analysis
make perf                                       # Performance testing (P95 < 500ms requirement)

# Code quality
poetry run black .                              # Format code
poetry run isort .                              # Sort imports
poetry run ruff check .                         # Lint code
poetry run mypy .                               # Type checking
```

### Deployment
```bash
# Local Docker deployment
docker compose up -d                            # Full stack deployment

# Vercel deployment
vercel --prod                                   # Deploy to production
vercel env add SUPABASE_DB_URL                  # Configure environment variables
```

## Architecture Overview

### Multi-Backend System
This project supports **dual deployment patterns**:
- **Local**: Docker + PostgreSQL with pgvector
- **Cloud**: Vercel serverless + Supabase managed database

Configuration is unified through `readwise_vector_db/config.py` with environment-driven backend switching:
- `DB_BACKEND=local|supabase`
- `DEPLOY_TARGET=docker|vercel`

### Core Components

**API Layer** (`readwise_vector_db/api/`):
- `main.py`: FastAPI app factory with async lifespan management
- `routes.py`: Endpoints for health, search, and MCP streaming (`/health`, `/search`, `/mcp/stream`)

**Core Business Logic** (`readwise_vector_db/core/`):
- `search.py`: Semantic search engine with vector similarity
- `embedding.py`: OpenAI API integration for text-to-vector conversion
- `readwise.py`: Readwise API client with pagination

**Database Layer** (`readwise_vector_db/db/`):
- `database.py`: Async connection management with lazy initialization
- `supabase_ops.py`: Optimized operations for Supabase cloud deployment
- `upsert.py`: Bulk data insertion with conflict resolution

**Background Jobs** (`readwise_vector_db/jobs/`):
- `backfill.py`: Full highlight synchronization
- `incremental.py`: Delta sync for recent updates
- `parser.py`: Data transformation and processing

**MCP Server** (`readwise_vector_db/mcp/`):
- `server.py`: TCP server for local development
- `search_service.py`: Shared search logic between protocols
- Dual protocol support: TCP for local + HTTP SSE for serverless

### Key Patterns

**Async-First Architecture**:
- All database operations use asyncpg with SQLModel
- Lazy initialization pattern for cold-start optimization
- Streaming responses via async generators

**Performance Optimization**:
- Connection pooling with different configurations for local vs serverless
- Sub-100ms search latency requirements (enforced by performance tests)
- Bulk operations for data synchronization

**Configuration Management**:
- Pydantic Settings for type-safe environment variable loading
- Single Settings class supports both local and cloud deployments
- Environment-driven feature toggles

## Development Guidelines

### Code Style
- **Line length**: 88 characters (Black formatter)
- **Import sorting**: isort with Black profile
- **Type hints**: Optional but encouraged for public APIs
- **Async patterns**: Prefer async/await throughout

### Testing Strategy
The project uses **targeted coverage thresholds**:
- **Core modules** (`core/`, `models/`): 100% coverage required
- **High-priority** (`api/`, `db/`): 85% coverage target
- **Standard modules**: 70% coverage minimum

Test files are organized by component:
- `test_api.py`: FastAPI endpoint testing
- `test_mcp_server.py`: MCP protocol compliance
- `test_core_search.py`: Search algorithm validation
- `test_supabase_ops.py`: Cloud database operations

### Adding New Features

**For API endpoints**:
1. Add models to `readwise_vector_db/models/api.py`
2. Implement route in `readwise_vector_db/api/routes.py`
3. Add tests in `tests/test_api.py`
4. Update OpenAPI documentation

**For database operations**:
1. Create migrations with `poetry run alembic revision --autogenerate -m "description"`
2. Implement operations in appropriate `db/` module
3. Add dual-backend support (local + Supabase) if needed
4. Test with both backends

**For background jobs**:
1. Implement in `readwise_vector_db/jobs/`
2. Add CLI integration in `main.py`
3. Consider incremental vs. full sync patterns
4. Test with realistic data volumes

### Environment Configuration

**Required Variables**:
```env
READWISE_TOKEN=xxxx                    # From readwise.io/api_token
OPENAI_API_KEY=sk-...                  # For embeddings generation
DATABASE_URL=postgresql+asyncpg://...  # Local PostgreSQL connection
```

**Backend Switching**:
```env
# Local development (default)
DB_BACKEND=local
DATABASE_URL=postgresql+asyncpg://rw_user:rw_pass@localhost:5432/readwise

# Supabase cloud
DB_BACKEND=supabase
SUPABASE_DB_URL=postgresql://postgres:[password]@db.[project].supabase.co:6543/postgres?options=project%3D[project]
```

**Deployment Targets**:
```env
# Docker deployment (default)
DEPLOY_TARGET=docker

# Vercel serverless (auto-detected)
DEPLOY_TARGET=vercel
```

## Special Features

### MCP Protocol Innovation
This project implements a **first-of-kind HTTP-based MCP server** using Server-Sent Events (SSE) for serverless compatibility:

- **TCP MCP Server** (`/mcp/server.py`): Traditional protocol for local development
- **HTTP SSE MCP** (`/mcp/stream` endpoint): Serverless-compatible streaming protocol

### Dual Database Architecture
Unified codebase with optimized operations for both backends:
- **Local PostgreSQL**: Full-featured development with pgvector extension
- **Supabase**: Optimized queries with connection pooling and sub-100ms latency

### Performance Monitoring
Built-in observability with Prometheus metrics:
- Request/response metrics via `prometheus-fastapi-instrumentator`
- Performance testing with P95 latency enforcement
- Coverage analysis with per-module thresholds

## Troubleshooting

### Database Issues
```bash
# Reset local database
docker compose down db && docker compose up -d db
poetry run alembic upgrade head

# Check Supabase connection
poetry run python -c "from readwise_vector_db.config import get_settings; print(get_settings().supabase_db_url)"
```

### Sync Problems
```bash
# Check Readwise API connectivity
poetry run python -c "from readwise_vector_db.core.readwise import get_highlights; print('API works')"

# Debug embedding generation
poetry run python -c "from readwise_vector_db.core.embedding import get_embedding; print(len(get_embedding('test')))"
```

### Performance Issues
```bash
# Run performance test locally
make perf

# Check database query performance
poetry run python -c "from readwise_vector_db.core.search import search_highlights; import time; start=time.time(); print(len(search_highlights('test', k=10))); print(f'Query took {time.time()-start:.3f}s')"
```

### MCP Server Issues
```bash
# Test TCP MCP server
poetry run python -m readwise_vector_db.mcp --host 0.0.0.0 --port 8375 &
printf '{"jsonrpc":"2.0","id":1,"method":"search","params":{"q":"test"}}\n' | nc 127.0.0.1 8375

# Test HTTP SSE MCP
curl -N -H "Accept: text/event-stream" "http://127.0.0.1:8000/mcp/stream?q=test&k=5"
```

## Task Master Integration

This project supports Task Master AI for structured task management and development workflows. For complete guidance on using Task Master commands with Claude Code, see:

📋 **[Task Master Integration Guide](docs/claude-code-integration-guide.md)**

The guide covers:
- Essential Task Master commands (`task-master init`, `task-master next`, etc.)
- MCP integration setup and configuration
- Daily development workflows with structured task tracking
- Custom slash commands for repeated Task Master operations
- Best practices for iterative implementation with task logging

---

This codebase demonstrates sophisticated async Python patterns, multi-cloud deployment strategies, and innovative approaches to MCP protocol implementation for modern AI applications.
