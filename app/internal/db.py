from typing import Annotated
import os

from fastapi import Depends
from sqlmodel import create_engine, Session, SQLModel
from dotenv import load_dotenv

from app.internal.models import User
load_dotenv()

DB_USER = os.getenv("DATABASE_USER")
DB_NAME = os.getenv("DATABASE_NAME")
DB_PASSWORD = os.getenv("DATABASE_PASSWORD")
DATABASE_URL=f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@nexus-iq-database-1/{DB_NAME}"

try:
    engine = create_engine(DATABASE_URL, echo=True)
except Exception as err:
    print("Error", err)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
