# Readwise Vector DB – Self-host your reading highlights search

[![Build](https://github.com/<org>/readwise-vector-db/actions/workflows/ci.yml/badge.svg)](https://github.com/<org>/readwise-vector-db/actions/workflows/ci.yml)
[![Coverage Status](https://img.shields.io/badge/coverage-90%25-brightgreen)](https://github.com/<org>/readwise-vector-db/actions/workflows/ci.yml)
[![Licence: MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENCE)

> **Turn your Readwise library into a blazing-fast, self-hosted semantic search engine** – complete with nightly syncs, vector search API, Prometheus metrics, and a streaming MCP server for LLM clients.

---

## Table of Contents
- [Readwise Vector DB – Self-host your reading highlights search](#readwise-vector-db--self-host-your-reading-highlights-search)
  - [Table of Contents](#table-of-contents)
  - [Quick Start](#quick-start)
  - [Detailed Setup](#detailed-setup)
    - [Prerequisites](#prerequisites)
    - [Environment Variables](#environment-variables)
    - [Database \& Migrations](#database--migrations)
    - [Sync Commands (CLI)](#sync-commands-cli)
  - [Usage Examples](#usage-examples)
    - [Vector Search (HTTP API)](#vector-search-http-api)
    - [Streaming Search (MCP TCP)](#streaming-search-mcp-tcp)
  - [Architecture Overview](#architecture-overview)
  - [Development \& Contribution](#development--contribution)
  - [Maintainer Notes](#maintainer-notes)
  - [License \& Credits](#license--credits)

---

## Quick Start
```bash
# ❶ Clone & install
git clone https://github.com/<org>/readwise-vector-db.git
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

## Detailed Setup
### Prerequisites
• **Python 3.12** \| **Poetry ≥ 1.8** \| **Docker + Compose**

### Environment Variables
Create `.env` (see `.env.example`) – minimal:
```env
READWISE_TOKEN=xxxx     # get from readwise.io/api_token
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+psycopg://rw_user:rw_pass@localhost:5432/readwise
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

### Streaming Search (MCP TCP)
```bash
poetry run python -m readwise_vector_db.mcp --host 0.0.0.0 --port 8375 &

# then from another shell
printf '{"jsonrpc":"2.0","id":1,"method":"search","params":{"q":"neural networks"}}\n' | \
  nc 127.0.0.1 8375
```

---

## Architecture Overview
```mermaid
flowchart LR
  subgraph Ingestion
    A[Readwise API] -- highlights --> B[Back-fill Job]
    C[Nightly Cron] -- since-cursor --> D[Incremental Job]
  end
  B & D --> E[Embedding Service (OpenAI)] --> F[(Postgres + pgvector)]
  F --> G[FastAPI / Search API]
  G --> H[MCP Server]
  G --> I[Prometheus Metrics]
```
*Full SVG available at `assets/architecture.svg`.*

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
