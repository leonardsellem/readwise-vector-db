# Readwise Vector DB – Self-host your reading highlights search

[![Build](https://github.com/leonardsellem/readwise-vector-db/actions/workflows/ci.yml/badge.svg)](https://github.com/leonardsellem/readwise-vector-db/actions/workflows/ci.yml)
[![Coverage Status](https://img.shields.io/badge/coverage-90%25-brightgreen)](https://github.com/leonardsellem/readwise-vector-db/actions/workflows/ci.yml)
[![Licence: MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENCE)

> **Turn your Readwise library into a blazing-fast semantic search engine** – complete with nightly syncs, vector search API, Prometheus metrics, and a streaming MCP server for LLM clients.

---

## Table of Contents
- [Readwise Vector DB – Self-host your reading highlights search](#readwise-vector-db--self-host-your-reading-highlights-search)
  - [Table of Contents](#table-of-contents)
  - [Quick Start](#quick-start)
  - [Using Supabase Cloud](#using-supabase-cloud)
  - [Deploy to Vercel in 3 Commands](#deploy-to-vercel-in-3-commands)
  - [Detailed Setup](#detailed-setup)
    - [Prerequisites](#prerequisites)
    - [Environment Variables](#environment-variables)
    - [Database \& Migrations](#database--migrations)
    - [Sync Commands (CLI)](#sync-commands-cli)
  - [Usage Examples](#usage-examples)
    - [Vector Search (HTTP API)](#vector-search-http-api)
    - [Streaming Search (MCP TCP)](#streaming-search-mcp-tcp)
  - [Architecture Overview](#architecture-overview)
    - [Docker + Local PostgreSQL (Default)](#docker--local-postgresql-default)
    - [Vercel + Supabase (Cloud)](#vercel--supabase-cloud)
  - [Development \& Contribution](#development--contribution)
  - [Maintainer Notes](#maintainer-notes)
  - [License \& Credits](#license--credits)

---

## Quick Start
```bash
# ❶ Clone & install
git clone https://github.com/leonardsellem/readwise-vector-db.git
cd readwise-vector-db
poetry install --sync

# ❷ Boot DB & run the API (localhost:8000)
docker compose up -d db
poetry run uvicorn readwise_vector_db.api:app --reload

# ❸ Verify
curl http://127.0.0.1:8000/health     # → {"status":"ok"}
open http://127.0.0.1:8000/docs       # interactive swagger UI
```

> **Tip:** Codespaces user? Click "Run → Open in Browser" after step ❷.

---

## Using Supabase Cloud

Skip the local Docker setup and use a managed PostgreSQL with pgvector support:

```bash
# ❶ Create Supabase project at https://supabase.com/dashboard
# ❷ Enable pgvector extension in SQL Editor:
#   CREATE EXTENSION IF NOT EXISTS vector;

# ❸ Set up environment
export DB_BACKEND=supabase
export SUPABASE_DB_URL="postgresql://postgres:[password]@db.[project].supabase.co:6543/postgres?options=project%3D[project]"
export READWISE_TOKEN=xxxx
export OPENAI_API_KEY=sk-...

# ❹ Run migrations and start the API
poetry run alembic upgrade head
poetry run uvicorn readwise_vector_db.api:app --reload

# ❺ Initial sync
poetry run rwv sync --backfill
```

> **⚠️ Fail-fast behavior:** The application will raise `ValueError` immediately on startup if `SUPABASE_DB_URL` is missing when `DB_BACKEND=supabase`.

**Environment Variables Required:**
- `DB_BACKEND=supabase` – Switches from local Docker to Supabase
- `SUPABASE_DB_URL` – Full PostgreSQL connection string from Supabase dashboard
- Standard variables: `READWISE_TOKEN`, `OPENAI_API_KEY`

**Benefits:**
- ✅ No Docker setup required
- ✅ Managed backups and scaling
- ✅ Built-in pgvector support
- ✅ Global edge network
- ✅ **SSE streaming optimized** – Connection pooling and sub-100ms query latency

---

## Deploy to Vercel in 3 Commands

Deploy the FastAPI app as a serverless function with Supabase backend:

```bash
# ❶ Set up Vercel project
npm install -g vercel
vercel login
vercel link  # or vercel --confirm for new project

# ❶ Configure environment variables in Vercel dashboard or CLI:
vercel env add SUPABASE_DB_URL
vercel env add READWISE_TOKEN
vercel env add OPENAI_API_KEY

# ❸ Deploy
vercel --prod
```

**Automatic Configuration:**
- `DEPLOY_TARGET=vercel` – Automatically set by Vercel environment
- `DB_BACKEND=supabase` – Pre-configured in `vercel.json`
- Build process uses optimized `vercel_build.sh` script

**Resource Limits:**
- ⏱️ Build timeout: 90 seconds
- 💾 Memory limit: 1024MB during build
- 🚀 Function timeout: 30 seconds per request

**SSE Streaming Support:**
- ✅ **HTTP-based MCP Server** – `/mcp/stream` endpoint works seamlessly
- ✅ **Real-time search results** – Server-Sent Events for streaming responses  
- ✅ **Cold-start optimized** – Sub-1s initialization, auto-scaling connections
- ✅ **HTTP/2 multiplexing** – Unlimited concurrent connections per client

**GitHub Integration:**
- Tagged releases (`v*.*.*`) automatically deploy to production
- Pull requests create preview deployments
- CI validates both Docker and Vercel builds

> **💡 Pro tip:** Use `vercel --prebuilt` for faster subsequent deployments.

### Why SSE for MCP in Serverless?

**Traditional TCP MCP servers don't work in serverless environments** because they require persistent connections. The **HTTP-based MCP Server with Server-Sent Events (SSE)** solves this by providing:

| Feature | TCP MCP Server | **HTTP SSE MCP Server** |
|---------|----------------|-------------------------|
| **Serverless Support** | ❌ Requires persistent connections | ✅ Works on Vercel, Lambda, etc. |
| **Firewall/Proxy** | ⚠️ May require custom ports | ✅ Standard HTTP/HTTPS (80/443) |
| **Browser Support** | ❌ No native support | ✅ EventSource API built-in |
| **Auto-scaling** | ⚠️ Limited by connection pooling | ✅ Infinite scaling via HTTP infrastructure |
| **Cold Starts** | ❌ Connection drops during restarts | ✅ Stateless, reconnects automatically |
| **HTTP/2 Benefits** | ❌ Not applicable | ✅ Multiplexing, header compression |

**Use the SSE endpoint** for production deployments on cloud platforms. The TCP server remains available for local development and dedicated server deployments.

> 📚 **Comprehensive deployment guide:** See [docs/deployment-sse.md](docs/deployment-sse.md) for detailed platform-specific instructions, troubleshooting, and performance tuning.

---

## Detailed Setup
### Prerequisites
• **Python 3.12** \| **Poetry ≥ 1.8** \| **Docker + Compose**

### Environment Variables
Create `.env` (see `.env.example`) – minimal:
```env
READWISE_TOKEN=xxxx     # get from readwise.io/api_token
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+asyncpg://rw_user:rw_pass@localhost:5432/readwise
```
All variables are documented in [docs/env.md](docs/env.md).

### Database & Migrations
```bash
docker compose up -d db       # Postgres 16 + pgvector
poetry run alembic upgrade head
```

### Sync Commands (CLI)
```bash
# first-time full sync
poetry run rwv sync --backfill

# daily incremental (fetch since yesterday)
poetry run rwv sync --since $(date -Idate -d 'yesterday')
```

---

## Usage Examples
### Vector Search (HTTP API)
```bash
curl -X POST http://127.0.0.1:8000/search \
     -H 'Content-Type: application/json' \
     -d '{
           "q": "Large Language Models",
           "k": 10,
           "filters": {
             "source": "kindle",
             "tags": ["ai", "research"],
             "highlighted_at": ["2024-01-01", "2024-12-31"]
           }
         }'
```

### Streaming Search (HTTP SSE)
```bash
# Real-time streaming via Server-Sent Events (serverless-friendly)
curl -N -H "Accept: text/event-stream" \
  "http://127.0.0.1:8000/mcp/stream?q=neural+networks&k=10"
```

### Streaming Search (MCP TCP)
```bash
poetry run python -m readwise_vector_db.mcp --host 0.0.0.0 --port 8375 &

# then from another shell
printf '{"jsonrpc":"2.0","id":1,"method":"search","params":{"q":"neural networks"}}\n' | \
  nc 127.0.0.1 8375
```

> **💡 New:** Check out the [SSE Usage Guide](docs/mcp-sse-usage.md) for JavaScript, Python, and browser examples!

---

## Architecture Overview

The system supports multiple deployment patterns to fit different infrastructure needs:

![Architecture Diagram](docs/images/architecture.png)

### Docker + Local PostgreSQL (Default)
```mermaid
flowchart TB
  subgraph "🐳 Docker Deployment"
    subgraph Ingestion
      A[Readwise API] --> B[Backfill Job]
      C[Nightly Cron] --> D[Incremental Job]
    end
    B --> E[OpenAI Embeddings]
    D --> E
    E --> F[Local PostgreSQL + pgvector]
    F --> G[FastAPI Container]
    G --> H[MCP Server :8375]
    G --> I[Prometheus /metrics]
  end
```

### Vercel + Supabase (Cloud)
```mermaid
flowchart TB
  subgraph "☁️ Serverless Deployment"
    subgraph "Vercel Edge"
      J[FastAPI Serverless] --> K[/health endpoint]
      J --> L[/search endpoint]
      J --> M[/docs Swagger UI]
    end
    subgraph "Supabase Cloud"
      N[Managed PostgreSQL] --> O[pgvector Extension]
      P[Automated Backups] --> N
    end
    J -.-> N
    Q[GitHub Actions] --> R[Auto Deploy on Tags]
    R --> J
  end
```

**Key Differences:**
- **Docker**: Full control, local data, requires infrastructure management
- **Vercel + Supabase**: Zero-ops, global edge deployment, managed scaling
- **Hybrid**: Use Supabase with local Docker for development → production consistency

**Documentation:**
- 📊 [Architecture diagrams](docs/images/architecture.png)
- 🚀 [SSE deployment patterns](docs/architecture-sse.md)
- ⚙️ [Platform-specific configurations](docs/deployment-sse.md)

---

## Development & Contribution
1. **Environment**
   ```bash
   poetry install --with dev
   poetry run pre-commit install   # black, isort, ruff, mypy, markdownlint
   ```
2. **Run tests & coverage**
   ```bash
   poetry run coverage run -m pytest && coverage report
   ```
3. **Performance check** (`make perf`) – fails if `/search` P95 >500 ms.
4. **Branching model**: feature/xyz → PR → squash-merge. Use Conventional Commits (`feat:`, `fix:` …).
5. **Coding style**: see `.editorconfig` and enforced linters.

See [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines.

---

## Maintainer Notes
* **CI/CD** – `.github/workflows/ci.yml` runs lint, type-check, tests (Py 3.11 + 3.12) and publishes images to GHCR.
* **Back-ups** – `pg_dump` weekly cron uploads compressed dump as artifact (`Goal G4`).
* **Releasing** – bump version in `pyproject.toml`, run `make release`.

---

## License & Credits
*Code licensed under the MIT License.*
Made with ❤️ by the community, powered by **FastAPI**, **SQLModel**, **pgvector**, **OpenAI** and **Taskmaster-AI**.
