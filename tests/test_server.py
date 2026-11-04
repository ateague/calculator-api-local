"""Contract tests for calculator API routes and generated documentation."""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect
from sqlalchemy.pool import QueuePool
from sqlmodel import Session

from server import Calculation


DIRECT_ROUTES = ("/add", "/subtract", "/multiply", "/divide")


def _assert_explicit_utc_offset(value: str) -> None:
    """Assert an API datetime carries an explicit UTC offset."""
    parsed = datetime.fromisoformat(value)

    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)


def test_lifespan_creates_calculation_table(engine: Engine) -> None:
    """Application startup creates the SQLModel calculation table."""
    assert inspect(engine).has_table("calculation")


@pytest.mark.parametrize(
    ("route", "payload", "expected_body"),
    [
        pytest.param("/add", {"a": -1.25, "b": 2.5}, {"result": 1.25}, id="add"),
        pytest.param(
            "/subtract", {"a": 5.5, "b": 8}, {"result": -2.5}, id="subtract"
        ),
        pytest.param(
            "/multiply", {"a": -3, "b": 0.5}, {"result": -1.5}, id="multiply"
        ),
        pytest.param("/divide", {"a": 7.5, "b": 2.5}, {"result": 3.0}, id="divide"),
    ],
)
def test_direct_arithmetic_success(
    client: TestClient,
    route: str,
    payload: dict[str, float],
    expected_body: dict[str, float],
) -> None:
    """Each direct arithmetic route returns its exact result contract."""
    response = client.post(route, json=payload)

    assert response.status_code == 200
    assert response.json() == expected_body


