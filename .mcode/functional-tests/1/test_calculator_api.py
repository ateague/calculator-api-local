"""Live functional coverage for the Python 3.12 calculator service foundation."""

from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import requests

REPO = Path(__file__).resolve().parents[3]
BASE_URL = os.environ.get("FT_BASE_URL", "http://127.0.0.1:18035")
EVIDENCE_PATH = Path(__file__).with_name("observations.json")
TIMEOUT = 10


def record_response(
    name: str,
    response: requests.Response,
    *,
    expected_status: int,
    category: str,
    description: str,
    endpoint: str,
    method: str,
    request_body: dict[str, Any] | None = None,
    duration_ms: float = 0.0,
) -> None:
    """Capture the exact response body and status for result registration."""
    observations = json.loads(EVIDENCE_PATH.read_text()) if EVIDENCE_PATH.exists() else []
    observations.append(
        {
            "name": name,
            "actual_output": response.text,
            "actual_status": response.status_code,
            "expected_status": expected_status,
            "category": category,
            "description": description,
            "endpoint": endpoint,
            "method": method,
            "request_body": request_body,
            "duration_ms": duration_ms,
        }
    )
    EVIDENCE_PATH.write_text(json.dumps(observations, indent=2) + "\n")


def request_and_record(
    name: str,
    method: str,
    endpoint: str,
    expected_status: int,
    category: str,
    description: str,
    payload: dict[str, Any] | None = None,
    *,
    base_url: str = BASE_URL,
) -> requests.Response:
    """Issue one timed request and preserve its exact response."""
    started = time.perf_counter()
    response = requests.request(
        method,
        f"{base_url}{endpoint}",
        json=payload,
        timeout=TIMEOUT,
    )
    duration_ms = (time.perf_counter() - started) * 1000
    record_response(
        name,
        response,
        expected_status=expected_status,
        category=category,
        description=description,
        endpoint=endpoint,
        method=method,
        request_body=payload,
        duration_ms=duration_ms,
    )
    return response


def delete_if_present(calculation_id: int, *, base_url: str = BASE_URL) -> None:
    """Remove test-created data without obscuring the behavior under test."""
    requests.delete(f"{base_url}/calculations/{calculation_id}", timeout=TIMEOUT)


def assert_calculation(
    body: dict[str, Any], operation: str, a: float, b: float, result: float
) -> None:
    """Validate the exact persisted calculation response contract."""
    assert set(body) == {"operation", "a", "b", "result", "id", "created_at"}
    assert body["operation"] == operation
    assert body["a"] == pytest.approx(a)
    assert body["b"] == pytest.approx(b)
    assert body["result"] == pytest.approx(result)
    assert isinstance(body["id"], int) and body["id"] > 0
    created_at = datetime.fromisoformat(body["created_at"])
    assert created_at.tzinfo is None
    assert abs((datetime.now(UTC).replace(tzinfo=None) - created_at).total_seconds()) < 60


@pytest.fixture(scope="session", autouse=True)
def clean_live_database() -> None:
    """Start and finish with no records in the disposable live database."""
    EVIDENCE_PATH.unlink(missing_ok=True)
    response = requests.get(f"{BASE_URL}/calculations", timeout=TIMEOUT)
    assert response.status_code == 200
    for calculation in response.json():
        delete_if_present(calculation["id"])
    yield
    response = requests.get(f"{BASE_URL}/calculations", timeout=TIMEOUT)
    if response.status_code == 200:
        for calculation in response.json():
            delete_if_present(calculation["id"])


@pytest.fixture(autouse=True)
def live_service_ready() -> None:
    """Verify running behavior before each test without using a docs/health probe."""
    response = requests.post(f"{BASE_URL}/add", json={"a": 0, "b": 0}, timeout=TIMEOUT)
    assert response.status_code == 200
    assert response.json() == {"result": 0.0}


