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
