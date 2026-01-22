from __future__ import annotations

import asyncio
from typing import Optional

from aiohttp import ClientSession

_lock = asyncio.Lock()
_session: Optional[ClientSession] = None


async def init_session(**kwargs) -> ClientSession:
    global _session
    async with _lock:
        if _session is None or _session.closed:
            _session = ClientSession(**kwargs)

        return _session


def get_session() -> ClientSession:
    if _session is None or _session.closed:
        raise RuntimeError("HTTP session not initialized. FastAPI lifespan didn't run?")

    return _session


async def close_session() -> None:
    global _session
    async with _lock:
        if _session is not None and not _session.closed:
            await _session.close()
        _session = None
