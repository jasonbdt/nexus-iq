from typing import Optional
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlmodel import Column, Field, SQLModel
from pydantic import BaseModel


class User(SQLModel, table=True):
    __tablename__ = "users"
    _time_factory = datetime.now()

    id: int | None = Field(default=None, primary_key=True)
    avatarName: str = Field(index=True, nullable=False)
    emailAddress: str = Field(unique=True, nullable=False)
    password: str = Field(nullable=False)
    is_active: bool = Field(default=False)
    created_at: datetime = Field(default=_time_factory)
    updated_at: Optional[datetime] = Field(
        default=_time_factory,
        sa_column=Column(DateTime(), onupdate=func.now())
    )


class UserSignUpRequest(BaseModel):
    avatarName: str
    emailAddress: str
    password: str
    password_confirm: str


class UserResponse(BaseModel):
    avatarName: str
    emailAddress: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
