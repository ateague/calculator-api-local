"""Tests for the pure calculator functions."""

import pytest

from core import add, divide, multiply, subtract


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [(2, 3, 5), (2.5, 0.25, 2.75), (-2, -3, -5), (-2, 3, 1), (0, 0, 0), (5, 0, 5)],
)
def test_add(a: float, b: float, expected: float) -> None:
    assert add(a, b) == expected


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [(5, 3, 2), (2.5, 0.5, 2.0), (-2, -3, 1), (3, -2, 5), (0, 0, 0), (5, 0, 5)],
)
def test_subtract(a: float, b: float, expected: float) -> None:
    assert subtract(a, b) == expected


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [(4, 3, 12), (1.5, 2.0, 3.0), (-2, -3, 6), (-2, 3, -6), (0, 7, 0), (7, 0, 0)],
)
def test_multiply(a: float, b: float, expected: float) -> None:
    assert multiply(a, b) == expected


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [(6, 3, 2), (7, 2, 3.5), (1.5, 0.5, 3.0), (-6, -3, 2), (-6, 3, -2), (0, 5, 0)],
)
def test_divide(a: float, b: float, expected: float) -> None:
    assert divide(a, b) == expected


@pytest.mark.parametrize("a", [1, 0, -1, 2.5])
@pytest.mark.parametrize("b", [0, 0.0])
def test_divide_by_zero_raises(a: float, b: float) -> None:
    with pytest.raises(ValueError, match="^Cannot divide by zero$"):
        divide(a, b)
