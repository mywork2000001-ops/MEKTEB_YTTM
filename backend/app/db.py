"""SQLAlchemy mühərriki və sessiya."""
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None):
    url = url or settings().database_url
    if url.startswith('sqlite:///'):
        Path(url.removeprefix('sqlite:///')).parent.mkdir(parents=True, exist_ok=True)
    eng = create_engine(url, connect_args={'check_same_thread': False} if url.startswith('sqlite') else {})
    if url.startswith('sqlite'):
        @event.listens_for(eng, 'connect')
        def _fk(conn, _):
            conn.execute('PRAGMA foreign_keys=ON')
    return eng


engine = make_engine()
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
