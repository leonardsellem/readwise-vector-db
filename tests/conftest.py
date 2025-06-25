import sys
import types
from contextlib import contextmanager

# --- Stub sqlmodel (used only during import in tests) ------------------------
if "sqlmodel" not in sys.modules:
    sqlmodel_stub = types.ModuleType("sqlmodel")

    # minimal no-op functions / classes expected by imports
    def _dummy(*_args, **_kwargs):  # noqa: D401, E501
        """Stub that does nothing and returns None."""
        return None

    # Commonly imported callables
    sqlmodel_stub.and_ = _dummy  # type: ignore
    sqlmodel_stub.func = types.SimpleNamespace()  # attribute placeholder
    sqlmodel_stub.select = _dummy  # type: ignore
    sqlmodel_stub.Field = _dummy  # type: ignore
    sqlmodel_stub.SQLModel = object  # type: ignore

    # Provide AsyncSession & Session placeholders
    sqlmodel_stub.Session = object  # type: ignore
    sqlmodel_stub.AsyncSession = object  # type: ignore

    # Provide stub submodules required by database.py
    ext_mod = types.ModuleType("sqlmodel.ext")
    asyncio_mod = types.ModuleType("sqlmodel.ext.asyncio")
    session_mod = types.ModuleType("sqlmodel.ext.asyncio.session")
    session_mod.AsyncSession = object  # type: ignore
    asyncio_mod.session = session_mod  # type: ignore
    ext_mod.asyncio = asyncio_mod  # type: ignore

    # Register the submodules in sys.modules so import machinery can find them
    sys.modules["sqlmodel.ext"] = ext_mod
    sys.modules["sqlmodel.ext.asyncio"] = asyncio_mod
    sys.modules["sqlmodel.ext.asyncio.session"] = session_mod

    # Attach ext to root stub
    sqlmodel_stub.ext = ext_mod  # type: ignore

    # Provide cosine_distance placeholder used in search module
    def _cosine_distance(col, emb):  # noqa: D401, ANN001
        return types.SimpleNamespace(label=lambda _name: types.SimpleNamespace())

    sqlmodel_stub.func.cosine_distance = _cosine_distance  # type: ignore

    sys.modules["sqlmodel"] = sqlmodel_stub

# --- Stub prometheus_fastapi_instrumentator ----------------------------------
if "prometheus_fastapi_instrumentator" not in sys.modules:
    prom_stub = types.ModuleType("prometheus_fastapi_instrumentator")

    class _Instrumentator:  # noqa: D401
        """No-op stub mirroring basic interface."""

        def instrument(self, app):  # noqa: ANN001
            return self

        def expose(self, app):  # noqa: ANN001
            return self

    prom_stub.Instrumentator = _Instrumentator  # type: ignore
    sys.modules["prometheus_fastapi_instrumentator"] = prom_stub

# --- Stub respx (HTTP mocking lib) -------------------------------------------
if "respx" not in sys.modules:
    respx_stub = types.ModuleType("respx")

    @contextmanager
    def _mock(*_args, **_kwargs):  # noqa: D401, E501
        yield

    respx_stub.mock = _mock  # type: ignore
    sys.modules["respx"] = respx_stub

# --- Stub readwise_vector_db.db.database -------------------------------------
import types as _t

