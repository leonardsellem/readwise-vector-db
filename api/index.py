"""Vercel ASGI entry point for readwise-vector-db API.

This module provides the ASGI application object that Vercel's Python runtime
expects to find. It imports and exposes the FastAPI app from the main package.
"""

import sys
from pathlib import Path

# Add the project root to Python path so we can import our modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables early for Vercel
import os
if os.path.exists('.env'):
    # ↳ Only load .env if it exists (not available in Vercel production)
    from dotenv import load_dotenv
    load_dotenv()

from readwise_vector_db.api.main import create_app  # noqa: E402

# Create the FastAPI app instance
# ↳ This is the ASGI application that Vercel will execute
app = create_app()

# For compatibility with different ASGI servers
application = app
