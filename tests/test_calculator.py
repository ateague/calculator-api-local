"""Integration tests for the arithmetic calculator endpoints."""

from fastapi.testclient import TestClient


def test_add_endpoint_returns_sum(client: TestClient) -> None:
    """POST /add returns 200 and the correct sum for valid operands.

    Args:
        client: The FastAPI ``TestClient`` fixture providing an HTTP test interface.
    """
    response = client.post("/add", json={"a": 2, "b": 3})
    assert response.status_code == 200
    assert response.json() == {"result": 5.0}


def test_subtract_endpoint_returns_difference(client: TestClient) -> None:
    """POST /subtract returns 200 and the correct difference.

    Args:
        client: The FastAPI ``TestClient`` fixture providing an HTTP test interface.
    """
    response = client.post("/subtract", json={"a": 10, "b": 4})
    assert response.status_code == 200
    assert response.json() == {"result": 6.0}


def test_multiply_endpoint_returns_product(client: TestClient) -> None:
    """POST /multiply returns 200 and the correct product.

    Args:
        client: The FastAPI ``TestClient`` fixture providing an HTTP test interface.
    """
    response = client.post("/multiply", json={"a": 3, "b": 4})
    assert response.status_code == 200
    assert response.json() == {"result": 12.0}


def test_divide_endpoint_returns_quotient(client: TestClient) -> None:
    """POST /divide returns 200 and the correct quotient for non-zero divisors.

    Args:
        client: The FastAPI ``TestClient`` fixture providing an HTTP test interface.
    """
    response = client.post("/divide", json={"a": 10, "b": 2})
    assert response.status_code == 200
    assert response.json() == {"result": 5.0}


def test_divide_by_zero_returns_400(client: TestClient) -> None:
    """POST /divide returns HTTP 400 when the divisor is zero.

    Args:
        client: The FastAPI ``TestClient`` fixture providing an HTTP test interface.
    """
    response = client.post("/divide", json={"a": 1, "b": 0})
    assert response.status_code == 400
    detail = response.json().get("detail", "")
    assert "zero" in detail.lower()


def test_divide_endpoint_float_operands(client: TestClient) -> None:
    """POST /divide handles float operands and returns a float result.

    Args:
        client: The FastAPI ``TestClient`` fixture providing an HTTP test interface.
    """
    response = client.post("/divide", json={"a": 7, "b": 2})
    assert response.status_code == 200
    assert response.json() == {"result": 3.5}


def test_add_endpoint_rejects_missing_field(client: TestClient) -> None:
    """POST /add returns 422 when a required field is missing.

    Args:
        client: The FastAPI ``TestClient`` fixture providing an HTTP test interface.
    """
    response = client.post("/add", json={"a": 1})
    assert response.status_code == 422
