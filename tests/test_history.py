"""Integration tests for the CRUD /calculations endpoints."""

from fastapi.testclient import TestClient


def test_create_calculation_persists_record(client: TestClient) -> None:
    """POST /calculations creates and returns a persisted record with the computed result.

    Args:
        client: A ``TestClient`` wired to an isolated in-memory SQLite database.
    """
    response = client.post(
        "/calculations",
        json={"operation": "add", "a": 2, "b": 3},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["operation"] == "add"
    assert body["a"] == 2
    assert body["b"] == 3
    assert body["result"] == 5.0
    assert isinstance(body["id"], int)
    assert "created_at" in body


def test_create_calculation_unknown_operation_returns_400(client: TestClient) -> None:
    """POST /calculations returns HTTP 400 when the operation is not recognized.

    Args:
        client: A ``TestClient`` wired to an isolated in-memory SQLite database.
    """
    response = client.post(
        "/calculations",
        json={"operation": "modulo", "a": 10, "b": 3},
    )
    assert response.status_code == 400
    assert "modulo" in response.json()["detail"]


def test_create_calculation_divide_by_zero_returns_400(client: TestClient) -> None:
    """POST /calculations returns HTTP 400 when a stored divide by zero is attempted.

    Args:
        client: A ``TestClient`` wired to an isolated in-memory SQLite database.
    """
    response = client.post(
        "/calculations",
        json={"operation": "div", "a": 5, "b": 0},
    )
    assert response.status_code == 400


def test_list_calculations_returns_all_records(client: TestClient) -> None:
    """GET /calculations returns every persisted record.

    Args:
        client: A ``TestClient`` wired to an isolated in-memory SQLite database.
    """
    client.post("/calculations", json={"operation": "add", "a": 1, "b": 1})
    client.post("/calculations", json={"operation": "mul", "a": 3, "b": 4})

    response = client.get("/calculations")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    operations = {item["operation"] for item in body}
    assert operations == {"add", "mul"}


def test_get_calculation_by_id_returns_record(client: TestClient) -> None:
    """GET /calculations/{id} returns the matching stored calculation.

    Args:
        client: A ``TestClient`` wired to an isolated in-memory SQLite database.
    """
    created = client.post(
        "/calculations",
        json={"operation": "sub", "a": 10, "b": 4},
    ).json()

    response = client.get(f"/calculations/{created['id']}")
    assert response.status_code == 200
    assert response.json()["result"] == 6.0
    assert response.json()["id"] == created["id"]


def test_get_calculation_missing_id_returns_404(client: TestClient) -> None:
    """GET /calculations/{id} returns HTTP 404 for an unknown ID.

    Args:
        client: A ``TestClient`` wired to an isolated in-memory SQLite database.
    """
    response = client.get("/calculations/9999")
    assert response.status_code == 404


def test_delete_calculation_removes_record(client: TestClient) -> None:
    """DELETE /calculations/{id} removes the record and subsequent GET returns 404.

    Args:
        client: A ``TestClient`` wired to an isolated in-memory SQLite database.
    """
    created = client.post(
        "/calculations",
        json={"operation": "add", "a": 5, "b": 5},
    ).json()

    delete_response = client.delete(f"/calculations/{created['id']}")
    assert delete_response.status_code == 204

    follow_up = client.get(f"/calculations/{created['id']}")
    assert follow_up.status_code == 404


def test_delete_calculation_missing_id_returns_404(client: TestClient) -> None:
    """DELETE /calculations/{id} returns HTTP 404 for an unknown ID.

    Args:
        client: A ``TestClient`` wired to an isolated in-memory SQLite database.
    """
    response = client.delete("/calculations/9999")
    assert response.status_code == 404
