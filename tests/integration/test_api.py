"""Integration tests for calculator, persistence, and generated HTTP contracts."""

import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlmodel import Session

import server
from server import Calculation, create_app

CALCULATION_KEYS = {"id", "created_at", "operation", "a", "b", "result"}


def assert_calculation_response(
    body: dict[str, Any],
    *,
    operation: str,
    a: float,
    b: float,
    result: float,
) -> None:
    """Assert the complete public shape and value types of a stored calculation."""
    assert set(body) == CALCULATION_KEYS
    assert isinstance(body["id"], int) and not isinstance(body["id"], bool)
    assert isinstance(body["created_at"], str)
    datetime.fromisoformat(body["created_at"])
    assert body["operation"] == operation
    assert isinstance(body["operation"], str)
    for field, expected in (("a", a), ("b", b), ("result", result)):
        assert isinstance(body[field], float)
        assert body[field] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("path", "payload", "expected"),
    [
        pytest.param("/add", {"a": 8.0, "b": 2.0}, 10.0, id="add"),
        pytest.param("/subtract", {"a": 8.0, "b": 2.0}, 6.0, id="subtract"),
        pytest.param("/multiply", {"a": 8.0, "b": 2.0}, 16.0, id="multiply"),
        pytest.param("/divide", {"a": 8.0, "b": 2.0}, 4.0, id="divide"),
    ],
)
def test_direct_arithmetic_success(
    client: TestClient, path: str, payload: dict[str, float], expected: float
) -> None:
    response = client.post(path, json=payload)

    assert response.status_code == 200
    assert response.json() == {"result": expected}
    assert isinstance(response.json()["result"], float)


def test_direct_division_by_zero_has_exact_error(client: TestClient) -> None:
    response = client.post("/divide", json={"a": 8.0, "b": 0.0})

    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot divide by zero"}


@pytest.mark.parametrize(
    ("operation", "a", "b", "expected"),
    [
        pytest.param("add", 7.5, 2.5, 10.0, id="add"),
        pytest.param("sub", 7.5, 2.5, 5.0, id="sub"),
        pytest.param("mul", 7.5, 2.0, 15.0, id="mul"),
        pytest.param("div", 7.5, 2.5, 3.0, id="div"),
    ],
)
def test_create_calculation_for_each_operation(
    client: TestClient, operation: str, a: float, b: float, expected: float
) -> None:
    response = client.post("/calculations", json={"operation": operation, "a": a, "b": b})

    assert response.status_code == 201
    assert_calculation_response(
        response.json(), operation=operation, a=a, b=b, result=expected
    )


@pytest.mark.parametrize(
    ("payload", "detail"),
    [
        pytest.param(
            {"operation": "pow", "a": 2.0, "b": 3.0},
            "Unknown operation: pow. Use: ['add', 'sub', 'mul', 'div']",
            id="unknown-operation",
        ),
        pytest.param(
            {"operation": "div", "a": 2.0, "b": 0.0},
            "Cannot divide by zero",
            id="division-by-zero",
        ),
    ],
)
def test_failed_calculation_is_not_persisted(
    client: TestClient, payload: dict[str, object], detail: str
) -> None:
    response = client.post("/calculations", json=payload)

    assert response.status_code == 400
    assert response.json() == {"detail": detail}
    assert client.get("/calculations").json() == []


def test_list_calculations_is_initially_empty(client: TestClient) -> None:
    response = client.get("/calculations")

    assert response.status_code == 200
    assert response.json() == []


def test_list_calculations_returns_complete_shapes(client: TestClient) -> None:
    create_responses = [
        client.post(
            "/calculations", json={"operation": "add", "a": 1.25, "b": 2.75}
        ),
        client.post(
            "/calculations", json={"operation": "mul", "a": 3.0, "b": 2.5}
        ),
    ]
    assert all(response.status_code == 201 for response in create_responses)
    created = [response.json() for response in create_responses]

    response = client.get("/calculations")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    by_id = {item["id"]: item for item in body}
    assert set(by_id) == {item["id"] for item in created}
    assert_calculation_response(
        by_id[created[0]["id"]], operation="add", a=1.25, b=2.75, result=4.0
    )
    assert_calculation_response(
        by_id[created[1]["id"]], operation="mul", a=3.0, b=2.5, result=7.5
    )


def test_list_calculations_is_deterministically_newest_first(
    client: TestClient, app: FastAPI
) -> None:
    rows = [
        Calculation(
            operation="add",
            a=1.0,
            b=1.0,
            result=2.0,
            created_at=datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc),
        ),
        Calculation(
            operation="sub",
            a=5.0,
            b=2.0,
            result=3.0,
            created_at=datetime(2024, 3, 1, 8, 0, 0, tzinfo=timezone.utc),
        ),
        Calculation(
            operation="mul",
            a=2.0,
            b=3.0,
            result=6.0,
            created_at=datetime(2024, 2, 1, 8, 0, 0, tzinfo=timezone.utc),
        ),
    ]
    with Session(app.state.engine) as session:
        session.add_all(rows)
        session.commit()
        for row in rows:
            session.refresh(row)
    assert all(row.id is not None for row in rows)

    response = client.get("/calculations")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [rows[1].id, rows[2].id, rows[0].id]
    timestamps = [datetime.fromisoformat(item["created_at"]) for item in body]
    assert timestamps == sorted(timestamps, reverse=True)


