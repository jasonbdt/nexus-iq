"""Pytest configuration and shared fixtures."""

# Set env vars before any app imports (dependencies.py reads them at import time)
import os

os.environ.setdefault("JWT_EXPIRES_IN", "60")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_USER", "test")
os.environ.setdefault("DATABASE_NAME", "test")
os.environ.setdefault("DATABASE_PASSWORD", "test")
os.environ.setdefault("RIOT_API_KEY", "test-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("APP_KEY", "12345678-1234-5678-1234-567812345678")
os.environ.setdefault("QDRANT_HOST", "localhost")
os.environ.setdefault("QDRANT_PORT", "6333")
os.environ.setdefault("QDRANT_COLLECTION_NAME", "test_patches")
os.environ.setdefault("EMBEDDING_DIMENSION", "1536")

import pytest
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient


@pytest.fixture
def app_no_lifespan():
    """Create app with no-op lifespan so tests don't need DB/Qdrant/aiohttp."""
    from app.main import app

    @asynccontextmanager
    async def _noop_lifespan(app):
        yield

    app.router.lifespan_context = _noop_lifespan
    return app


@pytest.fixture
def client(app_no_lifespan):
    """Test client for FastAPI app (no real lifespan)."""
    return TestClient(app_no_lifespan)
