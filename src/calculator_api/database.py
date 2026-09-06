"""Database engine and session management."""

from collections.abc import Generator

from sqlmodel import Session, create_engine

engine = None


def init_engine(database_url: str) -> None:
    """Create the global SQLAlchemy engine.

    Args:
        database_url: SQLAlchemy database connection URL.
    """
    global engine
    engine = create_engine(database_url, echo=False)


def get_session() -> Generator[Session, None, None]:
    """Yield a database session for use as a FastAPI dependency.

    Yields:
        A SQLModel session bound to the global engine.

    Raises:
        RuntimeError: If the engine has not been initialized via
            ``init_engine``.
    """
    if engine is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")
    with Session(engine) as session:
        yield session
