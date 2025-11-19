from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Annotated

from fastapi import FastAPI, HTTPException, status, Query
from fastapi.params import Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.internal.db import create_db_and_tables, SessionDep
from app.internal.models import User, UserResponse, UserSignUpRequest
from app.internal.auth import JWT_TOKEN_EXPIRE_MINUTES, Token, \
    authenticate_user, get_password_hash, oauth2_scheme, create_access_token, \
    get_current_active_user


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


# TODO: Change to sign_up
@app.post("/users/", response_model=UserResponse)
def create_user(user_in: UserSignUpRequest, session: SessionDep):
    if user_in.password != user_in.password_confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    user_in.password = get_password_hash(user_in.password)
    new_user = User(**user_in.model_dump())

    try:
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="User already exists")

    return new_user


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


@app.post("/login")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep
) -> Token:
    user = authenticate_user(form_data.username, form_data.password, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token_expires = timedelta(minutes=JWT_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.emailAddress}, expires_delta=access_token_expires
    )

    return Token(access_token=access_token, token_type="bearer")
