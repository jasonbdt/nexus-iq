"""aiohttp session lifecycle management for the application."""

from __future__ import annotations

import asyncio
from typing import Optional

from aiohttp import ClientSession

_lock = asyncio.Lock()
_STATE: list[Optional[ClientSession]] = [None]


async def init_session(**kwargs) -> ClientSession:
    """Create and store the shared aiohttp session if not already open."""
    async with _lock:
        if _STATE[0] is None or _STATE[0].closed:
            _STATE[0] = ClientSession(**kwargs)
        return _STATE[0]


def get_session() -> ClientSession:
    """Return the active shared aiohttp session, raising if not initialised."""
    if _STATE[0] is None or _STATE[0].closed:
        raise RuntimeError("HTTP session not initialized. FastAPI lifespan didn't run?")
    return _STATE[0]


async def close_session() -> None:
    """Close and discard the shared aiohttp session."""
    async with _lock:
        if _STATE[0] is not None and not _STATE[0].closed:
            await _STATE[0].close()
        _STATE[0] = None
