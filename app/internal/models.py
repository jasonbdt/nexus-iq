from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlmodel import Column, Field, SQLModel
from pydantic import BaseModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    avatarName: str = Field(index=True, nullable=False)
    emailAddress: str = Field(unique=True, nullable=False)
    password: str = Field(nullable=False)
    is_active: bool = Field(default=False)

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False
        )
    )
    updated_at: Optional[datetime] = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now()
        )
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
