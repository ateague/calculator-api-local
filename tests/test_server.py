"""Contract tests for calculator API routes and generated documentation."""

import runpy
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, MetaData, inspect
from sqlalchemy.pool import QueuePool
from sqlmodel import SQLModel, Session

import server
from server import Calculation, CalculationResponse


DIRECT_ROUTES = ("/add", "/subtract", "/multiply", "/divide")


def _execute_server_module(
    monkeypatch: pytest.MonkeyPatch, *, run_name: str
) -> dict[str, Any]:
    """Execute server.py with isolated model metadata and return its globals."""
    monkeypatch.setattr(SQLModel, "metadata", MetaData())
    return runpy.run_path(str(Path(server.__file__).resolve()), run_name=run_name)


def _assert_explicit_utc_offset(value: str) -> None:
    """Assert an API datetime carries an explicit UTC offset."""
    parsed = datetime.fromisoformat(value)

    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    ("database_url", "expected_connect_args"),
    [
        pytest.param(
            "sqlite:///temporary.db",
            {"check_same_thread": False},
            id="sqlite-thread-sharing",
        ),
        pytest.param(
            "postgresql://calculator@example.invalid/calculator",
            {},
            id="non-sqlite",
        ),
    ],
)
def test_database_engine_configuration(
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
    expected_connect_args: dict[str, bool],
) -> None:
    """Engine construction uses SQLite thread options only for SQLite URLs."""
    expected_engine = cast(Engine, object())
    create_engine = Mock(return_value=expected_engine)
    monkeypatch.setattr(server, "create_engine", create_engine)

    actual_engine = server.create_database_engine(database_url)

    assert actual_engine is expected_engine
    create_engine.assert_called_once_with(
        database_url, echo=False, connect_args=expected_connect_args
    )


def test_create_app_binds_overridden_temporary_database(tmp_path: Path) -> None:
    """Application construction binds its dependency to the requested database."""
    database_path = tmp_path / "create-app-override.sqlite3"
    database_url = f"sqlite:///{database_path}"
    application = server.create_app(database_url)
    application_engine: Engine = application.state.engine

    try:
        assert str(application_engine.url) == database_url
        assert server.get_session in application.dependency_overrides
        assert not database_path.exists()
    finally:
        application_engine.dispose()


def test_database_url_defaults_during_fresh_module_execution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A fresh server execution retains the documented local SQLite default."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    namespace = _execute_server_module(monkeypatch, run_name="server_default_database_test")
    application = cast(FastAPI, namespace["app"])
    application_engine: Engine = application.state.engine

    try:
        assert namespace["DATABASE_URL"] == "sqlite:///calculator.db"
        assert str(application_engine.url) == "sqlite:///calculator.db"
        assert not (tmp_path / "calculator.db").exists()
    finally:
        application_engine.dispose()


def test_database_url_override_during_fresh_module_execution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A fresh server execution binds its app to the environment override."""
    database_path = tmp_path / "environment-override.sqlite3"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    namespace = _execute_server_module(monkeypatch, run_name="server_database_override_test")
    application = cast(FastAPI, namespace["app"])
    application_engine: Engine = application.state.engine

    try:
        assert namespace["DATABASE_URL"] == database_url
        assert str(application_engine.url) == database_url
        assert not database_path.exists()
    finally:
        application_engine.dispose()


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


def test_calculation_response_retains_aware_timestamp() -> None:
    """Timestamp normalization leaves an existing explicit offset unchanged."""
    aware_timestamp = datetime(
        2030, 4, 5, 6, 7, 8, tzinfo=timezone(timedelta(hours=5, minutes=30))
    )

    response = CalculationResponse(
        id=1,
        operation="add",
        a=20,
        b=22,
        result=42,
        created_at=aware_timestamp,
    )

    assert response.created_at == aware_timestamp
    assert response.created_at.utcoffset() == timedelta(hours=5, minutes=30)


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


def test_direct_get_session_closes_checked_out_connection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The module session generator returns its connection when exhausted."""
    application_engine = server.create_database_engine(
        f"sqlite:///{tmp_path / 'direct-session.sqlite3'}"
    )
    pool = application_engine.pool
    assert isinstance(pool, QueuePool)
    monkeypatch.setattr(server, "engine", application_engine)
    session_dependency = cast(Generator[Session, None, None], server.get_session())

    try:
        session = next(session_dependency)
        session.connection()
        assert pool.checkedout() == 1

        with pytest.raises(StopIteration):
            next(session_dependency)

        assert pool.checkedout() == 0
    finally:
        session_dependency.close()
        application_engine.dispose()


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


@pytest.mark.parametrize(
    ("configured_port", "expected_port"),
    [
        pytest.param(None, 8000, id="default"),
        pytest.param("9123", 9123, id="environment-override"),
    ],
)
def test_main_runs_uvicorn_with_configured_port(
    monkeypatch: pytest.MonkeyPatch,
    configured_port: str | None,
    expected_port: int,
) -> None:
    """Main launches the module app on every interface with the selected port."""
    if configured_port is None:
        monkeypatch.delenv("PORT", raising=False)
    else:
        monkeypatch.setenv("PORT", configured_port)
    uvicorn_run = Mock()
    monkeypatch.setattr(server.uvicorn, "run", uvicorn_run)

    server.main()

    uvicorn_run.assert_called_once_with(
        server.app, host="0.0.0.0", port=expected_port
    )


def test_direct_module_execution_calls_main_without_listening(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Executing server.py directly reaches main with isolated model metadata."""
    database_path = tmp_path / "direct-execution.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("PORT", "9456")
    uvicorn_run = Mock()
    monkeypatch.setattr(server.uvicorn, "run", uvicorn_run)

    namespace = _execute_server_module(monkeypatch, run_name="__main__")
    application = cast(FastAPI, namespace["app"])
    application_engine: Engine = application.state.engine

    try:
        uvicorn_run.assert_called_once_with(
            application, host="0.0.0.0", port=9456
        )
        assert not database_path.exists()
    finally:
        application_engine.dispose()


def test_installed_console_entry_point_resolves_to_main() -> None:
    """Installed distribution metadata exposes the calculator-api command."""
    distribution = metadata.distribution("calculator-api")
    entry_points = [
        entry_point
        for entry_point in distribution.entry_points
        if entry_point.group == "console_scripts" and entry_point.name == "calculator-api"
    ]

    assert [entry_point.value for entry_point in entry_points] == ["server:main"]
    assert entry_points[0].load() is server.main
