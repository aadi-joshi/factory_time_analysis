"""Database session management using SQLModel/SQLAlchemy."""
from sqlmodel import SQLModel, create_engine, Session
from .config import settings
import os

os.makedirs(os.path.dirname(settings.database_url.replace('sqlite:///','')), exist_ok=True)
engine = create_engine(settings.database_url, echo=False)


def init_db():
    from . import models  # ensure models imported
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
