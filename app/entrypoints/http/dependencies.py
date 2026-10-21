"""FastAPI dependency wiring at the application boundary."""
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer

from app.bootstrap import Services
from app.domain.models import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='login')
oauth2_optional = OAuth2PasswordBearer(tokenUrl='login', auto_error=False)


def get_services(request: Request) -> Services:
    """Return the application-scoped composition, replaceable in factory tests."""
    return request.app.state.services


ServicesDep = Annotated[Services, Depends(get_services)]


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], services: ServicesDep) -> User:
    """Resolve credentials through the account use case."""
    return services.accounts.authenticate(token)


def get_current_active_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Retain the current inactive-account error contract."""
    if not user.is_active:
        raise HTTPException(status_code=400, detail='Inactive User')
    return user


def get_current_user_optional(token: Annotated[str | None, Depends(oauth2_optional)],
                              services: ServicesDep) -> User | None:
    """Preserve anonymous access even when a supplied token is invalid."""
    return services.accounts.authenticate(token, optional=True)


def require_role(*roles: UserRole):
    """Keep role authorization in the HTTP boundary."""
    def check(user: Annotated[User, Depends(get_current_active_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail='Insufficient permissions')
        return user
    return check


CurrentUser = Annotated[User, Depends(get_current_active_user)]
