"""SQLAlchemy mühərriki və sessiya."""
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None):
    url = url or settings().database_url
    if url.startswith(('postgres://', 'postgresql://')):          # Render/Neon formatı -> psycopg 3
        url = 'postgresql+psycopg://' + url.split('://', 1)[1]
    if url.startswith('sqlite:///'):
        Path(url.removeprefix('sqlite:///')).parent.mkdir(parents=True, exist_ok=True)
    # PostgreSQL: Neon/PgBouncer (tranzaksiya rejimi) server tərəfli hazırlanmış sorğuları dəstəkləmir – söndürülür
    args = {'check_same_thread': False} if url.startswith('sqlite') else {'prepare_threshold': None}
    pool = {} if url.startswith('sqlite') else {'pool_size': settings().db_pool_size,
                                                  'max_overflow': settings().db_max_overflow, 'pool_timeout': 20}
    eng = create_engine(url, connect_args=args, pool_pre_ping=True, pool_recycle=300, **pool)
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
