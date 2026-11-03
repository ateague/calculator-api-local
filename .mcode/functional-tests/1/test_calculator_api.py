"""Functional verification for the Python 3.12 calculator API foundation."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import socket
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
import requests

REPO_ROOT = Path(os.environ["WORKSPACE_DIR"]) / "calculator-api-local"
PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
CONSOLE = REPO_ROOT / ".venv" / "bin" / "calculator-api"
BASE_URL = os.environ.get("CALCULATOR_API_BASE_URL", "http://127.0.0.1:8127")
DATABASE_PATH = Path(
    os.environ.get("LIFECYCLE_DATABASE_PATH", "/tmp/calculator-api-lifecycle-m27.db")
)
EVIDENCE_PATH = Path(
    os.environ.get("FT_EVIDENCE_PATH", "/tmp/calculator-api-functional-evidence.json")
)
DEFAULT_DATABASE = REPO_ROOT / "calculator.db"


def _fingerprint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    stat = path.stat()
    return {
        "exists": True,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


DEFAULT_DATABASE_BEFORE = _fingerprint(DEFAULT_DATABASE)


def _record(name: str, *, actual_output: str, **details: Any) -> None:
    evidence: dict[str, Any] = {}
    if EVIDENCE_PATH.exists():
        evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    evidence[name] = {"actual_output": actual_output, **details}
    EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2), encoding="utf-8")


def _responses_output(responses: list[requests.Response]) -> str:
    return "\n".join(response.text for response in responses)


def _assert_utc_offset(value: str) -> None:
    assert value.endswith("Z") or value.endswith("+00:00"), value


@pytest.fixture(scope="session", autouse=True)
def managed_application() -> None:
    """Start the installed target command when no managed server remains live."""
    try:
        existing = requests.post(f"{BASE_URL}/add", json={"a": 1, "b": 1}, timeout=1)
        if existing.status_code == 200:
            yield
            return
    except requests.RequestException:
        pass

    environment = os.environ.copy()
    environment["PORT"] = BASE_URL.rsplit(":", 1)[1]
    environment["DATABASE_URL"] = f"sqlite:///{DATABASE_PATH}"
    process = subprocess.Popen(
        [str(CONSOLE)],
        cwd=REPO_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_server(BASE_URL)
        yield
    finally:
        stdout, stderr, returncode = _stop_server(process)
        assert returncode == 0, stdout + stderr


@pytest.fixture(autouse=True)
def running_application() -> None:
    """Use a real calculator request as the live-service readiness assertion."""
    response = requests.post(f"{BASE_URL}/add", json={"a": 1, "b": 1}, timeout=5)
    assert response.status_code == 200
    assert response.json() == {"result": 2.0}


def test_direct_arithmetic_happy_paths() -> None:
    cases = [
        ("add", {"a": -1.25, "b": 2.5}, 1.25),
        ("subtract", {"a": 5.5, "b": 8}, -2.5),
        ("multiply", {"a": -3, "b": 0.5}, -1.5),
        ("divide", {"a": 7.5, "b": 2.5}, 3.0),
    ]
    responses = []
    for route, payload, expected in cases:
        response = requests.post(f"{BASE_URL}/{route}", json=payload, timeout=10)
        responses.append(response)
        assert response.status_code == 200
        assert response.json() == {"result": expected}
    _record(
        "test_direct_arithmetic_happy_paths",
        actual_output=_responses_output(responses),
        actual_status=responses[-1].status_code,
    )


def test_direct_divide_by_zero() -> None:
    response = requests.post(f"{BASE_URL}/divide", json={"a": 4, "b": 0}, timeout=10)
    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot divide by zero"}
    _record(
        "test_direct_divide_by_zero",
        actual_output=response.text,
        actual_status=response.status_code,
    )


def test_direct_request_validation() -> None:
    responses = []
    for route in ("add", "subtract", "multiply", "divide"):
        missing = requests.post(f"{BASE_URL}/{route}", json={"a": 2}, timeout=10)
        malformed = requests.post(
            f"{BASE_URL}/{route}", json={"a": "not-a-number", "b": 2}, timeout=10
        )
        responses.extend((missing, malformed))
        assert missing.status_code == 422
        assert missing.json()["detail"][0]["loc"][-1] == "b"
        assert missing.json()["detail"][0]["type"] == "missing"
        assert malformed.status_code == 422
        assert malformed.json()["detail"][0]["loc"][-1] == "a"
    _record(
        "test_direct_request_validation",
        actual_output=_responses_output(responses),
        actual_status=responses[-1].status_code,
    )


def test_calculation_operations_and_persistence() -> None:
    cases = [("add", 4, 3, 7), ("sub", 4, 3, 1), ("mul", 4, 3, 12), ("div", 9, 3, 3)]
    responses: list[requests.Response] = []
    created_ids: list[int] = []
    try:
        for operation, a, b, expected in cases:
            created = requests.post(
                f"{BASE_URL}/calculations",
                json={"operation": operation, "a": a, "b": b},
                timeout=10,
            )
            responses.append(created)
            assert created.status_code == 201
            body = created.json()
            assert body["operation"] == operation
            assert body["a"] == float(a)
            assert body["b"] == float(b)
            assert body["result"] == float(expected)
            assert isinstance(body["id"], int)
            _assert_utc_offset(body["created_at"])
            created_ids.append(body["id"])

            fetched = requests.get(f"{BASE_URL}/calculations/{body['id']}", timeout=10)
            responses.append(fetched)
            assert fetched.status_code == 200
            assert fetched.json() == body
    finally:
        for calculation_id in created_ids:
            requests.delete(f"{BASE_URL}/calculations/{calculation_id}", timeout=10)
    _record(
        "test_calculation_operations_and_persistence",
        actual_output=_responses_output(responses),
        actual_status=responses[-1].status_code,
    )


def test_calculation_rejects_unknown_operation() -> None:
    response = requests.post(
        f"{BASE_URL}/calculations",
        json={"operation": "pow", "a": 2, "b": 8},
        timeout=10,
    )
    assert response.status_code == 400
    assert response.json() == {
        "detail": "Unknown operation: pow. Use: ['add', 'sub', 'mul', 'div']"
    }
    _record(
        "test_calculation_rejects_unknown_operation",
        actual_output=response.text,
        actual_status=response.status_code,
    )


def test_calculation_rejects_zero_divisor() -> None:
    response = requests.post(
        f"{BASE_URL}/calculations",
        json={"operation": "div", "a": 2, "b": 0},
        timeout=10,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot divide by zero"}
    _record(
        "test_calculation_rejects_zero_divisor",
        actual_output=response.text,
        actual_status=response.status_code,
    )


def test_calculation_request_validation() -> None:
    missing = requests.post(
        f"{BASE_URL}/calculations", json={"operation": "add", "a": 2}, timeout=10
    )
    invalid = requests.post(
        f"{BASE_URL}/calculations",
        json={"operation": "add", "a": [], "b": 2},
        timeout=10,
    )
    assert missing.status_code == 422
    assert missing.json()["detail"][0]["loc"][-1] == "b"
    assert invalid.status_code == 422
    assert invalid.json()["detail"][0]["loc"][-1] == "a"
    _record(
        "test_calculation_request_validation",
        actual_output=_responses_output([missing, invalid]),
        actual_status=invalid.status_code,
    )


def test_calculation_not_found_contract() -> None:
    missing_id = 2_147_483_647
    fetched = requests.get(f"{BASE_URL}/calculations/{missing_id}", timeout=10)
    deleted = requests.delete(f"{BASE_URL}/calculations/{missing_id}", timeout=10)
    assert fetched.status_code == 404
    assert deleted.status_code == 404
    assert fetched.json() == {"detail": "Calculation not found"}
    assert deleted.json() == {"detail": "Calculation not found"}
    _record(
        "test_calculation_not_found_contract",
        actual_output=_responses_output([fetched, deleted]),
        actual_status=deleted.status_code,
    )


def test_delete_removes_calculation() -> None:
    created = requests.post(
        f"{BASE_URL}/calculations",
        json={"operation": "add", "a": 81, "b": 19},
        timeout=10,
    )
    assert created.status_code == 201
    calculation_id = created.json()["id"]
    deleted = requests.delete(f"{BASE_URL}/calculations/{calculation_id}", timeout=10)
    fetched = requests.get(f"{BASE_URL}/calculations/{calculation_id}", timeout=10)
    assert deleted.status_code == 204
    assert deleted.text == ""
    assert fetched.status_code == 404
    assert fetched.json() == {"detail": "Calculation not found"}
    _record(
        "test_delete_removes_calculation",
        actual_output=_responses_output([created, deleted, fetched]),
        actual_status=deleted.status_code,
    )


def test_history_order_and_legacy_timestamp_normalization() -> None:
    connection = sqlite3.connect(DATABASE_PATH)
    ids: list[int] = []
    try:
        for timestamp, a in (
            ("2098-01-01 00:00:00.000000", 91001.0),
            ("2099-01-01 00:00:00.000000", 91002.0),
            ("2099-01-01 00:00:00.000000", 91003.0),
        ):
            cursor = connection.execute(
                "INSERT INTO calculation (operation, a, b, result, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("add", a, 1.0, a + 1.0, timestamp),
            )
            ids.append(int(cursor.lastrowid))
        connection.commit()

        response = requests.get(f"{BASE_URL}/calculations", timeout=10)
        assert response.status_code == 200
        indexed = {item["id"]: item for item in response.json()}
        returned_ids = [item["id"] for item in response.json() if item["id"] in ids]
        assert returned_ids == [ids[2], ids[1], ids[0]]
        for calculation_id in ids:
            _assert_utc_offset(indexed[calculation_id]["created_at"])
    finally:
        if ids:
            placeholders = ",".join("?" for _ in ids)
            connection.execute(f"DELETE FROM calculation WHERE id IN ({placeholders})", ids)
            connection.commit()
        connection.close()
    _record(
        "test_history_order_and_legacy_timestamp_normalization",
        actual_output=response.text,
        actual_status=response.status_code,
    )


def test_openapi_and_generated_documentation_contract() -> None:
    openapi = requests.get(f"{BASE_URL}/openapi.json", timeout=10)
    docs = requests.get(f"{BASE_URL}/docs", timeout=10)
    redoc = requests.get(f"{BASE_URL}/redoc", timeout=10)
    assert openapi.status_code == docs.status_code == redoc.status_code == 200
    schema = openapi.json()
    assert schema["info"] == {
        "title": "Calculator API",
        "version": "0.1.0",
    }
    expected_operations = {
        ("/add", "post"),
        ("/subtract", "post"),
        ("/multiply", "post"),
        ("/divide", "post"),
        ("/calculations", "post"),
        ("/calculations", "get"),
        ("/calculations/{calculation_id}", "get"),
        ("/calculations/{calculation_id}", "delete"),
    }
    assert expected_operations == {
        (path, method)
        for path, methods in schema["paths"].items()
        for method in methods
        if method in {"get", "post", "delete"}
    }
    assert set(schema["components"]["schemas"]) >= {
        "CalculationCreate",
        "CalculationRequest",
        "CalculationResponse",
        "ResultResponse",
    }
    assert "Swagger UI" in docs.text
    assert "ReDoc" in redoc.text
    _record(
        "test_openapi_and_generated_documentation_contract",
        actual_output=_responses_output([openapi, docs, redoc]),
        actual_status=redoc.status_code,
    )


def _unused_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_server(base_url: str) -> requests.Response:
    deadline = time.monotonic() + 15
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = requests.post(f"{base_url}/add", json={"a": 20, "b": 22}, timeout=1)
            if response.status_code == 200:
                return response
        except requests.RequestException as error:
            last_error = error
        time.sleep(0.1)
    raise AssertionError(f"server failed to start at {base_url}: {last_error}")


def _stop_server(process: subprocess.Popen[str]) -> tuple[str, str, int]:
    process.send_signal(signal.SIGINT)
    try:
        stdout, stderr = process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate(timeout=5)
    return stdout, stderr, int(process.returncode)


def _launch_and_probe(
    command: list[str], *, cwd: Path, environment: dict[str, str], port: int
) -> tuple[requests.Response, str, int]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    response: requests.Response | None = None
    try:
        response = _wait_for_server(f"http://127.0.0.1:{port}")
        assert response.json() == {"result": 42.0}
    finally:
        stdout, stderr, returncode = _stop_server(process)
    assert response is not None
    assert returncode == 0, stdout + stderr
    return response, stdout + stderr, returncode


def test_python_server_default_port_and_database(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.pop("PORT", None)
    environment.pop("DATABASE_URL", None)
    response, process_output, returncode = _launch_and_probe(
        [str(PYTHON), str(REPO_ROOT / "server.py")],
        cwd=tmp_path,
        environment=environment,
        port=8000,
    )
    assert (tmp_path / "calculator.db").exists()
    assert _fingerprint(DEFAULT_DATABASE) == DEFAULT_DATABASE_BEFORE
    _record(
        "test_python_server_default_port_and_database",
        actual_output=process_output,
        actual_exit_code=returncode,
        response_body=response.text,
    )


def test_console_script_database_and_port_overrides(tmp_path: Path) -> None:
    port = _unused_port()
    database_path = tmp_path / "console-override.db"
    environment = os.environ.copy()
    environment["PORT"] = str(port)
    environment["DATABASE_URL"] = f"sqlite:///{database_path}"
    response, process_output, returncode = _launch_and_probe(
        [str(CONSOLE)], cwd=tmp_path, environment=environment, port=port
    )
    assert database_path.exists()
    assert _fingerprint(DEFAULT_DATABASE) == DEFAULT_DATABASE_BEFORE
    _record(
        "test_console_script_database_and_port_overrides",
        actual_output=process_output,
        actual_exit_code=returncode,
        response_body=response.text,
    )


def test_uvicorn_imported_server_app(tmp_path: Path) -> None:
    port = _unused_port()
    database_path = tmp_path / "uvicorn-import.db"
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{database_path}"
    response, process_output, returncode = _launch_and_probe(
        [
            str(PYTHON),
            "-m",
            "uvicorn",
            "server:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=REPO_ROOT,
        environment=environment,
        port=port,
    )
    assert database_path.exists()
    assert _fingerprint(DEFAULT_DATABASE) == DEFAULT_DATABASE_BEFORE
    _record(
        "test_uvicorn_imported_server_app",
        actual_output=process_output,
        actual_exit_code=returncode,
        response_body=response.text,
    )
