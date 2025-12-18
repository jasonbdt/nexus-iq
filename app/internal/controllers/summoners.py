from sqlmodel import select

from ..db import SessionDep
from ..models import Summoner, SummonerLeagues
from ..riot_api.summoners import RiotSummoners


def get_summoner_by_name(game_name: str, tag_line: str, session: SessionDep):
    statement = select(Summoner).where(
        Summoner.summoner_name == game_name.strip(),
        Summoner.tag_line == tag_line.strip()
    )

    return session.exec(statement).first()


def get_summoner_by_puuid(puuid: str, session: SessionDep):
    statement = select(Summoner).where(Summoner.puuid == puuid)

    return session.exec(statement).first()


async def create_new(game_name: str, tag_line: str, session: SessionDep):
    summoner = await RiotSummoners().get_summoner(
        game_name=game_name,
        tag_line=tag_line
    )
    summoner_in_db = get_summoner_by_puuid(summoner.account_info.puuid, session)

    if not summoner_in_db:
        leagues = [SummonerLeagues(
            league_id=league.league_id,
            queue_type=league.queue_type,
            tier=league.tier,
            rank=league.rank,
            wins=league.wins,
            losses=league.losses,
            league_points=league.league_points
        ) for league in summoner.leagues]

        new_summoner = Summoner(
            puuid=summoner.account_info.puuid,
            region=summoner.region,
            summoner_name=summoner.account_info.game_name,
            tag_line=summoner.account_info.tag_line,
            summoner_level=summoner.level,
            profile_icon=summoner.profile_icon_id,
            revision_date=summoner.revision_date,
            leagues=leagues
        )

        session.add(new_summoner)
        session.commit()
        session.refresh(new_summoner)

        return new_summoner

    return None


async def find_or_create(game_name: str, tag_line: str, session: SessionDep):
    summoner = get_summoner_by_name(game_name, tag_line, session)

    if not summoner:
        summoner = await create_new(game_name, tag_line, session)

    return summoner
