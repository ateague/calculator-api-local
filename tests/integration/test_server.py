"""HTTP acceptance tests for the calculator API."""

from datetime import datetime
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlmodel import Session

from core import add, divide, multiply, subtract
from server import (
    OPERATIONS,
    Calculation,
    Settings,
    create_app,
    create_database_engine,
)

STATELESS_PATHS = ["/add", "/subtract", "/multiply", "/divide"]
BUSINESS_OPERATIONS = {
    "/add": {"post"},
    "/subtract": {"post"},
    "/multiply": {"post"},
    "/divide": {"post"},
    "/calculations": {"get", "post"},
    "/calculations/{calculation_id}": {"delete", "get"},
}


def _app(client: TestClient) -> FastAPI:
    return cast(FastAPI, client.app)


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_operation_registry_has_exact_tokens_and_function_mappings() -> None:
    assert set(OPERATIONS) == {"add", "sub", "mul", "div"}
    assert OPERATIONS["add"] is add
    assert OPERATIONS["sub"] is subtract
    assert OPERATIONS["mul"] is multiply
    assert OPERATIONS["div"] is divide


@pytest.mark.parametrize(
    ("path", "payload", "expected"),
    [
        ("/add", {"a": 2, "b": 3}, 5.0),
        ("/subtract", {"a": 2, "b": 3}, -1.0),
        ("/multiply", {"a": -2, "b": 3}, -6.0),
        ("/divide", {"a": 7.5, "b": 2.5}, 3.0),
    ],
)
def test_stateless_endpoint_success(
    client: TestClient, path: str, payload: dict[str, float], expected: float
) -> None:
    response = client.post(path, json=payload)

    assert response.status_code == 200
    assert response.json() == {"result": expected}


@pytest.mark.parametrize("path", STATELESS_PATHS)
@pytest.mark.parametrize(
    "body",
    [
        pytest.param("{", id="malformed-json"),
        pytest.param('{"a": 1}', id="missing-operand"),
        pytest.param(
            '{"a": "not-a-number", "b": 2}',
            id="nonnumeric-operand",
        ),
    ],
)
def test_each_stateless_endpoint_rejects_invalid_requests(
    client: TestClient, path: str, body: str
) -> None:
    response = client.post(path, content=body, headers={"content-type": "application/json"})

    assert response.status_code == 422
    assert response.json()["detail"]


def test_stateless_divide_by_zero_returns_exact_error(client: TestClient) -> None:
    response = client.post("/divide", json={"a": 8, "b": 0})

    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot divide by zero"}


@pytest.mark.parametrize(
    ("token", "a", "b", "expected"),
    [
        ("add", 2, 3, 5.0),
        ("sub", 2, 3, -1.0),
        ("mul", -2, 3, -6.0),
        ("div", 7.5, 2.5, 3.0),
    ],
)
def test_create_calculation_persists_every_operation_token(
    client: TestClient, token: str, a: float, b: float, expected: float
) -> None:
    response = client.post("/calculations", json={"operation": token, "a": a, "b": b})

    assert response.status_code == 201
    calculation = response.json()
    assert calculation["operation"] == token
    assert calculation["a"] == float(a)
    assert calculation["b"] == float(b)
    assert calculation["result"] == expected
    assert isinstance(calculation["id"], int)
    assert calculation["id"] > 0
    assert isinstance(_parse_timestamp(calculation["created_at"]), datetime)
    assert client.get("/calculations").json() == [calculation]


@pytest.mark.parametrize(
    ("payload", "detail"),
    [
        (
            {"operation": "power", "a": 2, "b": 3},
            "Unknown operation: power. Use: ['add', 'sub', 'mul', 'div']",
        ),
        ({"operation": "div", "a": 2, "b": 0}, "Cannot divide by zero"),
    ],
)
def test_failed_calculation_creation_does_not_persist(
    client: TestClient, payload: dict[str, float | str], detail: str
) -> None:
    response = client.post("/calculations", json=payload)

    assert response.status_code == 400
    assert response.json() == {"detail": detail}
    assert client.get("/calculations").json() == []


def test_calculation_history_is_initially_empty(client: TestClient) -> None:
    response = client.get("/calculations")

    assert response.status_code == 200
    assert response.json() == []


