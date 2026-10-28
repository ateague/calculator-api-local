"""Tests for process launcher configuration."""

import ast
import tomllib
from pathlib import Path
from unittest.mock import Mock

import pytest

import server


def test_main_uses_default_host_and_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_mock = Mock()
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setattr(server.uvicorn, "run", run_mock)

    server.main()

    run_mock.assert_called_once_with(server.app, host="0.0.0.0", port=8000)


def test_main_accepts_valid_port_override(monkeypatch: pytest.MonkeyPatch) -> None:
    run_mock = Mock()
    monkeypatch.setenv("PORT", "43210")
    monkeypatch.setattr(server.uvicorn, "run", run_mock)

    server.main()

    run_mock.assert_called_once_with(server.app, host="0.0.0.0", port=43210)


@pytest.mark.parametrize("raw_port", ["not-an-integer", "0", "65536", "-7"])
def test_main_rejects_invalid_port_clearly(
    monkeypatch: pytest.MonkeyPatch, raw_port: str
) -> None:
    run_mock = Mock()
    monkeypatch.setenv("PORT", raw_port)
    monkeypatch.setattr(server.uvicorn, "run", run_mock)

    with pytest.raises(ValueError) as exc_info:
        server.main()

    assert str(exc_info.value) == (
        f"Invalid PORT value {raw_port!r}: expected an integer between 1 and 65535"
    )
    run_mock.assert_not_called()


def test_both_launch_paths_share_server_main() -> None:
    server_path = Path(server.__file__)
    project = tomllib.loads((server_path.parent / "pyproject.toml").read_text(encoding="utf-8"))

    assert project["project"]["scripts"]["calculator-api"] == "server:main"

    module = ast.parse(server_path.read_text(encoding="utf-8"))
    module_guards = [
        node
        for node in module.body
        if isinstance(node, ast.If) and ast.unparse(node.test) == "__name__ == '__main__'"
    ]
    assert len(module_guards) == 1
    guard_body = module_guards[0].body
    assert len(guard_body) == 1
    assert ast.unparse(guard_body[0]) == "main()"
