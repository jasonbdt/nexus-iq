from typing import Any
from datetime import datetime, timezone, timedelta
from sqlmodel import select

from ..db import SessionDep
from ..logging import get_logger
from ..models import Summoner, SummonerLeagues, Match, MatchTeam, MatchTeamBans, MatchParticipant, \
    MatchParticipantRunes, MatchTeamObjectives
from ..riot_api import RiotAPIDep, RiotAPINotFoundError, LeagueEntry
from app.dependencies import SUMMONER_TTL_MINUTES
from ..riot_api.models import MatchParticipantPerkStyle

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


def get_match_by_match_id(
    match_id: str,
    session: SessionDep
) -> Match:
    statement = select(Match).where(
        Match.match_id == match_id
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


def get_participant_runes(style: str, perk_styles: list[MatchParticipantPerkStyle]) -> MatchParticipantPerkStyle:
    return list(filter(
        lambda x: x.description == style,
        perk_styles
    ))[0]


async def update_matches(
    summoner: Summoner,
    match_count: int,
    session: SessionDep,
    riot_api: RiotAPIDep
):
    recent_matches = await riot_api.get_recent_matches(summoner.puuid, summoner.region, match_count)

    for match in recent_matches:
        if not get_match_by_match_id(match.metadata.match_id, session):
            new_match = Match(
                match_id=match.metadata.match_id,
                platform=match.info.platform_id,
                queue_id=match.info.queue_id,
                game_mode=match.info.game_mode,
                game_type=match.info.game_type,
                game_version=match.info.game_version,
                map_id=match.info.map_id,
                game_start=match.info.game_creation_datetime,
                game_end=match.info.game_end_datetime,
                game_duration=match.info.game_duration,
            )
            session.add(new_match)
            session.commit()
            session.refresh(new_match)

            # Create match teams
            team_ids = {
                100: None,
                200: None
            }
            for team in match.info.teams:
                new_team = MatchTeam(
                    match_id=new_match.id,
                    team_id=team.team_id,
                    bans=[MatchTeamBans(
                        champion_id=team_ban.champion_id,
                        pick_turn=team_ban.pick_turn
                    ) for team_ban in team.bans],
                    objectives=[MatchTeamObjectives(
                        objective=name,
                        first=objective.first,
                        kills=objective.kills
                    ) for name, objective in team.objectives],
                    win=team.win
                )

                session.add(new_team)
                session.commit()
                session.refresh(new_team)
                team_ids[team.team_id] = new_team.id



            # Save participants
            for participant in match.info.participants:
                await find_or_create(participant.riot_id_game_name, participant.riot_id_tagline, session, riot_api)
                new_participant = MatchParticipant(
                    match_id=new_match.id,
                    team_id=team_ids[participant.team_id],
                    summoner_puuid=participant.puuid,
                    champion_id=participant.champion_id,
                    champion_name=participant.champion_name,
                    lane=participant.lane,
                    kills=participant.kills,
                    deaths=participant.deaths,
                    assists=participant.assists,
                    double_kills=participant.double_kills,
                    triple_kills=participant.triple_kills,
                    quadra_kills=participant.quadra_kills,
                    penta_kills=participant.penta_kills,
                    largest_multi_kill=participant.largest_multi_kill,
                    damage_dealt_to_champions=participant.damage_dealt_to_champions,
                    damage_taken=participant.damage_taken,
                    total_minions_killed=participant.total_minions_killed,
                    neutral_minions_killed=participant.neutral_minions_killed,
                    gold_earned=participant.gold_earned,
                    vision_score=participant.vision_score,
                    wards_placed=participant.wards_placed,
                    wards_killed=participant.wards_killed,
                    vision_wards_bought=participant.vision_wards_bought,
                    item0=participant.item0,
                    item1=participant.item1,
                    item2=participant.item2,
                    item3=participant.item3,
                    item4=participant.item4,
                    item5=participant.item5,
                    item6=participant.item6,
                )
                session.add(new_participant)
                session.commit()
                session.refresh(new_participant)

                # Create participants selected rune page
                primary_style = get_participant_runes("primaryStyle", participant.perks.styles)
                sub_style = get_participant_runes("subStyle", participant.perks.styles)

                new_runes = MatchParticipantRunes(
                    participant_id=new_participant.id,
                    primary_style=primary_style.style,
                    primary_perk0=primary_style.selections[0].perk,
                    primary_perk1=primary_style.selections[1].perk,
                    primary_perk2=primary_style.selections[2].perk,
                    primary_perk3=primary_style.selections[3].perk,
                    secondary_style=sub_style.style,
                    secondary_perk0=sub_style.selections[0].perk,
                    secondary_perk1=sub_style.selections[1].perk,
                    stat_perk_defense=participant.perks.stat_perks.defense,
                    stat_perk_flex=participant.perks.stat_perks.flex,
                    stat_perk_offense=participant.perks.stat_perks.offense
                )
                session.add(new_runes)
        else:
            logger.debug(f"Match {match.metadata.match_id} already exist.")
    session.commit()


async def update(
    summoner: Summoner,
    session: SessionDep,
    riot_api: RiotAPIDep,
    match_count: int
):
    if is_summoner_ttl_expired(summoner):
        try:
            summoner_at_riot = await riot_api.get_summoner_by_puuid(summoner.puuid)
        except RiotAPINotFoundError:
            return None

        summoner.summoner_name = summoner_at_riot.summoner_name
        summoner.tag_line = summoner_at_riot.tag_line
        summoner.region = summoner_at_riot.region
        summoner.summoner_level = summoner_at_riot.summoner_level
        summoner.profile_icon = summoner_at_riot.profile_icon

        update_leagues(summoner, summoner_at_riot.leagues, session)
        await update_matches(summoner, match_count, session, riot_api)
        summoner.updated_at = datetime.now(tz=timezone.utc)

        session.add(summoner)
        session.commit()
        session.refresh(summoner)

    return summoner


async def find_and_update(
    puuid: str,
    session: SessionDep,
    riot_api: RiotAPIDep,
    match_count: int
):
    summoner = get_summoner_by_puuid(puuid, session)

    if not summoner:
        return None

    return await update(summoner, session, riot_api, match_count)
