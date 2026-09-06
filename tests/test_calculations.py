"""API tests for the CRUD /calculations endpoints."""


def test_create_calculation(client):
    response = client.post("/calculations", json={"operation": "add", "a": 2, "b": 3})
    assert response.status_code == 201
    data = response.json()
    assert data["result"] == 5.0
    assert data["operation"] == "add"
    assert data["a"] == 2.0
    assert data["b"] == 3.0
    assert "id" in data
    assert "created_at" in data


def test_create_calculation_invalid_operation(client):
    response = client.post("/calculations", json={"operation": "invalid", "a": 2, "b": 3})
    assert response.status_code == 400


def test_create_calculation_divide_by_zero(client):
    response = client.post("/calculations", json={"operation": "div", "a": 1, "b": 0})
    assert response.status_code == 400


def test_list_calculations(client):
    client.post("/calculations", json={"operation": "add", "a": 1, "b": 2})
    client.post("/calculations", json={"operation": "sub", "a": 5, "b": 3})

    response = client.get("/calculations")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_calculation(client):
    create_resp = client.post("/calculations", json={"operation": "mul", "a": 3, "b": 4})
    calc_id = create_resp.json()["id"]

    response = client.get(f"/calculations/{calc_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == calc_id
    assert data["operation"] == "mul"
    assert data["result"] == 12.0


def test_get_calculation_not_found(client):
    response = client.get("/calculations/999")
    assert response.status_code == 404


def test_delete_calculation(client):
    create_resp = client.post("/calculations", json={"operation": "add", "a": 10, "b": 20})
    calc_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/calculations/{calc_id}")
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/calculations/{calc_id}")
    assert get_resp.status_code == 404


def test_delete_calculation_not_found(client):
    response = client.delete("/calculations/999")
    assert response.status_code == 404
