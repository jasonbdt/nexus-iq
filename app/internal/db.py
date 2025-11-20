from typing import Annotated

from fastapi import Depends
from sqlmodel import create_engine, Session, SQLModel

from ..dependencies import DATABASE_URL
from .logging import get_logger
from .models import User

logger = get_logger(__name__)

try:
    engine = create_engine(DATABASE_URL, echo=True)
except Exception as err:
    print("Error", err)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables created successfully")


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
