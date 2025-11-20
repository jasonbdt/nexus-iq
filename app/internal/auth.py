from typing import Annotated
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.params import Depends
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from pydantic import BaseModel

from sqlmodel import select
from sqlalchemy.exc import NoResultFound

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.internal.db import SessionDep
from app.internal.models import User
from ..dependencies import JWT_SECRET, JWT_ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
password_hash = PasswordHash.recommended()


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    emailAddress: str | None


def verify_password(plain_password: str, hashed_password: str):
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str):
    return password_hash.hash(password)


def authenticate_user(emailAddress: str, password: str, session: SessionDep):
    try:
        user = session.exec(select(User).where(User.emailAddress == emailAddress)).one()

        if not user:
            return False
        if not verify_password(password, user.password):
            return False
        return user
    except (NoResultFound, UnknownHashError):
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

    return encoded_jwt


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: SessionDep
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        emailAddress = payload.get("sub")
        if emailAddress is None:
            raise credentials_exception

        token_data = TokenData(emailAddress=emailAddress)
    except InvalidTokenError:
        raise credentials_exception

    user = session.exec(
        select(User).where(User.emailAddress == token_data.emailAddress)
    ).one()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive User")

    return current_user
