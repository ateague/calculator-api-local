"""HTTP and database coverage for persisted calculations."""

from datetime import datetime

import pytest
from sqlmodel import Session

from calculator_api.models import Calculation


@pytest.mark.parametrize(
    ("operation", "a", "b", "expected"),
    [
        ("add", 3, 2, 5.0),
        ("sub", 3, 5, -2.0),
        ("mul", -3, 2, -6.0),
        ("div", 7.5, 2.5, 3.0),
    ],
)
def test_create_each_calculation_operation(
    app_context,
    operation: str,
    a: float,
    b: float,
    expected: float,
) -> None:
    response = app_context.client.post(
        "/calculations",
        json={"operation": operation, "a": a, "b": b},
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "operation", "a", "b", "result", "created_at"}
    assert isinstance(body["id"], int)
    assert body["operation"] == operation
    assert body["a"] == float(a)
    assert body["b"] == float(b)
    assert body["result"] == pytest.approx(expected)
    datetime.fromisoformat(body["created_at"])

    listed = app_context.client.get("/calculations")
    assert listed.status_code == 200
    assert listed.json() == [body]


def test_unknown_operation_is_400_and_adds_no_row(app_context) -> None:
    response = app_context.client.post(
        "/calculations",
        json={"operation": "mod", "a": 7, "b": 2},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Unknown operation: mod. Use: ['add', 'sub', 'mul', 'div']"
    }
    assert app_context.client.get("/calculations").json() == []


def test_persisted_division_by_zero_is_400_and_adds_no_row(app_context) -> None:
    response = app_context.client.post(
        "/calculations",
        json={"operation": "div", "a": 7, "b": 0},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot divide by zero"}
    assert app_context.client.get("/calculations").json() == []


def test_create_rejects_malformed_json_and_adds_no_row(app_context) -> None:
    response = app_context.client.post(
        "/calculations",
        content="{",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert app_context.client.get("/calculations").json() == []


@pytest.mark.parametrize(
    "payload",
    [
        {"a": 1, "b": 2},
        {"operation": "add", "a": 1},
        {"operation": "add", "a": "invalid", "b": 2},
    ],
)
def test_create_validation_errors_add_no_row(app_context, payload: dict[str, object]) -> None:
    response = app_context.client.post("/calculations", json=payload)

    assert response.status_code == 422
    assert app_context.client.get("/calculations").json() == []


def test_list_is_empty_for_a_fresh_database(app_context) -> None:
    response = app_context.client.get("/calculations")

    assert response.status_code == 200
    assert response.json() == []


def test_list_returns_multiple_rows_newest_first_with_controlled_timestamps(app_context) -> None:
    records = [
        Calculation(
            operation="add",
            a=1,
            b=1,
            result=2,
            created_at=datetime(2024, 1, 1, 12, 0, 0),
        ),
        Calculation(
            operation="sub",
            a=5,
            b=3,
            result=2,
            created_at=datetime(2024, 1, 3, 12, 0, 0),
        ),
        Calculation(
            operation="mul",
            a=2,
            b=3,
            result=6,
            created_at=datetime(2024, 1, 2, 12, 0, 0),
        ),
    ]
    with Session(app_context.engine) as session:
        session.add_all(records)
        session.commit()

    response = app_context.client.get("/calculations")

    assert response.status_code == 200
    assert [item["operation"] for item in response.json()] == ["sub", "mul", "add"]
    assert [item["created_at"] for item in response.json()] == [
        "2024-01-03T12:00:00",
        "2024-01-02T12:00:00",
        "2024-01-01T12:00:00",
    ]


def test_get_calculation_success(app_context) -> None:
    created = app_context.client.post(
        "/calculations",
        json={"operation": "add", "a": 4, "b": 6},
    ).json()

    response = app_context.client.get(f"/calculations/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_calculation_returns_404(app_context) -> None:
    response = app_context.client.get("/calculations/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Calculation not found"}


def test_delete_returns_empty_204_and_record_is_absent_afterward(app_context) -> None:
    created = app_context.client.post(
        "/calculations",
        json={"operation": "mul", "a": 4, "b": 6},
    ).json()

    response = app_context.client.delete(f"/calculations/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert app_context.client.get("/calculations").json() == []
    missing = app_context.client.get(f"/calculations/{created['id']}")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Calculation not found"}


def test_delete_unknown_calculation_returns_404(app_context) -> None:
    response = app_context.client.delete("/calculations/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Calculation not found"}


@pytest.mark.parametrize("method", ["get", "delete"])
def test_calculation_paths_reject_non_integer_ids(app_context, method: str) -> None:
    response = getattr(app_context.client, method)("/calculations/not-an-integer")

    assert response.status_code == 422
