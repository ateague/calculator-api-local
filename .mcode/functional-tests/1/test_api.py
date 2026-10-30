"""Functional tests against a real calculator-api subprocess and SQLite database."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
import requests
from server_runner import ServerRunner, free_port

REPO_ROOT = Path(__file__).parents[3]
CONSOLE = REPO_ROOT / ".venv" / "bin" / "calculator-api"


@pytest.fixture(scope="session")
def base_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Start the installed app with a run-owned database and track its PID."""
    runtime_dir = tmp_path_factory.mktemp("calculator-functional-api")
    database_path = runtime_dir / "functional-calculator.db"
    port = free_port()
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["DATABASE_URL"] = f"sqlite:///{database_path}"
    with ServerRunner(
        [str(CONSOLE)],
        cwd=runtime_dir,
        env=env,
        port=port,
        label="calculator-api",
    ) as server:
        server.wait_until_ready(
            lambda: requests.post(
                f"{server.base_url}/add", json={"a": 1, "b": 1}, timeout=0.5
            ),
            lambda response: response.status_code == 200
            and response.json() == {"result": 2.0},
        )
        assert database_path.exists()
        yield server.base_url


@pytest.fixture(autouse=True)
def isolated_history(base_url: str) -> Iterator[None]:
    """Use the public API to give every test an empty, reproducible history."""

    def clear() -> None:
        response = requests.get(f"{base_url}/calculations", timeout=5)
        assert response.status_code == 200
        for calculation in response.json():
            deleted = requests.delete(
                f"{base_url}/calculations/{calculation['id']}", timeout=5
            )
            assert deleted.status_code == 204

    clear()
    yield
    clear()


class TestStatelessArithmetic:
    @pytest.mark.parametrize(
        ("name", "path", "payload", "expected"),
        [
            ("test_add_success", "/add", {"a": 2, "b": 3}, {"result": 5.0}),
            (
                "test_subtract_success",
                "/subtract",
                {"a": 2, "b": 3},
                {"result": -1.0},
            ),
            (
                "test_multiply_success",
                "/multiply",
                {"a": -2, "b": 3},
                {"result": -6.0},
            ),
            (
                "test_divide_success",
                "/divide",
                {"a": 7.5, "b": 2.5},
                {"result": 3.0},
            ),
        ],
    )
    def test_success(
        self, base_url: str, record_rest, name: str, path: str, payload: dict, expected: dict
    ) -> None:
        response = requests.post(f"{base_url}{path}", json=payload, timeout=5)
        record_rest(name, response)
        assert response.status_code == 200
        assert response.json() == expected

    @pytest.mark.parametrize(
        ("name", "body"),
        [
            ("test_malformed_json_validation", "{"),
            ("test_missing_operand_validation", '{"a": 1}'),
            ("test_nonnumeric_operand_validation", '{"a": "bad", "b": 2}'),
        ],
    )
    def test_shared_validation_on_every_route(
        self, base_url: str, record_rest_sequence, name: str, body: str
    ) -> None:
        responses = [
            requests.post(
                f"{base_url}{path}",
                data=body,
                headers={"content-type": "application/json"},
                timeout=5,
            )
            for path in ("/add", "/subtract", "/multiply", "/divide")
        ]
        record_rest_sequence(name, responses)
        assert [response.status_code for response in responses] == [422, 422, 422, 422]
        assert all(response.json()["detail"] for response in responses)

    def test_divide_by_zero_exact_error(self, base_url: str, record_rest) -> None:
        response = requests.post(
            f"{base_url}/divide", json={"a": 8, "b": 0}, timeout=5
        )
        record_rest("test_divide_by_zero_exact_error", response)
        assert response.status_code == 400
        assert response.json() == {"detail": "Cannot divide by zero"}


