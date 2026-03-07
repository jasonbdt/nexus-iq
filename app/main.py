"""FastAPI application factory, lifespan, middleware, and top-level routes."""

import os
import logging
from pathlib import Path

from contextlib import asynccontextmanager

import aiohttp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .internal.db import create_db_and_tables
from .internal.logging import configure_logging
from .dependencies import APP_ENV
from .internal.services.vector_store import ensure_collection
from .internal.session import init_session, close_session
from .routers import auth, coach, matches, rag, summoners, users


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialise and tear down application resources around the request lifecycle."""
    log_level = logging.DEBUG if APP_ENV == "dev" else logging.INFO

    timeout = aiohttp.ClientTimeout(total=10)
    headers = {"X-Riot-Token": os.getenv("RIOT_API_KEY")}
    connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)

    await init_session(timeout=timeout, connector=connector, headers=headers)
    await ensure_collection()

    configure_logging(log_level)
    create_db_and_tables()

    try:
        yield
    finally:
        await close_session()

app = FastAPI(
    root_path="/api/v1",
    lifespan=lifespan,
    redoc_url=None
)

app.include_router(auth.router)
app.include_router(summoners.router)
app.include_router(rag.router)
app.include_router(coach.router)
app.include_router(matches.router)
app.include_router(users.router)

# DDragon static assets (profile icons, champion images, etc.)
# Served at /cdn/... to match DDragon path structure (no /ddragon prefix)
# Use DDragon_CACHE_DIR env var to override (e.g. /usr/src/ddragon/cdn in Docker)
_ddragon_cdn = Path(
    os.getenv("DDragon_CACHE_DIR", "")
    or str(Path(__file__).resolve().parent.parent / "ddragon" / "cdn")
)
_ddragon_cdn = Path(_ddragon_cdn)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def index():
    """Return a simple health-check response."""
    return {
        "status": 200,
        "message": "It work's!"
    }


@app.get("/cdn/{file_path:path}")
def serve_ddragon(file_path: str):
    """Serve DDragon static files with explicit route to avoid path resolution issues."""
    if not _ddragon_cdn.exists():
        raise HTTPException(status_code=404, detail="DDragon cache not configured")
    # Prevent path traversal
    full_path = (_ddragon_cdn / file_path).resolve()
    if not str(full_path).startswith(str(_ddragon_cdn.resolve())):
        raise HTTPException(status_code=403, detail="Invalid path")
    if not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(full_path)
