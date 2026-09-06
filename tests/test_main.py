"""Unit tests for the ``main()`` entry point."""

from unittest.mock import MagicMock

import pytest

import calculator_api.main as main_module


def test_main_calls_uvicorn_run_with_default_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``main()`` threads default Settings values through ``create_app`` and ``uvicorn.run``.

    Args:
        monkeypatch: Pytest fixture used to swap ``create_app`` and
            ``uvicorn.run`` for mocks so no server is actually started.
    """
    mock_app = object()
    mock_create_app = MagicMock(return_value=mock_app)
    mock_uvicorn_run = MagicMock()
    monkeypatch.setattr(main_module, "create_app", mock_create_app)
    monkeypatch.setattr(main_module.uvicorn, "run", mock_uvicorn_run)

    main_module.main()

    mock_create_app.assert_called_once()
    settings_arg = mock_create_app.call_args.args[0]
    assert settings_arg.database_url == "sqlite:///calculator.db"
    assert settings_arg.port == 8000
    mock_uvicorn_run.assert_called_once_with(
        mock_app, host="0.0.0.0", port=8000
    )


def test_main_threads_custom_settings_to_create_app_and_uvicorn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Environment overrides on Settings propagate to ``create_app`` and ``uvicorn.run``.

    Args:
        monkeypatch: Pytest fixture used to set ``DATABASE_URL`` / ``PORT``
            env vars and to swap ``create_app`` / ``uvicorn.run`` for mocks.
    """
    monkeypatch.setenv("DATABASE_URL", "sqlite:///custom.db")
    monkeypatch.setenv("PORT", "9090")
    mock_app = object()
    mock_create_app = MagicMock(return_value=mock_app)
    mock_uvicorn_run = MagicMock()
    monkeypatch.setattr(main_module, "create_app", mock_create_app)
    monkeypatch.setattr(main_module.uvicorn, "run", mock_uvicorn_run)

    main_module.main()

    settings_arg = mock_create_app.call_args.args[0]
    assert settings_arg.database_url == "sqlite:///custom.db"
    assert settings_arg.port == 9090
    mock_uvicorn_run.assert_called_once_with(
        mock_app, host="0.0.0.0", port=9090
    )
