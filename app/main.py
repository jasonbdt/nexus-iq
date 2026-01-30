import os
import logging
from contextlib import asynccontextmanager

import aiohttp
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .internal.db import create_db_and_tables
from .internal.logging import configure_logging
from .dependencies import APP_ENV
from .internal.session import init_session, close_session
from .routers import auth, matches, summoners, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_level = logging.DEBUG if APP_ENV == "dev" else logging.INFO

    timeout = aiohttp.ClientTimeout(total=10)
    headers = {"X-Riot-Token": os.getenv("RIOT_API_KEY")}
    connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)

    await init_session(timeout=timeout, connector=connector, headers=headers)

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
app.include_router(matches.router)
app.include_router(users.router)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def index():
    return {
        "status": 200,
        "message": "It work's!"
    }
