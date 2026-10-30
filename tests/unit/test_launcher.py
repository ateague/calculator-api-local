"""Unit tests for environment settings and the Uvicorn launch boundary."""

import runpy
from unittest.mock import Mock

import pytest

import server


def test_load_settings_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("PORT", raising=False)

    assert server.load_settings() == server.Settings(
        database_url="sqlite:///calculator.db", port=8000
    )


def test_load_settings_uses_custom_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/custom-calculator.db")
    monkeypatch.delenv("PORT", raising=False)

    assert server.load_settings() == server.Settings(
        database_url="sqlite:////tmp/custom-calculator.db", port=8000
    )


def test_load_settings_converts_valid_port_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("PORT", "9123")

    assert server.load_settings() == server.Settings(
        database_url="sqlite:///calculator.db", port=9123
    )


def test_load_settings_rejects_invalid_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "not-a-port")

    with pytest.raises(ValueError):
        server.load_settings()


@pytest.mark.parametrize(("port_value", "expected_port"), [(None, 8000), ("9123", 9123)])
def test_main_runs_uvicorn_with_app_host_and_port(
    monkeypatch: pytest.MonkeyPatch, port_value: str | None, expected_port: int
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    if port_value is None:
        monkeypatch.delenv("PORT", raising=False)
    else:
        monkeypatch.setenv("PORT", port_value)
    run_mock = Mock()
    monkeypatch.setattr(server.uvicorn, "run", run_mock)

    server.main()

    run_mock.assert_called_once_with(server.app, host="0.0.0.0", port=expected_port)


def test_direct_script_guard_launches_its_fastapi_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    run_mock = Mock()
    monkeypatch.setattr(server.uvicorn, "run", run_mock)

    script_path = server.__file__
    assert script_path is not None
    script_globals = runpy.run_path(script_path, run_name="__main__")

    run_mock.assert_called_once_with(script_globals["app"], host="0.0.0.0", port=8000)