@pytest.mark.parametrize("route", DIRECT_ROUTES)
@pytest.mark.parametrize(
    ("payload", "expected_location", "expected_type"),
    [
        pytest.param({"a": 2}, ("body", "b"), "missing", id="missing-required-value"),
        pytest.param([], ("body",), "model_attributes_type", id="malformed-body"),
        pytest.param(
            {"a": "not-a-number", "b": 2},
            ("body", "a"),
            "float_parsing",
            id="non-numeric-value",
        ),
    ],
)
def test_direct_arithmetic_validation(
    client: TestClient,
    route: str,
    payload: Any,
    expected_location: tuple[str, ...],
    expected_type: str,
) -> None:
    """Direct routes expose stable validation locations and error categories."""
    response = client.post(route, json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert [(tuple(error["loc"]), error["type"]) for error in detail] == [
        (expected_location, expected_type)
    ]


def test_direct_divide_by_zero(client: TestClient) -> None:
    """Division by zero retains its stable client error response."""
    response = client.post("/divide", json={"a": 4, "b": 0})

    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot divide by zero"}


@pytest.mark.parametrize(
    ("operation", "a", "b", "expected_result"),
    [
        pytest.param("add", 4.0, 3.0, 7.0, id="add"),
        pytest.param("sub", 4.0, 3.0, 1.0, id="sub"),
        pytest.param("mul", 4.0, 3.0, 12.0, id="mul"),
        pytest.param("div", 9.0, 3.0, 3.0, id="div"),
    ],
)
def test_create_calculation_persists_each_operation(
    client: TestClient,
    engine: Engine,
    operation: str,
    a: float,
    b: float,
    expected_result: float,
) -> None:
    """Every accepted identifier returns and persists the exact calculation."""
    response = client.post(
        "/calculations", json={"operation": operation, "a": a, "b": b}
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "operation", "a", "b", "result", "created_at"}
    assert {key: body[key] for key in ("operation", "a", "b", "result")} == {
        "operation": operation,
        "a": a,
        "b": b,
        "result": expected_result,
    }
    assert isinstance(body["id"], int) and not isinstance(body["id"], bool)
    assert isinstance(body["created_at"], str)
    _assert_explicit_utc_offset(body["created_at"])

    with Session(engine) as session:
        stored = session.get(Calculation, body["id"])

        assert stored is not None
        assert (stored.operation, stored.a, stored.b, stored.result) == (
            operation,
            a,
            b,
            expected_result,
        )


def test_create_calculation_rejects_unknown_operation(client: TestClient) -> None:
    """Unknown stored-calculation operations retain their exact client error."""
    response = client.post(
        "/calculations", json={"operation": "pow", "a": 2, "b": 8}
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Unknown operation: pow. Use: ['add', 'sub', 'mul', 'div']"
    }


def test_create_calculation_rejects_zero_divisor(client: TestClient) -> None:
    """Stored division translates its domain error to HTTP 400."""
    response = client.post(
        "/calculations", json={"operation": "div", "a": 2, "b": 0}
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot divide by zero"}


@pytest.mark.parametrize(
    ("payload", "expected_location", "expected_type"),
    [
        pytest.param(
            {"operation": "add", "a": 2},
            ("body", "b"),
            "missing",
            id="missing-required-value",
        ),
        pytest.param([], ("body",), "model_attributes_type", id="malformed-body"),
        pytest.param(
            {"operation": "add", "a": "not-a-number", "b": 2},
            ("body", "a"),
            "float_parsing",
            id="non-numeric-value",
        ),
    ],
)
def test_create_calculation_validation(
    client: TestClient,
    payload: Any,
    expected_location: tuple[str, ...],
    expected_type: str,
) -> None:
    """Stored-calculation validation asserts stable locations and categories."""
    response = client.post("/calculations", json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert [(tuple(error["loc"]), error["type"]) for error in detail] == [
        (expected_location, expected_type)
    ]


def test_list_calculations_is_empty_for_a_fresh_database(client: TestClient) -> None:
    """A fresh isolated database has no calculation history."""
    response = client.get("/calculations")

    assert response.status_code == 200
    assert response.json() == []


def test_list_calculations_returns_persisted_item(client: TestClient) -> None:
    """Calculation history returns a populated response contract."""
    created = client.post(
        "/calculations", json={"operation": "mul", "a": 2.5, "b": 4}
    )
    response = client.get("/calculations")

    assert created.status_code == 201
    assert response.status_code == 200
    assert response.json() == [created.json()]


def test_list_calculations_orders_by_timestamp_then_descending_id(
    client: TestClient, engine: Engine
) -> None:
    """History is newest-first with descending IDs breaking timestamp ties."""
    oldest = Calculation(
        operation="add",
        a=1,
        b=1,
        result=2,
        created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    newer_first = Calculation(
        operation="sub",
        a=5,
        b=2,
        result=3,
        created_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
    )
    newer_second = Calculation(
        operation="mul",
        a=3,
        b=4,
        result=12,
        created_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
    )
    with Session(engine) as session:
        session.add_all([oldest, newer_first, newer_second])
        session.commit()
        session.refresh(oldest)
        session.refresh(newer_first)
        session.refresh(newer_second)
        oldest_id = oldest.id
        newer_first_id = newer_first.id
        newer_second_id = newer_second.id

    assert oldest_id is not None
    assert newer_first_id is not None
    assert newer_second_id is not None
    assert newer_second_id > newer_first_id

    response = client.get("/calculations")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [
        newer_second_id,
        newer_first_id,
        oldest_id,
    ]


def test_get_calculation_returns_exact_stored_item(client: TestClient) -> None:
    """Item lookup returns the exact creation response."""
    created = client.post(
        "/calculations", json={"operation": "sub", "a": 10, "b": 2.5}
    )
    calculation_id = created.json()["id"]

    response = client.get(f"/calculations/{calculation_id}")

    assert created.status_code == 201
    assert response.status_code == 200
    assert response.json() == created.json()


def test_get_calculation_returns_not_found(client: TestClient) -> None:
    """Missing item lookup exposes the stable 404 detail."""
    response = client.get("/calculations/2147483647")

    assert response.status_code == 404
    assert response.json() == {"detail": "Calculation not found"}


def test_delete_calculation_removes_row(client: TestClient, engine: Engine) -> None:
    """Deletion returns an empty 204 and removes the persisted row."""
    created = client.post(
        "/calculations", json={"operation": "add", "a": 81, "b": 19}
    )
    calculation_id = created.json()["id"]

    deleted = client.delete(f"/calculations/{calculation_id}")

    assert created.status_code == 201
    assert deleted.status_code == 204
    assert deleted.content == b""
    with Session(engine) as session:
        assert session.get(Calculation, calculation_id) is None

    deleted_again = client.delete(f"/calculations/{calculation_id}")

    assert deleted_again.status_code == 404
    assert deleted_again.json() == {"detail": "Calculation not found"}


def test_legacy_naive_timestamp_is_retained_and_serialized_as_utc(
    client: TestClient, engine: Engine
) -> None:
    """A legacy naive database timestamp is preserved but exposed as UTC."""
    legacy_timestamp = datetime(2001, 2, 3, 4, 5, 6, 789000)
    calculation = Calculation(
        operation="add",
        a=20,
        b=22,
        result=42,
        created_at=legacy_timestamp,
    )
    with Session(engine) as session:
        session.add(calculation)
        session.commit()
        session.refresh(calculation)
        calculation_id = calculation.id

        assert calculation.created_at == legacy_timestamp
        assert calculation.created_at.tzinfo is None

    assert calculation_id is not None
    response = client.get(f"/calculations/{calculation_id}")

    assert response.status_code == 200
    serialized_timestamp = response.json()["created_at"]
    assert isinstance(serialized_timestamp, str)
    _assert_explicit_utc_offset(serialized_timestamp)
    assert datetime.fromisoformat(serialized_timestamp) == legacy_timestamp.replace(
        tzinfo=timezone.utc
    )

    with Session(engine) as session:
        retained = session.get(Calculation, calculation_id)

        assert retained is not None
        assert retained.created_at == legacy_timestamp
        assert retained.created_at.tzinfo is None


def test_request_dependency_returns_sessions_to_engine_pool(
    client: TestClient, engine: Engine
) -> None:
    """Database-backed success and error requests return checked-out connections."""
    pool = engine.pool
    assert isinstance(pool, QueuePool)
    assert pool.checkedout() == 0

    created = client.post(
        "/calculations", json={"operation": "add", "a": 20, "b": 22}
    )

    assert created.status_code == 201
    assert pool.checkedout() == 0

    missing = client.get("/calculations/2147483647")

    assert missing.status_code == 404
    assert pool.checkedout() == 0


def test_openapi_and_generated_documentation(client: TestClient) -> None:
    """OpenAPI, Swagger UI, and ReDoc expose the calculator contract."""
    openapi_response = client.get("/openapi.json")
    docs_response = client.get("/docs")
    redoc_response = client.get("/redoc")

    assert openapi_response.status_code == 200
    assert docs_response.status_code == 200
    assert redoc_response.status_code == 200

    schema = openapi_response.json()
    assert schema["info"]["title"] == "Calculator API"
    assert schema["info"]["version"] == "0.1.0"

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
    actual_operations = {
        (path, method)
        for path, methods in schema["paths"].items()
        for method in methods
        if method in {"get", "post", "delete"}
    }
    assert actual_operations == expected_operations
    assert "Swagger UI" in docs_response.text
    assert "ReDoc" in redoc_response.text
