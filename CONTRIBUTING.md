# Contributing to **Readwise-Vector-DB**

Welcome — and thanks for wanting to improve this project!  The goal of this
document is to ensure you can run the full quality-gate (linters, tests,
coverage **and** performance) exactly like the CI pipeline does, so surprises
are kept to a minimum.

---

## Prerequisites

| Tool | Version (or newer) | Notes |
|------|--------------------|-------|
| **Python** | 3.12 | Other minor versions are used in the CI matrix, but 3.12 is the dev default. |
| **Poetry** | ≥ 1.8 | Manages Python deps/virtual-env. |
| **Docker + Compose v2** | latest | Used for Postgres and app containers during perf tests. |
| **Make** | any | Convenience wrapper for common commands. |

```bash
# Once-off local setup
poetry install --with dev --sync  # install runtime *and* dev dependencies
poetry run pre-commit install    # enable auto-format/lint before each commit
```

---

## Running the Test Suite

```bash
# Fast feedback loop
poetry run pytest -q

# Full run with coverage (same as CI)
poetry run coverage run -m pytest
poetry run coverage report  # should be ≥ 90 %
```

* Configuration lives in `.coveragerc`; the `fail_under = 90` threshold makes
  `pytest` fail automatically if total coverage drops.
* A HTML report can be generated with `coverage html`.

---

## Static Analysis

```bash
poetry run ruff .   # style / correctness
poetry run mypy .   # strict typing (see `pyproject.toml`)
```

Both commands run in CI; please make sure they pass before pushing.

---

## Performance Regression Test

The **Locust** load-test ensures the `/search` endpoint remains responsive.

* **Threshold**: 95-th percentile latency must stay **≤ 500 ms**.
* Script: [`locustfile.py`](./locustfile.py) (uses environment variables for
  overrides).
* Wrapper target:

```bash
# Default: 20 users for 1 minute against http://localhost:8000
make perf

# Custom run (e.g. 50 users for 2 minutes against a remote host)
make perf USERS=50 DURATION=2m BASE_URL=https://api.example.com
```

`make perf` will spin up the Docker Compose stack if it isn't already running,
execute the Locust test headless, and exit non-zero if the latency gate is
breached.

> **Tip** If you want to inspect the live statistics, drop the `--headless`
> flag in `Makefile` temporarily and open the Locust web UI at
> http://localhost:8089.

---

## Continuous Integration

* **Unit tests + coverage** run on every push & pull-request (`.github/workflows/ci.yml`).
* **Nightly performance gate** runs via cron and can be triggered manually
  (`.github/workflows/perf.yml`).
* A pull-request cannot be merged unless the **tests** job passes.  The
  performance job is informational, but maintainers may choose to make it
  required if latency regressions become frequent.

---

## Troubleshooting

| Issue | Likely Cause | Fix |
|-------|--------------|-----|
| Duplicate Prometheus metrics errors during tests | Stubs not imported | Ensure you use the fixtures in `tests/stubs` as documented. |
| `make perf` fails instantly with *connection refused* | API container not healthy | Run `docker compose logs api` and verify the FastAPI app started correctly. |
| Coverage below 90 % | New code lacks tests | Add unit or integration tests for the new paths. |

When in doubt, open an issue or start a discussion — we're happy to help!
