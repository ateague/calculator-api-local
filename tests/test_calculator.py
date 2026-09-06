"""API tests for the pure-math calculator endpoints."""


def test_add(client):
    response = client.post("/add", json={"a": 2, "b": 3})
    assert response.status_code == 200
    assert response.json() == {"result": 5.0}


def test_subtract(client):
    response = client.post("/subtract", json={"a": 10, "b": 4})
    assert response.status_code == 200
    assert response.json() == {"result": 6.0}


def test_multiply(client):
    response = client.post("/multiply", json={"a": 3, "b": 7})
    assert response.status_code == 200
    assert response.json() == {"result": 21.0}


def test_divide(client):
    response = client.post("/divide", json={"a": 10, "b": 2})
    assert response.status_code == 200
    assert response.json() == {"result": 5.0}


def test_divide_by_zero(client):
    response = client.post("/divide", json={"a": 1, "b": 0})
    assert response.status_code == 400
