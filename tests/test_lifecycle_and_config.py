"""Application lifecycle, construction, session, and process configuration tests."""

import tomllib
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, inspect
from sqlalchemy.engine import Engine
from sqlmodel import select
from starlette.requests import Request

import server
from server import Calculation


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_lifespan_creates_calculation_table(tmp_path: Path) -> None:
    selected_engine = server.build_engine(
        f"sqlite:///{tmp_path / 'lifespan-calculations.sqlite3'}"
    )
    selected_app = server.create_app(selected_engine)

    try:
        assert "calculation" not in inspect(selected_engine).get_table_names()
        with TestClient(selected_app):
            assert "calculation" in inspect(selected_engine).get_table_names()
    finally:
        selected_app.dependency_overrides.clear()
        selected_engine.dispose()


def test_get_session_yields_usable_session_and_releases_connection(
    application: FastAPI, client: TestClient, database_engine: Engine
) -> None:
    connection_events: list[str] = []

    def record_checkout(*_args: object) -> None:
        connection_events.append("checkout")

    def record_checkin(*_args: object) -> None:
        connection_events.append("checkin")

    event.listen(database_engine, "checkout", record_checkout)
    event.listen(database_engine, "checkin", record_checkin)
    request = Request({"type": "http", "app": application})
    dependency = server.get_session(request)

    try:
        session = next(dependency)
        assert list(session.exec(select(Calculation)).all()) == []
        assert connection_events == ["checkout"]

        with pytest.raises(StopIteration):
            next(dependency)

        assert connection_events == ["checkout", "checkin"]
    finally:
        dependency.close()
        event.remove(database_engine, "checkout", record_checkout)
        event.remove(database_engine, "checkin", record_checkin)


def test_build_engine_uses_explicit_database_url(tmp_path: Path) -> None:
    explicit_url = f"sqlite:///{tmp_path / 'explicit.sqlite3'}"
    selected_engine = server.build_engine(explicit_url)

    try:
        assert str(selected_engine.url) == explicit_url
    finally:
        selected_engine.dispose()


def test_build_engine_uses_default_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    selected_engine = server.build_engine()

    try:
        assert str(selected_engine.url) == server.DATABASE_URL
    finally:
        selected_engine.dispose()


def test_build_engine_uses_environment_database_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    environment_url = f"sqlite:///{tmp_path / 'environment.sqlite3'}"
    monkeypatch.setenv("DATABASE_URL", environment_url)
    selected_engine = server.build_engine()

    try:
        assert str(selected_engine.url) == environment_url
    finally:
        selected_engine.dispose()


def test_module_exposes_constructed_application() -> None:
    assert isinstance(server.app, FastAPI)
    assert server.app.state.engine is server.engine
    assert server.app.title == "Calculator API"


def test_create_app_binds_selected_engine(database_engine: Engine) -> None:
    selected_app = server.create_app(database_engine)

    assert selected_app.state.engine is database_engine
    assert selected_app.title == "Calculator API"
    assert selected_app.version == "0.1.0"
    assert {route.path for route in selected_app.routes}.issuperset(
        {"/add", "/subtract", "/multiply", "/divide", "/calculations"}
    )


@pytest.mark.parametrize(
    ("configured_port", "expected_port"),
    [
        pytest.param(None, 8000, id="default-port"),
        pytest.param("9123", 9123, id="overridden-port"),
    ],
)
def test_main_runs_uvicorn_with_selected_port(
    monkeypatch: pytest.MonkeyPatch,
    configured_port: str | None,
    expected_port: int,
) -> None:
    run = Mock()
    monkeypatch.setattr(server.uvicorn, "run", run)
    if configured_port is None:
        monkeypatch.delenv("PORT", raising=False)
    else:
        monkeypatch.setenv("PORT", configured_port)

    server.main()

    run.assert_called_once_with(server.app, host="0.0.0.0", port=expected_port)


def test_main_rejects_invalid_port_before_starting_uvicorn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = Mock()
    monkeypatch.setattr(server.uvicorn, "run", run)
    monkeypatch.setenv("PORT", "not-an-integer")

    with pytest.raises(ValueError):
        server.main()

    run.assert_not_called()


def test_main_is_the_declared_console_callable() -> None:
    project_configuration = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert callable(server.main)
    console_callable = project_configuration["project"]["scripts"]["calculator-api"]
    assert console_callable == "server:main"
