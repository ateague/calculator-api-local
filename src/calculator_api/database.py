"""Database engine and request-session construction."""

from collections.abc import Callable, Iterator

from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

SessionDependency = Callable[[], Iterator[Session]]


def create_db_engine(database_url: str) -> Engine:
    """Create an engine for the configured database URL."""
    return create_engine(database_url, echo=False)


def create_session_dependency(engine: Engine) -> SessionDependency:
    """Build a FastAPI dependency whose sessions are bound to ``engine``."""

    def get_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    return get_session


__all__ = ["SessionDependency", "create_db_engine", "create_session_dependency"]
