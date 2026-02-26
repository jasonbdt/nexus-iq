from typing import Annotated

from fastapi import Depends
from sqlmodel import create_engine, Session, SQLModel, select

from ..dependencies import DATABASE_URL
from .logging import get_logger
from .models import User, Role, UserRole, UserRoleLink

logger = get_logger(__name__)

try:
    engine = create_engine(DATABASE_URL)
except Exception as err:
    print("Error", err)


def seed_roles() -> None:
    """Ensure default roles exist in the roles table."""
    with Session(engine) as session:
        existing = session.exec(select(Role)).all()
        if existing:
            return
        for r in UserRole:
            session.add(Role(name=r.value))
        session.commit()
    logger.debug("Roles table seeded successfully")


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    seed_roles()
    logger.debug("Database tables created successfully")


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
