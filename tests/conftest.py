"""Shared fixtures for isolated calculator API integration tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import Settings, create_app, create_database_engine


@pytest.fixture
def repository_database_guard() -> Iterator[Path]:
    """Fail if a test creates or changes the repository's runtime database."""
    database_path = Path(__file__).resolve().parents[1] / "calculator.db"
    existed = database_path.exists()
    before_bytes = database_path.read_bytes() if existed else None
    before_stat = database_path.stat() if existed else None

    yield database_path

    if existed:
        assert database_path.exists()
        assert database_path.read_bytes() == before_bytes
        assert database_path.stat() == before_stat
    else:
        assert not database_path.exists()


@pytest.fixture
def client(tmp_path: Path, repository_database_guard: Path) -> Iterator[TestClient]:
    """Run an app lifespan against a unique file-backed temporary database."""
    database_path = tmp_path / "calculator-test.db"
    database_url = f"sqlite:///{database_path}"
    engine = create_database_engine(database_url)
    application = create_app(
        engine=engine,
        settings=Settings(database_url=database_url),
    )

    try:
        with TestClient(application) as test_client:
            yield test_client
    finally:
        engine.dispose()
