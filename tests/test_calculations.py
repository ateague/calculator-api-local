"""HTTP and real-SQLModel behavior tests for persisted calculations."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session

from server import Calculation

RESPONSE_FIELDS = {"operation", "a", "b", "result", "id", "created_at"}


def assert_complete_calculation(
    body: dict[str, object],
    *,
    operation: str,
    a: float,
    b: float,
    result: float,
) -> None:
    """Assert the complete public response schema for one calculation."""
    assert set(body) == RESPONSE_FIELDS
    assert body["operation"] == operation
    assert body["a"] == a
    assert body["b"] == b
    assert body["result"] == result
    assert isinstance(body["id"], int)
    created_at = body["created_at"]
    assert isinstance(created_at, str)
    parsed_created_at = datetime.fromisoformat(created_at)
    assert parsed_created_at.tzinfo is None
    assert not created_at.endswith("Z")


def test_calculation_created_at_default_is_naive() -> None:
    calculation = Calculation(operation="add", a=1.0, b=2.0, result=3.0)

    assert calculation.created_at.tzinfo is None


@pytest.mark.parametrize(
    ("operation", "a", "b", "expected"),
    [
        pytest.param("add", 8.0, 2.0, 10.0, id="persist-add"),
        pytest.param("sub", 8.0, 2.0, 6.0, id="persist-subtract"),
        pytest.param("mul", -4.0, 2.5, -10.0, id="persist-multiply"),
        pytest.param("div", 8.0, 2.0, 4.0, id="persist-divide"),
    ],
)
def test_create_calculation_persists_every_operation(
    client: TestClient,
    operation: str,
    a: float,
    b: float,
    expected: float,
) -> None:
    response = client.post(
        "/calculations", json={"operation": operation, "a": a, "b": b}
    )

    assert response.status_code == 201
    created = response.json()
    assert_complete_calculation(
        created, operation=operation, a=a, b=b, result=expected
    )

    persisted = client.get(f"/calculations/{created['id']}")
    assert persisted.status_code == 200
    assert persisted.json() == created


def test_create_calculation_rejects_unknown_operation(client: TestClient) -> None:
    response = client.post(
        "/calculations", json={"operation": "power", "a": 2.0, "b": 3.0}
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Unknown operation: power. Use: ['add', 'sub', 'mul', 'div']"
    }
    assert client.get("/calculations").json() == []


def test_create_calculation_rejects_division_by_zero(client: TestClient) -> None:
    response = client.post(
        "/calculations", json={"operation": "div", "a": 2.0, "b": 0.0}
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot divide by zero"}
    assert client.get("/calculations").json() == []


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"a": 1.0, "b": 2.0}, id="missing-operation"),
        pytest.param(
            {"operation": "add", "a": "not-a-number", "b": 2.0},
            id="nonnumeric-a",
        ),
        pytest.param(
            {"operation": "add", "a": 1.0, "b": "not-a-number"},
            id="nonnumeric-b",
        ),
    ],
)
def test_create_calculation_rejects_invalid_payload(
    client: TestClient, payload: dict[str, object]
) -> None:
    response = client.post("/calculations", json=payload)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_list_calculations_is_empty_initially(client: TestClient) -> None:
    response = client.get("/calculations")

    assert response.status_code == 200
    assert response.json() == []


def test_list_calculations_orders_newest_first_deterministically(
    client: TestClient, database_engine: Engine
) -> None:
    created = [
        client.post(
            "/calculations", json={"operation": "add", "a": value, "b": 1.0}
        ).json()
        for value in (1.0, 2.0, 3.0)
    ]
    base_time = datetime(2024, 1, 1, 12, 0, 0)

    with Session(database_engine) as session:
        for index, body in enumerate(created):
            calculation = session.get(Calculation, body["id"])
            assert calculation is not None
            calculation.created_at = base_time + timedelta(minutes=index)
        session.commit()

    response = client.get("/calculations")

    assert response.status_code == 200
    listed = response.json()
    assert [item["id"] for item in listed] == [
        created[2]["id"],
        created[1]["id"],
        created[0]["id"],
    ]
    for body in listed:
        assert set(body) == RESPONSE_FIELDS


def test_get_calculation_returns_complete_found_record(client: TestClient) -> None:
    created = client.post(
        "/calculations", json={"operation": "mul", "a": 6.0, "b": 7.0}
    ).json()

    response = client.get(f"/calculations/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created
    assert_complete_calculation(
        response.json(), operation="mul", a=6.0, b=7.0, result=42.0
    )


def test_get_calculation_returns_not_found(client: TestClient) -> None:
    response = client.get("/calculations/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Calculation not found"}


def test_get_calculation_rejects_noninteger_id(client: TestClient) -> None:
    response = client.get("/calculations/not-an-integer")

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_delete_calculation_removes_record_and_returns_empty_body(
    client: TestClient,
) -> None:
    created = client.post(
        "/calculations", json={"operation": "sub", "a": 10.0, "b": 4.0}
    ).json()

    response = client.delete(f"/calculations/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    missing = client.get(f"/calculations/{created['id']}")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Calculation not found"}


def test_delete_calculation_returns_not_found(client: TestClient) -> None:
    response = client.delete("/calculations/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Calculation not found"}


def test_delete_calculation_rejects_noninteger_id(client: TestClient) -> None:
    response = client.delete("/calculations/not-an-integer")

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
