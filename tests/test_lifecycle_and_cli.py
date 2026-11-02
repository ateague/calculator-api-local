"""Lifecycle, configuration, documentation, compatibility, and CLI coverage."""

import importlib
import runpy
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from calculator_api.config import (
    DEFAULT_DATABASE_URL,
    DEFAULT_PORT,
    Settings,
    load_settings,
    validate_port,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_module_app_defers_database_creation_until_lifespan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "module-default.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    api = importlib.import_module("calculator_api.api")

    api = importlib.reload(api)

    assert not database_path.exists()
    with TestClient(api.app) as client:
        assert client.get("/calculations").json() == []
        assert database_path.is_file()
        assert inspect(api.app.state.engine).has_table("calculation")


def test_explicit_app_lifespan_creates_table_only_on_startup(tmp_path: Path) -> None:
    api = importlib.import_module("calculator_api.api")
    database_path = tmp_path / "lifecycle.sqlite3"
    app = api.create_app(Settings(database_url=f"sqlite:///{database_path}"))

    assert not database_path.exists()
    with TestClient(app):
        assert database_path.is_file()
        assert inspect(app.state.engine).has_table("calculation")


def test_app_instances_have_isolated_database_state(tmp_path: Path) -> None:
    api = importlib.import_module("calculator_api.api")
    first_path = tmp_path / "first.sqlite3"
    second_path = tmp_path / "second.sqlite3"
    first_app = api.create_app(Settings(database_url=f"sqlite:///{first_path}"))
    second_app = api.create_app(Settings(database_url=f"sqlite:///{second_path}"))

    with TestClient(first_app) as first_client:
        created = first_client.post(
            "/calculations",
            json={"operation": "add", "a": 1, "b": 2},
        )
        assert created.status_code == 201
        assert len(first_client.get("/calculations").json()) == 1

    with TestClient(second_app) as second_client:
        assert second_client.get("/calculations").json() == []

    assert first_path.is_file()
    assert second_path.is_file()
    assert first_path != second_path


def test_openapi_metadata_and_generated_documentation(app_context) -> None:
    schema = app_context.client.get("/openapi.json")

    assert schema.status_code == 200
    assert schema.json()["info"] == {"title": "Calculator API", "version": "0.1.0"}
    for path in ("/docs", "/docs/oauth2-redirect", "/redoc"):
        response = app_context.client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


def test_session_dependency_closes_session_after_generator_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = importlib.import_module("calculator_api.database")
    events: list[str] = []

    class TrackingSession:
        def __init__(self, engine: Engine) -> None:
            events.append(f"init:{id(engine)}")

        def __enter__(self) -> "TrackingSession":
            events.append("enter")
            return self

        def __exit__(self, *args: object) -> None:
            events.append("exit")

    engine = cast(Engine, object())
    monkeypatch.setattr(database, "Session", TrackingSession)
    dependency = database.create_session_dependency(engine)
    generator: Iterator[Any] = dependency()

    assert next(generator).__class__ is TrackingSession
    with pytest.raises(StopIteration):
        next(generator)
    assert events == [f"init:{id(engine)}", "enter", "exit"]


def test_load_settings_uses_exact_defaults_and_overrides() -> None:
    defaults = load_settings({})
    overridden = load_settings(
        {"PORT": "9123", "DATABASE_URL": "sqlite:////tmp/overridden.sqlite3"}
    )

    assert defaults == Settings(port=DEFAULT_PORT, database_url=DEFAULT_DATABASE_URL)
    assert overridden == Settings(
        port=9123,
        database_url="sqlite:////tmp/overridden.sqlite3",
    )


@pytest.mark.parametrize("value", [1, "1", 65535, "65535"])
def test_validate_port_accepts_boundaries(value: int | str) -> None:
    assert validate_port(value) in {1, 65535}


@pytest.mark.parametrize("value", [True, 1.5, "not-an-integer", 0, 65536, -1])
def test_invalid_ports_raise_exact_error(value: object) -> None:
    with pytest.raises(ValueError, match=r"^PORT must be an integer between 1 and 65535$"):
        validate_port(cast(int | str, value))


@pytest.mark.parametrize("value", ["invalid", "0", "65536"])
def test_load_settings_rejects_invalid_environment_port(value: str) -> None:
    with pytest.raises(ValueError, match=r"^PORT must be an integer between 1 and 65535$"):
        load_settings({"PORT": value})


def test_create_app_without_explicit_settings_loads_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = importlib.import_module("calculator_api.api")
    database_url = f"sqlite:///{tmp_path / 'environment.sqlite3'}"
    monkeypatch.setenv("PORT", "9234")
    monkeypatch.setenv("DATABASE_URL", database_url)

    app = api.create_app()

    assert app.state.settings == Settings(port=9234, database_url=database_url)
    assert not (tmp_path / "environment.sqlite3").exists()


def test_main_invokes_uvicorn_with_validated_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    api = importlib.import_module("calculator_api.api")
    calls: list[tuple[object, dict[str, object]]] = []

    def fake_run(application: object, **kwargs: object) -> None:
        calls.append((application, kwargs))

    monkeypatch.setattr(
        api,
        "load_settings",
        lambda: Settings(port=9345, database_url="sqlite:///unused.sqlite3"),
    )
    monkeypatch.setattr(api.uvicorn, "run", fake_run)

    api.main()

    assert calls == [(api.app, {"host": "0.0.0.0", "port": 9345})]


def test_top_level_core_and_server_shims_preserve_exports(tmp_path: Path) -> None:
    packaged_core = importlib.import_module("calculator_api.core")
    api = importlib.reload(importlib.import_module("calculator_api.api"))
    compatibility_core = importlib.import_module("core")
    server = importlib.reload(importlib.import_module("server"))
    legacy_callable_names = (
        "lifespan",
        "api_add",
        "api_subtract",
        "api_multiply",
        "api_divide",
        "create_calculation",
        "list_calculations",
        "get_calculation",
        "delete_calculation",
    )

    assert compatibility_core.add is packaged_core.add
    assert compatibility_core.subtract is packaged_core.subtract
    assert compatibility_core.multiply is packaged_core.multiply
    assert compatibility_core.divide is packaged_core.divide
    assert server.app is api.app
    assert server.DATABASE_URL == server.app.state.settings.database_url
    assert server.PORT == server.app.state.settings.port
    assert server.get_session is server.app.state.get_session
    assert server.engine is server.app.state.engine
    assert set(server.OPERATIONS) == {"add", "sub", "mul", "div"}
    for name in legacy_callable_names:
        assert callable(getattr(api, name))
        assert getattr(server, name) is getattr(api, name)
        assert name in api.__all__
        assert name in server.__all__

    fresh_app = api.create_app(
        Settings(database_url=f"sqlite:///{tmp_path / 'compatibility.sqlite3'}")
    )
    registered_endpoints = {
        nested_route.endpoint
        for route in fresh_app.routes
        for nested_route in getattr(getattr(route, "original_router", None), "routes", ())
    }
    for name in legacy_callable_names[1:]:
        assert getattr(api, name) in registered_endpoints

    with pytest.raises(AttributeError, match="does_not_exist"):
        getattr(server, "does_not_exist")


def test_server_script_main_guard_launches_delegated_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = importlib.import_module("calculator_api.api")
    calls: list[str] = []

    def fake_main() -> None:
        calls.append("called")

    monkeypatch.setattr(api, "main", fake_main)

    namespace = runpy.run_path(str(REPOSITORY_ROOT / "server.py"), run_name="__main__")

    assert calls == ["called"]
    assert namespace["__name__"] == "__main__"


def test_packaging_and_coverage_configuration_enforce_public_scope() -> None:
    configuration = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text())
    pytest_options = configuration["tool"]["pytest"]["ini_options"]["addopts"]
    coverage = configuration["tool"]["coverage"]

    assert configuration["project"]["scripts"]["calculator-api"] == "calculator_api.api:main"
    assert {
        "--cov=calculator_api",
        "--cov=core",
        "--cov=server",
        "--cov-branch",
        "--cov-report=term-missing",
        "--cov-report=xml",
        "--cov-fail-under=80",
    } <= set(pytest_options)
    assert coverage["run"]["branch"] is True
    assert set(coverage["run"]["source"]) == {"calculator_api", "core", "server"}
    assert coverage["report"]["fail_under"] == 80
    assert coverage["report"]["show_missing"] is True
    assert coverage["xml"]["output"] == "coverage.xml"
    assert "omit" not in coverage["run"]
    assert "exclude_lines" not in coverage["report"]
