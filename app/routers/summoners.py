from typing import Annotated, Any, Optional
from datetime import datetime, timedelta, timezone

from fastapi.params import Depends
from fastapi.routing import APIRouter

from sqlmodel import select

from ..dependencies import SUMMONER_TTL_MINUTES
from ..internal.auth import get_current_active_user
from ..internal.logging import get_logger
from ..internal.db import SessionDep
from ..internal.models import Summoner, SummonerLeagues, SummonerSearch, User
from ..internal.riot_api.riot_api import RiotAPI


router = APIRouter(
    tags=["Summoners"]
)

logger = get_logger(__name__)


def is_summoner_ttl_expired(summoner: Summoner) -> bool:
    current_time = datetime.now(timezone.utc)
    logger.info(f"Timedelta Results: {current_time - summoner.updated_at}, "
                f"{timedelta(minutes=SUMMONER_TTL_MINUTES)}")

    return current_time - summoner.updated_at >= timedelta(minutes=SUMMONER_TTL_MINUTES)


def should_refresh_from_riot(summoner: Summoner, summoner_data: dict) -> bool:
    new_rev = summoner_data.get("revisionDate")
    old_rev = summoner.revision_date

    logger.debug(type(new_rev))
    logger.debug(new_rev)
    logger.debug(type(old_rev))
    logger.debug(old_rev)


    return new_rev > old_rev


def get_summoner_from_db_by_name(
    player_name: str,
    tag_line: str,
    session: SessionDep,
) -> Optional[Summoner]:
    return session.exec(
        select(Summoner).where(Summoner.summoner_name == player_name.strip())
                        .where(Summoner.tag_line == tag_line.strip())
    ).first()


def get_summoner_from_db_by_puuid(
    puuid: str,
    session: SessionDep,
) -> Optional[Summoner]:
    return session.exec(
        select(Summoner).where(Summoner.puuid == puuid)
    ).first()


def update_field_if_changed(
    obj: Any,
    attr: str,
    new_value: Any,
    field_label: str
) -> None:
    old_value = getattr(obj, attr)
    if old_value != new_value:
        logger.info(f"Summoners {field_label} had been changed... updating in DB")
        setattr(obj, attr, new_value)
    else:
        logger.info(f"Summoners {field_label} is up to date... nothing to change")


def apply_basic_summoner_updates(summoner: Summoner, data: dict):
    update_field_if_changed(
        summoner, "profile_icon", data.get("profileIcon"), "profile icon")
    update_field_if_changed(
        summoner, "summoner_name", data.get("summonerName"), "name")
    update_field_if_changed(
        summoner, "tag_line", data.get("tagLine"), "tag")


def handle_existing_summoner(
    summoner: Summoner,
    session: SessionDep
) -> Summoner:
    logger.info(
        f"Summoner \"{summoner.riot_id}\" exists in DB. Check cached object")

    if not is_summoner_ttl_expired(summoner):
        logger.info("Summoners TTL isn't expired. Returning cached Summoner.")
        return summoner

    logger.info("Summoners TTL is expired, check if an update is required...")

    riot_api = RiotAPI()
    summoner_data = riot_api.get_summoner(summoner.summoner_name, summoner.tag_line)
    logger.debug(f"Riot Summoner data: {summoner_data}")

    apply_basic_summoner_updates(summoner, summoner_data)

    if should_refresh_from_riot(summoner, summoner_data):
        # TODO: Determine when to update summoner region, level and revision date
        logger.info("Summoners data at Riot is changed... updating Summoner and Leagues in DB")
        summoner_leagues = riot_api.get_summoner_leagues(summoner.region, summoner.puuid)

        summoner.region = summoner_data.get("region")
        summoner.summoner_level = summoner_data.get("summonerLevel")
        summoner.revision_date = summoner_data.get("revisionDate")
        summoner.leagues = [SummonerLeagues(**league) for league in summoner_leagues]
    else:
        logger.info("Summoners data at Riot is unchanged...")

    summoner.updated_at = datetime.now()
    session.add(summoner)
    session.commit()
    session.refresh(summoner)

    return summoner


def create_or_update_summoner_from_riot(
    player_name: str,
    tag_line: str,
    session: SessionDep
):
    summoner_name = f"{player_name}#{tag_line}"
    logger.info(f"Summoner \"{summoner_name}\" does not exist in DB... creating new one")

    riot_api = RiotAPI()
    summoner_data = riot_api.get_summoner(player_name, tag_line)

    if not summoner_data:
        logger.info(f"Summoner doesn't exist at Riot Servers")

    summoner_puuid = summoner_data.get("puuid")
    summoner = get_summoner_from_db_by_puuid(summoner_puuid, session)

    if summoner:
        logger.info(f"Summoner exists in DB - Prepare updating")
        apply_basic_summoner_updates(summoner, summoner_data)
    else:
        logger.info(f"Summoner seems to be completely fresh - Prepare create")
        summoner_region = summoner_data.get("region")
        summoner_leagues = riot_api.get_summoner_leagues(summoner_region, summoner_puuid)
        summoner = Summoner(
            puuid=summoner_puuid,
            region=summoner_region,
            summoner_name=summoner_data.get("summonerName"),
            tag_line=summoner_data.get("tagLine"),
            summoner_level=summoner_data.get("summonerLevel"),
            profile_icon=summoner_data.get("profileIcon"),
            revision_date=summoner_data.get("revisionDate"),
            leagues=[SummonerLeagues(**league) for league in summoner_leagues]
        )
        session.add(summoner)

    session.commit()
    session.refresh(summoner)

    return summoner


@router.get("/search/{tag_line}/{player_name}", response_model=SummonerSearch)
def search_summoner(
    current_user: Annotated[User, Depends(get_current_active_user)],
    tag_line: str,
    player_name: str,
    session: SessionDep
):
    logger.info(
        f"User[{current_user.id}] searching for Summoner \"{player_name}#{tag_line}\"")

    summoner = get_summoner_from_db_by_name(player_name, tag_line, session)
    if summoner:
        return handle_existing_summoner(summoner, session)

    return create_or_update_summoner_from_riot(player_name, tag_line, session)
