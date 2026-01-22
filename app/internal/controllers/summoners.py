from typing import Any
from datetime import datetime, timezone, timedelta
from sqlmodel import select

from ..db import SessionDep
from ..logging import get_logger
from ..models import Summoner, SummonerLeagues
from ..riot_api import RiotAPIDep, RiotAPINotFoundError, LeagueEntry
from app.dependencies import SUMMONER_TTL_MINUTES


# from ..riot_api.summoners import RiotSummoners

logger = get_logger(__name__)


def get_summoner_by_name(
    game_name: str,
    tag_line: str,
    session: SessionDep
) -> Summoner:
    statement = select(Summoner).where(
        Summoner.summoner_name == game_name.strip(),
        Summoner.tag_line == tag_line.strip()
    )

    return session.exec(statement).first()


def get_summoner_by_puuid(puuid: str, session: SessionDep) -> Summoner:
    statement = select(Summoner).where(Summoner.puuid == puuid)

    return session.exec(statement).first()


def is_summoner_ttl_expired(summoner: Summoner) -> bool:
    current_time = datetime.now(timezone.utc)
    logger.info(f"Timedelta Results: {current_time - summoner.updated_at}, "
                f"{timedelta(minutes=SUMMONER_TTL_MINUTES)}")

    return current_time - summoner.updated_at >= timedelta(minutes=SUMMONER_TTL_MINUTES)


async def create(
    game_name: str,
    tag_line: str,
    session: SessionDep,
    riot_api: RiotAPIDep
):
    try:
        summoner = await riot_api.get_summoner(game_name, tag_line)
    except RiotAPINotFoundError:
        return None

    summoner_in_db = get_summoner_by_puuid(summoner.puuid, session)

    if not summoner_in_db:
        summoner_leagues = [SummonerLeagues(
            league_id=league.league_id,
            queue_type=league.queue_type,
            tier=league.tier,
            rank=league.rank,
            wins=league.wins,
            losses=league.losses,
            league_points=league.league_points
        ) for league in summoner.leagues]

        new_summoner = Summoner(
            puuid=summoner.puuid,
            region=summoner.region,
            summoner_name=summoner.summoner_name,
            tag_line=summoner.tag_line,
            summoner_level=summoner.summoner_level,
            profile_icon=summoner.profile_icon,
            revision_date=summoner.revision_date,
            leagues=summoner_leagues
        )

        session.add(new_summoner)
        session.commit()
        session.refresh(new_summoner)

        return new_summoner

    return None


async def find_or_create(
    game_name: str,
    tag_line: str,
    session: SessionDep,
    riot_api: RiotAPIDep
):
    summoner = get_summoner_by_name(game_name, tag_line, session)

    if not summoner:
        summoner = await create(game_name, tag_line, session, riot_api)

    return summoner

def update_leagues(
    summoner: Summoner,
    leagues: list[LeagueEntry],
    session: SessionDep
) -> None:
    leagues_at_riot = [SummonerLeagues(
        league_id=league.league_id,
        queue_type=league.queue_type,
        tier=league.tier,
        rank=league.rank,
        wins=league.wins,
        losses=league.losses,
        league_points=league.league_points
    ) for league in leagues]

    for index, league in enumerate(summoner.leagues):
        summoner_league = list(filter(lambda riot_league: riot_league.league_id == league.league_id, leagues_at_riot))

        # Delete old leagues
        if not summoner_league:
            # TODO: Determine if this is really useful (maybe needed for historic data?)
            session.delete(summoner.leagues[index])
            summoner.leagues = leagues_at_riot
        else:
            summoner_league = summoner_league[0]
            league.wins = summoner_league.wins
            league.losses = summoner_league.losses
            league.league_points = summoner_league.league_points

            session.add(league)
            session.commit()
            print(summoner_league)


async def update(
    summoner: Summoner,
    session: SessionDep,
    riot_api: RiotAPIDep
):
    # TODO: Add SummonerInfoTTL and only update every fifth minute

    try:
        summoner_at_riot = await riot_api.get_summoner_by_puuid(summoner.puuid)
    except RiotAPINotFoundError:
        return None

    summoner.summoner_name = summoner_at_riot.summoner_name
    summoner.tag_line = summoner_at_riot.tag_line
    summoner.region = summoner_at_riot.region
    summoner.summoner_level = summoner_at_riot.summoner_level
    summoner.profile_icon = summoner_at_riot.profile_icon

    # TODO: Add SummonerMatchesTTL
    # TODO: Update Leagues AND Matches
    if is_summoner_ttl_expired(summoner):
        update_leagues(summoner, summoner_at_riot.leagues, session)
        summoner.updated_at = datetime.now(tz=timezone.utc)

    session.add(summoner)
    session.commit()
    session.refresh(summoner)

    return summoner


async def find_and_update(
    puuid: str,
    session: SessionDep,
    riot_api: RiotAPIDep
):
    summoner = get_summoner_by_puuid(puuid, session)

    if not summoner:
        return None

    return await update(summoner, session, riot_api)
