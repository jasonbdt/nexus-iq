"""FastAPI application factory; importing this module opens no external resources."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.bootstrap import Services, open_services
from app.domain.errors import ApplicationError, Forbidden, NotFound, Unauthenticated
from app.entrypoints.http import routes, sse, cdn
from app.entrypoints.http.dependencies import ServicesDep


def create_app(services: Services | None = None) -> FastAPI:
    """Build an isolated API, optionally using fake or test-scoped application ports."""
    @asynccontextmanager
    async def lifespan(application):
        if services is not None:
            yield
        else:
            async with open_services() as runtime:
                application.state.services = runtime
                yield

    application = FastAPI(root_path='/api/v1', lifespan=lifespan, redoc_url=None)
    if services is not None:
        application.state.services = services
    application.add_middleware(CORSMiddleware, allow_origins=['*'],
                               allow_methods=['*'], allow_headers=['*'])
    for router in (routes.router, sse.router, cdn.router):
        application.include_router(router)

    @application.exception_handler(ApplicationError)
    async def application_error(_request: Request, error: ApplicationError):
        status = 400
        if isinstance(error, NotFound):
            status = 404
        elif isinstance(error, Forbidden):
            status = 403
        elif isinstance(error, Unauthenticated):
            status = 401
        headers = {'WWW-Authenticate': 'Bearer'} if status == 401 else None
        return JSONResponse({'detail': str(error)}, status_code=status, headers=headers)

    @application.get('/')
    def index():
        """Preserve the existing health response."""
        return {'status': 200, 'message': "It work's!"}

    @application.get('/health/redis')
    async def redis_health(runtime: ServicesDep):
        """Await the Redis health query on the owned asynchronous client."""
        return {'status': 'ok' if await runtime.updates.client.ping() else 'not ok'}

    return application


app = create_app()
