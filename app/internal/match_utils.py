"""
Utility functions for processing match data from Riot API
"""
from typing import Optional

from sqlmodel import select, or_

from .db import SessionDep
from .logging import get_logger
from .models import Summoner

logger = get_logger(__name__)


def extract_runes_from_participant(participant_data: dict) -> Optional[dict]:
    perks = participant_data.get("perks")

    if not perks:
        logger.warning("Participant data missing 'perks' field")
        return None

    styles = perks.get("styles", [])
    stat_perks = perks.get("statPerks", {})

    if not styles or len(styles) < 2:
        logger.warning(f"Participant has invalid rune styles: {len(styles) if styles else 0} styles found")
        return None

    primary_style = styles[0]
    secondary_style = styles[1]

    primary_selections = primary_style.get("selections", [])
    secondary_selections = secondary_style.get("selections", [])

    primary_perk0 = primary_selections[0].get("perk", 0)
    primary_perk1 = primary_selections[1].get("perk", 0)
    primary_perk2 = primary_selections[2].get("perk", 0)
    primary_perk3 = primary_selections[3].get("perk", 0)

    secondary_perk0 = secondary_selections[0].get("perk", 0)
    secondary_perk1 = secondary_selections[1].get("perk", 0)

    stat_perk_defense = stat_perks.get("defense", 0)
    stat_perk_flex = stat_perks.get("flex", 0)
    stat_perk_offense = stat_perks.get("offense", 0)

    rune_data = {
        "primary_style": primary_style.get("style", 0),
        "primary_perk0": primary_perk0,
        "primary_perk1": primary_perk1,
        "primary_perk2": primary_perk2,
        "primary_perk3": primary_perk3,
        "secondary_style": secondary_style.get("style", 0),
        "secondary_perk0": secondary_perk0,
        "secondary_perk1": secondary_perk1,
        "stat_perk_defense": stat_perk_defense,
        "stat_perk_flex": stat_perk_flex,
        "stat_perk_offense": stat_perk_offense
    }

    if rune_data["primary_style"] == rune_data["secondary_style"]:
        logger.warning(f"Invalid rune styles extracted: primary={rune_data['primary_style']}, secondary={rune_data["secondary_style"]}")
        return None

    return rune_data


def create_match_participant_with_runes(
        participant_data: dict,
        match_id: str,
        session: SessionDep
) -> tuple:
    from .models import Summoner, SummonerLeagues, MatchParticipant, MatchParticipantRunes

    summoner = session.exec(
        select(Summoner).where(or_(
            Summoner.puuid == participant_data.get("puuid"),
            Summoner.summoner_name == participant_data.get("riotIdGameName")
            and Summoner.tag_line == participant_data.get("riotIdTagline")
        ))
    ).first()

    if not summoner:
        pass

    participant = MatchParticipant(
        match_id=match_id,
        team_id=participant_data.get("teamId", 0),
        summoner_puuid=participant_data.get("puuid", 0),
        champion_id=participant_data.get("championId", 0),
        champion_name=participant_data.get("championName", ""),
        lane=participant_data.get("individualPosition", "UNKNOWN"),
        kills=participant_data.get("kills", 0),
        deaths=participant_data.get("deaths", 0),
        assists=participant_data.get("assists", 0),
        kill_participation=participant_data.get("challenges", {}).get("killParticipation", 0.0),
        double_kills=participant_data.get("doubleKills", 0),
        triple_kills=participant_data.get("tripleKills", 0),
        quadra_kills=participant_data.get("quadraKills", 0),
        penta_kills=participant_data.get("pentaKills", 0),
        largest_multi_kill=participant_data.get("largestMultiKill", 0),
        damage_dealt_to_champions=participant_data.get("totalDamageDealtToChampions", 0),
        damage_taken=participant_data.get("totalDamageTaken", 0),
        total_minions_killed=participant_data.get("totalMinionsKilled", 0),
        neutral_minions_killed=participant_data.get("neutralMinionsKilled", 0),
        gold_earned=participant_data.get("goldEarned", 0),
        vision_score=participant_data.get("visionScore", 0),
        wards_placed=participant_data.get("wardsPlaced", 0),
        wards_killed=participant_data.get("wardsKilled", 0),
        vision_wards_bought=participant_data.get("visionWardsBoughtInGame", 0),
        item0=participant_data.get("item0", 0),
        item1=participant_data.get("item1", 0),
        item2=participant_data.get("item2", 0),
        item3=participant_data.get("item3", 0),
        item4=participant_data.get("item4", 0),
        item5=participant_data.get("item5", 0),
        item6=participant_data.get("item6", 0),
    )

    rune_data = extract_runes_from_participant(participant_data)
    runes = None

    if rune_data:
        runes = MatchParticipantRunes(**rune_data)
        participant.runes = [runes]

    return participant, runes


def find_or_create_summoner_by_puuid(participant_data: dict, session: SessionDep):
    puuid = participant_data.get("puuid")
    summoner = session.exec(
        select(Summoner).where(or_(
            Summoner.puuid == puuid,
            Summoner.summoner_name == participant_data.get("riotIdGameName")
            and Summoner.tag_line == participant_data.get("riotIdTagline")
        ))
    ).first()

    if not summoner:
        pass
