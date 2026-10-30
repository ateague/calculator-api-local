"""Live functional coverage for the Calculator API milestone."""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("CALCULATOR_BASE_URL", "http://127.0.0.1:8180")
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PYTHON = REPOSITORY_ROOT / ".venv" / "bin" / "python"
CONSOLE = REPOSITORY_ROOT / ".venv" / "bin" / "calculator-api"
RESPONSE_FIELDS = {"id", "operation", "a", "b", "result", "created_at"}


def evidence(name: str, output: str, status: int) -> None:
    """Emit exact response evidence for result recording."""
    print(
        "FT_EVIDENCE "
        + json.dumps(
            {"name": name, "actual_output": output, "actual_status": status},
            ensure_ascii=False,
        )
    )


@pytest.fixture(autouse=True)
def live_application_is_ready() -> None:
    """Require the managed application to be available for every test."""
    response = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
    assert response.status_code == 200


@pytest.fixture
def empty_store() -> Iterator[None]:
    """Provide an empty API-owned store and restore it after the test."""

    def remove_all() -> None:
        response = requests.get(f"{BASE_URL}/calculations", timeout=5)
        response.raise_for_status()
        for calculation in response.json():
            deleted = requests.delete(
                f"{BASE_URL}/calculations/{calculation['id']}", timeout=5
            )
            assert deleted.status_code == 204

    remove_all()
    yield
    remove_all()


def assert_arithmetic(
    name: str, route: str, payload: dict[str, float], expected: float
) -> None:
    response = requests.post(f"{BASE_URL}{route}", json=payload, timeout=5)
    evidence(name, response.text, response.status_code)
    assert response.status_code == 200
    assert response.json() == {"result": expected}


def test_add_success() -> None:
    assert_arithmetic("test_add_success", "/add", {"a": -2.5, "b": 3.75}, 1.25)


def test_subtract_success() -> None:
    assert_arithmetic(
        "test_subtract_success", "/subtract", {"a": 0.0, "b": -4.5}, 4.5
    )


def test_multiply_success() -> None:
    assert_arithmetic(
        "test_multiply_success", "/multiply", {"a": -3.0, "b": 2.5}, -7.5
    )


def test_divide_success() -> None:
    assert_arithmetic("test_divide_success", "/divide", {"a": 0.0, "b": 5.0}, 0.0)


def test_divide_zero_error_is_exact() -> None:
    response = requests.post(
        f"{BASE_URL}/divide", json={"a": 9.0, "b": 0.0}, timeout=5
    )
    evidence("test_divide_zero_error_is_exact", response.text, response.status_code)
    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot divide by zero"}


def test_arithmetic_validation_errors() -> None:
    responses = []
    for route in ("add", "subtract", "multiply", "divide"):
        responses.append(
            requests.post(f"{BASE_URL}/{route}", json={"a": 1.0}, timeout=5)
        )
        responses.append(
            requests.post(
                f"{BASE_URL}/{route}",
                json={"a": "not-a-number", "b": 2.0},
                timeout=5,
            )
        )
    output = json.dumps([response.text for response in responses])
    evidence("test_arithmetic_validation_errors", output, 422)
    assert all(response.status_code == 422 for response in responses)
    assert all(isinstance(response.json()["detail"], list) for response in responses)


def assert_created_calculation(
    name: str,
    operation: str,
    a: float,
    b: float,
    expected: float,
) -> None:
    response = requests.post(
        f"{BASE_URL}/calculations",
        json={"operation": operation, "a": a, "b": b},
        timeout=5,
    )
    evidence(name, response.text, response.status_code)
    assert response.status_code == 201
    body = response.json()
    assert set(body) == RESPONSE_FIELDS
    assert body["operation"] == operation
    assert body["a"] == a
    assert body["b"] == b
    assert body["result"] == expected
    assert isinstance(body["id"], int) and body["id"] > 0
    created_at = body["created_at"]
    parsed_created_at = datetime.fromisoformat(created_at)
    assert parsed_created_at.tzinfo is None
    assert not created_at.endswith("Z")

    persisted = requests.get(f"{BASE_URL}/calculations/{body['id']}", timeout=5)
    assert persisted.status_code == 200
    assert persisted.json() == body


def test_create_add_persists_full_schema(empty_store: None) -> None:
    assert_created_calculation("test_create_add_persists_full_schema", "add", 1.5, 2.5, 4.0)


def test_create_subtract_persists_full_schema(empty_store: None) -> None:
    assert_created_calculation(
        "test_create_subtract_persists_full_schema", "sub", 8.5, 3.0, 5.5
    )


def test_create_multiply_persists_full_schema(empty_store: None) -> None:
    assert_created_calculation(
        "test_create_multiply_persists_full_schema", "mul", -4.0, 2.5, -10.0
    )


def test_create_divide_persists_full_schema(empty_store: None) -> None:
    assert_created_calculation(
        "test_create_divide_persists_full_schema", "div", 7.5, 2.5, 3.0
    )


