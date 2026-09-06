"""Unit tests for the ``Settings`` configuration class."""

import pytest

from calculator_api.config import Settings


def test_settings_default_database_url() -> None:
    """``Settings.database_url`` defaults to the SQLite file URL when no env var is set."""
    settings = Settings()
    assert settings.database_url == "sqlite:///calculator.db"


def test_settings_default_port() -> None:
    """``Settings.port`` defaults to 8000 when no env var is set."""
    settings = Settings()
    assert settings.port == 8000


def test_settings_port_is_int_type() -> None:
    """``Settings.port`` is coerced to ``int`` by pydantic."""
    settings = Settings()
    assert isinstance(settings.port, int)


def test_settings_database_url_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ``DATABASE_URL`` environment variable overrides the default URL.

    Args:
        monkeypatch: Pytest fixture used to temporarily set the ``DATABASE_URL``
            environment variable for this test only.
    """
    monkeypatch.setenv("DATABASE_URL", "sqlite:///custom.db")
    settings = Settings()
    assert settings.database_url == "sqlite:///custom.db"


def test_settings_port_env_override_is_coerced(monkeypatch: pytest.MonkeyPatch) -> None:
    """A string ``PORT`` env value is coerced to ``int`` by pydantic-settings.

    Args:
        monkeypatch: Pytest fixture used to temporarily set the ``PORT``
            environment variable for this test only.
    """
    monkeypatch.setenv("PORT", "9090")
    settings = Settings()
    assert settings.port == 9090
    assert isinstance(settings.port, int)
