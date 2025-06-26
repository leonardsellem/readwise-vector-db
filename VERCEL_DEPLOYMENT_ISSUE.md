# Vercel Deployment Issue: Python Version Detection Failure Despite Successful Build

## **Problem Summary**

Vercel deployment consistently fails with
`Error: Unable to find any supported Python versions`
**after** a completely successful build process. The build completes with
100% success (all dependencies installed, imports verified, 169M deployment
ready), but the Python runtime detection fails at the final deployment step.

## **Environment Details**

- **Project**: readwise-vector-db (FastAPI application)
- **Python Version**: 3.12.2 (confirmed working in build)
- **Poetry Version**: 2.1.3
- **Vercel Runtime**: @vercel/python@4.1.0
- **Build Status**: ✅ 100% successful (55 production dependencies installed)
- **Deployment Status**: ❌ Fails at runtime detection

## **Error Details**

```text
[22:39:45.915] Error: Unable to find any supported Python versions.
[22:39:45.916] Learn More: http://vercel.link/python-version
```

**Critical**: This error occurs **after** the build summary shows:

```text
📋 Build Summary:
- Environment: production
- Python: Python 3.12.2
- Poetry: Poetry (version 2.1.3)
- Cache dir: /vercel/.cache/pip
- Is Vercel: true
```

## **What We've Tried (Comprehensive)**

### 1. **Python Version Specification**

- ✅ Created `Pipfile` with `python_version = "3.12"`
- ✅ Created `.python-version` file with `3.12`
- ✅ Verified both files are in project root and committed

### 2. **Vercel Configuration Fixes**

- ✅ Fixed legacy `routes` → `rewrites` format conflict
- ✅ Removed invalid schema fields (`_comment`)
- ✅ Specified correct runtime: `@vercel/python@4.1.0`
- ✅ Added proper function configuration (memory: 1024, maxDuration: 300)

### 3. **ASGI Entry Point Optimization**

- ✅ Cleaned up `api/index.py` to have single `app` variable
- ✅ Removed duplicate app definitions that could confuse runtime detection
- ✅ Verified clean ASGI application structure per Vercel docs

### 4. **Poetry Lock File Synchronization**

- ✅ Regenerated `poetry.lock` with `poetry lock --no-update`
- ✅ Ensured `pyproject.toml` and lock file are synchronized

### 5. **Cache Invalidation Attempts**

- ✅ Modified build command: `./vercel_build.sh --force-fresh`
- ✅ Updated build script to handle cache-busting arguments
- ✅ Forced fresh builds without cached artifacts

### 6. **Environment Variable Management**

- ✅ Removed problematic secret references that caused validation errors
- ✅ Simplified configuration to minimal working setup

## **Build Log Evidence**

**Build Phase (100% Successful)**:

```bash
🔄 Force fresh build requested (cache busting)
🚀 Starting Vercel build process...
📚 Poetry not found, installing...
✅ Poetry confirmed available: Poetry (version 2.1.3)
📥 Installing production dependencies...
# ... 55 packages installed successfully ...
🔍 Verifying application imports...
✅ API module imports successfully
✅ Database module imports successfully
✅ FastAPI app creation works
🎉 All critical imports verified
📊 Total deployment size: 169M
🎉 Vercel build completed successfully!

📋 Build Summary:
- Environment: production
- Python: Python 3.12.2  # ← PYTHON DETECTED CORRECTLY
- Poetry: Poetry (version 2.1.3)
- Cache dir: /vercel/.cache/pip
- Is Vercel: true
```

**Runtime Detection Phase (Failure)**:

```text
Error: Unable to find any supported Python versions.
Learn More: http://vercel.link/python-version
```

## **Current Configuration Files**

### `vercel.json`

```json
{
  "version": 2,
  "buildCommand": "./vercel_build.sh --force-fresh",
  "functions": {
    "api/index.py": {
      "runtime": "@vercel/python@4.1.0",
      "maxDuration": 300,
      "memory": 1024
    }
  },
  "rewrites": [
    { "source": "/health", "destination": "api/index.py" },
    { "source": "/search", "destination": "api/index.py" },
    { "source": "/mcp/stream", "destination": "api/index.py" },
    { "source": "/metrics", "destination": "api/index.py" },
    { "source": "/(.*)", "destination": "api/index.py" }
  ],
  "env": {
    "DEPLOY_TARGET": "vercel",
    "DB_BACKEND": "supabase"
  },
  "regions": ["iad1"],
  "trailingSlash": false
}
```

### `Pipfile`

```ini
[[source]]
url = "https://pypi.org/simple"
verify_ssl = true
name = "pypi"

[packages]

[dev-packages]

[requires]
python_version = "3.12"
```

### `.python-version`

```text
3.12
```

### `api/index.py` (Clean ASGI Entry Point)

```python
"""Vercel ASGI entry point for readwise-vector-db API."""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables early for Vercel
if os.path.exists(".env"):
    from dotenv import load_dotenv
    load_dotenv()

from readwise_vector_db.api.main import create_app

# Create the FastAPI app instance - single clean ASGI application
app = create_app()
```

## **Hypothesis: Vercel Platform Bug**

Given that:

1. **Build phase detects Python 3.12.2 correctly**
2. **All Python version specification methods are in place**
3. **Build completes with 100% success**
4. **Runtime detection fails after successful build**
5. **Multiple cache invalidation attempts show same pattern**

This appears to be a **Vercel platform issue** where the runtime detection
logic is disconnected from or ignoring the build-time Python detection.

## **Potential Solutions to Investigate**

### 1. **Vercel Support Contact**

- This may require Vercel platform team investigation
- Build succeeds but runtime detection fails suggests platform bug

### 2. **Alternative Function Configuration**

```json
{
  "functions": {
    "api/index.py": {
      "runtime": "python3.12",
      "maxDuration": 300,
      "memory": 1024
    }
  }
}
```

### 3. **Runtime Environment Variables**

```json
{
  "env": {
    "PYTHON_VERSION": "3.12",
    "DEPLOY_TARGET": "vercel",
    "DB_BACKEND": "supabase"
  }
}
```

### 4. **Alternative Runtime Specification**

```json
{
  "functions": {
    "api/index.py": {
      "runtime": "@vercel/python@4.0.0",
      "maxDuration": 300,
      "memory": 1024
    }
  }
}
```

## **Repository Information**

- **Repository**: leonardsellem/readwise-vector-db
- **Latest Commit**: `f8c5051` (contains all fixes attempted)
- **Branch**: master
- **Test Coverage**: 96.4% (162/168 tests passing)

## **Request for Help**

This issue has persisted through multiple comprehensive configuration attempts.
The disconnect between successful build-time Python detection and failed
runtime detection suggests a potential Vercel platform issue that may require:

1. **Vercel platform team investigation**
2. **Alternative runtime configuration approaches**
3. **Workarounds for this specific deployment pattern**

Any insights into this runtime detection vs. build-time detection discrepancy
would be greatly appreciated.
