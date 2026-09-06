"""Shared pytest fixtures for the Calculator API test suite."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from calculator_api.app import create_app
from calculator_api.database import get_session


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    """Provide a SQLModel session bound to a fresh in-memory SQLite database.

    A new engine is created per test so each test starts with an empty
    schema and no state leaks between tests. ``StaticPool`` keeps the
    single in-memory database shared across the session's connections.

    Yields:
        A SQLModel ``Session`` scoped to the current test.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    """Provide a FastAPI ``TestClient`` wired to the in-memory test session.

    The ``get_session`` dependency is overridden so route handlers receive
    the per-test session created by :func:`session_fixture`. Overrides are
    cleared after the test to prevent leakage.

    Args:
        session: The per-test SQLModel session provided by
            :func:`session_fixture`.

    Yields:
        A ``TestClient`` targeting a freshly created application instance.
    """
    app = create_app()

    def get_session_override() -> Generator[Session, None, None]:
        """Yield the test session in place of the real dependency.

        Yields:
            The per-test SQLModel session.
        """
        yield session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
