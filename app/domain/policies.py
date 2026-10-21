"""Pure account, cache, match and conversation rules."""
from datetime import datetime, timedelta, timezone

from .errors import Forbidden, InvalidOperation
from .models import User, Summoner

PREMIUM_ROLES = frozenset(('paid_member', 'moderator', 'administrator'))
LANE_ORDER = {'TOP': 0, 'JUNGLE': 1, 'MIDDLE': 2, 'BOTTOM': 3, 'UTILITY': 4}


def aware(value: datetime) -> datetime:
    """Interpret timezone-free persisted UTC values consistently."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def check_link(user: User, slot: int, now: datetime) -> None:
    """Enforce the existing premium limits and primary-account cooldown."""
    if slot in (1, 2):
        if user.role.value not in PREMIUM_ROLES:
            raise Forbidden('Premium role required to add additional player accounts.')
        if sum(link.link_slot in (1, 2) for link in user.summoner_links) >= 2:
            raise InvalidOperation('Maximum 2 additional accounts allowed.')
    primary = next((link for link in user.summoner_links if link.link_slot == 0), None)
    if slot == 0 and primary:
        remaining = timedelta(days=30) - (now - aware(primary.linked_at))
        if remaining > timedelta(0):
            raise InvalidOperation(
                f'You can change your linked account in {remaining.days} days'
            )


def ttl_expired(summoner: Summoner, now: datetime, minutes: float) -> bool:
    """Return whether the cached profile needs refreshing."""
    return now - aware(summoner.updated_at) >= timedelta(minutes=minutes)


def initial_title(question: str) -> str:
    """Use the first question as the default conversation title."""
    return question[:80] + ('…' if len(question) > 80 else '')


def resolved_question(question: str, history: list[dict[str, str]]) -> str:
    """Supply the last three turns to keyword and patch extraction."""
    if not history:
        return question
    turns = '\n'.join(
        f"{'User' if message['role'] == 'user' else 'Assistant'}: {message['content']}"
        for message in history[-6:]
    )
    return f'{turns}\nUser: {question}'
