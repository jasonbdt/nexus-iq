"""Player lookup, cache refresh and atomic match import."""
from dataclasses import asdict, dataclass

from app.domain.errors import NotFound
from app.domain.models import Summoner, utc_now
from app.domain.policies import LANE_ORDER, ttl_expired
from .ports import UnitOfWorkFactory, Riot, Updates, Assets


def reconcile_profile(existing: Summoner, incoming: Summoner) -> Summoner:
    """Keep ranked row identities while replacing the external snapshot."""
    old_queues = {entry.queue_type: entry for entry in existing.leagues}
    incoming_queues = {entry.queue_type: entry for entry in incoming.leagues}
    for name in ('summoner_name', 'tag_line', 'region', 'summoner_level', 'profile_icon'):
        setattr(existing, name, getattr(incoming, name))
    for queue, entry in incoming_queues.items():
        entry.id = old_queues[queue].id if queue in old_queues else None
        entry.summoner_id = existing.id
    existing.leagues = list(incoming_queues.values())
    existing.updated_at = utc_now()
    return existing


@dataclass
class Players:
    """The same operations are used by HTTP and RQ entrypoints."""

    uow: UnitOfWorkFactory
    riot: Riot
    updates: Updates
    assets: Assets
    ttl_minutes: float = 0.5

    async def search(self, game_name: str, tag_line: str) -> dict:
        """Find or create a player, including existing progress metadata."""
        with self.uow() as work:
            summoner = work.summoners.by_name(game_name, tag_line)
        if summoner is None:
            profile = await self.riot.profile(game_name, tag_line)
            if profile is None:
                raise NotFound('Summoner not found')
            with self.uow() as work:
                summoner = work.summoners.get(profile.puuid) or work.summoners.save(profile)
                work.commit()
        remaining, total = await self.updates.progress(summoner.puuid)
        result = asdict(summoner)
        result['riot_id'] = summoner.riot_id
        result['leagues'] = [dict(asdict(entry), total_games=entry.total_games,
                                 win_rate=entry.win_rate) for entry in summoner.leagues]
        return {**result, 'status': 'idle' if not remaining else 'updating',
                'update_progress': (round((1 - remaining / total) * 100, 2) if total else 0.0)
                if remaining else None}

    async def refresh(self, puuid: str) -> None:
        """Refresh profile and queues in one short transaction if the TTL expired."""
        with self.uow() as work:
            current = work.summoners.get(puuid)
        if current is None or not ttl_expired(current, utc_now(), self.ttl_minutes):
            return
        incoming = await self.riot.profile_by_puuid(puuid)
        if incoming is None:
            return
        with self.uow() as work:
            current = work.summoners.get(puuid)
            if current:
                work.summoners.save(reconcile_profile(current, incoming))
                work.commit()

    async def missing_matches(self, puuid: str, count: int) -> tuple[str, list[str]] | None:
        """Resolve external match IDs without holding a database transaction open."""
        with self.uow() as work:
            summoner = work.summoners.get(puuid)
        if summoner is None:
            return None
        match_ids = await self.riot.match_ids(puuid, summoner.region, count)
        with self.uow() as work:
            missing = [match_id for match_id in reversed(match_ids)
                       if work.matches.get(match_id) is None]
        return summoner.region, missing

    async def import_match(self, region: str, match_id: str) -> bool:
        """Persist a whole match and newly resolved participants as one atomic write."""
        with self.uow() as work:
            if work.matches.get(match_id):
                return False
        match = await self.riot.match(match_id, region)
        if match is None:
            return False
        puuids = {participant.summoner_puuid for team in match.teams
                  for participant in team.participants if participant.summoner_puuid != 'BOT'}
        with self.uow() as work:
            missing = [puuid for puuid in puuids if work.summoners.get(puuid) is None]
        profiles = [profile for puuid in missing
                    if (profile := await self.riot.profile_by_puuid(puuid)) is not None]
        with self.uow() as work:
            if work.matches.get(match_id):
                return False
            for profile in profiles:
                if work.summoners.get(profile.puuid) is None:
                    work.summoners.save(profile)
            work.matches.save(match)
            work.commit()
        return True

    def match(self, match_id: str) -> dict:
        """Load a single match with an independent asset-enriched projection."""
        with self.uow() as work:
            match = work.matches.get(match_id)
        if match is None:
            raise NotFound('Match not found')
        return self.assets.enrich(match)

    def recent(self, puuid: str, count: int) -> list[dict]:
        """Keep the existing lane order in recent match responses."""
        with self.uow() as work:
            matches = work.matches.recent(puuid, count)
        for match in matches:
            for team in match.teams:
                team.participants.sort(key=lambda player: LANE_ORDER.get(player.lane, 999))
        return [self.assets.enrich(match) for match in matches]
