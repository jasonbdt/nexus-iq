"""FastAPI application factory, lifespan, middleware, and top-level routes."""
import mimetypes
import os
import logging
import tempfile
from pathlib import Path
from PIL import Image

from contextlib import asynccontextmanager

import aiohttp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .internal.db import create_db_and_tables
from .internal.logging import configure_logging
from .dependencies import APP_ENV
from .internal.redis import close_redis, init_redis, RedisDep
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
    await init_redis()
    await ensure_collection()

    configure_logging(log_level)
    create_db_and_tables()

    try:
        yield
    finally:
        await close_redis()
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


@app.get("/health/redis")
def redis_health(redis: RedisDep):
    """Health check for Redis Service."""
    return {"status": "ok" if redis.ping() else "not ok"}


BASE_CDN_DIR = Path("/usr/src/ddragon/cdn").resolve()
def resolve_safe_path(file_path: str) -> Path:
    full_path = (BASE_CDN_DIR / file_path).resolve()

    if not full_path.is_relative_to(BASE_CDN_DIR):
        raise HTTPException(status_code=403, detail="Invalid path")

    return full_path


def is_champion_image(file_path: Path) -> bool:
    relative_path = file_path.relative_to(BASE_CDN_DIR)
    parts = [part.lower() for part in relative_path.parts]

    return len(parts) >= 4 and parts[1] == "img" and parts[2] == "champion"


def is_already_cropped(file_path: Path) -> bool:
    return file_path.stem.endswith("_cropped")


def get_source_png_path(requested_path: Path) -> Path:
    stem = requested_path.stem
    if stem.endswith("_cropped"):
        stem = stem.removesuffix("_cropped")

    return requested_path.with_name(f"{stem}.png")


def crop_image(img: Image.Image) -> Image.Image:
    width, height = img.size

    crop_x = max(1, round(width * 0.06))
    crop_y = max(1, round(height * 0.06))

    left = crop_x
    top = crop_y
    right = width - crop_x
    bottom = height - crop_y

    if left >= right or top >= bottom:
        raise ValueError("Invalid cropping area")

    cropped = img.crop((left, top, right, bottom))

    return cropped.resize(
        (width, height),
        Image.Resampling.LANCZOS
    )


def convert_png_to_webp(source: Path, target: Path, crop: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as img:
        result = crop_image(img) if crop else img.copy()

        if result.mode not in ("RGB", "RGBA"):
            result = result.convert("RGBA")

        with tempfile.NamedTemporaryFile(
            suffix=".webp",
            dir=str(target.parent),
            delete=False
        ) as tmp_file:
            temp_path = Path(tmp_file.name)

        try:
            result.save(temp_path, format="WEBP", quality=90, method=6)
            temp_path.replace(target)
        finally:
            temp_path.unlink(missing_ok=True)


def guess_media_type(file_path: Path) -> str:
    media_type, _ = mimetypes.guess_type(str(file_path))
    return media_type or "application/octet-stream"


@app.get("/cdn/{file_path:path}")
def serve_ddragon(file_path: str):
    """Serve DDragon static files with explicit route to avoid path resolution issues."""
    if not _ddragon_cdn.exists():
        raise HTTPException(status_code=404, detail="DDragon cache not configured")

    requested_path = resolve_safe_path(file_path)
    requested_suffix = requested_path.suffix.lower()

    if requested_suffix == ".png":
        raise HTTPException(status_code=404, detail="File not found")

    if requested_suffix == ".webp" and requested_path.is_file():
        return FileResponse(
            path=requested_path,
            media_type="image/webp"
        )

    if requested_suffix == ".webp":
        source_path = get_source_png_path(requested_path)
        if not source_path.is_file():
            raise HTTPException(status_code=404, detail="Source PNG file not found")

        should_crop = is_champion_image(source_path)
        convert_png_to_webp(
            source=source_path,
            target=requested_path,
            crop=should_crop
        )

        return FileResponse(
            path=requested_path,
            media_type="image/webp"
        )

    raise HTTPException(status_code=404, detail="File not found")
