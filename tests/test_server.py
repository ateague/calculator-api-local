"""Contract tests for calculator API routes and generated documentation."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect


DIRECT_ROUTES = ("/add", "/subtract", "/multiply", "/divide")


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
