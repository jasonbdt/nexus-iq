"""Authentication utilities: JWT handling, password hashing, and user resolution."""

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

from ..dependencies import JWT_SECRET, JWT_ALGORITHM
from .db import SessionDep
from .models import User, UserRole
from .controllers import users as UsersController

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)
password_hash = PasswordHash.recommended()


class Token(BaseModel):  # pylint: disable=too-few-public-methods
    """OAuth2 access token response model."""

    access_token: str
    token_type: str


class TokenData(BaseModel):  # pylint: disable=too-few-public-methods
    """Decoded JWT payload data (subject email and role)."""

    email_address: str | None
    role: UserRole | None = None


def verify_password(plain_password: str, hashed_password: str):
    """Verify a plain-text password against a hashed password."""
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str):
    """Hash a plain-text password for storage."""
    return password_hash.hash(password)


def authenticate_user(email_address: str, password: str, session: SessionDep):
    """Authenticate a user by email and password. Returns User or False."""
    try:
        user = session.exec(select(User).where(User.emailAddress == email_address)).one()

        if not user:
            return False
        if not verify_password(password, user.password):
            return False
        return user
    except (NoResultFound, UnknownHashError):
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Create a JWT access token from the given payload."""
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
    """Resolve the current user from the Bearer token. Raises 401 if invalid."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email_address = payload.get("sub")
        if email_address is None:
            raise credentials_exception

        token_data = TokenData(
            email_address=email_address,
            role=payload.get("role"),
        )
    except InvalidTokenError as exc:
        raise credentials_exception from exc

    user = session.exec(
        select(User).where(User.emailAddress == token_data.email_address)
    ).one()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
):
    """Ensure the current user is active. Raises 400 if inactive."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive User")

    return current_user


async def get_current_user_optional(
    token: Annotated[str | None, Depends(oauth2_scheme_optional)],
    session: SessionDep,
):
    """Returns the current user if authenticated, else None. Does not raise on missing/invalid token."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email_address = payload.get("sub")
        if not email_address:
            return None
        user = session.exec(
            select(User).where(User.emailAddress == email_address)
        ).first()
        return user if user and user.is_active else None
    except InvalidTokenError:
        return None


def require_role(*roles: UserRole):
    """Dependency factory that restricts access to users with one of the given roles.

    Usage::

        @router.get("/admin-only")
        def admin_endpoint(
            user: Annotated[User, Depends(require_role(UserRole.administrator))],
        ):
            ...
    """
    async def _check(
        current_user: Annotated[User, Depends(get_current_active_user)],
        session: SessionDep,
    ):
        user_role = UsersController.get_user_role(current_user, session)
        if user_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _check