class TestImmediateArithmetic:
    def test_add(self) -> None:
        response = request_and_record(
            "test_add",
            "POST",
            "/add",
            200,
            "HAPPY_PATH",
            "POST /add performs numeric addition",
            {"a": 5.25, "b": -2},
        )
        assert response.status_code == 200
        assert response.json() == {"result": 3.25}

        openapi = requests.get(f"{BASE_URL}/openapi.json", timeout=TIMEOUT)
        assert openapi.status_code == 200
        assert {
            "/add",
            "/subtract",
            "/multiply",
            "/divide",
            "/calculations",
            "/calculations/{calculation_id}",
        } <= set(openapi.json()["paths"])
        for path, marker in (
            ("/docs", "Swagger UI"),
            ("/docs/oauth2-redirect", "oauth2"),
            ("/redoc", "ReDoc"),
        ):
            page = requests.get(f"{BASE_URL}{path}", timeout=TIMEOUT)
            assert page.status_code == 200
            assert "text/html" in page.headers["content-type"]
            assert marker.lower() in page.text.lower()

    def test_subtract(self) -> None:
        response = request_and_record(
            "test_subtract",
            "POST",
            "/subtract",
            200,
            "HAPPY_PATH",
            "POST /subtract computes a minus b",
            {"a": -4, "b": 2.5},
        )
        assert response.status_code == 200
        assert response.json() == {"result": -6.5}

    def test_multiply(self) -> None:
        response = request_and_record(
            "test_multiply",
            "POST",
            "/multiply",
            200,
            "HAPPY_PATH",
            "POST /multiply performs numeric multiplication",
            {"a": -3, "b": 4.5},
        )
        assert response.status_code == 200
        assert response.json() == {"result": -13.5}

    def test_divide(self) -> None:
        response = request_and_record(
            "test_divide",
            "POST",
            "/divide",
            200,
            "HAPPY_PATH",
            "POST /divide performs numeric division",
            {"a": 7.5, "b": 2.5},
        )
        assert response.status_code == 200
        assert response.json() == {"result": 3.0}

    def test_divide_by_zero(self) -> None:
        response = request_and_record(
            "test_divide_by_zero",
            "POST",
            "/divide",
            400,
            "INVALID_INPUT",
            "POST /divide rejects division by zero with the domain error",
            {"a": 1, "b": 0},
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "Cannot divide by zero"}

    def test_missing_required_field(self) -> None:
        response = request_and_record(
            "test_missing_required_field",
            "POST",
            "/add",
            422,
            "MISSING_REQUIRED",
            "Immediate calculation rejects a missing required field",
            {"a": 1},
        )
        assert response.status_code == 422
        assert response.json()["detail"]

    def test_invalid_numeric_type(self) -> None:
        response = request_and_record(
            "test_invalid_numeric_type",
            "POST",
            "/multiply",
            422,
            "INVALID_TYPE",
            "Immediate calculation rejects a nonnumeric operand",
            {"a": "not-a-number", "b": 2},
        )
        assert response.status_code == 422
        assert response.json()["detail"]


@pytest.mark.parametrize(
    ("test_name", "operation", "a", "b", "expected"),
    [
        ("test_persist_add", "add", 2, 3, 5),
        ("test_persist_sub", "sub", 7.5, 2.5, 5),
        ("test_persist_mul", "mul", -4, 6, -24),
        ("test_persist_div", "div", 9, 4.5, 2),
    ],
)
def test_persist_operation(
    test_name: str, operation: str, a: float, b: float, expected: float
) -> None:
    payload = {"operation": operation, "a": a, "b": b}
    response = request_and_record(
        test_name,
        "POST",
        "/calculations",
        201,
        "HAPPY_PATH",
        f"POST /calculations persists the {operation} operation code",
        payload,
    )
    assert response.status_code == 201
    body = response.json()
    assert_calculation(body, operation, a, b, expected)
    try:
        fetched = requests.get(
            f"{BASE_URL}/calculations/{body['id']}", timeout=TIMEOUT
        )
        assert fetched.status_code == 200
        assert fetched.json() == body
        if operation == "add":
            database_url = os.environ["DATABASE_URL"]
            assert database_url.startswith("sqlite:///")
            database_path = Path(database_url.removeprefix("sqlite:///"))
            assert REPO not in database_path.resolve().parents
            with sqlite3.connect(database_path) as connection:
                columns = [
                    row[1]
                    for row in connection.execute("PRAGMA table_info(calculation)")
                ]
            assert columns == ["operation", "a", "b", "result", "id", "created_at"]
    finally:
        delete_if_present(body["id"])


