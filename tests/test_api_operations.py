"""HTTP contract coverage for the four stateless calculator routes."""

import pytest


@pytest.mark.parametrize(
    ("path", "payload", "expected"),
    [
        ("/add", {"a": 2, "b": 3}, 5.0),
        ("/subtract", {"a": -2, "b": 3}, -5.0),
        ("/multiply", {"a": 2.5, "b": 4}, 10.0),
        ("/divide", {"a": 7.5, "b": 2.5}, 3.0),
    ],
)
def test_direct_operation_success(
    app_context, path: str, payload: dict[str, float], expected: float
) -> None:
    response = app_context.client.post(path, json=payload)

    assert response.status_code == 200
    assert response.json() == {"result": expected}


def test_direct_division_by_zero_returns_exact_400(app_context) -> None:
    response = app_context.client.post("/divide", json={"a": 4, "b": 0})

    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot divide by zero"}


@pytest.mark.parametrize("path", ["/add", "/subtract", "/multiply", "/divide"])
def test_direct_operations_reject_malformed_json(app_context, path: str) -> None:
    response = app_context.client.post(
        path,
        content="{",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize("path", ["/add", "/subtract", "/multiply", "/divide"])
def test_direct_operations_reject_missing_operand(app_context, path: str) -> None:
    response = app_context.client.post(path, json={"a": 2})

    assert response.status_code == 422


@pytest.mark.parametrize("path", ["/add", "/subtract", "/multiply", "/divide"])
def test_direct_operations_reject_non_numeric_operand(app_context, path: str) -> None:
    response = app_context.client.post(path, json={"a": 2, "b": "not-a-number"})

    assert response.status_code == 422