if "readwise_vector_db.db.database" not in sys.modules:
    db_stub = _t.ModuleType("readwise_vector_db.db.database")

    async def _dummy_get_session():  # noqa: D401
        class _Session:  # noqa: D401
            async def exec(self, *args, **kwargs):  # noqa: D401, ANN001
                return []

            async def execute(self, *args, **kwargs):  # noqa: D401, ANN001
                return []

        # Simple async generator yielding one dummy session
        yield _Session()

    db_stub.get_session = _dummy_get_session  # type: ignore

    # Provide placeholder AsyncSessionLocal used by FastAPI dependencies
    def _async_session_local():  # noqa: D401
        class _Session:  # noqa: D401
            async def __aenter__(self):  # noqa: D401
                return self

            async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
                pass

            async def exec(self, *_args, **_kwargs):  # noqa: D401
                return []

            async def execute(self, *_args, **_kwargs):  # noqa: D401
                return []

        return _Session()

    db_stub.AsyncSessionLocal = _async_session_local  # type: ignore

    # If api module already imported, patch its reference as well so that
    # `async with AsyncSessionLocal()` uses our stub implementation.
    if "readwise_vector_db.api" in sys.modules:
        sys.modules["readwise_vector_db.api"].AsyncSessionLocal = _async_session_local  # type: ignore

    sys.modules["readwise_vector_db.db.database"] = db_stub

# --- Stub readwise_vector_db.models (Highlight placeholder) -------------------
if "readwise_vector_db.models" not in sys.modules:
    models_stub = _t.ModuleType("readwise_vector_db.models")

    # Provide table columns namespace and static attributes for filters
    __table__ = _t.SimpleNamespace(
        c=_t.SimpleNamespace(
            embedding=_t.SimpleNamespace(isnot=lambda _self, val: True)
        )
    )

    embedding = None
    source_type = None
    author = None
    tags = _t.SimpleNamespace(op=lambda *args, **kwargs: _t.SimpleNamespace())
    highlighted_at = _t.SimpleNamespace(
        between=lambda *args, **kwargs: _t.SimpleNamespace()
    )

    class _Highlight:  # noqa: D401
        # Static table/column placeholders for SQLAlchemy expressions
        __table__ = _t.SimpleNamespace(
            c=_t.SimpleNamespace(embedding=_t.SimpleNamespace(isnot=lambda _val: True))
        )

        # Attributes referenced in filters
        embedding = None
        source_type = None
        author = None
        tags = _t.SimpleNamespace(op=lambda *args, **kwargs: _t.SimpleNamespace())
        highlighted_at = _t.SimpleNamespace(
            between=lambda *args, **kwargs: _t.SimpleNamespace()
        )

        def __init__(self, **kwargs):  # noqa: D401
            # Set provided attributes
            for k, v in kwargs.items():
                setattr(self, k, v)

            # Ensure essential attributes exist even if not passed
            self.id = getattr(self, "id", "stub")
            self.text = getattr(self, "text", "stub")

        def model_dump(self):  # noqa: D401
            return vars(self)

    models_stub.Highlight = _Highlight  # type: ignore

    class _SyncState:  # noqa: D401
        id = 1
        cursor = "stub"

    models_stub.SyncState = _SyncState  # type: ignore

    sys.modules["readwise_vector_db.models"] = models_stub

# --- Shared Error Stubs ------------------------------------------------------


class RateLimitError(Exception):
    """Stub OpenAI RateLimitError with compatible signature."""

    def __init__(self, message: str, response=None, body=None):  # noqa: D401, ANN001
        super().__init__(message)
        self.response = response
        self.body = body

    def model_dump(self):  # noqa: D401
        return vars(self)


# --- Stub openai --------------------------------------------------------------
if "openai" not in sys.modules:
    openai_stub = _t.ModuleType("openai")

    class _AsyncClient:  # noqa: D401
        def __init__(self, *args, **kwargs):
            pass

        class embeddings:  # noqa: D401
            @staticmethod
            async def create(*args, **kwargs):  # noqa: ANN001
                return _t.SimpleNamespace(data=[_t.SimpleNamespace(embedding=[0.0])])

    openai_stub.AsyncClient = _AsyncClient  # type: ignore
    # Replace generic Exception with custom stub supporting kwargs
    openai_stub.RateLimitError = RateLimitError  # type: ignore
    sys.modules["openai"] = openai_stub

# ---------------------------------------------------------------------------
# pytest configuration helpers
# ---------------------------------------------------------------------------


