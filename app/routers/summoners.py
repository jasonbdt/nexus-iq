from typing import Annotated, Any, Optional
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from fastapi.params import Depends
from fastapi.routing import APIRouter

from sqlmodel import select, or_

from .matches import process_match
from ..dependencies import SUMMONER_TTL_MINUTES
from ..internal.auth import get_current_active_user
from ..internal.controllers import summoners as SummonersController
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


@router.get("/v2/get_summoner/by-puuid/{puuid}")
async def get_summoner(
    current_user: Annotated[User, Depends(get_current_active_user)],
    puuid: str
):
    from app.internal.riot_api.summoners import RiotSummoners
    account_data = await RiotSummoners().get_account_by_puuid(puuid)
    region = await RiotSummoners().get_active_region("lol", puuid)

    print(account_data.puuid)

    return account_data, region

@router.get("/v2/get_summoner/{tag_line}/{game_name}", response_model=SummonerSearch)
async def get_summoner(
    current_user: Annotated[User, Depends(get_current_active_user)],
    tag_line: str,
    game_name: str,
    session: SessionDep
):
    logger.info(
        f"User[{current_user.id}] searching for Summoner \"{game_name}#{tag_line}\"")

    return await SummonersController.find_or_create(game_name, tag_line, session)


@router.post("/refresh/{tag_line}/{player_name}")
def refresh_summoner(
    current_user: Annotated[User, Depends(get_current_active_user)],
    tag_line: str,
    player_name: str,
    session: SessionDep,
    match_count: int = 20
):
    logger.info(
        f"User[{current_user.id}] refreshing Summoner \"{player_name}#{tag_line}\" "
        f"with {match_count} matches"
    )

    summoner = get_summoner_from_db_by_name(player_name, tag_line, session)

    if not summoner:
        logger.info("Summoner not found, creating new one")
        raise HTTPException(status_code=404, detail="Summoner doesn't exist")
        summoner = create_or_update_summoner_from_riot(player_name, tag_line, session)
    else:
        logger.info(f"Refreshing existing summoner: {summoner.riot_id}")

        riot_api = RiotAPI()
        summoner_data = riot_api.get_summoner(player_name, tag_line)

        if summoner_data:
            apply_basic_summoner_updates(summoner, summoner_data)

            if should_refresh_from_riot(summoner, summoner_data):
                summoner_leagues = riot_api.get_summoner_leagues(
                    summoner.region, summoner.puuid
                )
                summoner.region = summoner_data.get("region")
                summoner.summoner_level = summoner_data.get("summonerLevel")
                summoner.revision_date = summoner_data.get("revisionDate")
                summoner.leagues = [
                    SummonerLeagues(**league) for league in summoner_leagues
                ]

            summoner.updated_at = datetime.now(timezone.utc)
            session.add(summoner)
            session.commit()
            session.refresh(summoner)

            # Step 2: Fetch match history
            riot_api = RiotAPI()
            match_ids = riot_api.get_match_history(
                puuid=summoner.puuid,
                count=min(match_count, 100)  # Cap at 100
            )

            if not match_ids:
                logger.warning(f"No match history found for summoner {summoner.riot_id}")
                return {
                    "status": "success",
                    "summoner": {
                        "puuid": summoner.puuid,
                        "riot_id": summoner.riot_id,
                        "updated": True
                    },
                    "matches": {
                        "fetched": 0,
                        "processed": 0,
                        "skipped": 0,
                        "errors": 0
                    },
                    "message": "Summoner refreshed, but no matches found"
                }

            logger.info(f"Found {len(match_ids)} matches for {summoner.riot_id}")

            # Step 3: Process each match
            matches_processed = 0
            matches_skipped = 0
            matches_errors = 0

            for match_id in match_ids:
                try:
                    # Fetch match details
                    match_data = riot_api.get_match_by_id(match_id, puuid=summoner.puuid)

                    if not match_data:
                        logger.warning(f"Could not fetch match details for {match_id}")
                        matches_errors += 1
                        continue

                    # Process match
                    result = process_match(
                        match_data=match_data,
                        session=session,
                        # skip_existing=True
                    )

                    if result:
                        if result.get("status") == "skipped":
                            matches_skipped += 1
                        elif result.get("status") == "success":
                            matches_processed += 1
                        else:
                            matches_errors += 1
                    else:
                        matches_errors += 1

                except HTTPException as e:
                    if e.status_code == 429:
                        logger.error("Rate limit exceeded while fetching matches")
                        raise HTTPException(
                            status_code=429,
                            detail="Rate limit exceeded. Please try again later."
                        )
                    logger.error(f"HTTP error processing match {match_id}: {e.detail}")
                    matches_errors += 1
                except Exception as e:
                    logger.error(f"Unexpected error processing match {match_id}: {e}")
                    matches_errors += 1

            return {
                "status": "success",
                "summoner": {
                    "puuid": summoner.puuid,
                    "riot_id": summoner.riot_id,
                    "updated": True
                },
                "matches": {
                    "fetched": len(match_ids),
                    "processed": matches_processed,
                    "skipped": matches_skipped,
                    "errors": matches_errors
                },
                "message": f"Refreshed {summoner.riot_id} with {matches_processed} new matches"
            }
