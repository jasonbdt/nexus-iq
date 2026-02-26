from typing import Optional

from sqlmodel import select

from ..db import SessionDep
from ..models import (
    LinkedSummonerInfo,
    Summoner,
    User,
    UserResponse,
    UserRole,
    UserRoleAssignment,
    UserSummonerLink,
)

MAX_ADDITIONAL_LINKS = 2  # Premium users can add up to 2 extra accounts


def _summoner_link_to_info(session: SessionDep, link: UserSummonerLink) -> LinkedSummonerInfo | None:
    summoner = session.exec(
        select(Summoner).where(Summoner.puuid == link.summoner_puuid)
    ).first()
    if not summoner:
        return None
    return LinkedSummonerInfo(
        puuid=summoner.puuid,
        riot_id=f"{summoner.summoner_name}#{summoner.tag_line}",
        profile_icon=summoner.profile_icon,
        region=summoner.region,
        summoner_level=summoner.summoner_level,
        link_slot=link.link_slot,
        link_id=link.id,
        linked_at=link.linked_at,
    )


def user_to_response(user: User, session: SessionDep) -> UserResponse:
    """Build UserResponse from a User, resolving linked summoners and role from junction tables."""
    role = get_user_role(user, session)
    links = get_user_summoner_links(user, session)

    primary_link = next((l for l in links if l.link_slot == 0), None)
    additional_links = [l for l in links if l.link_slot in (1, 2)]

    linked_summoner = _summoner_link_to_info(session, primary_link) if primary_link else None
    summoner_linked_at = primary_link.linked_at if primary_link else None
    additional_summoners = [
        info for link in additional_links
        if (info := _summoner_link_to_info(session, link))
    ]

    return UserResponse(
        avatarName=user.avatarName,
        emailAddress=user.emailAddress,
        is_active=user.is_active,
        role=role,
        created_at=user.created_at,
        updated_at=user.updated_at,
        linked_summoner=linked_summoner,
        summoner_linked_at=summoner_linked_at,
        additional_summoners=additional_summoners,
        language=getattr(user, "language", "en") or "en",
        subscription_tier=getattr(user, "subscription_tier", "free") or "free",
    )


def get_user_role(user: User, session: SessionDep) -> UserRole:
    """Get the current role for a user from the user_role_assignments table."""
    assignment = session.exec(
        select(UserRoleAssignment).where(UserRoleAssignment.user_id == user.id)
    ).first()
    return assignment.role if assignment else UserRole.member


def get_or_create_role_assignment(user: User, session: SessionDep) -> UserRoleAssignment:
    """Get or create the role assignment for a user. Returns the assignment with default role if none exists."""
    assignment = session.exec(
        select(UserRoleAssignment).where(UserRoleAssignment.user_id == user.id)
    ).first()
    if assignment:
        return assignment
    assignment = UserRoleAssignment(user_id=user.id, role=UserRole.member)
    session.add(assignment)
    session.commit()
    session.refresh(assignment)
    return assignment


def get_user_summoner_links(user: User, session: SessionDep) -> list[UserSummonerLink]:
    """Get all summoner links for a user, ordered by link_slot."""
    links = session.exec(
        select(UserSummonerLink).where(UserSummonerLink.user_id == user.id).order_by(UserSummonerLink.link_slot)
    ).all()
    return list(links)


def get_user_summoner_link(user: User, session: SessionDep, link_slot: int = 0) -> Optional[UserSummonerLink]:
    """Get the summoner link for a user at a given slot (0=primary, 1-2=additional)."""
    return session.exec(
        select(UserSummonerLink).where(
            UserSummonerLink.user_id == user.id,
            UserSummonerLink.link_slot == link_slot,
        )
    ).first()
