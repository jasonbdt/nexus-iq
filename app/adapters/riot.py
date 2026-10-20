"""Translate Riot transport payloads into infrastructure-free entities."""
from app.domain.models import (
    Summoner, SummonerLeagues, Match, MatchTeam, MatchTeamBans, MatchTeamObjectives,
    MatchParticipant, MatchParticipantRunes,
)
from .riot_api.exceptions import RiotAPINotFoundError


def profile_entity(profile):
    """Copy the external profile without exposing Pydantic SDK values."""
    if profile is None:
        return None
    return Summoner(
        puuid=profile.puuid, region=profile.region, summoner_name=profile.summoner_name,
        tag_line=profile.tag_line, summoner_level=profile.summoner_level,
        profile_icon=profile.profile_icon, revision_date=profile.revision_date,
        leagues=[SummonerLeagues(summoner_id=None, queue_type=entry.queue_type,
                 tier=entry.tier, rank=entry.rank, wins=entry.wins, losses=entry.losses,
                 league_points=entry.league_points) for entry in profile.leagues],
    )


def match_entity(riot_match):
    """Translate all match children before starting a database write."""
    new_match = Match(
        match_id=riot_match.metadata.match_id,
        platform=riot_match.info.platform_id,
        queue_id=riot_match.info.queue_id,
        game_mode=riot_match.info.game_mode,
        game_type=riot_match.info.game_type,
        game_version=riot_match.info.game_version,
        map_id=riot_match.info.map_id,
        game_start=riot_match.info.game_creation_datetime,
        game_end=riot_match.info.game_end_datetime,
        game_duration=riot_match.info.game_duration,
    )
    for team in riot_match.info.teams:
        new_team = MatchTeam(
            match_id=None,
            team_id=team.team_id,
            bans=[
                MatchTeamBans(
                    team_id=None,
                    champion_id=team_ban.champion_id,
                    pick_turn=team_ban.pick_turn,
                ) for team_ban in team.bans
            ],
            objectives=[
                MatchTeamObjectives(
                    team_id=None,
                    objective=name,
                    first=objective.first,
                    kills=objective.kills,
                ) for (name, objective) in team.objectives
            ],
            win=team.win,
        )
        new_match.teams.append(new_team)
    teams = {team.team_id: team for team in new_match.teams}
    for participant in riot_match.info.participants:
        new_participant = MatchParticipant(
            match_id=None,
            team_id=None,
            summoner_puuid=participant.puuid,
            summoner_name=participant.riot_id_game_name,
            tag_line=participant.riot_id_tagline,
            champion_id=participant.champion_id,
            champion_name=participant.champion_name,
            champion_level=participant.champion_level,
            summoner_spell_1=participant.summoner_spell_1,
            summoner_spell_2=participant.summoner_spell_2,
            lane=participant.team_position,
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
        primary_style = next(
            style for style in participant.perks.styles if style.description == 'primaryStyle'
        )
        sub_style = next(
            style for style in participant.perks.styles if style.description == 'subStyle'
        )
        runes = MatchParticipantRunes(
            participant_id=None,
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
            stat_perk_offense=participant.perks.stat_perks.offense,
        )
        new_participant.runes.append(runes)
        teams[participant.team_id].participants.append(new_participant)
    return new_match


class RiotGateway:
    """Application port backed by the existing Riot facade."""

    def __init__(self, facade):
        self.facade = facade

    async def profile(self, game_name, tag_line):
        """Resolve a Riot ID, treating only not-found as a missing profile."""
        try:
            return profile_entity(await self.facade.get_summoner(game_name, tag_line))
        except RiotAPINotFoundError:
            return None

    async def profile_by_puuid(self, puuid):
        """Preserve the facade's existing unavailable-profile behavior."""
        return profile_entity(await self.facade.get_summoner_by_puuid(puuid))

    async def match(self, match_id, region):
        """Resolve a full match graph."""
        result = await self.facade.get_match_by_id(match_id, region)
        return match_entity(result) if result else None

    async def match_ids(self, puuid, region, count):
        """Resolve recent IDs with the existing Riot routing rules."""
        return await self.facade.get_recent_match_ids(puuid, region, count)