class TestCalculationErrors:
    def test_unknown_operation(self) -> None:
        response = request_and_record(
            "test_unknown_operation",
            "POST",
            "/calculations",
            400,
            "INVALID_INPUT",
            "POST /calculations rejects unknown operation codes",
            {"operation": "pow", "a": 2, "b": 3},
        )
        assert response.status_code == 400
        assert response.json()["detail"].startswith("Unknown operation: pow")

    def test_persisted_division_by_zero(self) -> None:
        before = requests.get(f"{BASE_URL}/calculations", timeout=TIMEOUT).json()
        response = request_and_record(
            "test_persisted_division_by_zero",
            "POST",
            "/calculations",
            400,
            "INVALID_INPUT",
            "Persisted division rejects a zero divisor without storing a row",
            {"operation": "div", "a": 2, "b": 0},
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "Cannot divide by zero"}
        after = requests.get(f"{BASE_URL}/calculations", timeout=TIMEOUT).json()
        assert after == before


class TestCalculationCrud:
    def test_list_descending(self) -> None:
        created: list[dict[str, Any]] = []
        try:
            for index in range(3):
                response = requests.post(
                    f"{BASE_URL}/calculations",
                    json={"operation": "add", "a": index, "b": 10},
                    timeout=TIMEOUT,
                )
                assert response.status_code == 201
                created.append(response.json())
                time.sleep(0.02)
            response = request_and_record(
                "test_list_descending",
                "GET",
                "/calculations",
                200,
                "HAPPY_PATH",
                "GET /calculations returns newest persisted records first",
            )
            assert response.status_code == 200
            body = response.json()
            assert [item["id"] for item in body] == [
                item["id"] for item in reversed(created)
            ]
            assert [item["created_at"] for item in body] == sorted(
                [item["created_at"] for item in body], reverse=True
            )
        finally:
            for calculation in created:
                delete_if_present(calculation["id"])

    def test_get_existing(self) -> None:
        created = requests.post(
            f"{BASE_URL}/calculations",
            json={"operation": "mul", "a": 3, "b": 7},
            timeout=TIMEOUT,
        )
        assert created.status_code == 201
        body = created.json()
        try:
            response = request_and_record(
                "test_get_existing",
                "GET",
                f"/calculations/{body['id']}",
                200,
                "HAPPY_PATH",
                "GET /calculations/{id} returns the matching persisted calculation",
            )
            assert response.status_code == 200
            assert response.json() == body
        finally:
            delete_if_present(body["id"])

    def test_get_not_found(self) -> None:
        response = request_and_record(
            "test_get_not_found",
            "GET",
            "/calculations/2147483647",
            404,
            "NOT_FOUND",
            "GET /calculations/{id} returns the specified 404 detail",
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "Calculation not found"}

    def test_delete_existing(self) -> None:
        created = requests.post(
            f"{BASE_URL}/calculations",
            json={"operation": "sub", "a": 12, "b": 5},
            timeout=TIMEOUT,
        )
        assert created.status_code == 201
        calculation_id = created.json()["id"]
        response = request_and_record(
            "test_delete_existing",
            "DELETE",
            f"/calculations/{calculation_id}",
            204,
            "HAPPY_PATH",
            "DELETE /calculations/{id} removes a row and returns an empty body",
        )
        assert response.status_code == 204
        assert response.content == b""
        assert requests.get(
            f"{BASE_URL}/calculations/{calculation_id}", timeout=TIMEOUT
        ).status_code == 404

    def test_delete_not_found(self) -> None:
        response = request_and_record(
            "test_delete_not_found",
            "DELETE",
            "/calculations/2147483647",
            404,
            "NOT_FOUND",
            "DELETE /calculations/{id} returns the specified 404 detail",
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "Calculation not found"}


