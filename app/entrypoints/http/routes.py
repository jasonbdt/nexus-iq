"""Thin REST entrypoints preserving the existing frontend contracts."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from app.domain.errors import NotFound
from app.domain.models import User, UserRole
from .dependencies import (
    CurrentUser, ServicesDep, get_current_user_optional, require_role,
)
from .schemas import (
    UserSignUpRequest, UserResponse, UserUpdateRequest, LinkSummonerRequest,
    SummonerSearch, MatchesRead, CoachSessionCreate, CoachSessionRead,
    Token, UpdateQueued,
)

router = APIRouter()


@router.post('/register', response_model=UserResponse, tags=['Authentication'])
async def register(payload: UserSignUpRequest, services: ServicesDep):
    """Register the user, role and primary player account atomically."""
    return await services.accounts.register(payload.model_dump())


@router.post('/login', response_model=Token, tags=['Authentication'])
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], services: ServicesDep):
    """Accept the existing form-encoded OAuth2 login."""
    return services.accounts.login(form.username, form.password)


@router.get('/users', tags=['Users'])
def list_users(services: ServicesDep,
               _user: Annotated[User, Depends(require_role(
                   UserRole.ADMINISTRATOR, UserRole.MODERATOR))],
               offset: int = 0, limit: Annotated[int, Query(le=100)] = 100):
    """List public user projections for administrators and moderators."""
    return services.accounts.list(offset, limit)


@router.get('/users/me', response_model=UserResponse, tags=['Users'])
def get_me(user: CurrentUser, services: ServicesDep):
    """Return the current user's complete profile."""
    return services.accounts.get(user.id)


@router.patch('/users/me', response_model=UserResponse, tags=['Users'])
def update_me(payload: UserUpdateRequest, user: CurrentUser, services: ServicesDep):
    """Update profile settings using the existing request fields."""
    return services.accounts.update(user.id, payload.model_dump())


@router.post('/users/me/link-summoner', response_model=UserResponse, tags=['Users'])
async def link_summoner(payload: LinkSummonerRequest, user: CurrentUser, services: ServicesDep):
    """Link an account after checking premium rules and cooldown."""
    return await services.accounts.link(user.id, payload.model_dump())


@router.delete('/users/me/summoner-links/{link_id}', response_model=UserResponse, tags=['Users'])
def unlink_summoner(link_id: int, user: CurrentUser, services: ServicesDep):
    """Remove an additional account owned by the current user."""
    return services.accounts.unlink(user.id, link_id)


@router.get('/users/{user_id}', response_model=UserResponse, tags=['Users'])
def get_user(user_id: int, services: ServicesDep, _user: CurrentUser):
    """Retain the authenticated by-ID user lookup."""
    return services.accounts.get(user_id)


@router.delete('/users/{user_id}', tags=['Users'])
def delete_user(user_id: int, services: ServicesDep, _user: CurrentUser):
    """Retain the existing authorization behavior of the delete route."""
    return services.accounts.delete(user_id)


@router.get('/search/{tag_line}/{game_name}', response_model=SummonerSearch,
            response_model_exclude_none=True, tags=['Summoners'])
async def search(tag_line: str, game_name: str, services: ServicesDep,
                 _user: Annotated[User | None, Depends(get_current_user_optional)]):
    """Find a profile while keeping the legacy message-style not-found response."""
    try:
        return await services.players.search(game_name, tag_line)
    except NotFound as error:
        return JSONResponse({'message': str(error)}, status_code=404)


@router.patch('/update/{puuid}', response_model=UpdateQueued, tags=['Summoners'])
def update(puuid: str, services: ServicesDep, _user: CurrentUser, match_count: int = 100):
    """Queue an update and preserve the actual frontend response, not the old annotation."""
    services.updates.enqueue(puuid, match_count)
    return {'message': 'Update queued'}


@router.get('/matches', tags=['Matches'])
def matches_index():
    """Keep the existing match API health response."""
    return {'message': 'It works'}


@router.get('/matches/{region}/by-id/{match_id}', response_model=MatchesRead, tags=['Matches'])
def match_by_id(region: str, match_id: str, services: ServicesDep):
    """Return a stored match (the existing lookup does not filter by region)."""
    del region
    return services.players.match(match_id)


@router.get('/matches/{region}/by-puuid/{puuid}', response_model=list[MatchesRead], tags=['Matches'])
def recent_matches(region: str, puuid: str, services: ServicesDep, match_count: int = 10):
    """Return a player's recent matches."""
    del region
    return services.players.recent(puuid, match_count)


@router.get('/coach/sessions', response_model=list[CoachSessionRead], tags=['Coach'])
def list_sessions(user: CurrentUser, services: ServicesDep):
    """List the current user's conversation metadata."""
    return services.coaching.list(user.id)


@router.post('/coach/sessions', response_model=CoachSessionRead, status_code=201, tags=['Coach'])
def create_session(payload: CoachSessionCreate, user: CurrentUser, services: ServicesDep):
    """Create an empty conversation."""
    return services.coaching.create(user.id, payload.title)


@router.get('/coach/sessions/{session_id}', response_model=CoachSessionRead, tags=['Coach'])
def get_session(session_id: int, user: CurrentUser, services: ServicesDep):
    """Read the owned conversation with its messages."""
    return services.coaching.get(session_id, user.id)


@router.patch('/coach/sessions/{session_id}', response_model=CoachSessionRead, tags=['Coach'])
def rename_session(session_id: int, payload: CoachSessionCreate,
                   user: CurrentUser, services: ServicesDep):
    """Rename an owned conversation."""
    return services.coaching.rename(session_id, user.id, payload.title)


@router.delete('/coach/sessions/{session_id}', status_code=204, tags=['Coach'])
def delete_session(session_id: int, user: CurrentUser, services: ServicesDep):
    """Delete the owned conversation and all messages."""
    services.coaching.delete(session_id, user.id)


@router.get('/patches', tags=['RAG'])
async def patches(services: ServicesDep):
    """List available patch notes."""
    return {'patches': await services.retrieval.patches.list()}


@router.post('/ingest/{patch_version}', tags=['RAG'])
async def ingest(patch_version: str, services: ServicesDep):
    """Ingest a patch while retaining the existing message response shape."""
    payload, status = await services.retrieval.ingest(patch_version)
    return JSONResponse(payload, status_code=status)


@router.post('/query', tags=['RAG'])
async def query(question: str, services: ServicesDep, top_k: int = 5):
    """Answer a stateless patch-notes question."""
    context = await services.retrieval.context(question, top_k)
    return {'message': services.retrieval.ai.answer(question, context)}
