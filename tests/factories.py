"""Small complete domain graphs shared by persistence and contract tests."""
from app.domain.models import (
    Match, MatchTeam, MatchTeamBans, MatchTeamObjectives, MatchParticipant,
    MatchParticipantRunes, User, utc_now,
)
from dataclasses import asdict
from types import SimpleNamespace


def player(lane='TOP', puuid='p' * 78):
    """Create a realistic participant with a complete rune selection."""
    return MatchParticipant(
        match_id=None, team_id=None, summoner_puuid=puuid, summoner_name='Player',
        tag_line='EUW', champion_id=1, champion_name='Annie', champion_level=18, lane=lane,
        summoner_spell_1=4, summoner_spell_2=14, kills=10, deaths=4, assists=5,
        double_kills=0, triple_kills=0, quadra_kills=0, penta_kills=0, largest_multi_kill=1,
        damage_dealt_to_champions=10000, damage_taken=5000, total_minions_killed=180,
        neutral_minions_killed=15, gold_earned=12000, vision_score=25, wards_placed=10,
        wards_killed=5, vision_wards_bought=2,
        item0=0, item1=0, item2=0, item3=0, item4=0, item5=0, item6=0,
        runes=[MatchParticipantRunes(
            participant_id=None, primary_style=8000, primary_perk0=8005, primary_perk1=9111,
            primary_perk2=9104, primary_perk3=8014, secondary_style=8100,
            secondary_perk0=8139, secondary_perk1=8135, stat_perk_defense=5002,
            stat_perk_flex=5008, stat_perk_offense=5005,
        )],
    )


def match():
    """Create both teams and all kinds of aggregate-owned match children."""
    return Match(
        match_id='EUW1_123', platform='EUW1', queue_id=420, game_mode='CLASSIC',
        game_type='MATCHED_GAME', game_version='16.20.1', map_id=11,
        game_start=utc_now(), game_end=utc_now(), game_duration=1800,
        teams=[MatchTeam(
            match_id=None, team_id=100, win=True,
            bans=[MatchTeamBans(team_id=None, champion_id=2, pick_turn=1)],
            objectives=[MatchTeamObjectives(team_id=None, objective='baron', first=True, kills=1)],
            participants=[player('UTILITY'), player('TOP', 'q' * 78)],
        ), MatchTeam(match_id=None, team_id=200, win=False,
                     participants=[player('MIDDLE', 'r' * 78)])],
    )


def active_user(services, email='active@example.test'):
    """Persist an active account and return its domain snapshot and Bearer header."""
    security = services.accounts.security
    with services.accounts.uow() as work:
        user = work.users.save(User(avatarName='Active', emailAddress=email,
                                   password=security.hash_password('password'), is_active=True))
        work.commit()
    return user, {'Authorization': 'Bearer ' + security.token(email, user.role.value)}


def riot_match():
    """A transport-shaped match containing the exact fields used by the Riot gateway."""
    source = match()
    players = []
    teams = []
    for team in source.teams:
        teams.append(SimpleNamespace(
            team_id=team.team_id, win=team.win,
            bans=[SimpleNamespace(champion_id=ban.champion_id, pick_turn=ban.pick_turn)
                  for ban in team.bans],
            objectives=[(entry.objective, SimpleNamespace(first=entry.first, kills=entry.kills))
                        for entry in team.objectives],
        ))
        for participant in team.participants:
            data = asdict(participant)
            rune = participant.runes[0]
            data.update(puuid=participant.summoner_puuid, team_id=team.team_id,
                        riot_id_game_name=participant.summoner_name,
                        riot_id_tagline=participant.tag_line, team_position=participant.lane,
                        perks=SimpleNamespace(
                            styles=[SimpleNamespace(description='primaryStyle', style=8000,
                                                    selections=[SimpleNamespace(perk=8005)] * 4),
                                    SimpleNamespace(description='subStyle', style=8100,
                                                    selections=[SimpleNamespace(perk=8139)] * 2)],
                            stat_perks=SimpleNamespace(defense=rune.stat_perk_defense,
                                                       flex=rune.stat_perk_flex,
                                                       offense=rune.stat_perk_offense)))
            players.append(SimpleNamespace(**data))
    return SimpleNamespace(metadata=SimpleNamespace(match_id=source.match_id),
                           info=SimpleNamespace(
                               platform_id=source.platform, queue_id=source.queue_id,
                               game_mode=source.game_mode, game_type=source.game_type,
                               game_version=source.game_version, map_id=source.map_id,
                               game_creation_datetime=source.game_start,
                               game_end_datetime=source.game_end, game_duration=source.game_duration,
                               teams=teams, participants=players))