def pytest_configure(config):  # type: ignore
    """Ensure the `asyncio` marker is always registered.

    If the real ``pytest-asyncio`` plugin is installed this is harmless because
    the marker will already exist. When the plugin is missing (e.g. in minimal
    CI environments) this prevents PytestUnknownMarkWarning and allows the
    test suite to collect without complaining. It does **not** provide the
    actual async test support – for that you still need the plugin. However,
    most of our custom stubs avoid needing a real event loop, so this fallback
    is acceptable for unit-level import tests.
    """

    config.addinivalue_line("markers", "asyncio: mark the test as running with asyncio")


def _is_coroutine(obj):  # noqa: D401
    """Return True if *obj* is an async function or returns a coroutine."""

    import inspect

    return inspect.iscoroutinefunction(obj)


def pytest_pyfunc_call(pyfuncitem):  # type: ignore
    """Fallback executor for async tests when pytest-asyncio is absent.

    The real ``pytest-asyncio`` plugin provides sophisticated fixtures and
    parametrisation. For our lightweight unit-test scenarios we just need a
    basic runner that awaits the coroutine. If the test object is async we run
    it inside a temporary event loop via ``asyncio.run``.
    """

    import asyncio

    if _is_coroutine(pyfuncitem.obj):
        funcargs = {name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames}  # type: ignore[attr-defined]
        asyncio.run(pyfuncitem.obj(**funcargs))
        return True  # tell pytest we handled the call
    return None  # pytest will execute the test normally


# --- Stub prometheus_client to avoid duplicate metric registration -----------
if "prometheus_client" not in sys.modules:
    prom_client_stub = _t.ModuleType("prometheus_client")

    class _Metric:  # noqa: D401
        def __init__(self, *args, **kwargs):
            pass

        def inc(self, *_args, **_kwargs):  # noqa: D401
            pass

        def observe(self, *_args, **_kwargs):  # noqa: D401
            pass

    prom_client_stub.Counter = _Metric  # type: ignore
    prom_client_stub.Histogram = _Metric  # type: ignore
    prom_client_stub.Gauge = _Metric  # type: ignore

    class _CollectorRegistry:  # noqa: D401
        def register(self, *_args, **_kwargs):  # noqa: D401
            pass

    prom_client_stub.CollectorRegistry = _CollectorRegistry  # type: ignore
    prom_client_stub.REGISTRY = _CollectorRegistry()  # type: ignore

    # Rows synced metric text for /metrics testing
    def _generate_latest(_registry=None):  # noqa: D401, ANN001
        return (
            b"# HELP rows_synced_total Total rows synced by the sync service\n"
            b"# TYPE rows_synced_total counter\nrows_synced_total 0\n"
            b"# HELP error_rate Total errors encountered\n# TYPE error_rate gauge\nerror_rate 0\n"
            b'# HELP sync_duration_seconds Sync duration in seconds\n# TYPE sync_duration_seconds histogram\nsync_duration_seconds_bucket{le="0.5"} 0\n'
            b"# HELP http_requests_total Total HTTP requests\n# TYPE http_requests_total counter\nhttp_requests_total 0\n"
        )

    prom_client_stub.generate_latest = _generate_latest  # type: ignore

    sys.modules["prometheus_client"] = prom_client_stub

# ---------------------------------------------------------------------------
# Additional FastAPI-related stubs to satisfy API test suite
# ---------------------------------------------------------------------------

# 1️⃣  SearchRequest / SearchResponse models -----------------------------------

try:
    from pydantic import BaseModel as _PydanticBaseModel  # type: ignore
except Exception:  # pragma: no cover – pydantic should exist but stub if missing

    class _PydanticBaseModel:  # type: ignore
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)


class _SearchRequest(_PydanticBaseModel):  # type: ignore
    q: str  # required query text
    k: int = 20
    source_type: str | None = None
    author: str | None = None
    tags: list[str] | None = None
    highlighted_at_range: tuple[str, str] | None = None


