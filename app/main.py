from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.params import Depends
from sqlmodel import select

from app.internal.db import create_db_and_tables, SessionDep
from app.internal.models import User, UserResponse
from app.internal.auth import oauth2_scheme, get_current_active_user

from .routers import auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(auth.router)

@app.get("/")
def index():
    return {
        "status": 200,
        "message": "It work's!"
    }


# TODO: Add Role-Based Authorization Check
@app.get("/users")
def get_all_users(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100
):
    users = session.exec(select(User).offset(offset).limit(limit)).all()
    return {
        "status": 200,
        "message": "Success",
        "users": users
    }


@app.get("/users/me", response_model=UserResponse)
async def get_me(current_user: Annotated[User, Depends(get_current_active_user)]):
    return current_user


@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    user_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: SessionDep
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@app.delete("/users/{user_id}")
def delete_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    user_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: SessionDep
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    session.delete(user)
    session.commit()

    return {
        "status": 200,
        "message": "Success"
    }
