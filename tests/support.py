"""Network-free composition for tests and the optional proxy smoke server."""
from functools import partial
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import os
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine
from sqlmodel.pool import StaticPool
from sqlalchemy.schema import CreateSchema, DropSchema
from app.config import Settings
from app.bootstrap import Services, initialize_database
from app.main import create_app
from app.domain.models import Summoner, utc_now
from app.service_layer.accounts import Accounts
from app.service_layer.players import Players
from app.service_layer.coaching import Coaching
from app.service_layer.rag import Retrieval
from app.adapters.assets import DDragonAssets
from app.adapters.persistence.unit_of_work import SqlUnitOfWork
from app.adapters.security import SecurityAdapter


def build_services(db_engine, tmp_path):
    """Real persistence and security with fake network and queue boundaries."""
    uow = partial(SqlUnitOfWork, partial(Session, db_engine))
    riot = SimpleNamespace(
        profile=AsyncMock(return_value=Summoner(
            puuid='p' * 78, region='euw', summoner_name='Test Player', tag_line='EUW',
            summoner_level=30, profile_icon=1, revision_date=utc_now(),
        )), profile_by_puuid=AsyncMock(return_value=None),
        match=AsyncMock(return_value=None), match_ids=AsyncMock(return_value=[]),
    )
    updates = SimpleNamespace(progress=AsyncMock(return_value=(0, 0)), enqueue=Mock(),
                              client=SimpleNamespace(ping=AsyncMock(return_value=True)))
    ai = SimpleNamespace(versions=Mock(return_value=(0.0, 26.4)), keywords=Mock(return_value=[]),
                         embed=AsyncMock(return_value=[0.1]), embed_many=Mock(return_value=[[0.1]]),
                         answer=Mock(return_value='Answer'),
                         stream=Mock(side_effect=lambda *_: iter(['Hello', ' world'])))
    retrieval = Retrieval(ai, SimpleNamespace(search=AsyncMock(return_value=[]), upsert=AsyncMock()),
                          SimpleNamespace(list=AsyncMock(return_value=[]),
                                          chunks=AsyncMock(return_value=[])))
    assets = DDragonAssets(tmp_path)
    security = SecurityAdapter('test-secret')
    return Services(Accounts(uow, riot, security), Players(uow, riot, updates, assets),
                    updates, assets, retrieval, Coaching(uow, retrieval))

