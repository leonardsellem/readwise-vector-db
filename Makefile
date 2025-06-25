.PHONY: perf migrate-supabase

# ---------------------------------------------------------------------------
# Performance testing
# ---------------------------------------------------------------------------
# Run a headless Locust load-test against the `/search` endpoint and fail if
# 95-th percentile latency exceeds the threshold defined inside `locustfile.py`.
#
# Optional environment overrides:
#   BASE_URL — target host (default http://localhost:8000)
#   USERS    — concurrent virtual users (default 20)
#   DURATION — test duration understood by Locust (default 1m)
#
# Example:
#   make perf USERS=50 DURATION=2m BASE_URL=http://api.local:8000
# ---------------------------------------------------------------------------
perf:
	@echo "Starting Docker services (if not already running)…"
	@docker compose up -d --wait db api
	@echo "Running Locust performance test…"
	@export BASE_URL:=${BASE_URL-http://localhost:8000}; \
	export USERS:=${USERS-20}; \
	export DURATION:=${DURATION-1m}; \
	locust -f locustfile.py --headless -u $$USERS -r 2 -t $$DURATION -H $$BASE_URL; \
	EXIT=$$?; \
	echo "Stopping API container…"; \
	docker compose stop api; \
	exit $$EXIT

# ---------------------------------------------------------------------------
# Supabase Migration
# ---------------------------------------------------------------------------
# Run Alembic migrations against a Supabase PostgreSQL database.
# Ensures pgvector extension is enabled and all schema changes are applied.
#
# Prerequisites:
#   - SUPABASE_DB_URL environment variable must be set
#   - Network access to your Supabase project
#
# Usage:
#   export SUPABASE_DB_URL="postgresql://postgres:password@project.supabase.co:6543/postgres?options=project%3Dproject"
#   make migrate-supabase
#
# Or load from .env file:
#   make migrate-supabase
# ---------------------------------------------------------------------------
migrate-supabase:
	@if [ -f .env ]; then \
		echo "📄 Loading environment from .env file..."; \
		set -a; source .env; set +a; \
	fi; \
	./scripts/run_migrations_supabase.sh
