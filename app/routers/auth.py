"""Authentication endpoints: registration and login."""

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
from ..internal.models import (
    User,
    UserResponse,
    UserSignUpRequest,
    UserSummonerLink,
)
from ..internal.controllers import users as UsersController
from ..internal.controllers import summoners as SummonersController
from ..internal.riot_api import RiotAPIDep

router = APIRouter(
    tags=["Authentication"]
)

logger = get_logger(__name__)


@router.post("/register", response_model=UserResponse)
async def register(
    user_in: UserSignUpRequest,
    session: SessionDep,
    riot_api: RiotAPIDep,
):
    """Register a new user with email, password, and primary player account."""
    logger.info("Try to register User with email: %s", user_in.emailAddress)
    if user_in.password != user_in.password_confirm:
        logger.warning("Passwords for User[%s] do not match", user_in.emailAddress)
        raise HTTPException(status_code=400, detail="Passwords do not match")

    user_in.password = get_password_hash(user_in.password)

    # Primary player account is required at registration
    if not user_in.gameName or not user_in.tagLine:
        raise HTTPException(
            status_code=400,
            detail="Player account (game name and tag) is required to register.",
        )

    user_data = user_in.model_dump(exclude={"password_confirm", "gameName", "tagLine"})
    if not user_data.get("avatarName"):
        user_data["avatarName"] = user_in.emailAddress.split("@")[0]
    new_user = User(**user_data)

    try:
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
    except IntegrityError as exc:
        logger.warning("User[%s] already exists", user_in.emailAddress)
        raise HTTPException(status_code=400, detail="User already exists") from exc

    # Create default role assignment (2NF)
    UsersController.get_or_create_role_assignment(new_user, session)

    # Link primary player account (required)
    summoner = await SummonersController.find_or_create(
        user_in.gameName.strip(),
        user_in.tagLine.strip(),
        session,
        riot_api,
    )
    if not summoner:
        raise HTTPException(
            status_code=404,
            detail="Player account not found. Check the name and tag.",
        )

    link = UserSummonerLink(
        user_id=new_user.id,
        link_slot=0,
        summoner_puuid=summoner.puuid,
    )
    setattr(new_user, "avatarName", f"{summoner.summoner_name}#{summoner.tag_line}")
    session.add(link)
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    logger.info(
        "User[%s] linked primary summoner %s during registration",
        new_user.id, summoner.puuid,
    )

    logger.info("User[%s] created successfully", new_user.id)
    return UsersController.user_to_response(new_user, session)


@router.post("/login")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep
) -> Token:
    """Authenticate user and return JWT access token."""
    logger.info("Try to authenticate User: %s", form_data.username)
    user = authenticate_user(form_data.username, form_data.password, session)
    if not user:
        logger.warning("Authentication error: Incorrect username or password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_role = UsersController.get_user_role(user, session)
    access_token_expires = timedelta(minutes=JWT_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.emailAddress, "role": user_role.value},
        expires_delta=access_token_expires,
    )

    logger.info("Authentication was successful")
    return Token(access_token=access_token, token_type="bearer")
