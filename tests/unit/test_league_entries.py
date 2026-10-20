"""Regression tests for Riot ranked entries and unranked registration."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.internal.controllers import summoners
from app.internal.db import get_session
from app.internal.models import Role, Summoner, SummonerLeagues, User, UserRole, UserRoleLink
from app.internal.models import UserSummonerLink
from app.internal.redis import get_redis
from app.internal.riot_api.clients.league_client import LeagueClient
from app.internal.riot_api.config import RiotAPIConfig, RiotPlatform
from app.internal.riot_api.dependencies import get_riot_api
from app.internal.riot_api.exceptions import RiotAPIError, RiotAPIServerError
from app.internal.riot_api.facade import FacadeClients, RiotAPIFacade
from app.internal.riot_api.models import LeagueEntry, RiotAccount, SummonerInfo, SummonerProfile


@pytest.fixture
def ranked_payload():
    """A valid ranked response using Riot's current fields."""
    return {
        "queueType": "RANKED_SOLO_5x5", "tier": "GOLD", "rank": "II",
        "leaguePoints": 45, "wins": 12, "losses": 8,
        "veteran": False, "inactive": False, "freshBlood": False, "hotStreak": False,
    }


def profile(entries):
    """Build a profile without depending on Riot or application lifespan."""
    return SummonerProfile(
        puuid="p" * 78, region="euw", summoner_name="Test Player", tag_line="EUW",
        summoner_level=30, profile_icon=1, revision_date=datetime.now(timezone.utc),
        leagues=entries,
    )


