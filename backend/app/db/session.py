"""
Database engine + session management.

`get_db` is a FastAPI dependency that yields a session and always closes it,
even if the request raises. Swapping SQLite for Postgres is just an
environment variable change (DATABASE_URL) — nothing here needs to change.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Registering these listeners here — where the Session is created — is what
# makes synchronization structural rather than a convention. Every write, from
# every code path including ones not written yet, announces itself to every
# connected client. Imported for its side effect; there is nothing to call.
from app.db import sync_hooks  # noqa: E402,F401  (import placement is deliberate)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
