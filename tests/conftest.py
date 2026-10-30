"""Shared fixtures for isolated Calculator API behavior tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

import server


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_DATABASE = PROJECT_ROOT / "calculator.db"


def _database_identity(path: Path) -> tuple[int, int, int] | None:
    """Return stable metadata used to detect accidental database changes."""
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_ino, stat.st_size, stat.st_mtime_ns


@pytest.fixture(autouse=True)
def isolate_process_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[None]:
    """Keep environment, dependency state, and relative SQLite files isolated."""
    repository_database_before = _database_identity(REPOSITORY_DATABASE)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    server.app.dependency_overrides.clear()

    yield

    server.app.dependency_overrides.clear()
    assert _database_identity(REPOSITORY_DATABASE) == repository_database_before


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    """Return a fresh on-disk SQLite URL owned by the current test."""
    return f"sqlite:///{tmp_path / 'calculator-test.sqlite3'}"


@pytest.fixture
def database_engine(database_url: str) -> Iterator[Engine]:
    """Build and dispose the current test's isolated database engine."""
    selected_engine = server.build_engine(database_url)
    try:
        yield selected_engine
    finally:
        selected_engine.dispose()


@pytest.fixture
def application(database_engine: Engine) -> Iterator[FastAPI]:
    """Create an application bound only to the current test engine."""
    selected_app = server.create_app(database_engine)
    try:
        yield selected_app
    finally:
        selected_app.dependency_overrides.clear()


@pytest.fixture
def client(application: FastAPI) -> Iterator[TestClient]:
    """Run lifespan for an isolated application and expose its test client."""
    with TestClient(application) as test_client:
        yield test_client