def test_get_calculation_returns_stored_row(client: TestClient) -> None:
    created = client.post(
        "/calculations", json={"operation": "sub", "a": 9.0, "b": 3.5}
    ).json()

    response = client.get(f"/calculations/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created
    assert_calculation_response(
        response.json(), operation="sub", a=9.0, b=3.5, result=5.5
    )


def test_get_missing_calculation_has_exact_error(client: TestClient) -> None:
    response = client.get("/calculations/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Calculation not found"}


def test_delete_calculation_removes_row(client: TestClient) -> None:
    created = client.post(
        "/calculations", json={"operation": "add", "a": 2.0, "b": 3.0}
    ).json()

    response = client.delete(f"/calculations/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    missing = client.get(f"/calculations/{created['id']}")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Calculation not found"}


def test_delete_missing_calculation_has_exact_error(client: TestClient) -> None:
    response = client.delete("/calculations/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Calculation not found"}


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        pytest.param("/add", {"a": 1.0}, id="direct-request"),
        pytest.param(
            "/calculations", {"operation": "add", "a": 1.0}, id="stored-request"
        ),
    ],
)
def test_missing_request_fields_return_422(
    client: TestClient, path: str, payload: dict[str, object]
) -> None:
    assert client.post(path, json=payload).status_code == 422


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        pytest.param("/multiply", {"a": "not-a-number", "b": 2.0}, id="direct-request"),
        pytest.param(
            "/calculations",
            {"operation": "add", "a": [], "b": 2.0},
            id="stored-request",
        ),
    ],
)
def test_nonnumeric_operands_return_422(
    client: TestClient, path: str, payload: dict[str, object]
) -> None:
    assert client.post(path, json=payload).status_code == 422


@pytest.mark.parametrize("path", ["/add", "/calculations"])
def test_malformed_json_returns_422(client: TestClient, path: str) -> None:
    response = client.post(path, content=b'{"a":', headers={"content-type": "application/json"})

    assert response.status_code == 422


@pytest.mark.parametrize("method", ["GET", "DELETE"])
def test_noninteger_calculation_id_returns_422(client: TestClient, method: str) -> None:
    response = client.request(method, "/calculations/not-an-integer")

    assert response.status_code == 422


def test_lifespan_creates_calculation_table(
    app: FastAPI, database_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert not database_path.exists()
    dispose_mock = Mock(wraps=app.state.engine.dispose)
    monkeypatch.setattr(app.state.engine, "dispose", dispose_mock)

    with TestClient(app) as lifespan_client:
        assert lifespan_client.get("/calculations").status_code == 200
        assert database_path.is_file()
        assert "calculation" in inspect(app.state.engine).get_table_names()

    dispose_mock.assert_called_once_with()


def test_each_request_uses_and_closes_an_independent_session(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created_sessions: list[Any] = []

    class TrackingSession(Session):
        closed_by_dependency: bool

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.closed_by_dependency = False
            created_sessions.append(self)

        def close(self) -> None:
            self.closed_by_dependency = True
            super().close()

    monkeypatch.setattr(server, "Session", TrackingSession)

    assert client.get("/calculations").status_code == 200
    assert client.get("/calculations").status_code == 200

    assert len(created_sessions) == 2
    assert created_sessions[0] is not created_sessions[1]
    assert all(session.closed_by_dependency for session in created_sessions)


def test_committed_row_is_visible_across_separate_sessions(
    client: TestClient, app: FastAPI
) -> None:
    row = Calculation(operation="mul", a=4.0, b=2.5, result=10.0)
    with Session(app.state.engine) as writer:
        writer.add(row)
        writer.commit()
        writer.refresh(row)
        row_id = row.id
    assert row_id is not None

    with Session(app.state.engine) as reader:
        persisted = reader.get(Calculation, row_id)
        assert persisted is not None
        assert persisted.operation == "mul"
        assert persisted.result == pytest.approx(10.0)

    response = client.get(f"/calculations/{row_id}")
    assert response.status_code == 200
    assert response.json()["result"] == pytest.approx(10.0)


@pytest.mark.parametrize(
    "path", ["/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"]
)
def test_generated_documentation_routes_are_available(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert response.content


def test_openapi_preserves_service_identity(client: TestClient) -> None:
    document = client.get("/openapi.json").json()

    assert document["info"]["title"] == "Calculator API"
    assert document["info"]["version"] == "0.1.0"


def test_factory_resolves_database_url_from_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "from-environment.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    environment_app = create_app()
    try:
        with TestClient(environment_app) as environment_client:
            response = environment_client.post(
                "/calculations", json={"operation": "add", "a": 1.0, "b": 2.0}
            )
            assert response.status_code == 201
        assert database_path.is_file()
    finally:
        environment_app.state.engine.dispose()


def test_factory_rejects_invalid_database_url() -> None:
    with pytest.raises(ValueError) as exc_info:
        create_app("not a valid database url")

    assert str(exc_info.value) == "Invalid DATABASE_URL: provide a valid SQLAlchemy database URL"


def test_factory_database_url_error_does_not_expose_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = "postgresql://alice:dummy-password@example.invalid/calculator"

    def fail_to_create_engine(
        url: object, *, echo: bool, connect_args: dict[str, bool]
    ) -> NoReturn:
        raise ModuleNotFoundError(f"Unable to load database driver for {database_url}")

    monkeypatch.setattr(server, "create_engine", fail_to_create_engine)

    with pytest.raises(ValueError) as exc_info:
        create_app(database_url)

    displayed_exception = "".join(
        traceback.format_exception(exc_info.type, exc_info.value, exc_info.tb)
    )
    assert "Invalid DATABASE_URL: provide a valid SQLAlchemy database URL" in displayed_exception
    assert database_url not in displayed_exception
    assert "dummy-password" not in displayed_exception