def free_port() -> int:
    """Reserve and release a loopback port for a short-lived launch check."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_for_server(process: subprocess.Popen[str], base_url: str) -> None:
    """Wait until a spawned application command serves a real calculation."""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(
                f"server exited early ({process.returncode})\nstdout={stdout}\nstderr={stderr}"
            )
        try:
            response = requests.post(
                f"{base_url}/add", json={"a": 1, "b": 1}, timeout=1
            )
            if response.status_code == 200 and response.json() == {"result": 2.0}:
                return
        except requests.RequestException:
            pass
        time.sleep(0.2)
    raise AssertionError(f"server did not become ready at {base_url}")


def stop_server(process: subprocess.Popen[str]) -> None:
    """Terminate a tracked short-lived server process."""
    process.terminate()
    try:
        process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=5)


class TestLaunchBehavior:
    def test_python_server_default_port(self, tmp_path: Path) -> None:
        database = tmp_path / "direct.db"
        environment = os.environ.copy()
        environment.pop("PORT", None)
        environment["DATABASE_URL"] = f"sqlite:///{database}"
        process = subprocess.Popen(
            [sys.executable, "server.py"],
            cwd=REPO,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            base_url = "http://127.0.0.1:8000"
            wait_for_server(process, base_url)
            response = request_and_record(
                "test_python_server_default_port",
                "POST",
                "/subtract",
                200,
                "HAPPY_PATH",
                "python server.py serves calculations on the default port 8000",
                {"a": 11, "b": 4},
                base_url=base_url,
            )
            assert response.status_code == 200
            assert response.json() == {"result": 7.0}
            assert database.exists()
        finally:
            stop_server(process)

    def test_installed_command_port_and_default_database(self, tmp_path: Path) -> None:
        port = free_port()
        environment = os.environ.copy()
        environment["PORT"] = str(port)
        environment.pop("DATABASE_URL", None)
        command = Path(sys.executable).with_name("calculator-api")
        process = subprocess.Popen(
            [str(command)],
            cwd=tmp_path,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            base_url = f"http://127.0.0.1:{port}"
            wait_for_server(process, base_url)
            payload = {"operation": "mul", "a": 6, "b": 7}
            response = request_and_record(
                "test_installed_command_port_and_default_database",
                "POST",
                "/calculations",
                201,
                "HAPPY_PATH",
                "calculator-api honors PORT and the sqlite:///calculator.db default",
                payload,
                base_url=base_url,
            )
            assert response.status_code == 201
            assert_calculation(response.json(), "mul", 6, 7, 42)
            database = tmp_path / "calculator.db"
            assert database.exists()
            with sqlite3.connect(database) as connection:
                stored = connection.execute(
                    "SELECT operation, a, b, result FROM calculation"
                ).fetchall()
            assert stored == [("mul", 6.0, 7.0, 42.0)]
        finally:
            stop_server(process)


def test_repository_database_was_not_created() -> None:
    response = request_and_record(
        "test_repository_database_was_not_created",
        "POST",
        "/add",
        200,
        "HAPPY_PATH",
        "Isolated DATABASE_URL leaves no repository-local calculator.db",
        {"a": 20, "b": 22},
    )
    assert response.status_code == 200
    assert response.json() == {"result": 42.0}
    assert not (REPO / "calculator.db").exists()
