"""Functional tests for both real application launcher paths."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).parents[3]
PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
CONSOLE = REPO_ROOT / ".venv" / "bin" / "calculator-api"
SERVER = REPO_ROOT / "server.py"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _exercise_and_stop(
    command: list[str], cwd: Path, env: dict[str, str], port: int
) -> tuple[int, str, str, requests.Response]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    print(f"launcher PID={process.pid} command={command[0]}")
    response = None
    deadline = time.monotonic() + 15
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            try:
                candidate = requests.post(
                    f"http://127.0.0.1:{port}/calculations",
                    json={"operation": "mul", "a": 7, "b": 6},
                    timeout=0.5,
                )
                if candidate.status_code == 201:
                    response = candidate
                    break
            except requests.RequestException:
                pass
            time.sleep(0.05)
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=10)
    if response is None:
        raise AssertionError(
            f"launcher did not serve a persisted calculation\n{stdout}{stderr}"
        )
    return process.returncode, stdout, stderr, response


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
    port = _free_port()
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

