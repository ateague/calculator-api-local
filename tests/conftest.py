"""Shared fixtures for isolated calculator API integration tests."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

import server


@dataclass(frozen=True)
class CalculatorApi:
    """A running calculator application bound to an isolated database."""

    client: TestClient
    app: FastAPI
    engine: Engine
    database_path: Path


@pytest.fixture
def calculator_api(tmp_path: Path) -> Iterator[CalculatorApi]:
    """Run one application lifespan against a unique file-backed SQLite database."""
    database_path = tmp_path / "calculator-test.sqlite3"
    application = server.create_app(f"sqlite:///{database_path}")
    application_engine: Engine = application.state.engine

    try:
        with TestClient(application) as client:
            yield CalculatorApi(
                client=client,
                app=application,
                engine=application_engine,
                database_path=database_path,
            )
    finally:
        application_engine.dispose()


@pytest.fixture
def client(calculator_api: CalculatorApi) -> TestClient:
    """Return the client for the current isolated application."""
    return calculator_api.client


@pytest.fixture
def app(calculator_api: CalculatorApi) -> FastAPI:
    """Return the current isolated application."""
    return calculator_api.app


@pytest.fixture
def engine(calculator_api: CalculatorApi) -> Engine:
    """Return the engine owned by the current isolated application."""
    return calculator_api.engine


@pytest.fixture
def database_path(calculator_api: CalculatorApi) -> Path:
    """Return the temporary database path for the current isolated application."""
    return calculator_api.database_path
