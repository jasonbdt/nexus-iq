from typing import Annotated
from datetime import timedelta

from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.params import Depends
from fastapi.routing import APIRouter
from fastapi.security import OAuth2PasswordRequestForm

from sqlalchemy.exc import IntegrityError

from ..dependencies import JWT_TOKEN_EXPIRE_MINUTES
from ..internal.auth import Token, authenticate_user, create_access_token, \
    get_password_hash
from ..internal.db import SessionDep
from ..internal.logging import get_logger
from ..internal.models import User, UserResponse, UserSignUpRequest

router = APIRouter(
    tags=["Authentication"]
)

logger = get_logger(__name__)


@router.post("/register", response_model=UserResponse)
def register(user_in: UserSignUpRequest, session: SessionDep):
    logger.info(f"Try to register User with email: {user_in.emailAddress}")
    if user_in.password != user_in.password_confirm:
        logger.warning(f"Passwords for User[{user_in.emailAddress}] do not match")
        raise HTTPException(status_code=400, detail="Passwords do not match")

    user_in.password = get_password_hash(user_in.password)
    new_user = User(**user_in.model_dump())

    try:
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
    except IntegrityError:
        logger.warning(f"User[{user_in.emailAddress}] already exists")
        raise HTTPException(status_code=400, detail="User already exists")

    logger.info(f"User[{new_user.id}] created successfully")
    return new_user


@router.post("/login")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep
) -> Token:
    logger.info(f"Try to authenticate User: {form_data.username}")
    user = authenticate_user(form_data.username, form_data.password, session)
    if not user:
        logger.warning("Authentication error: Incorrect username or password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token_expires = timedelta(minutes=JWT_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.emailAddress}, expires_delta=access_token_expires
    )

    logger.info(f"Authentication was successful")
    return Token(access_token=access_token, token_type="bearer")