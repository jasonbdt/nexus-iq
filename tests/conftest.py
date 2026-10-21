"""Isolated API composition and shared local database fixtures."""
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


@pytest.fixture
def db_engine():
    """Use SQLite by default, or a disposable PostgreSQL schema in integration runs."""
    if os.getenv('NEXUS_TEST_POSTGRES') == '1':
        base = create_engine(Settings.from_environment().database_url)
        schema = 'nexusiq_test_' + uuid4().hex
        with base.begin() as connection:
            connection.execute(CreateSchema(schema))
        engine = base.execution_options(schema_translate_map={None: schema})
        try:
            initialize_database(engine)
            yield engine
        finally:
            with base.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
            base.dispose()
        return
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    initialize_database(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Independent inspection session, never reused as an application transaction."""
    with Session(db_engine) as session:
        yield session


@pytest.fixture
def services(db_engine, tmp_path):
    """Real adapters with fake upstream ports."""
    from tests.support import build_services
    return build_services(db_engine, tmp_path)


@pytest.fixture
def app_no_lifespan(services):
    """Each test gets a new app without modifying a module-level singleton."""
    return create_app(services)


@pytest.fixture
def client(app_no_lifespan):
    """HTTP client requiring no external infrastructure."""
    with TestClient(app_no_lifespan) as test_client:
        yield test_client
