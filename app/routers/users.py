from typing import Annotated

from fastapi.exceptions import HTTPException
from fastapi.params import Depends
from fastapi.param_functions import Query
from fastapi.routing import APIRouter

from sqlmodel import select

from ..internal.auth import oauth2_scheme, get_current_active_user
from ..internal.db import SessionDep
from ..internal.models import User, UserResponse


router = APIRouter(
    tags=["Users"]
)


# TODO: Add Role-Based Authorization Check
@router.get("/users")
def get_all_users(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    offset: int = 0,
    limit: Annotated[int, Query(le=100)] = 100
):
    users = session.exec(select(User).offset(offset).limit(limit)).all()
    return {
        "status": 200,
        "message": "Success",
        "users": users
    }


@router.get("/users/me", response_model=UserResponse)
async def get_me(current_user: Annotated[User, Depends(get_current_active_user)]):
    return current_user


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    user_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: SessionDep
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.delete("/users/{user_id}")
def delete_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    user_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: SessionDep
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    session.delete(user)
    session.commit()

    return {
        "status": 200,
        "message": "Success"
    }