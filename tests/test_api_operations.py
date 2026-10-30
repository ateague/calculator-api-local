"""HTTP behavior tests for stateless calculator operations and generated docs."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    ("route", "payload", "expected"),
    [
        pytest.param("/add", {"a": 7.5, "b": 2.5}, 10.0, id="post-add"),
        pytest.param("/subtract", {"a": 7.5, "b": 2.5}, 5.0, id="post-subtract"),
        pytest.param("/multiply", {"a": -3.0, "b": 2.5}, -7.5, id="post-multiply"),
        pytest.param("/divide", {"a": 7.5, "b": 2.5}, 3.0, id="post-divide"),
    ],
)
def test_arithmetic_routes_succeed(
    client: TestClient, route: str, payload: dict[str, float], expected: float
) -> None:
    response = client.post(route, json=payload)

    assert response.status_code == 200
    assert response.json() == {"result": expected}


def test_divide_route_translates_zero_divisor_error(client: TestClient) -> None:
    response = client.post("/divide", json={"a": 8.0, "b": 0.0})

    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot divide by zero"}


@pytest.mark.parametrize(
    ("route", "payload"),
    [
        pytest.param("/add", {"a": 1.0}, id="add-missing-b"),
        pytest.param("/add", {"a": "not-a-number", "b": 2.0}, id="add-nonnumeric-a"),
        pytest.param("/subtract", {"a": 1.0}, id="subtract-missing-b"),
        pytest.param(
            "/subtract", {"a": "not-a-number", "b": 2.0}, id="subtract-nonnumeric-a"
        ),
        pytest.param("/multiply", {"a": 1.0}, id="multiply-missing-b"),
        pytest.param(
            "/multiply", {"a": "not-a-number", "b": 2.0}, id="multiply-nonnumeric-a"
        ),
        pytest.param("/divide", {"a": 1.0}, id="divide-missing-b"),
        pytest.param(
            "/divide", {"a": "not-a-number", "b": 2.0}, id="divide-nonnumeric-a"
        ),
    ],
)
def test_arithmetic_routes_reject_invalid_operands(
    client: TestClient, route: str, payload: dict[str, object]
) -> None:
    response = client.post(route, json=payload)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


@pytest.mark.parametrize(
    "route",
    [
        pytest.param("/openapi.json", id="openapi"),
        pytest.param("/docs", id="swagger-ui"),
        pytest.param("/redoc", id="redoc"),
    ],
)
def test_generated_documentation_surfaces_are_available(
    client: TestClient, route: str
) -> None:
    response = client.get(route)

    assert response.status_code == 200


def test_oauth_redirect_helper_remains_registered(application: FastAPI) -> None:
    matching_routes = [
        route
        for route in application.routes
        if getattr(route, "path", None) == "/docs/oauth2-redirect"
    ]

    assert len(matching_routes) == 1
    methods = getattr(matching_routes[0], "methods", None)
    assert methods is not None
    assert "GET" in methods