def test_calculation_history_is_newest_first_without_clock_timing(client: TestClient) -> None:
    created = []
    for index in (10, 20, 30):
        response = client.post(
            "/calculations", json={"operation": "add", "a": index, "b": 1}
        )
        assert response.status_code == 201
        created.append(response.json())
    timestamps = [
        datetime(2024, 1, 1, 12, 0, 0),
        datetime(2024, 1, 3, 12, 0, 0),
        datetime(2024, 1, 2, 12, 0, 0),
    ]
    engine = _app(client).state.engine
    with Session(engine) as session:
        for item, created_at in zip(created, timestamps, strict=True):
            calculation = session.get(Calculation, item["id"])
            assert calculation is not None
            calculation.created_at = created_at
            session.add(calculation)
        session.commit()

    response = client.get("/calculations")

    assert response.status_code == 200
    history = response.json()
    assert [item["id"] for item in history] == [
        created[1]["id"],
        created[2]["id"],
        created[0]["id"],
    ]
    parsed_timestamps = [_parse_timestamp(item["created_at"]) for item in history]
    assert parsed_timestamps == sorted(parsed_timestamps, reverse=True)


def test_get_calculation_returns_matching_row_and_exact_missing_error(
    client: TestClient,
) -> None:
    created = client.post(
        "/calculations", json={"operation": "mul", "a": 4, "b": 2.5}
    ).json()

    found = client.get(f"/calculations/{created['id']}")
    missing = client.get("/calculations/999999")

    assert found.status_code == 200
    assert found.json() == created
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Calculation not found"}


def test_delete_calculation_is_bodyless_and_durable(client: TestClient) -> None:
    created = client.post(
        "/calculations", json={"operation": "sub", "a": 9, "b": 4}
    ).json()

    deleted = client.delete(f"/calculations/{created['id']}")

    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get("/calculations").json() == []
    missing_after_delete = client.get(f"/calculations/{created['id']}")
    assert missing_after_delete.status_code == 404
    assert missing_after_delete.json() == {"detail": "Calculation not found"}


def test_delete_missing_calculation_returns_exact_error(client: TestClient) -> None:
    response = client.delete("/calculations/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Calculation not found"}


def test_lifespan_creates_table_on_selected_engine(client: TestClient) -> None:
    selected_engine = _app(client).state.engine

    assert inspect(selected_engine).get_table_names() == ["calculation"]


def test_file_backed_databases_are_isolated(client: TestClient, tmp_path: Path) -> None:
    primary = client.post(
        "/calculations", json={"operation": "add", "a": 1, "b": 2}
    ).json()
    secondary_path = tmp_path / "second-calculator-test.db"
    secondary_url = f"sqlite:///{secondary_path}"
    secondary_engine = create_database_engine(secondary_url)
    secondary_app = create_app(
        engine=secondary_engine,
        settings=Settings(database_url=secondary_url),
    )

    try:
        with TestClient(secondary_app) as secondary_client:
            assert secondary_client.get("/calculations").json() == []
            secondary = secondary_client.post(
                "/calculations", json={"operation": "mul", "a": 3, "b": 4}
            ).json()
            assert secondary_client.get("/calculations").json() == [secondary]
    finally:
        secondary_engine.dispose()

    assert secondary_path.exists()
    assert client.get("/calculations").json() == [primary]
    assert _app(client).state.engine.url.database != secondary_engine.url.database


def test_repository_database_is_untouched(
    client: TestClient, repository_database_guard: Path
) -> None:
    selected_database = Path(str(_app(client).state.engine.url.database)).resolve()

    assert selected_database != repository_database_guard.resolve()
    assert client.post("/add", json={"a": 1, "b": 2}).json() == {"result": 3.0}


def test_openapi_has_exactly_eight_business_operations(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"] == {"title": "Calculator API", "version": "0.1.0"}
    assert set(schema["paths"]) == set(BUSINESS_OPERATIONS)
    actual_operations = {
        path: set(path_item) for path, path_item in schema["paths"].items()
    }
    assert actual_operations == BUSINESS_OPERATIONS
    assert sum(len(methods) for methods in actual_operations.values()) == 8


@pytest.mark.parametrize(("path", "page_name"), [("/docs", "Swagger UI"), ("/redoc", "ReDoc")])
def test_generated_documentation_returns_browser_html(
    client: TestClient, path: str, page_name: str
) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert page_name in response.text