def test_create_unknown_operation_error(empty_store: None) -> None:
    response = requests.post(
        f"{BASE_URL}/calculations",
        json={"operation": "pow", "a": 2.0, "b": 3.0},
        timeout=5,
    )
    evidence("test_create_unknown_operation_error", response.text, response.status_code)
    assert response.status_code == 400
    assert response.json() == {
        "detail": "Unknown operation: pow. Use: ['add', 'sub', 'mul', 'div']"
    }


def test_create_divide_zero_error(empty_store: None) -> None:
    response = requests.post(
        f"{BASE_URL}/calculations",
        json={"operation": "div", "a": 2.0, "b": 0.0},
        timeout=5,
    )
    evidence("test_create_divide_zero_error", response.text, response.status_code)
    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot divide by zero"}


def test_create_validation_errors(empty_store: None) -> None:
    payloads = [
        {"a": 1.0, "b": 2.0},
        {"operation": "add", "a": "bad", "b": 2.0},
        {"operation": "add", "a": 1.0, "b": "bad"},
    ]
    responses = [
        requests.post(f"{BASE_URL}/calculations", json=payload, timeout=5)
        for payload in payloads
    ]
    output = json.dumps([response.text for response in responses])
    evidence("test_create_validation_errors", output, 422)
    assert all(response.status_code == 422 for response in responses)
    assert all(isinstance(response.json()["detail"], list) for response in responses)


def test_lifespan_initialized_empty_store(empty_store: None) -> None:
    response = requests.get(f"{BASE_URL}/calculations", timeout=5)
    evidence("test_lifespan_initialized_empty_store", response.text, response.status_code)
    assert response.status_code == 200
    assert response.json() == []


def test_list_calculations_newest_first(empty_store: None) -> None:
    created = []
    for value in (1.0, 2.0, 3.0):
        response = requests.post(
            f"{BASE_URL}/calculations",
            json={"operation": "add", "a": value, "b": 1.0},
            timeout=5,
        )
        assert response.status_code == 201
        created.append(response.json())
        time.sleep(0.01)

    response = requests.get(f"{BASE_URL}/calculations", timeout=5)
    evidence("test_list_calculations_newest_first", response.text, response.status_code)
    assert response.status_code == 200
    listed = response.json()
    assert [item["id"] for item in listed] == [
        created[2]["id"],
        created[1]["id"],
        created[0]["id"],
    ]
    assert all(set(item) == RESPONSE_FIELDS for item in listed)


def test_get_calculation_found(empty_store: None) -> None:
    created = requests.post(
        f"{BASE_URL}/calculations",
        json={"operation": "mul", "a": 6.0, "b": 7.0},
        timeout=5,
    ).json()
    response = requests.get(f"{BASE_URL}/calculations/{created['id']}", timeout=5)
    evidence("test_get_calculation_found", response.text, response.status_code)
    assert response.status_code == 200
    assert response.json() == created


def test_get_calculation_missing(empty_store: None) -> None:
    response = requests.get(f"{BASE_URL}/calculations/999999", timeout=5)
    evidence("test_get_calculation_missing", response.text, response.status_code)
    assert response.status_code == 404
    assert response.json() == {"detail": "Calculation not found"}


def test_get_calculation_noninteger(empty_store: None) -> None:
    response = requests.get(f"{BASE_URL}/calculations/not-an-integer", timeout=5)
    evidence("test_get_calculation_noninteger", response.text, response.status_code)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_delete_calculation_persists_removal(empty_store: None) -> None:
    created = requests.post(
        f"{BASE_URL}/calculations",
        json={"operation": "sub", "a": 10.0, "b": 4.0},
        timeout=5,
    ).json()
    response = requests.delete(f"{BASE_URL}/calculations/{created['id']}", timeout=5)
    evidence(
        "test_delete_calculation_persists_removal", response.text, response.status_code
    )
    assert response.status_code == 204
    assert response.content == b""
    missing = requests.get(f"{BASE_URL}/calculations/{created['id']}", timeout=5)
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Calculation not found"}


def test_delete_calculation_missing(empty_store: None) -> None:
    response = requests.delete(f"{BASE_URL}/calculations/999999", timeout=5)
    evidence("test_delete_calculation_missing", response.text, response.status_code)
    assert response.status_code == 404
    assert response.json() == {"detail": "Calculation not found"}


