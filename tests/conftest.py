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

        # Simple async generator yielding one dummy session
        yield _Session()

    db_stub.get_session = _dummy_get_session  # type: ignore

    # Provide placeholder AsyncSessionLocal used by FastAPI dependencies
    async def _async_session_local():  # noqa: D401
        class _Session:  # noqa: D401
            async def __aenter__(self):  # noqa: D401
                return self

            async def __aexit__(self, exc_type, exc, tb):  # noqa: D401
                pass

            async def exec(self, *_args, **_kwargs):  # noqa: D401
                return []

        return _Session()

    db_stub.AsyncSessionLocal = _async_session_local  # type: ignore

    sys.modules["readwise_vector_db.db.database"] = db_stub

# --- Stub readwise_vector_db.models (Highlight placeholder) -------------------
if "readwise_vector_db.models" not in sys.modules:
    models_stub = _t.ModuleType("readwise_vector_db.models")

    class _Highlight:  # noqa: D401
        __table__ = _t.SimpleNamespace(c=_t.SimpleNamespace(embedding=None))

        # attributes referenced in filters
        embedding = None
        source_type = None
        author = None
        tags = None
        highlighted_at = None

        def model_dump(self):  # noqa: D401
            return {"id": "stub", "text": "stub"}

    models_stub.Highlight = _Highlight  # type: ignore

    class _SyncState:  # noqa: D401
        id = 1
        cursor = "stub"

    models_stub.SyncState = _SyncState  # type: ignore

    sys.modules["readwise_vector_db.models"] = models_stub

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
    openai_stub.RateLimitError = Exception  # type: ignore
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

# Stub submodule `readwise_vector_db.models.api` with Pydantic-like models
api_models_stub = _t.ModuleType("readwise_vector_db.models.api")

try:
    from pydantic import BaseModel as _BaseModel  # type: ignore
except Exception:
    _BaseModel = object  # type: ignore

class _SearchRequest(_BaseModel):  # type: ignore
    q: str
    k: int = 20

class _SearchResponse(_BaseModel):  # type: ignore
    results: list[str] = []

api_models_stub.SearchRequest = _SearchRequest  # type: ignore
api_models_stub.SearchResponse = _SearchResponse  # type: ignore

sys.modules["readwise_vector_db.models.api"] = api_models_stub

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

    sys.modules["prometheus_client"] = prom_client_stub
