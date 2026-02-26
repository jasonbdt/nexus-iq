"""Unit tests for model computed fields."""

import pytest

from app.internal.models import MatchParticipant


def test_match_participant_kda_zero_deaths():
    p = MatchParticipant(
        match_id=1,
        team_id=1,
        summoner_puuid="x" * 78,
        champion_id=1,
        champion_name="Test",
        lane="MID",
        kills=10,
        deaths=0,
        assists=5,
        double_kills=0,
        triple_kills=0,
        quadra_kills=0,
        penta_kills=0,
        largest_multi_kill=1,
        damage_dealt_to_champions=10000,
        damage_taken=5000,
        total_minions_killed=200,
        neutral_minions_killed=20,
        gold_earned=10000,
        vision_score=25,
        wards_placed=10,
        wards_killed=5,
        vision_wards_bought=2,
    )
    assert p.kda == 15.0  # kills + assists when deaths=0


def test_match_participant_kda_with_deaths():
    p = MatchParticipant(
        match_id=1,
        team_id=1,
        summoner_puuid="x" * 78,
        champion_id=1,
        champion_name="Test",
        lane="MID",
        kills=10,
        deaths=4,
        assists=5,
        double_kills=0,
        triple_kills=0,
        quadra_kills=0,
        penta_kills=0,
        largest_multi_kill=1,
        damage_dealt_to_champions=10000,
        damage_taken=5000,
        total_minions_killed=200,
        neutral_minions_killed=20,
        gold_earned=10000,
        vision_score=25,
        wards_placed=10,
        wards_killed=5,
        vision_wards_bought=2,
    )
    assert p.kda == round((10 + 5) / 4, 2)  # 3.75


def test_match_participant_total_cs():
    p = MatchParticipant(
        match_id=1,
        team_id=1,
        summoner_puuid="x" * 78,
        champion_id=1,
        champion_name="Test",
        lane="MID",
        kills=0,
        deaths=0,
        assists=0,
        double_kills=0,
        triple_kills=0,
        quadra_kills=0,
        penta_kills=0,
        largest_multi_kill=0,
        damage_dealt_to_champions=0,
        damage_taken=0,
        total_minions_killed=180,
        neutral_minions_killed=15,
        gold_earned=0,
        vision_score=0,
        wards_placed=0,
        wards_killed=0,
        vision_wards_bought=0,
    )
    assert p.total_cs == 195
