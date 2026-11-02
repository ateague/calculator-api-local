"""Live functional coverage for the modular Calculator API milestone."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
import requests
from requests import Response

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_PATH = Path(__file__).with_name("evidence.jsonl")
BASE_URL = os.environ.get("CALCULATOR_API_BASE_URL", "http://127.0.0.1:18191")
COMPAT_BASE_URL = os.environ.get(
    "CALCULATOR_API_COMPAT_BASE_URL", "http://127.0.0.1:18192"
)
TIMEOUT = 10


def record_response(name: str, response: Response) -> None:
    """Save the exact live response used by a test for result ingestion."""
    evidence = {
        "name": name,
        "actual_status": response.status_code,
        "actual_output": response.text,
        "duration_ms": response.elapsed.total_seconds() * 1000,
    }
    with EVIDENCE_PATH.open("a", encoding="utf-8") as output:
        output.write(json.dumps(evidence) + "\n")


def clear_calculations(base_url: str = BASE_URL) -> None:
    response = requests.get(f"{base_url}/calculations", timeout=TIMEOUT)
    response.raise_for_status()
    for calculation in response.json():
        deleted = requests.delete(
            f"{base_url}/calculations/{calculation['id']}", timeout=TIMEOUT
        )
        assert deleted.status_code == 204


def unused_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_for_app(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=1)
            pytest.fail(
                f"server exited with {process.returncode}; stdout={stdout!r}; stderr={stderr!r}"
            )
        try:
            response = requests.post(
                f"{base_url}/add", json={"a": 1, "b": 1}, timeout=1
            )
            if response.status_code == 200 and response.json() == {"result": 2.0}:
                return
        except requests.RequestException:
            pass
        time.sleep(0.1)
    pytest.fail(f"server did not become ready at {base_url}")


@contextmanager
def managed_console_server(
    tmp_path: Path, *, database_name: str, port: int | None
) -> Iterator[str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{tmp_path / database_name}"
    if port is None:
        environment.pop("PORT", None)
        server_port = 8000
    else:
        environment["PORT"] = str(port)
        server_port = port

    base_url = f"http://127.0.0.1:{server_port}"
    process = subprocess.Popen(
        [str(REPOSITORY_ROOT / ".venv/bin/calculator-api")],
        cwd=tmp_path,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_for_app(base_url, process)
        yield base_url
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)


@pytest.fixture(scope="session", autouse=True)
def live_app(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    EVIDENCE_PATH.unlink(missing_ok=True)
    database_path = tmp_path_factory.mktemp("live-app") / "functional.sqlite3"
    shared_environment = os.environ.copy()
    shared_environment["DATABASE_URL"] = f"sqlite:///{database_path}"
    launch_specs = [
        (
            [str(REPOSITORY_ROOT / ".venv/bin/calculator-api")],
            BASE_URL,
            "18191",
        ),
        (
            [str(REPOSITORY_ROOT / ".venv/bin/python"), "server.py"],
            COMPAT_BASE_URL,
            "18192",
        ),
    ]
    processes: list[subprocess.Popen[str]] = []
    try:
        for command, url, port in launch_specs:
            environment = shared_environment | {"PORT": port}
            process = subprocess.Popen(
                command,
                cwd=REPOSITORY_ROOT,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            processes.append(process)
            wait_for_app(url, process)
        clear_calculations()
        yield
        clear_calculations()
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)


@pytest.fixture(autouse=True)
def isolated_test_state() -> Iterator[None]:
    clear_calculations()
    yield
    clear_calculations()


class TestStatelessArithmetic:
    @pytest.mark.parametrize(
        ("name", "endpoint", "payload", "expected"),
        [
            ("test_add_success", "/add", {"a": 5, "b": 3}, {"result": 8.0}),
            (
                "test_subtract_success",
                "/subtract",
                {"a": 5, "b": 8},
                {"result": -3.0},
            ),
            (
                "test_multiply_success",
                "/multiply",
                {"a": -4, "b": 2.5},
                {"result": -10.0},
            ),
            (
                "test_divide_success",
                "/divide",
                {"a": 7.5, "b": 2.5},
                {"result": 3.0},
            ),
        ],
    )
    def test_operation_success(
        self, name: str, endpoint: str, payload: dict[str, float], expected: dict[str, float]
    ) -> None:
        response = requests.post(f"{BASE_URL}{endpoint}", json=payload, timeout=TIMEOUT)
        record_response(name, response)
        assert response.status_code == 200
        assert response.json() == expected

    def test_divide_by_zero(self) -> None:
        response = requests.post(
            f"{BASE_URL}/divide", json={"a": 9, "b": 0}, timeout=TIMEOUT
        )
        record_response("test_divide_by_zero", response)
        assert response.status_code == 400
        assert response.json() == {"detail": "Cannot divide by zero"}

    def test_missing_operand_validation(self) -> None:
        response = requests.post(f"{BASE_URL}/add", json={"a": 9}, timeout=TIMEOUT)
        record_response("test_missing_operand_validation", response)
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", "b"]


class TestPersistedCalculations:
    def test_create_calculation(self) -> None:
        response = requests.post(
            f"{BASE_URL}/calculations",
            json={"operation": "add", "a": 2.5, "b": 4},
            timeout=TIMEOUT,
        )
        record_response("test_create_calculation", response)
        assert response.status_code == 201
        assert response.json().keys() == {
            "id",
            "operation",
            "a",
            "b",
            "result",
            "created_at",
        }
        assert response.json()["operation"] == "add"
        assert response.json()["result"] == 6.5

    def test_get_calculation(self) -> None:
        created = requests.post(
            f"{BASE_URL}/calculations",
            json={"operation": "sub", "a": 9, "b": 4},
            timeout=TIMEOUT,
        )
        assert created.status_code == 201
        response = requests.get(
            f"{BASE_URL}/calculations/{created.json()['id']}", timeout=TIMEOUT
        )
        record_response("test_get_calculation", response)
        assert response.status_code == 200
        assert response.json() == created.json()

    def test_list_calculations_newest_first(self) -> None:
        first = requests.post(
            f"{BASE_URL}/calculations",
            json={"operation": "add", "a": 1, "b": 2},
            timeout=TIMEOUT,
        )
        second = requests.post(
            f"{BASE_URL}/calculations",
            json={"operation": "mul", "a": 3, "b": 4},
            timeout=TIMEOUT,
        )
        assert first.status_code == second.status_code == 201
        response = requests.get(f"{BASE_URL}/calculations", timeout=TIMEOUT)
        record_response("test_list_calculations_newest_first", response)
        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [
            second.json()["id"],
            first.json()["id"],
        ]

    def test_delete_calculation(self) -> None:
        created = requests.post(
            f"{BASE_URL}/calculations",
            json={"operation": "div", "a": 12, "b": 3},
            timeout=TIMEOUT,
        )
        response = requests.delete(
            f"{BASE_URL}/calculations/{created.json()['id']}", timeout=TIMEOUT
        )
        record_response("test_delete_calculation", response)
        assert response.status_code == 204
        assert response.content == b""
        assert requests.get(f"{BASE_URL}/calculations", timeout=TIMEOUT).json() == []

    @pytest.mark.parametrize(
        ("name", "payload", "expected_detail"),
        [
            (
                "test_unknown_operation",
                {"operation": "mod", "a": 4, "b": 2},
                "Unknown operation: mod. Use: ['add', 'sub', 'mul', 'div']",
            ),
            (
                "test_persisted_divide_by_zero",
                {"operation": "div", "a": 4, "b": 0},
                "Cannot divide by zero",
            ),
        ],
    )
    def test_failed_creation_is_not_persisted(
        self, name: str, payload: dict[str, object], expected_detail: str
    ) -> None:
        response = requests.post(
            f"{BASE_URL}/calculations", json=payload, timeout=TIMEOUT
        )
        record_response(name, response)
        assert response.status_code == 400
        assert response.json() == {"detail": expected_detail}
        assert requests.get(f"{BASE_URL}/calculations", timeout=TIMEOUT).json() == []

    def test_missing_creation_field(self) -> None:
        response = requests.post(
            f"{BASE_URL}/calculations",
            json={"operation": "add", "a": 1},
            timeout=TIMEOUT,
        )
        record_response("test_missing_creation_field", response)
        assert response.status_code == 422

    def test_get_missing_calculation(self) -> None:
        response = requests.get(f"{BASE_URL}/calculations/999999", timeout=TIMEOUT)
        record_response("test_get_missing_calculation", response)
        assert response.status_code == 404
        assert response.json() == {"detail": "Calculation not found"}

    def test_delete_missing_calculation(self) -> None:
        response = requests.delete(f"{BASE_URL}/calculations/999999", timeout=TIMEOUT)
        record_response("test_delete_missing_calculation", response)
        assert response.status_code == 404
        assert response.json() == {"detail": "Calculation not found"}

    def test_non_integer_calculation_id(self) -> None:
        response = requests.get(f"{BASE_URL}/calculations/not-an-integer", timeout=TIMEOUT)
        record_response("test_non_integer_calculation_id", response)
        assert response.status_code == 422


class TestGeneratedDocumentation:
    def test_openapi_metadata_and_routes(self) -> None:
        response = requests.get(f"{BASE_URL}/openapi.json", timeout=TIMEOUT)
        record_response("test_openapi_metadata_and_routes", response)
        assert response.status_code == 200
        assert response.json()["info"] == {"title": "Calculator API", "version": "0.1.0"}
        assert {
            "/add",
            "/subtract",
            "/multiply",
            "/divide",
            "/calculations",
            "/calculations/{calculation_id}",
        } <= set(response.json()["paths"])

    @pytest.mark.parametrize(
        ("name", "path"),
        [
            ("test_swagger_ui", "/docs"),
            ("test_swagger_oauth_redirect", "/docs/oauth2-redirect"),
            ("test_redoc", "/redoc"),
        ],
    )
    def test_documentation_surface(self, name: str, path: str) -> None:
        response = requests.get(f"{BASE_URL}{path}", timeout=TIMEOUT)
        record_response(name, response)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")


class TestLaunchAndConfiguration:
    def test_console_override_launch(self) -> None:
        response = requests.post(
            f"{BASE_URL}/add", json={"a": 20, "b": 22}, timeout=TIMEOUT
        )
        record_response("test_console_override_launch", response)
        assert response.status_code == 200
        assert response.json() == {"result": 42.0}

    def test_server_compatibility_launch(self) -> None:
        response = requests.post(
            f"{COMPAT_BASE_URL}/multiply", json={"a": 6, "b": 7}, timeout=TIMEOUT
        )
        record_response("test_server_compatibility_launch", response)
        assert response.status_code == 200
        assert response.json() == {"result": 42.0}

    def test_default_port_console_launch(self, tmp_path: Path) -> None:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(("127.0.0.1", 8000))

        with managed_console_server(
            tmp_path, database_name="default-port.sqlite3", port=None
        ) as default_url:
            response = requests.post(
                f"{default_url}/subtract", json={"a": 50, "b": 8}, timeout=TIMEOUT
            )
            record_response("test_default_port_console_launch", response)
            assert response.status_code == 200
            assert response.json() == {"result": 42.0}

    def test_database_url_isolates_persistence(self, tmp_path: Path) -> None:
        main_created = requests.post(
            f"{BASE_URL}/calculations",
            json={"operation": "add", "a": 40, "b": 2},
            timeout=TIMEOUT,
        )
        assert main_created.status_code == 201

        port = unused_port()
        with managed_console_server(
            tmp_path, database_name="isolated.sqlite3", port=port
        ) as isolated_url:
            response = requests.get(f"{isolated_url}/calculations", timeout=TIMEOUT)
            record_response("test_database_url_isolates_persistence", response)
            assert response.status_code == 200
            assert response.json() == []
            assert len(requests.get(f"{BASE_URL}/calculations", timeout=TIMEOUT).json()) == 1
