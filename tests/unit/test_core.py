"""Unit tests for the pure calculator operations."""

import pytest

from core import add, divide, multiply, subtract


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (2, 3, 5),
        (-2, -3, -5),
        (0, 4, 4),
        (1.25, 2.5, 3.75),
    ],
)
def test_add(a: float, b: float, expected: float) -> None:
    assert add(a, b) == expected


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (7, 2, 5),
        (-7, -2, -5),
        (0, 4, -4),
        (5.5, 2.25, 3.25),
    ],
)
def test_subtract(a: float, b: float, expected: float) -> None:
    assert subtract(a, b) == expected


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (3, 4, 12),
        (-3, 4, -12),
        (0, -8, 0),
        (1.5, 2.5, 3.75),
    ],
)
def test_multiply(a: float, b: float, expected: float) -> None:
    assert multiply(a, b) == expected


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (12, 3, 4),
        (-12, 3, -4),
        (0, -8, 0),
        (2.5, 0.5, 5),
    ],
)
def test_divide(a: float, b: float, expected: float) -> None:
    assert divide(a, b) == expected


def test_divide_by_zero_has_exact_error_message() -> None:
    with pytest.raises(ValueError, match="^Cannot divide by zero$"):
        divide(10, 0)
