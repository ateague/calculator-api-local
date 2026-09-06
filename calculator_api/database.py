"""Database engine and session management."""

from sqlmodel import Session, SQLModel, create_engine

from calculator_api.config import get_settings

engine = create_engine(get_settings().database_url, echo=False)


def init_db() -> None:
    """Create all database tables."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:  # type: ignore[misc]
    """Yield a database session."""
    with Session(engine) as session:
        yield session
