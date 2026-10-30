"""Functional tests for both real application launcher paths."""

from __future__ import annotations

import os
from pathlib import Path

import requests
from server_runner import ServerRunner, free_port

REPO_ROOT = Path(__file__).parents[3]
PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
CONSOLE = REPO_ROOT / ".venv" / "bin" / "calculator-api"
SERVER = REPO_ROOT / "server.py"


def _exercise_and_stop(
    command: list[str], cwd: Path, env: dict[str, str], port: int
) -> tuple[int, str, str, requests.Response]:
    with ServerRunner(
        command,
        cwd=cwd,
        env=env,
        port=port,
        label="launcher",
    ) as server:
        response = server.wait_until_ready(
            lambda: requests.post(
                f"{server.base_url}/calculations",
                json={"operation": "mul", "a": 7, "b": 6},
                timeout=0.5,
            ),
            lambda candidate: candidate.status_code == 201,
        )
    result = server.result
    return result.returncode, result.stdout, result.stderr, response


def test_direct_script_uses_default_port_and_database(tmp_path: Path, record_cli) -> None:
    env = os.environ.copy()
    env.pop("PORT", None)
    env.pop("DATABASE_URL", None)
    returncode, stdout, stderr, response = _exercise_and_stop(
        [str(PYTHON), str(SERVER)], tmp_path, env, 8000
    )
    record_cli(
        "test_direct_script_uses_default_port_and_database",
        returncode,
        stdout,
        stderr,
    )
    assert returncode == 0
    assert response.json()["result"] == 42.0
    assert (tmp_path / "calculator.db").exists()
    assert "http://0.0.0.0:8000" in stderr


def test_console_launcher_uses_overridden_port_and_database(
    tmp_path: Path, record_cli
) -> None:
    port = free_port()
    database_path = tmp_path / "overridden-calculator.db"
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["DATABASE_URL"] = f"sqlite:///{database_path}"
    returncode, stdout, stderr, response = _exercise_and_stop(
        [str(CONSOLE)], tmp_path, env, port
    )
    record_cli(
        "test_console_launcher_uses_overridden_port_and_database",
        returncode,
        stdout,
        stderr,
    )
    assert returncode == 0
    assert response.json()["result"] == 42.0
    assert database_path.exists()
    assert not (tmp_path / "calculator.db").exists()
    assert f"http://0.0.0.0:{port}" in stderr
