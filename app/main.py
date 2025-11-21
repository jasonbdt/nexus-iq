import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .internal.db import create_db_and_tables
from .routers import auth, users
from .internal.logging import configure_logging
from .dependencies import APP_ENV


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_level = logging.DEBUG if APP_ENV == "dev" else logging.INFO
    configure_logging(log_level)
    create_db_and_tables()
    yield

app = FastAPI(
    lifespan=lifespan,
    redoc_url=None
)

app.include_router(auth.router)
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
