"""Database engine, session factory, and startup helpers."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import create_engine, Session, SQLModel, select

from ..dependencies import DATABASE_URL
from .logging import get_logger
from .models import Role, UserRole

logger = get_logger(__name__)

try:
    engine = create_engine(DATABASE_URL)
except SQLAlchemyError as err:
    print("Error", err)


def seed_roles() -> None:
    """Ensure default roles exist in the roles table."""
    with Session(engine) as session:
        existing = session.exec(select(Role)).all()
        if existing:
            return
        for role in UserRole:
            session.add(Role(name=role.value))
        session.commit()
    logger.debug("Roles table seeded successfully")


def create_db_and_tables() -> None:
    """Create all database tables and seed initial data."""
    SQLModel.metadata.create_all(engine)
    seed_roles()
    logger.debug("Database tables created successfully")


def get_session():
    """Yield a database session for use as a FastAPI dependency."""
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
