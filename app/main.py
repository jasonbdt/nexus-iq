from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Query
from sqlmodel import select

from app.internal.db import create_db_and_tables, SessionDep
from app.internal.models import User


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
def index():
    return {
        "status": 200,
        "message": "It work's!"
    }

@app.get("/users")
def get_all_users(
    session: SessionDep,
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100
):
    users = session.exec(select(User).offset(offset).limit(limit)).all()
    return {
        "status": 200,
        "message": "Success",
        "users": users
    }
