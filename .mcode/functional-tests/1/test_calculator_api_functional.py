"""Live functional tests for the calculator API modernization milestone."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parents[3]
BASE_URL = os.environ.get("CALCULATOR_API_BASE_URL", "http://127.0.0.1:18080")
DEFAULT_DATABASE = REPO_ROOT / "calculator.db"
EVIDENCE_PATH = Path(__file__).with_name("evidence.json")
REQUEST_TIMEOUT = 10


def _save_evidence(name: str, evidence: dict[str, Any]) -> None:
    existing = json.loads(EVIDENCE_PATH.read_text()) if EVIDENCE_PATH.exists() else {}
    existing[name] = evidence
    EVIDENCE_PATH.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n")


def _record_rest(
    name: str,
    response: requests.Response,
    *,
    endpoint: str,
    method: str,
    request_body: str = "",
) -> None:
    _save_evidence(
        name,
        {
            "protocol": "rest",
            "endpoint": endpoint,
            "method": method,
            "request_body": request_body,
            "actual_status": response.status_code,
            "actual_output": response.text,
        },
    )


def _record_cli(name: str, result: subprocess.CompletedProcess[str], command: str) -> None:
    _save_evidence(
        name,
        {
            "protocol": "cli",
            "command": command,
            "actual_exit_code": result.returncode,
            "actual_output": result.stdout + result.stderr,
        },
    )


def _delete_all_calculations() -> None:
    response = requests.get(f"{BASE_URL}/calculations", timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    for item in response.json():
        deleted = requests.delete(
            f"{BASE_URL}/calculations/{item['id']}", timeout=REQUEST_TIMEOUT
        )
        assert deleted.status_code == 204


@pytest.fixture(autouse=True)
def isolated_lifecycle_state() -> Iterator[None]:
    """Keep the shared live server reproducible and verify it remains reachable."""
    ready = requests.get(f"{BASE_URL}/openapi.json", timeout=REQUEST_TIMEOUT)
    assert ready.status_code == 200
    _delete_all_calculations()
    assert not DEFAULT_DATABASE.exists()
    yield
    _delete_all_calculations()
    assert not DEFAULT_DATABASE.exists()


class TestDirectArithmetic:
    def test_direct_arithmetic_successes_and_generated_docs(self) -> None:
        cases = {
            "/add": ({"a": 8.5, "b": 4}, 12.5),
            "/subtract": ({"a": -3, "b": 2.5}, -5.5),
            "/multiply": ({"a": 7, "b": 6}, 42.0),
            "/divide": ({"a": 10, "b": 4}, 2.5),
        }
        responses: dict[str, requests.Response] = {}
        for endpoint, (payload, expected) in cases.items():
            response = requests.post(
                f"{BASE_URL}{endpoint}", json=payload, timeout=REQUEST_TIMEOUT
            )
            assert response.status_code == 200
            assert response.json() == {"result": expected}
            responses[endpoint] = response

        for endpoint in ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"):
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=REQUEST_TIMEOUT)
            assert response.status_code == 200

        openapi = requests.get(f"{BASE_URL}/openapi.json", timeout=REQUEST_TIMEOUT).json()
        assert openapi["info"] == {"title": "Calculator API", "version": "0.1.0"}
        _record_rest(
            "test_direct_arithmetic_successes_and_generated_docs",
            responses["/add"],
            endpoint="/add",
            method="POST",
            request_body=json.dumps(cases["/add"][0]),
        )

    def test_direct_divide_by_zero_exact_error(self) -> None:
        payload = {"a": 5, "b": 0}
        response = requests.post(
            f"{BASE_URL}/divide", json=payload, timeout=REQUEST_TIMEOUT
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "Cannot divide by zero"}
        _record_rest(
            "test_direct_divide_by_zero_exact_error",
            response,
            endpoint="/divide",
            method="POST",
            request_body=json.dumps(payload),
        )


class TestCalculationHistory:
    def test_create_all_operation_codes(self) -> None:
        cases = [
            ({"operation": "add", "a": 1.5, "b": 2.5}, 4.0),
            ({"operation": "sub", "a": 10, "b": 3}, 7.0),
            ({"operation": "mul", "a": -4, "b": 2.5}, -10.0),
            ({"operation": "div", "a": 9, "b": 2}, 4.5),
        ]
        last_response: requests.Response | None = None
        for payload, expected in cases:
            response = requests.post(
                f"{BASE_URL}/calculations", json=payload, timeout=REQUEST_TIMEOUT
            )
            assert response.status_code == 201
            body = response.json()
            assert isinstance(body["id"], int)
            assert body["operation"] == payload["operation"]
            assert body["a"] == float(payload["a"])
            assert body["b"] == float(payload["b"])
            assert body["result"] == expected
            assert body["created_at"].endswith("Z")
            last_response = response
        assert last_response is not None
        _record_rest(
            "test_create_all_operation_codes",
            last_response,
            endpoint="/calculations",
            method="POST",
            request_body=json.dumps(cases[-1][0]),
        )

    def test_failed_creates_are_atomic(self) -> None:
        unknown_payload = {"operation": "pow", "a": 2, "b": 3}
        unknown = requests.post(
            f"{BASE_URL}/calculations", json=unknown_payload, timeout=REQUEST_TIMEOUT
        )
        assert unknown.status_code == 400
        assert unknown.json() == {
            "detail": "Unknown operation: pow. Use: ['add', 'sub', 'mul', 'div']"
        }
        assert requests.get(f"{BASE_URL}/calculations", timeout=REQUEST_TIMEOUT).json() == []

        zero_payload = {"operation": "div", "a": 3, "b": 0}
        zero = requests.post(
            f"{BASE_URL}/calculations", json=zero_payload, timeout=REQUEST_TIMEOUT
        )
        assert zero.status_code == 400
        assert zero.json() == {"detail": "Cannot divide by zero"}
        assert requests.get(f"{BASE_URL}/calculations", timeout=REQUEST_TIMEOUT).json() == []
        _record_rest(
            "test_failed_creates_are_atomic",
            unknown,
            endpoint="/calculations",
            method="POST",
            request_body=json.dumps(unknown_payload),
        )

    def test_initial_and_newest_first_list(self) -> None:
        initial = requests.get(f"{BASE_URL}/calculations", timeout=REQUEST_TIMEOUT)
        assert initial.status_code == 200
        assert initial.json() == []

        created = []
        for value in (1, 2, 3):
            response = requests.post(
                f"{BASE_URL}/calculations",
                json={"operation": "add", "a": value, "b": 10},
                timeout=REQUEST_TIMEOUT,
            )
            assert response.status_code == 201
            created.append(response.json())

        listed = requests.get(f"{BASE_URL}/calculations", timeout=REQUEST_TIMEOUT)
        assert listed.status_code == 200
        rows = listed.json()
        assert {row["id"] for row in rows} == {row["id"] for row in created}
        timestamps = [row["created_at"] for row in rows]
        assert timestamps == sorted(timestamps, reverse=True)
        expected_fields = {"operation", "a", "b", "result", "id", "created_at"}
        assert all(set(row) == expected_fields for row in rows)
        _record_rest(
            "test_initial_and_newest_first_list",
            listed,
            endpoint="/calculations",
            method="GET",
        )

    def test_get_found_and_missing(self) -> None:
        payload = {"operation": "mul", "a": 6, "b": 7}
        created = requests.post(
            f"{BASE_URL}/calculations", json=payload, timeout=REQUEST_TIMEOUT
        ).json()
        found = requests.get(
            f"{BASE_URL}/calculations/{created['id']}", timeout=REQUEST_TIMEOUT
        )
        assert found.status_code == 200
        assert found.json() == created
        missing = requests.get(f"{BASE_URL}/calculations/99999999", timeout=REQUEST_TIMEOUT)
        assert missing.status_code == 404
        assert missing.json() == {"detail": "Calculation not found"}
        _record_rest(
            "test_get_found_and_missing",
            found,
            endpoint=f"/calculations/{created['id']}",
            method="GET",
        )

    def test_delete_found_empty_body_and_missing(self) -> None:
        created = requests.post(
            f"{BASE_URL}/calculations",
            json={"operation": "add", "a": 2, "b": 8},
            timeout=REQUEST_TIMEOUT,
        ).json()
        deleted = requests.delete(
            f"{BASE_URL}/calculations/{created['id']}", timeout=REQUEST_TIMEOUT
        )
        assert deleted.status_code == 204
        assert deleted.content == b""
        missing_get = requests.get(
            f"{BASE_URL}/calculations/{created['id']}", timeout=REQUEST_TIMEOUT
        )
        assert missing_get.status_code == 404
        missing_delete = requests.delete(
            f"{BASE_URL}/calculations/{created['id']}", timeout=REQUEST_TIMEOUT
        )
        assert missing_delete.status_code == 404
        assert missing_delete.json() == {"detail": "Calculation not found"}
        _record_rest(
            "test_delete_found_empty_body_and_missing",
            deleted,
            endpoint=f"/calculations/{created['id']}",
            method="DELETE",
        )

    def test_persistence_across_requests_without_default_storage(self) -> None:
        payload = {"operation": "sub", "a": 12.5, "b": 2.5}
        created = requests.post(
            f"{BASE_URL}/calculations", json=payload, timeout=REQUEST_TIMEOUT
        )
        assert created.status_code == 201
        listed = requests.get(f"{BASE_URL}/calculations", timeout=REQUEST_TIMEOUT)
        assert listed.status_code == 200
        assert created.json() in listed.json()
        assert not DEFAULT_DATABASE.exists()
        _record_rest(
            "test_persistence_across_requests_without_default_storage",
            listed,
            endpoint="/calculations",
            method="GET",
        )


class TestValidation:
    def test_request_validation_failures(self) -> None:
        responses = [
            requests.post(
                f"{BASE_URL}/add", json={"a": 1}, timeout=REQUEST_TIMEOUT
            ),
            requests.post(
                f"{BASE_URL}/add", json={"a": "not-a-number", "b": 2}, timeout=REQUEST_TIMEOUT
            ),
            requests.post(
                f"{BASE_URL}/calculations",
                data="{",
                headers={"Content-Type": "application/json"},
                timeout=REQUEST_TIMEOUT,
            ),
            requests.get(f"{BASE_URL}/calculations/not-an-int", timeout=REQUEST_TIMEOUT),
        ]
        assert [response.status_code for response in responses] == [422, 422, 422, 422]
        assert all(response.json()["detail"] for response in responses)
        _record_rest(
            "test_request_validation_failures",
            responses[0],
            endpoint="/add",
            method="POST",
            request_body=json.dumps({"a": 1}),
        )


def _available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(f"server exited early: {stdout}{stderr}")
        try:
            response = requests.get(f"{base_url}/calculations", timeout=0.5)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(0.05)
    raise AssertionError("server did not become ready within 10 seconds")


def _run_live_launcher(
    command: list[str], database_path: Path, action: Any
) -> subprocess.CompletedProcess[str]:
    port = _available_port()
    env = os.environ.copy()
    env.update({"PORT": str(port), "DATABASE_URL": f"sqlite:///{database_path}"})
    process = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_server(base_url, process)
        action(base_url)
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


class TestLaunchersAndConfiguration:
    def test_python_launcher_database_isolation_and_restart_persistence(
        self, tmp_path: Path
    ) -> None:
        python_command = [str(REPO_ROOT / ".venv/bin/python"), "server.py"]
        database_a = tmp_path / "factory-a.db"
        database_b = tmp_path / "factory-b.db"
        created: dict[str, Any] = {}

        def create_in_a(base_url: str) -> None:
            response = requests.post(
                f"{base_url}/calculations",
                json={"operation": "mul", "a": 7, "b": 6},
                timeout=REQUEST_TIMEOUT,
            )
            assert response.status_code == 201
            created.update(response.json())

        first = _run_live_launcher(python_command, database_a, create_in_a)
        assert first.returncode == 0

        def assert_b_empty(base_url: str) -> None:
            response = requests.get(f"{base_url}/calculations", timeout=REQUEST_TIMEOUT)
            assert response.status_code == 200
            assert response.json() == []

        isolated = _run_live_launcher(python_command, database_b, assert_b_empty)
        assert isolated.returncode == 0

        def assert_a_persisted(base_url: str) -> None:
            response = requests.get(f"{base_url}/calculations", timeout=REQUEST_TIMEOUT)
            assert response.status_code == 200
            assert response.json() == [created]

        restarted = _run_live_launcher(python_command, database_a, assert_a_persisted)
        assert restarted.returncode == 0
        assert not DEFAULT_DATABASE.exists()
        combined = subprocess.CompletedProcess(
            python_command,
            restarted.returncode,
            first.stdout + isolated.stdout + restarted.stdout,
            first.stderr + isolated.stderr + restarted.stderr,
        )
        _record_cli(
            "test_python_launcher_database_isolation_and_restart_persistence",
            combined,
            "python server.py",
        )

    def test_installed_calculator_api_launcher(self, tmp_path: Path) -> None:
        command = [str(REPO_ROOT / ".venv/bin/calculator-api")]

        def exercise(base_url: str) -> None:
            response = requests.post(
                f"{base_url}/add", json={"a": 0.25, "b": 0.5}, timeout=REQUEST_TIMEOUT
            )
            assert response.status_code == 200
            assert response.json() == {"result": 0.75}

        result = _run_live_launcher(command, tmp_path / "installed.db", exercise)
        assert result.returncode == 0
        assert not DEFAULT_DATABASE.exists()
        _record_cli("test_installed_calculator_api_launcher", result, "calculator-api")

    def test_invalid_port_fails_clearly_for_both_launchers(self, tmp_path: Path) -> None:
        env = os.environ.copy()
        env.update(
            {
                "PORT": "not-a-port",
                "DATABASE_URL": f"sqlite:///{tmp_path / 'invalid-port.db'}",
            }
        )
        commands = [
            [str(REPO_ROOT / ".venv/bin/python"), "server.py"],
            [str(REPO_ROOT / ".venv/bin/calculator-api")],
        ]
        results = [
            subprocess.run(
                command,
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            for command in commands
        ]
        assert all(result.returncode != 0 for result in results)
        assert all("Invalid PORT value 'not-a-port'" in result.stderr for result in results)
        _record_cli(
            "test_invalid_port_fails_clearly_for_both_launchers",
            results[-1],
            "calculator-api",
        )

    def test_invalid_database_url_fails_clearly(self) -> None:
        env = os.environ.copy()
        env.update({"PORT": str(_available_port()), "DATABASE_URL": "not a database url"})
        command = [str(REPO_ROOT / ".venv/bin/calculator-api")]
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0
        assert (
            "Invalid DATABASE_URL: provide a valid SQLAlchemy database URL"
            in result.stderr
        )
        assert "not a database url" not in result.stderr
        _record_cli(
            "test_invalid_database_url_fails_clearly", result, "calculator-api"
        )
