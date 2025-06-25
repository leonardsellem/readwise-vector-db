"""Vercel ASGI entry point for readwise-vector-db API.

This module provides the ASGI application object that Vercel's Python runtime
expects to find. It imports and exposes the FastAPI app from the main package.
"""

import sys
from pathlib import Path

# Add the project root to Python path so we can import our modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from readwise_vector_db.api.main import create_app  # noqa: E402

# Export the ASGI app for Vercel (use create_app instead of get_application for Vercel)
app = create_app()

# For compatibility, also expose as 'application'
application = app
