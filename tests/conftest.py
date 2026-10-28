"""Shared fixtures for isolated calculator API tests."""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import create_app

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[1] / "calculator.db"


@pytest.fixture(scope="session", autouse=True)
def default_database_remains_absent() -> Generator[None, None, None]:
    """Guard against tests accidentally using the developer database."""
    assert not DEFAULT_DATABASE_PATH.exists(), "calculator.db must be absent before tests"
    yield
    assert not DEFAULT_DATABASE_PATH.exists(), "calculator.db must remain absent after tests"


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    """Return a unique file-backed SQLite path for one test."""
    return tmp_path / "calculator-test.db"


@pytest.fixture
def app(database_path: Path) -> Generator[FastAPI, None, None]:
    """Build an application with an engine owned by one test."""
    application = create_app(f"sqlite:///{database_path}")
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Run application lifespan for every client-backed test."""
    with TestClient(app) as test_client:
        yield test_client
