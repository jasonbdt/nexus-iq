import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .internal.db import create_db_and_tables
from .routers import auth, users
from .internal.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_level = logging.DEBUG if APP_ENV == "dev" else logging.INFO
    configure_logging(log_level)
    create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(auth.router)
app.include_router(users.router)

@app.get("/")
def index():
    return {
        "status": 200,
        "message": "It work's!"
    }
