"""User-facing account operations and their transaction boundaries."""
from dataclasses import asdict, dataclass

from app.domain.errors import Forbidden, InvalidOperation, NotFound, Unauthenticated
from app.domain.models import User, UserSummonerLink, utc_now
from app.domain.policies import PREMIUM_ROLES, check_link
from .ports import Riot, Security, UnitOfWorkFactory


def user_response(user: User, summoners) -> dict:
    """Build a public projection without leaking credentials or persistence objects."""
    linked = []
    for link in sorted(user.summoner_links, key=lambda item: item.link_slot):
        summoner = summoners.get(link.summoner_puuid)
        if summoner:
            linked.append({
                'puuid': summoner.puuid, 'riot_id': summoner.riot_id,
                'profile_icon': summoner.profile_icon, 'region': summoner.region,
                'summoner_level': summoner.summoner_level, 'link_slot': link.link_slot,
                'link_id': link.id, 'linked_at': link.linked_at,
            })
    primary = next((link for link in user.summoner_links if link.link_slot == 0), None)
    return {
        **{key: value for key, value in asdict(user).items()
           if key not in ('id', 'password', 'summoner_links')},
        'language': user.language or 'en', 'subscription_tier': user.subscription_tier or 'free',
        'linked_summoner': next((info for info in linked if info['link_slot'] == 0), None),
        'summoner_linked_at': primary.linked_at if primary else None,
        'additional_summoners': [info for info in linked if info['link_slot'] in (1, 2)],
    }


@dataclass
class Accounts:
    """Use cases shared by HTTP entrypoints and other application clients."""

    uow: UnitOfWorkFactory
    riot: Riot
    security: Security

    async def register(self, payload: dict) -> dict:
        """Register all required associations atomically after resolving Riot data."""
        if payload['password'] != payload['password_confirm']:
            raise InvalidOperation('Passwords do not match')
        if not payload['gameName'] or not payload['tagLine']:
            raise InvalidOperation('Player account (game name and tag) is required to register.')
        name, tag = payload['gameName'].strip(), payload['tagLine'].strip()
        with self.uow() as work:
            if work.users.by_email(payload['emailAddress']):
                raise InvalidOperation('User already exists')
            profile = work.summoners.by_name(name, tag)
        profile = profile or await self.riot.profile(name, tag)
        if profile is None:
            raise NotFound('Player account not found. Check the name and tag.')
        password = self.security.hash_password(payload['password'])
        with self.uow() as work:
            summoner = work.summoners.get(profile.puuid) or work.summoners.save(profile)
            user = User(avatarName=summoner.riot_id, emailAddress=payload['emailAddress'],
                        password=password)
            user.summoner_links.append(UserSummonerLink(
                user_id=None, link_slot=0, summoner_puuid=summoner.puuid,
            ))
            user = work.users.save(user)
            result = user_response(user, work.summoners)
            work.commit()
            return result

    def login(self, email: str, password: str) -> dict:
        """Preserve JWT subject, role and Bearer token shape."""
        with self.uow() as work:
            user = work.users.by_email(email)
        if user is None or not self.security.verify_password(password, user.password):
            raise Unauthenticated('Incorrect username or password')
        return {'access_token': self.security.token(user.emailAddress, user.role.value),
                'token_type': 'bearer'}

    def authenticate(self, token: str | None, optional: bool = False) -> User | None:
        """Resolve current persisted permissions; optional lookup also requires activity."""
        subject = self.security.subject(token) if token else None
        with self.uow() as work:
            user = work.users.by_email(subject) if subject else None
        if optional:
            return user if user and user.is_active else None
        if user is None:
            raise Unauthenticated('Could not validate credentials')
        return user

    def get(self, identity: int) -> dict:
        """Read the same public user projection for self and by-ID routes."""
        with self.uow() as work:
            user = work.users.get(identity)
            if user is None:
                raise NotFound('User not found')
            return user_response(user, work.summoners)

    def list(self, offset: int, limit: int) -> dict:
        """List the existing public projections."""
        with self.uow() as work:
            return {'status': 200, 'message': 'Success', 'users': [
                user_response(user, work.summoners) for user in work.users.list(offset, limit)
            ]}

    def update(self, identity: int, payload: dict) -> dict:
        """Apply existing email, password and language rules atomically."""
        if not any(payload.get(key) is not None
                   for key in ('emailAddress', 'new_password', 'language')):
            raise InvalidOperation('No fields to update')
        with self.uow() as work:
            user = work.users.get(identity)
            current = payload.get('current_password')
            if current and not self.security.verify_password(current, user.password):
                raise InvalidOperation('Current password is incorrect')
            email, password = payload.get('emailAddress'), payload.get('new_password')
            if email is not None:
                if not current:
                    raise InvalidOperation('Current password required to change email')
                existing = work.users.by_email(email)
                if existing and existing.id != identity:
                    raise InvalidOperation('Email already in use')
                user.emailAddress = email
            if password is not None:
                if not current:
                    raise InvalidOperation('Current password required to change password')
                user.password = self.security.hash_password(password)
            if payload.get('language') is not None:
                user.language = payload['language'][:10]
            user.updated_at = utc_now()
            user = work.users.save(user)
            result = user_response(user, work.summoners)
            work.commit()
            return result

    async def link(self, identity: int, payload: dict) -> dict:
        """Resolve externally, then recheck link rules within the write transaction."""
        slot = payload['link_slot'] if payload['link_slot'] in (0, 1, 2) else 0
        name, tag = payload['gameName'].strip(), payload['tagLine'].strip()
        with self.uow() as work:
            check_link(work.users.get(identity), slot, utc_now())
            profile = work.summoners.by_name(name, tag)
        profile = profile or await self.riot.profile(name, tag)
        if profile is None:
            raise NotFound('Summoner not found')
        with self.uow() as work:
            user = work.users.get(identity)
            now = utc_now()
            check_link(user, slot, now)
            summoner = work.summoners.get(profile.puuid) or work.summoners.save(profile)
            link = next((item for item in user.summoner_links if item.link_slot == slot), None)
            if link:
                link.summoner_puuid, link.linked_at = summoner.puuid, now
            else:
                user.summoner_links.append(UserSummonerLink(
                    user_id=identity, link_slot=slot, summoner_puuid=summoner.puuid,
                ))
            if slot == 0:
                user.avatarName = summoner.riot_id
            user = work.users.save(user)
            result = user_response(user, work.summoners)
            work.commit()
            return result

    def unlink(self, identity: int, link_id: int) -> dict:
        """Remove only an additional account owned by this user."""
        with self.uow() as work:
            user = work.users.get(identity)
            link = next((item for item in user.summoner_links
                         if item.id == link_id and item.link_slot in (1, 2)), None)
            if link is None:
                raise NotFound('Additional account link not found')
            if user.role.value not in PREMIUM_ROLES:
                raise Forbidden('Premium role required to manage additional accounts')
            user.summoner_links.remove(link)
            user = work.users.save(user)
            result = user_response(user, work.summoners)
            work.commit()
            return result

    def delete(self, identity: int) -> dict:
        """Delete the requested user; authorization remains an entrypoint concern."""
        with self.uow() as work:
            user = work.users.get(identity)
            if user is None:
                raise NotFound('User not found')
            work.users.delete(user)
            work.commit()
        return {'status': 200, 'message': 'Success'}
