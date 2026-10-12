from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


# pre_ping replaces connections the database or network dropped; recycle keeps
# them younger than typical idle timeouts on hosted PostgreSQL.
engine = create_engine(get_settings().database_url, pool_pre_ping=True, pool_recycle=1800, pool_size=5, max_overflow=5)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