class TestCalculationHistory:
    def test_all_operation_tokens_persist_and_retrieve(
        self, base_url: str, record_rest_sequence
    ) -> None:
        cases = [
            ("add", 2, 3, 5.0),
            ("sub", 2, 3, -1.0),
            ("mul", -2, 3, -6.0),
            ("div", 7.5, 2.5, 3.0),
        ]
        retrieved = []
        for token, a, b, expected in cases:
            created = requests.post(
                f"{base_url}/calculations",
                json={"operation": token, "a": a, "b": b},
                timeout=5,
            )
            assert created.status_code == 201
            item = created.json()
            assert item["operation"] == token
            assert item["result"] == expected
            assert isinstance(item["id"], int) and item["id"] > 0
            created_at = datetime.fromisoformat(item["created_at"])
            assert created_at.tzinfo is None
            found = requests.get(
                f"{base_url}/calculations/{item['id']}", timeout=5
            )
            assert found.status_code == 200
            assert found.json() == item
            retrieved.append(found)
        record_rest_sequence("test_all_operation_tokens_persist_and_retrieve", retrieved)

    def test_history_is_newest_first(self, base_url: str, record_rest) -> None:
        created = []
        for value in (10, 20, 30):
            response = requests.post(
                f"{base_url}/calculations",
                json={"operation": "add", "a": value, "b": 1},
                timeout=5,
            )
            assert response.status_code == 201
            created.append(response.json())
        listed = requests.get(f"{base_url}/calculations", timeout=5)
        record_rest("test_history_is_newest_first", listed)
        assert listed.status_code == 200
        history = listed.json()
        assert [item["id"] for item in history] == [
            item["id"] for item in reversed(created)
        ]
        timestamps = [
            datetime.fromisoformat(item["created_at"])
            for item in history
        ]
        assert all(timestamp.tzinfo is None for timestamp in timestamps)
        assert timestamps == sorted(timestamps, reverse=True)

    def test_unknown_operation_fails_without_persisting(
        self, base_url: str, record_rest
    ) -> None:
        response = requests.post(
            f"{base_url}/calculations",
            json={"operation": "power", "a": 2, "b": 3},
            timeout=5,
        )
        record_rest("test_unknown_operation_fails_without_persisting", response)
        assert response.status_code == 400
        assert response.json() == {
            "detail": "Unknown operation: power. Use: ['add', 'sub', 'mul', 'div']"
        }
        assert requests.get(f"{base_url}/calculations", timeout=5).json() == []

    def test_persisted_divide_by_zero_fails_without_persisting(
        self, base_url: str, record_rest
    ) -> None:
        response = requests.post(
            f"{base_url}/calculations",
            json={"operation": "div", "a": 2, "b": 0},
            timeout=5,
        )
        record_rest("test_persisted_divide_by_zero_fails_without_persisting", response)
        assert response.status_code == 400
        assert response.json() == {"detail": "Cannot divide by zero"}
        assert requests.get(f"{base_url}/calculations", timeout=5).json() == []

    def test_missing_required_calculation_field(self, base_url: str, record_rest) -> None:
        response = requests.post(
            f"{base_url}/calculations", json={"operation": "add", "a": 2}, timeout=5
        )
        record_rest("test_missing_required_calculation_field", response)
        assert response.status_code == 422
        assert response.json()["detail"]

    def test_get_missing_calculation(self, base_url: str, record_rest) -> None:
        response = requests.get(f"{base_url}/calculations/999999", timeout=5)
        record_rest("test_get_missing_calculation", response)
        assert response.status_code == 404
        assert response.json() == {"detail": "Calculation not found"}

    def test_delete_is_bodyless_and_durable(self, base_url: str, record_rest) -> None:
        created = requests.post(
            f"{base_url}/calculations",
            json={"operation": "sub", "a": 9, "b": 4},
            timeout=5,
        ).json()
        deleted = requests.delete(
            f"{base_url}/calculations/{created['id']}", timeout=5
        )
        record_rest("test_delete_is_bodyless_and_durable", deleted)
        assert deleted.status_code == 204
        assert deleted.content == b""
        assert requests.get(f"{base_url}/calculations", timeout=5).json() == []
        missing = requests.get(
            f"{base_url}/calculations/{created['id']}", timeout=5
        )
        assert missing.status_code == 404

    def test_delete_missing_calculation(self, base_url: str, record_rest) -> None:
        response = requests.delete(f"{base_url}/calculations/999999", timeout=5)
        record_rest("test_delete_missing_calculation", response)
        assert response.status_code == 404
        assert response.json() == {"detail": "Calculation not found"}
