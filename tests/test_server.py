"""Tests for the FastAPI application, persistence layer, and launcher."""

from collections.abc import Generator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

import server
from server import Calculation, app, get_session

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def test_engine(tmp_path: Path) -> Generator[Engine, None, None]:
    """Provide a fresh temporary SQLite engine installed as the module engine."""
    original_engine = server.engine
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    server.engine = engine

    def override_get_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        yield engine
    finally:
        app.dependency_overrides.clear()
        server.engine = original_engine
        engine.dispose()


@pytest.fixture
def client(test_engine: Engine) -> Generator[TestClient, None, None]:
    """Provide a TestClient entered only after the isolation seams are installed."""
    with TestClient(app) as test_client:
        yield test_client
    assert not (REPO_ROOT / "calculator.db").exists()


# --- Persistence and model ---


def test_lifespan_creates_schema(client: TestClient, test_engine: Engine) -> None:
    inspector = inspect(test_engine)
    assert "calculation" in inspector.get_table_names()
    columns = {column["name"] for column in inspector.get_columns("calculation")}
    assert columns == {"id", "operation", "a", "b", "result", "created_at"}


def test_calculation_model_defaults() -> None:
    before = datetime.now()
    calculation = Calculation(operation="add", a=1, b=2, result=3)
    assert calculation.id is None
    assert (calculation.operation, calculation.a, calculation.b, calculation.result) == (
        "add",
        1,
        2,
        3,
    )
    assert calculation.created_at.tzinfo is None
    assert abs(calculation.created_at - server.naive_utc_now()) < timedelta(seconds=5)
    assert calculation.created_at.date() >= (before - timedelta(days=1)).date()


def test_calculation_persistence_and_ordering(client: TestClient, test_engine: Engine) -> None:
    base = datetime(2024, 1, 1, 12, 0, 0)
    with Session(test_engine) as session:
        for index, operation in enumerate(["add", "sub", "mul"]):
            session.add(
                Calculation(
                    operation=operation,
                    a=index,
                    b=1,
                    result=index,
                    created_at=base + timedelta(minutes=index),
                )
            )
        session.commit()
        stored = session.exec(select(Calculation)).all()
        assert [row.id for row in stored] == [1, 2, 3]

    response = client.get("/calculations")
    assert response.status_code == 200
    assert [item["operation"] for item in response.json()] == ["mul", "sub", "add"]
    assert client.get("/calculations/2").json()["operation"] == "sub"
    assert client.delete("/calculations/2").status_code == 204
    assert [item["id"] for item in client.get("/calculations").json()] == [3, 1]


def test_metadata_tables_present() -> None:
    assert "calculation" in SQLModel.metadata.tables


# --- Immediate routes ---


@pytest.mark.parametrize(
    ("path", "a", "b", "expected"),
    [
        ("/add", 5, 3, 8),
        ("/subtract", 5, 3, 2),
        ("/multiply", 5, 3, 15),
        ("/divide", 6, 3, 2),
        ("/divide", 7, 2, 3.5),
        ("/add", -1.5, 0, -1.5),
    ],
)
def test_immediate_routes(client: TestClient, path: str, a: float, b: float, expected: float):
    response = client.post(path, json={"a": a, "b": b})
    assert response.status_code == 200
    assert response.json() == {"result": expected}


def test_immediate_divide_by_zero(client: TestClient) -> None:
    response = client.post("/divide", json={"a": 1, "b": 0})
    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot divide by zero"}


@pytest.mark.parametrize("path", ["/add", "/subtract", "/multiply", "/divide"])
@pytest.mark.parametrize("body", [{"a": 1}, {}, {"a": "x", "b": 1}, {"a": 1, "b": "y"}])
def test_immediate_validation_errors(client: TestClient, path: str, body: dict[str, Any]):
    response = client.post(path, json=body)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


# --- Calculation routes ---


@pytest.mark.parametrize(
    ("operation", "a", "b", "expected"),
    [("add", 5, 3, 8), ("sub", 5, 3, 2), ("mul", 7, 6, 42), ("div", 9, 3, 3)],
)
def test_create_calculation(
    client: TestClient, operation: str, a: float, b: float, expected: float
) -> None:
    response = client.post("/calculations", json={"operation": operation, "a": a, "b": b})
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert (body["operation"], body["a"], body["b"], body["result"]) == (
        operation,
        a,
        b,
        expected,
    )
    created_at = datetime.fromisoformat(body["created_at"])
    assert created_at.tzinfo is None
    assert set(body) == {"id", "operation", "a", "b", "result", "created_at"}


def test_create_calculation_unknown_operation(client: TestClient) -> None:
    response = client.post("/calculations", json={"operation": "pow", "a": 1, "b": 2})
    assert response.status_code == 400
    assert response.json()["detail"].startswith("Unknown operation: pow. Use: ")
    assert client.get("/calculations").json() == []


def test_create_calculation_divide_by_zero(client: TestClient) -> None:
    response = client.post("/calculations", json={"operation": "div", "a": 1, "b": 0})
    assert response.status_code == 400
    assert response.json() == {"detail": "Cannot divide by zero"}
    assert client.get("/calculations").json() == []


@pytest.mark.parametrize(
    "body",
    [
        {"operation": "add", "a": 1},
        {"a": 1, "b": 2},
        {"operation": "add", "a": "x", "b": 2},
    ],
)
def test_create_calculation_validation_errors(client: TestClient, body: dict[str, Any]) -> None:
    assert client.post("/calculations", json=body).status_code == 422


def test_list_calculations_empty(client: TestClient) -> None:
    response = client.get("/calculations")
    assert response.status_code == 200
    assert response.json() == []


def test_get_and_delete_calculation(client: TestClient) -> None:
    created = client.post("/calculations", json={"operation": "add", "a": 1, "b": 2}).json()
    fetched = client.get(f"/calculations/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == created

    deleted = client.delete(f"/calculations/{created['id']}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get(f"/calculations/{created['id']}").status_code == 404


def test_get_missing_calculation(client: TestClient) -> None:
    response = client.get("/calculations/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Calculation not found"}


def test_delete_missing_calculation(client: TestClient) -> None:
    response = client.delete("/calculations/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Calculation not found"}


# --- Generated documentation ---


def test_openapi_schema(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Calculator API"
    assert {"/add", "/subtract", "/multiply", "/divide", "/calculations"} <= set(schema["paths"])
    assert "/calculations/{calculation_id}" in schema["paths"]


@pytest.mark.parametrize("path", ["/docs", "/docs/oauth2-redirect", "/redoc"])
def test_documentation_pages(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# --- Launcher ---


def test_main_default_port(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setattr(server.uvicorn, "run", lambda *a, **k: calls.append((a, k)))
    server.main()
    assert calls == [((server.app,), {"host": "0.0.0.0", "port": 8000})]


def test_main_port_override(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    monkeypatch.setenv("PORT", "9123")
    monkeypatch.setattr(server.uvicorn, "run", lambda *a, **k: calls.append((a, k)))
    server.main()
    assert calls == [((server.app,), {"host": "0.0.0.0", "port": 9123})]

