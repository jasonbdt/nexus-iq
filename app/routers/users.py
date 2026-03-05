"""User management, profile, and account-linking endpoints."""

from typing import Annotated
from datetime import datetime, timezone, timedelta

from fastapi.exceptions import HTTPException
from fastapi.params import Depends
from fastapi.param_functions import Query
from fastapi.routing import APIRouter
from fastapi.responses import JSONResponse

from sqlalchemy import or_
from sqlmodel import select

from ..internal.auth import (
    oauth2_scheme,
    get_current_active_user,
    require_role,
    verify_password,
    get_password_hash,
)
from ..internal.db import SessionDep
from ..internal.models import (
    User,
    UserResponse,
    UserRole,
    UserUpdateRequest,
    LinkSummonerRequest,
)
from ..internal.controllers import summoners as SummonersController
from ..internal.controllers import users as UsersController
from ..internal.logging import get_logger
from ..internal.models import UserSummonerLink
from ..internal.riot_api import RiotAPIDep

LINK_COOLDOWN_DAYS = 30

router = APIRouter(tags=["Users"])
logger = get_logger(__name__)


@router.get("/users")
def get_all_users(
    session: SessionDep,
    _current_user: Annotated[
        User, Depends(require_role(UserRole.administrator, UserRole.moderator))
    ],
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100,
):
    """List users (admin/moderator only)."""
    users = session.exec(select(User).offset(offset).limit(limit)).all()
    return {
        "status": 200,
        "message": "Success",
        "users": [UsersController.user_to_response(u, session) for u in users],
    }


@router.get("/users/me", response_model=UserResponse)
def get_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: SessionDep,
):
    """Return the current user's profile."""
    return UsersController.user_to_response(current_user, session)


@router.patch("/users/me", response_model=UserResponse)
def update_me(
    payload: UserUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: SessionDep,
):
    """Update the current user's profile (email, password, language)."""
    fields = (payload.emailAddress, payload.new_password, payload.language)
    if not any(f is not None for f in fields):
        raise HTTPException(status_code=400, detail="No fields to update")

    if payload.current_password and not verify_password(
        payload.current_password, current_user.password
    ):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if payload.emailAddress is not None:
        if not payload.current_password:
            raise HTTPException(
                status_code=400, detail="Current password required to change email"
            )
        stmt = select(User).where(User.emailAddress == payload.emailAddress)
        existing = session.exec(stmt).first()
        if existing and existing.id != current_user.id:
            raise HTTPException(status_code=400, detail="Email already in use")
        current_user.emailAddress = payload.emailAddress

    if payload.new_password is not None:
        if not payload.current_password:
            raise HTTPException(
                status_code=400, detail="Current password required to change password"
            )
        current_user.password = get_password_hash(payload.new_password)

    if payload.language is not None:
        current_user.language = payload.language[:10]

    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return UsersController.user_to_response(current_user, session)


@router.post("/users/me/link-summoner", response_model=UserResponse)
async def link_summoner(
    payload: LinkSummonerRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: SessionDep,
    riot_api: RiotAPIDep,
):
    """Link a summoner account to the current user (primary or additional slot)."""
    slot = payload.link_slot if payload.link_slot in (0, 1, 2) else 0

    # Slot 0 = primary; slot 1-2 = additional (Premium only)
    if slot in (1, 2):
        role = UsersController.get_user_role(current_user, session)
        allowed = (UserRole.paid_member, UserRole.moderator, UserRole.administrator)
        if role not in allowed:
            return JSONResponse(
                content={"detail": "Premium role required to add additional player accounts."},
                status_code=403,
            )
        existing_additional = UsersController.get_user_summoner_links(current_user, session)
        additional_count = sum(1 for l in existing_additional if l.link_slot in (1, 2))
        if additional_count >= UsersController.MAX_ADDITIONAL_LINKS:
            return JSONResponse(
                content={
                    "detail": f"Maximum {UsersController.MAX_ADDITIONAL_LINKS} "
                    "additional accounts allowed."
                },
                status_code=400,
            )

    now = datetime.now(timezone.utc)
    existing_link = UsersController.get_user_summoner_link(current_user, session, link_slot=slot)

    if slot == 0 and existing_link:
        # Primary: 30-day cooldown on change
        elapsed = now - existing_link.linked_at
        if elapsed < timedelta(days=LINK_COOLDOWN_DAYS):
            days_left = (timedelta(days=LINK_COOLDOWN_DAYS) - elapsed).days
            return JSONResponse(
                content={"detail": f"You can change your linked account in {days_left} days"},
                status_code=400,
            )

    summoner = await SummonersController.find_or_create(
        payload.gameName.strip(), payload.tagLine.strip(), session, riot_api
    )
    if not summoner:
        return JSONResponse(content={"detail": "Summoner not found"}, status_code=404)

    if existing_link:
        existing_link.summoner_puuid = summoner.puuid
        existing_link.linked_at = now
        session.add(existing_link)
    else:
        link = UserSummonerLink(
            user_id=current_user.id,
            link_slot=slot,
            summoner_puuid=summoner.puuid,
        )
        session.add(link)

    if slot == 0:
        current_user.avatarName = f"{summoner.summoner_name}#{summoner.tag_line}"
        session.add(current_user)

    session.commit()
    session.refresh(current_user)
    logger.info(
        "User[%s] linked summoner %s (slot %s)",
        current_user.id, summoner.puuid, slot,
    )
    return UsersController.user_to_response(current_user, session)


@router.delete("/users/me/summoner-links/{link_id}", response_model=UserResponse)
def remove_summoner_link(
    link_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: SessionDep,
):
    """Remove an additional player account link (Premium only, slot 1 or 2)."""
    stmt = select(UserSummonerLink).where(
        UserSummonerLink.id == link_id,
        UserSummonerLink.user_id == current_user.id,
        or_(UserSummonerLink.link_slot == 1, UserSummonerLink.link_slot == 2),
    )
    link = session.exec(stmt).first()
    if not link:
        raise HTTPException(status_code=404, detail="Additional account link not found")

    role = UsersController.get_user_role(current_user, session)
    allowed = (UserRole.paid_member, UserRole.moderator, UserRole.administrator)
    if role not in allowed:
        raise HTTPException(
            status_code=403,
            detail="Premium role required to manage additional accounts",
        )

    session.delete(link)
    session.commit()
    session.refresh(current_user)
    logger.info("User[%s] removed summoner link %s", current_user.id, link_id)
    return UsersController.user_to_response(current_user, session)


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    _token: Annotated[str, Depends(oauth2_scheme)],
    user_id: int,
    _current_user: Annotated[User, Depends(get_current_active_user)],
    session: SessionDep
):
    """Get a user by ID (authenticated)."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UsersController.user_to_response(user, session)


@router.delete("/users/{user_id}")
def delete_user(
    _token: Annotated[str, Depends(oauth2_scheme)],
    user_id: int,
    _current_user: Annotated[User, Depends(get_current_active_user)],
    session: SessionDep
):
    """Delete a user by ID (admin)."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    session.delete(user)
    session.commit()

    return {
        "status": 200,
        "message": "Success"
    }
