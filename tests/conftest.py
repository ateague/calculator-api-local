"""Shared deterministic fixtures for the Calculator API test suite."""

from collections.abc import Iterator
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from calculator_api.config import Settings


@dataclass(frozen=True, slots=True)
class AppContext:
    """Resources owned by one isolated API test."""

    app: FastAPI
    client: TestClient

    @property
    def engine(self) -> Engine:
        """Return the app-bound engine with its concrete public type."""
        return cast(Engine, self.app.state.engine)


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep every relative runtime artifact inside that test's temporary directory."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'default.sqlite3'}")
    monkeypatch.setenv("PORT", "8000")
    yield


@pytest.fixture
def app_context(tmp_path: Path) -> Iterator[AppContext]:
    """Yield a new lifespan-active app backed by one unique SQLite file."""
    api = import_module("calculator_api.api")
    database_path = tmp_path / "calculator.sqlite3"
    settings = Settings(database_url=f"sqlite:///{database_path}")
    app = api.create_app(settings)

    assert not database_path.exists()
    with TestClient(app) as client:
        assert database_path.is_file()
        yield AppContext(app=app, client=client)
