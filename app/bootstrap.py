"""Composition root and resource ownership for API processes and worker jobs."""
import asyncio
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from functools import partial

import aiohttp
from openai import OpenAI
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import Settings
from app.domain.models import UserRole
from app.service_layer.accounts import Accounts
from app.service_layer.players import Players
from app.service_layer.coaching import Coaching
from app.service_layer.rag import Retrieval
from app.adapters.ai.gateway import AIGateway, PatchGateway, VectorGateway
from app.adapters.ai.vector_store import VectorStore
from app.adapters.assets import DDragonAssets
from app.adapters.ddragon_sync import ensure_ddragon_cached_sync
from app.adapters.logging import configure_logging
from app.adapters.persistence.models import Role
from app.adapters.persistence.unit_of_work import SqlUnitOfWork
from app.adapters.redis import RiotRateLimiter
from app.adapters.riot import RiotGateway
from app.adapters.riot_api.config import RiotAPIConfig
from app.adapters.riot_api.facade import RiotAPIFacade
from app.adapters.security import SecurityAdapter
from app.adapters.updates import UpdateGateway


@dataclass
class Services:
    """Application-scoped services; tests can supply ports without opening resources."""

    accounts: Accounts
    players: Players
    updates: UpdateGateway
    assets: DDragonAssets
    retrieval: Retrieval | None = None
    coaching: Coaching | None = None


def initialize_database(engine) -> None:
    """Keep existing table creation and initial role seeding behavior."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        if not session.exec(select(Role)).first():
            session.add_all([Role(name=role.value) for role in UserRole])
            session.commit()


@asynccontextmanager
async def open_services(settings: Settings | None = None, *, worker: bool = False):
    """Create resources after startup, and close them even if initialization fails."""
    settings = settings or Settings.from_environment()
    configure_logging(logging.DEBUG if settings.app_env == 'dev' else logging.INFO)
    async with AsyncExitStack() as resources:
        engine = create_engine(settings.database_url)
        resources.callback(engine.dispose)
        session_factory = partial(Session, engine)
        uow = partial(SqlUnitOfWork, session_factory)
        redis = Redis(host=settings.redis_host)
        resources.push_async_callback(redis.aclose)
        http = await resources.enter_async_context(aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            connector=aiohttp.TCPConnector(limit=100, ttl_dns_cache=300),
            headers={'X-Riot-Token': settings.riot_key},
        ))
        riot = RiotGateway(RiotAPIFacade(
            RiotAPIConfig(api_key=settings.riot_key), session=http,
            limiter=RiotRateLimiter(redis).acquire,
        ))
        updates = UpdateGateway(redis, settings.redis_host)
        assets = DDragonAssets()
        security = SecurityAdapter(settings.jwt_secret, settings.jwt_minutes)
        services = Services(Accounts(uow, riot, security),
                            Players(uow, riot, updates, assets), updates, assets)
        if not worker:
            await asyncio.to_thread(ensure_ddragon_cached_sync)
            ai_client = OpenAI(api_key=settings.openai_key)
            resources.callback(ai_client.close)
            vector_client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
            resources.push_async_callback(vector_client.close)
            store = VectorStore(vector_client, settings.collection, settings.dimension,
                                settings.namespace, settings.top_k)
            await store.ensure_collection()
            await asyncio.to_thread(initialize_database, engine)
            services.retrieval = Retrieval(AIGateway(ai_client, settings.embedding_model),
                                           VectorGateway(store), PatchGateway(http))
            services.coaching = Coaching(uow, services.retrieval)
        yield services
