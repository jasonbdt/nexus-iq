"""Optional isolated backend for checking real frontend proxies without application data."""
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

from app.bootstrap import initialize_database
from app.main import create_app as create_api
from tests.factories import active_user, match
from tests.support import build_services
from tests.unit.test_assets import write_metadata


def create_app():
    """Run with uvicorn --factory tests.proxy_app:create_app in a temporary container."""
    temporary = TemporaryDirectory(prefix='nexusiq-proxy-')
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False},
                           poolclass=StaticPool)
    initialize_database(engine)
    services = build_services(engine, Path(temporary.name))
    write_metadata(services.assets.root)
    active_user(services)
    with services.players.uow() as work:
        work.matches.save(match())
        work.commit()
    application = create_api(services)
    @asynccontextmanager
    async def lifespan(_application):
        try:
            yield
        finally:
            engine.dispose()
            temporary.cleanup()
    application.router.lifespan_context = lifespan
    return application
