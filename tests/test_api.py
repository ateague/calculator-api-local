from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import server


@pytest.mark.parametrize(
    ("path", "a", "b", "expected"),
    [
        ("/add", 5, 3, 8),
        ("/subtract", 5, 3, 2),
        ("/multiply", 5, 3, 15),
        ("/divide", 6, 3, 2),
    ],
)
def test_calculator_endpoints(client, path, a, b, expected):
    r = client.post(path, json={"a": a, "b": b})
    assert r.status_code == 200
    assert r.json() == {"result": expected}


def test_divide_by_zero(client):
    r = client.post("/divide", json={"a": 1, "b": 0})
    assert r.status_code == 400
    assert r.json()["detail"] == "Cannot divide by zero"


@pytest.mark.parametrize("payload", [{}, {"a": 1}, {"a": "x", "b": 2}])
def test_invalid_payload(client, payload):
    assert client.post("/add", json=payload).status_code == 422


@pytest.mark.parametrize(
    ("op", "a", "b", "expected"),
    [("add", 2, 3, 5), ("sub", 5, 3, 2), ("mul", 4, 3, 12), ("div", 8, 2, 4)],
)
def test_create_calculation(client, op, a, b, expected):
    r = client.post("/calculations", json={"operation": op, "a": a, "b": b})
    assert r.status_code == 201
    body = r.json()
    assert body["result"] == expected
    assert body["operation"] == op
    assert body["id"] >= 1
    datetime.fromisoformat(body["created_at"])


def test_create_unknown_operation(client):
    r = client.post("/calculations", json={"operation": "pow", "a": 1, "b": 2})
    assert r.status_code == 400
    assert "Unknown operation" in r.json()["detail"]


def test_create_division_by_zero(client):
    r = client.post("/calculations", json={"operation": "div", "a": 1, "b": 0})
    assert r.status_code == 400


def test_list_calculations_newest_first(client):
    ids = [
        client.post("/calculations", json={"operation": "add", "a": i, "b": 1}).json()["id"]
        for i in range(3)
    ]
    r = client.get("/calculations")
    assert r.status_code == 200
    assert [c["id"] for c in r.json()] == ids[::-1]


def test_list_empty(client):
    assert client.get("/calculations").json() == []


def test_get_calculation(client):
    cid = client.post("/calculations", json={"operation": "add", "a": 1, "b": 2}).json()["id"]
    r = client.get(f"/calculations/{cid}")
    assert r.status_code == 200
    assert r.json()["result"] == 3


def test_get_missing(client):
    assert client.get("/calculations/999").status_code == 404


def test_delete_calculation(client):
    cid = client.post("/calculations", json={"operation": "add", "a": 1, "b": 2}).json()["id"]
    assert client.delete(f"/calculations/{cid}").status_code == 204
    assert client.get(f"/calculations/{cid}").status_code == 404


def test_delete_missing(client):
    assert client.delete("/calculations/999").status_code == 404


def test_lifespan_creates_tables(monkeypatch, tmp_path):
    from sqlalchemy import inspect
    from sqlmodel import create_engine

    db = tmp_path / "lifespan.db"
    engine = create_engine(f"sqlite:///{db}")
    monkeypatch.setattr(server, "engine", engine)
    with TestClient(server.app):
        assert "calculation" in inspect(engine).get_table_names()
    assert not Path("calculator.db").exists()


def test_get_session_yields_session(monkeypatch):
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, create_engine

    engine = create_engine("sqlite://", poolclass=StaticPool)
    monkeypatch.setattr(server, "engine", engine)
    gen = server.get_session()
    assert isinstance(next(gen), Session)
    gen.close()


def test_main_uses_port_env(monkeypatch):
    monkeypatch.setenv("PORT", "9123")
    with patch("server.uvicorn.run") as run:
        server.main()
    run.assert_called_once_with(server.app, host="0.0.0.0", port=9123)


def test_main_default_port(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    with patch("server.uvicorn.run") as run:
        server.main()
    assert run.call_args.kwargs["port"] == 8000