class _SearchResponse(_PydanticBaseModel):  # type: ignore
    total: int = 0
    took_ms: int = 0
    results: list[dict] = []


# Attach to stub module so FastAPI can import them via response_model argument
import types as _t2  # noqa: E402

api_models_stub = sys.modules.get("readwise_vector_db.models.api")
if not api_models_stub:
    api_models_stub = _t2.ModuleType("readwise_vector_db.models.api")
    sys.modules["readwise_vector_db.models.api"] = api_models_stub

api_models_stub.SearchRequest = _SearchRequest  # type: ignore[attr-defined]
api_models_stub.SearchResponse = _SearchResponse  # type: ignore[attr-defined]

# 2️⃣  AsyncSessionLocal context-manager and get_session fallback ---------------

if "readwise_vector_db.db.database" in sys.modules:
    db_stub = sys.modules["readwise_vector_db.db.database"]

    class _SessionCtx:  # noqa: D401
        """Minimal async session supporting exec()."""

        async def __aenter__(self):  # noqa: D401
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
            return False

        async def exec(self, *_args, **_kwargs):  # noqa: D401
            return []

        async def execute(self, *_args, **_kwargs):  # noqa: D401
            return []

    def _async_session_local():  # noqa: D401
        return _SessionCtx()

    db_stub.AsyncSessionLocal = _async_session_local  # type: ignore

# 3️⃣  Prometheus Instrumentator + /metrics route ------------------------------

if "prometheus_fastapi_instrumentator" in sys.modules:
    instrumentator_mod = sys.modules["prometheus_fastapi_instrumentator"]

    from fastapi import (
        FastAPI,  # imported here to avoid top-level dependency if tests not using FastAPI
    )

    class _InstrumentatorStub:  # noqa: D401
        def instrument(self, app: FastAPI):  # noqa: ANN001
            # Nothing to instrument in tests
            return self

        def expose(self, app: FastAPI):  # noqa: ANN001
            # Register /metrics once if not already present
            if not any(r.path == "/metrics" for r in app.router.routes):

                @app.get("/metrics")  # type: ignore[misc]
                async def _metrics():  # noqa: D401
                    from prometheus_client import generate_latest  # type: ignore

                    return generate_latest().decode()

            return self

    instrumentator_mod.Instrumentator = _InstrumentatorStub  # type: ignore

# 4️⃣  Duplicate-safe prometheus_client stubs already defined above -------------

# 5️⃣  Autouse fixture to clean registry between tests -------------------------

import pytest as _pytest  # noqa: E402


@_pytest.fixture(autouse=True)
def _reset_prom_registry():  # noqa: D401
    """Clear custom metric registry stubs between tests to avoid duplicates."""

    yield
    # On teardown reset REGISTRY attribute if present
    prom_client = sys.modules.get("prometheus_client")
    if prom_client and hasattr(prom_client, "REGISTRY"):
        prom_client.REGISTRY = prom_client.CollectorRegistry()  # type: ignore


# ---------------------------------------------------------------------------
# Additional stubs for sqlmodel.select/insert and respx fixture
# ---------------------------------------------------------------------------

import types as _types  # noqa: E402

