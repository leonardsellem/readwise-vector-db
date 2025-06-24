"""Load-testing script for the `/search` endpoint.

Run headless with:

    locust -f locustfile.py --headless -u 20 -r 2 -t1m -H http://localhost:8000

Exit code will be non-zero if the 95th percentile latency for the endpoint
exceeds the threshold defined by the environment variable
`LATENCY_P95_THRESHOLD_MS` (default **500 ms**).
"""

from __future__ import annotations

# Standard library
import os
import random
import sys
from typing import Final

# Third-party
from locust import HttpUser, between, events, task

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

#: Number of results requested per search. Lower numbers keep payloads small
#: so we mainly measure *query* latency rather than JSON serialisation cost.
K_RESULTS: Final[int] = int(os.getenv("K_RESULTS", "10"))

#: Threshold (milliseconds) for the 95th-percentile latency.  Failing the
#: threshold sets a non-zero exit code so that CI pipelines fail fast.
LATENCY_THRESHOLD_MS: Final[float] = float(os.getenv("LATENCY_P95_THRESHOLD_MS", "500"))

#: A small corpus of realistic search queries.  Each virtual user will pick
#: randomly to avoid caching artefacts.
QUERIES: Final[list[str]] = [
    "artificial intelligence",
    "productivity",
    "philosophy",
    "python",
    "history of science",
    "machine learning",
    "deep work",
    "startup advice",
    "mindfulness",
    "data structures",
]

# ---------------------------------------------------------------------------
# Locust user definition
# ---------------------------------------------------------------------------


class SearchUser(HttpUser):
    """Simulates a client performing semantic search requests."""

    # Wait 0.5–1.5 s between tasks to mimic human think-time.
    wait_time = between(0.5, 1.5)

    @task
    def search(self) -> None:  # noqa: D401 – imperative mood
        """POST `/search` with a random query and validate the response."""
        query = random.choice(QUERIES)
        payload = {"q": query, "k": K_RESULTS}

        # `catch_response=True` allows us to mark the request as a failure if
        # we receive a non-200 status code – such failures are counted in the
        # aggregated stats that drive the threshold check below.
        with self.client.post("/search", json=payload, catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"Unexpected status code {resp.status_code}")


# ---------------------------------------------------------------------------
# Percentile threshold enforcement
# ---------------------------------------------------------------------------


def _check_latency_threshold(environment) -> None:  # type: ignore[valid-type]
    """Compute P95 latency for `/search` and fail build if it is too high."""

    stats_entry = environment.stats.get("/search", "POST")
    if stats_entry is None:
        # No stats – likely a configuration error. Fail hard so CI notices.
        print("No statistics collected for POST /search", file=sys.stderr)
        environment.process_exit_code = 1
        return

    p95 = stats_entry.get_current_response_time_percentile(0.95)
    print(
        f"POST /search P95 latency: {p95:.2f} ms (threshold {LATENCY_THRESHOLD_MS} ms)"
    )

    if p95 > LATENCY_THRESHOLD_MS:
        print(
            "Latency threshold exceeded! Marking test run as failed.",
            file=sys.stderr,
        )
        environment.process_exit_code = 1


# Register listener **after** the test stops but **before** Locust sets the
# final exit code. The `quitting` event is ideal for that.
@events.quitting.add_listener  # type: ignore[arg-type]
def _(environment, **_kwargs):  # noqa: D401 – anonymous function acceptable here
    _check_latency_threshold(environment)
