from contextlib import asynccontextmanager

from fastapi import FastAPI

from .internal.db import create_db_and_tables
from .routers import auth, users


@asynccontextmanager
async def lifespan(app: FastAPI):
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
