"""
Simple Vercel handler for readwise-vector-db API.
This module provides a handler function that Vercel can execute.
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from readwise_vector_db.api.main import create_app  # noqa: E402

# Create the FastAPI app instance
app = create_app()


# Vercel handler function
def handler(request, response):
    """Handler function for Vercel."""
    return app(request, response)


# For ASGI compatibility
application = app


# For Vercel function compatibility
def api(request):
    """Simple API handler for Vercel."""
    return app(request)