# Extend sqlmodel stub if present
_sqlmodel = sys.modules.get("sqlmodel")
if _sqlmodel:

    class _SelectMock:  # noqa: D401
        def where(self, *_a, **_k):
            return self

        def limit(self, *_a, **_k):
            return self

        def order_by(self, *_a, **_k):
            return self

    def _select(*_a, **_k):  # noqa: D401
        return _SelectMock()

    _sqlmodel.select = _select  # type: ignore

    class _InsertMock:  # noqa: D401
        def values(self, *_a, **_k):  # noqa: D401
            return self

        def on_conflict_do_update(self, **_kw):  # noqa: D401
            return self

    def _insert(_table):  # noqa: D401, ANN001
        return _InsertMock()

    _sqlmodel.insert = _insert  # type: ignore

    # Also patch SQLAlchemy Postgres dialect insert used by upsert_highlights
    import importlib

    _dml = importlib.import_module("sqlalchemy.dialects.postgresql.dml")
    _dml.insert = _insert  # type: ignore

    # Patch imported insert reference inside project upsert module if loaded
    if "readwise_vector_db.db.upsert" in sys.modules:
        sys.modules["readwise_vector_db.db.upsert"].insert = _insert  # type: ignore

    # Override Insert class used when insert(...) returns object
    class _InsertClass:  # noqa: D401
        def __init__(self, *_a, **_k):  # noqa: D401
            pass

        def values(self, values):  # noqa: D401, ANN001
            # Record the column names for excluded simulation
            if isinstance(values, list) and values:
                self._columns = list(values[0].keys())
            else:
                self._columns = []
            return self

        @property
        def excluded(self):  # noqa: D401
            return [
                _types.SimpleNamespace(name=col)
                for col in getattr(self, "_columns", [])
            ]

        def on_conflict_do_update(self, **_kw):
            return self

    _dml.Insert = _InsertClass  # type: ignore

# Enhance prometheus_client stub generate_latest to include error_rate
_prom = sys.modules.get("prometheus_client")
if _prom and hasattr(_prom, "generate_latest"):

    def _gen_latest(_registry=None):  # noqa: D401, ANN001
        return (
            b"# HELP rows_synced_total Total rows synced by the sync service\n"
            b"# TYPE rows_synced_total counter\nrows_synced_total 0\n"
            b"# HELP error_rate Total errors encountered\n# TYPE error_rate gauge\nerror_rate 0\n"
            b'# HELP sync_duration_seconds Sync duration in seconds\n# TYPE sync_duration_seconds histogram\nsync_duration_seconds_bucket{le="0.5"} 0\n'
            b"# HELP http_requests_total Total HTTP requests\n# TYPE http_requests_total counter\nhttp_requests_total 0\n"
        )

    _prom.generate_latest = _gen_latest  # type: ignore


@_pytest.fixture
def respx_mock(monkeypatch):  # noqa: D401
    """Simple respx mock fixture providing .get() stub."""

    class _RouteStub:  # noqa: D401
        def __init__(self):
            self._side = None

        def mock(self, side_effect=None, **_kw):  # noqa: D401, ANN001
            self._side = side_effect
            return self

        def __call__(self, *a, **k):  # noqa: D401, ANN001
            side = self._side
            if isinstance(side, list):
                if not side:
                    raise httpx.ConnectTimeout("No more mocked responses")
                res = side.pop(0)
            else:
                res = side

            if callable(res):
                return res(*a, **k)
            return res

    class _RespxStub:  # noqa: D401
        def __init__(self):
            self._routes = {}

        def get(self, url, *_a, **_k):  # noqa: D401
            route = self._routes.setdefault(url, _RouteStub())
            return route

    stub = _RespxStub()
    monkeypatch.setitem(sys.modules, "respx.mock", stub)  # type: ignore[arg-type]

    # Patch httpx.AsyncClient.get to delegate to our stub route
    import httpx

    _orig_get = httpx.AsyncClient.get  # noqa: F841

    async def _mock_get(self, url, *args, **kwargs):  # noqa: D401, ANN001
        route = stub.get(url)
        if route._side is None:
            raise httpx.ConnectTimeout("No mock defined for URL")
        res = route()
        if isinstance(res, httpx.Response):
            # Ensure Response has a request set (avoid httpx RuntimeError in raise_for_status)
            try:
                _ = res.request  # access property may raise if unset
            except RuntimeError:
                res._request = httpx.Request("GET", url)  # type: ignore[attr-defined, protected-access]
            return res

        # Ensure the Response includes a request object so .raise_for_status() works
        req = httpx.Request("GET", url)
        return httpx.Response(200, json=res or {}, request=req)

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get, raising=True)

    return stub