def test_delete_calculation_noninteger(empty_store: None) -> None:
    response = requests.delete(f"{BASE_URL}/calculations/not-an-integer", timeout=5)
    evidence("test_delete_calculation_noninteger", response.text, response.status_code)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_generated_docs_describe_and_drive_add_route() -> None:
    schema = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
    docs = requests.get(f"{BASE_URL}/docs", timeout=5)
    redoc = requests.get(f"{BASE_URL}/redoc", timeout=5)
    oauth_redirect = requests.get(f"{BASE_URL}/docs/oauth2-redirect", timeout=5)

    assert schema.status_code == 200
    assert "post" in schema.json()["paths"]["/add"]
    assert docs.status_code == 200 and "Swagger UI" in docs.text
    assert redoc.status_code == 200 and "ReDoc" in redoc.text
    assert oauth_redirect.status_code == 200
    assert "OAuth2 Redirect" in oauth_redirect.text

    response = requests.post(
        f"{BASE_URL}/add", json={"a": 13.5, "b": -3.5}, timeout=5
    )
    evidence(
        "test_generated_docs_describe_and_drive_add_route",
        json.dumps(
            {
                "openapi": schema.status_code,
                "docs": docs.status_code,
                "redoc": redoc.status_code,
                "oauth_redirect": oauth_redirect.status_code,
                "calculation": response.text,
            }
        ),
        response.status_code,
    )
    assert response.status_code == 200
    assert response.json() == {"result": 10.0}


@contextmanager
def running_entrypoint(
    command: list[str], cwd: Path, env: dict[str, str], port: int, payload: dict[str, float]
) -> Iterator[requests.Response]:
    """Start one real application entry point and yield its feature response."""
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 10
    last_error: Exception | None = None
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                stdout, stderr = process.communicate(timeout=1)
                raise AssertionError(
                    f"entry point exited {process.returncode}: {stdout}{stderr}"
                )
            try:
                response = requests.post(
                    f"http://127.0.0.1:{port}/add", json=payload, timeout=1
                )
                if response.status_code == 200:
                    yield response
                    return
            except requests.RequestException as error:
                last_error = error
            time.sleep(0.1)
        raise AssertionError(f"entry point did not become ready: {last_error}")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_console_entry_uses_default_port_and_database(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.pop("PORT", None)
    env.pop("DATABASE_URL", None)
    with running_entrypoint(
        [str(CONSOLE)], tmp_path, env, 8000, {"a": 11.0, "b": 4.0}
    ) as response:
        evidence(
            "test_console_entry_uses_default_port_and_database",
            response.text,
            response.status_code,
        )
        assert response.json() == {"result": 15.0}
    assert (tmp_path / "calculator.db").is_file()


def test_script_entry_honors_port_and_database_environment(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PORT"] = "8181"
    env["DATABASE_URL"] = "sqlite:///script-environment.sqlite3"
    with running_entrypoint(
        [str(PYTHON), str(REPOSITORY_ROOT / "server.py")],
        tmp_path,
        env,
        8181,
        {"a": 12.0, "b": 5.0},
    ) as response:
        evidence(
            "test_script_entry_honors_port_and_database_environment",
            response.text,
            response.status_code,
        )
        assert response.json() == {"result": 17.0}
    assert (tmp_path / "script-environment.sqlite3").is_file()
    assert not (tmp_path / "calculator.db").exists()


def test_parallel_database_configuration_isolates_persistence(
    empty_store: None, tmp_path: Path
) -> None:
    managed = requests.post(
        f"{BASE_URL}/calculations",
        json={"operation": "add", "a": 20.0, "b": 1.0},
        timeout=5,
    )
    assert managed.status_code == 201

    env = os.environ.copy()
    env["PORT"] = "8182"
    env["DATABASE_URL"] = "sqlite:///isolated-process.sqlite3"
    with running_entrypoint(
        [str(PYTHON), str(REPOSITORY_ROOT / "server.py")],
        tmp_path,
        env,
        8182,
        {"a": 2.0, "b": 3.0},
    ):
        isolated_before = requests.get(
            "http://127.0.0.1:8182/calculations", timeout=5
        )
        isolated_created = requests.post(
            "http://127.0.0.1:8182/calculations",
            json={"operation": "mul", "a": 6.0, "b": 7.0},
            timeout=5,
        )

    managed_after = requests.get(f"{BASE_URL}/calculations", timeout=5)
    output = json.dumps(
        {
            "isolated_before": isolated_before.json(),
            "isolated_created": isolated_created.json(),
            "managed_after": managed_after.json(),
        }
    )
    evidence(
        "test_parallel_database_configuration_isolates_persistence",
        output,
        isolated_created.status_code,
    )
    assert isolated_before.status_code == 200
    assert isolated_before.json() == []
    assert isolated_created.status_code == 201
    assert isolated_created.json()["result"] == 42.0
    assert managed_after.status_code == 200
    assert [item["id"] for item in managed_after.json()] == [managed.json()["id"]]
    assert (tmp_path / "isolated-process.sqlite3").is_file()


def test_console_entry_rejects_invalid_port(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PORT"] = "not-an-integer"
    env["DATABASE_URL"] = "sqlite:///invalid-port.sqlite3"
    result = subprocess.run(
        [str(CONSOLE)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    print(
        "FT_CLI_EVIDENCE "
        + json.dumps(
            {
                "name": "test_console_entry_rejects_invalid_port",
                "actual_output": result.stderr,
                "actual_exit_code": result.returncode,
            },
            ensure_ascii=False,
        )
    )
    assert result.returncode == 1
    assert "invalid literal for int() with base 10: 'not-an-integer'" in result.stderr
    assert not (tmp_path / "invalid-port.sqlite3").exists()