@pytest.fixture
def db_session():
    """Use a fresh database for each persistence and API test."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([Role(name=role.value) for role in UserRole])
        session.commit()
        yield session
    engine.dispose()


@pytest.mark.parametrize("legacy", [False, True])
def test_ranked_payload_ignores_legacy_league_id(ranked_payload, legacy):
    if legacy:
        ranked_payload["leagueId"] = "old-riot-id"
    entry = LeagueEntry.model_validate(ranked_payload)
    assert entry.queue_type == "RANKED_SOLO_5x5"
    assert entry.league_points == 45
    assert "league_id" not in entry.model_dump()
    assert "leagueId" not in entry.model_dump(by_alias=True)


def test_ranked_payload_still_requires_rank_fields(ranked_payload):
    del ranked_payload["tier"]
    with pytest.raises(ValidationError):
        LeagueEntry.model_validate(ranked_payload)


@pytest.mark.parametrize("kind", ["ranked", "legacy", "unranked", "invalid", "unavailable"])
async def test_league_client_parses_real_response_shape(monkeypatch, ranked_payload, kind):
    payload = dict(ranked_payload)
    if kind == "legacy":
        payload["leagueId"] = "old-riot-id"
    if kind == "invalid":
        del payload["rank"]
    response = SimpleNamespace(
        ok=kind != "unavailable", status=503, headers={},
        json=AsyncMock(return_value=[] if kind == "unranked" else [payload]),
    )
    http = SimpleNamespace(get=AsyncMock(return_value=response))
    monkeypatch.setattr("app.internal.riot_api.base.get_session", lambda: http)
    monkeypatch.setattr("app.internal.riot_api.base.acquire_riot", AsyncMock())
    client = LeagueClient(RiotAPIConfig(api_key="test-key"))
    if kind in ("invalid", "unavailable"):
        with pytest.raises(RiotAPIError):
            await client.get_entries_by_puuid("p" * 78, RiotPlatform.EUW1)
    else:
        entries = await client.get_entries_by_puuid("p" * 78, RiotPlatform.EUW1)
        assert len(entries) == (0 if kind == "unranked" else 1)
        if entries:
            assert entries[0].tier == "GOLD"


@pytest.mark.parametrize("ranked", [False, True])
async def test_facade_preserves_ranked_and_unranked_profiles(ranked_payload, ranked):
    entries = [LeagueEntry.model_validate(ranked_payload)] if ranked else []
    account = SimpleNamespace(
        get_by_riot_id=AsyncMock(return_value=RiotAccount(
            puuid="p" * 78, gameName="Test Player", tagLine="EUW",
        )),
        get_active_region=AsyncMock(return_value="euw"),
    )
    league = SimpleNamespace(get_entries_by_puuid_with_region=AsyncMock(return_value=entries))
    facade = RiotAPIFacade(RiotAPIConfig(api_key="test-key"), FacadeClients(
        account_client=account,
        summoner_client=SimpleNamespace(get_by_puuid_with_region=AsyncMock(
            return_value=SummonerInfo(
                puuid="p" * 78, profileIconId=1, revisionDate=1700000000000, summonerLevel=30,
            ),
        )),
        league_client=league, match_client=MagicMock(),
    ))
    assert (await facade.get_summoner("Test Player", "EUW")).leagues == entries
    assert len(await facade.get_summoner_leagues("euw", "p" * 78)) == len(entries)
    league.get_entries_by_puuid_with_region.side_effect = RiotAPIServerError()
    with pytest.raises(RiotAPIServerError):
        await facade.get_summoner("Test Player", "EUW")


@pytest.mark.parametrize("lookup", ["riot_id", "puuid"])
@pytest.mark.parametrize("ranked", [False, True])
async def test_profile_persistence_without_league_id(db_session, ranked_payload, ranked, lookup):
    entries = [LeagueEntry.model_validate(ranked_payload)] if ranked else []
    riot = SimpleNamespace(
        get_summoner=AsyncMock(return_value=profile(entries)),
        get_summoner_by_puuid=AsyncMock(return_value=profile(entries)),
    )
    if lookup == "riot_id":
        saved = await summoners.find_or_create("Test Player", "EUW", db_session, riot)
    else:
        saved = await summoners.find_or_create_by_puuid("p" * 78, db_session, riot)
    assert saved.id is not None
    assert len(saved.leagues) == len(entries)


async def test_sync_tracks_queues_and_preserves_row_ids(db_session, ranked_payload):
    riot = SimpleNamespace(get_summoner=AsyncMock(return_value=profile([])))
    saved = await summoners.create("Test Player", "EUW", db_session, riot)
    solo = LeagueEntry.model_validate(ranked_payload)
    flex = LeagueEntry.model_validate({**ranked_payload, "queueType": "RANKED_FLEX_SR"})
    for _ in range(2):
        summoners.update_leagues(saved, [solo, flex], db_session)
        db_session.commit()
    ids = {entry.queue_type: entry.id for entry in saved.leagues}
    assert len(ids) == 2
    solo = solo.model_copy(update={"tier": "PLATINUM", "rank": "IV", "wins": 20,
                                  "losses": 10, "league_points": 70})
    summoners.update_leagues(saved, [solo, flex], db_session)
    db_session.commit()
    updated = next(entry for entry in saved.leagues if entry.queue_type == solo.queue_type)
    assert updated.id == ids[solo.queue_type]
    assert (updated.tier, updated.rank, updated.wins, updated.losses,
            updated.league_points) == ("PLATINUM", "IV", 20, 10, 70)
    summoners.update_leagues(saved, [flex], db_session)
    db_session.commit()
    assert [entry.id for entry in saved.leagues] == [ids[flex.queue_type]]
    summoners.update_leagues(saved, [], db_session)
    db_session.commit()
    assert saved.leagues == []
    assert db_session.exec(select(SummonerLeagues)).all() == []
    summoners.update_leagues(saved, [solo], db_session)
    db_session.commit()
    assert len(saved.leagues) == 1


@pytest.mark.parametrize("ranked", [False, True])
@pytest.mark.parametrize("search_first", [False, True])
def test_search_then_register_without_league_id(
    client, app_no_lifespan, db_session, monkeypatch, ranked_payload, ranked, search_first,
):
    entries = [LeagueEntry.model_validate(ranked_payload)] if ranked else []
    riot = SimpleNamespace(get_summoner=AsyncMock(return_value=profile(entries)))
    redis = SimpleNamespace(scard=AsyncMock(return_value=0), get=AsyncMock(return_value=0))
    monkeypatch.setitem(app_no_lifespan.dependency_overrides, get_session, lambda: db_session)
    monkeypatch.setitem(app_no_lifespan.dependency_overrides, get_riot_api, lambda: riot)
    monkeypatch.setitem(app_no_lifespan.dependency_overrides, get_redis, lambda: redis)
    if search_first:
        response = client.get("/search/EUW/Test%20Player")
        assert response.status_code == 200
        assert len(response.json()["leagues"]) == len(entries)
        assert all("league_id" not in entry for entry in response.json()["leagues"])
    response = client.post("/register", json={
        "emailAddress": "new@example.test", "password": "test-password-123",
        "password_confirm": "test-password-123", "gameName": "Test Player", "tagLine": "EUW",
    })
    assert response.status_code == 200
    assert response.json()["linked_summoner"]["puuid"] == "p" * 78
    user = db_session.exec(select(User)).one()
    assert user.is_active is False
    assert db_session.exec(select(UserRoleLink)).one().user_id == user.id
    assert db_session.exec(select(UserSummonerLink)).one().summoner_puuid == "p" * 78


def test_upstream_failure_does_not_create_unranked_player(
    app_no_lifespan, db_session, monkeypatch,
):
    riot = SimpleNamespace(get_summoner=AsyncMock(side_effect=RiotAPIServerError()))
    monkeypatch.setitem(app_no_lifespan.dependency_overrides, get_session, lambda: db_session)
    monkeypatch.setitem(app_no_lifespan.dependency_overrides, get_riot_api, lambda: riot)
    monkeypatch.setitem(app_no_lifespan.dependency_overrides, get_redis, lambda: MagicMock())
    client = TestClient(app_no_lifespan, raise_server_exceptions=False)
    assert client.get("/search/EUW/Test%20Player").status_code >= 500
    assert db_session.exec(select(Summoner)).all() == []


def test_fresh_schema_has_no_riot_league_id(db_session):
    columns = inspect(db_session.get_bind()).get_columns("summoner_leagues")
    assert "id" in {column["name"] for column in columns}
    assert "league_id" not in {column["name"] for column in columns}
