"""Unit coverage for every arithmetic operation and value category."""

from collections.abc import Callable

import pytest

from calculator_api.core import add, divide, multiply, subtract


@pytest.mark.parametrize(
    ("operation", "a", "b", "expected"),
    [
        (add, 7, 5, 12.0),
        (add, -7, -5, -12.0),
        (add, 0, 0, 0.0),
        (add, 2.25, 1.5, 3.75),
        (subtract, 7, 5, 2.0),
        (subtract, -7, -5, -2.0),
        (subtract, 5, 5, 0.0),
        (subtract, 0, 4, -4.0),
        (subtract, 2.25, 1.5, 0.75),
        (multiply, 7, 5, 35.0),
        (multiply, -7, 5, -35.0),
        (multiply, 0, -9, 0.0),
        (multiply, 2.5, 1.5, 3.75),
        (divide, 8, 4, 2.0),
        (divide, -9, 3, -3.0),
        (divide, 0, 7, 0.0),
        (divide, 7.5, 2.5, 3.0),
    ],
)
def test_arithmetic_value_matrix(
    operation: Callable[[float, float], float],
    a: float,
    b: float,
    expected: float,
) -> None:
    assert operation(a, b) == pytest.approx(expected)


def test_divide_by_zero_raises_exact_error() -> None:
    with pytest.raises(ValueError, match=r"^Cannot divide by zero$"):
        divide(3, 0)
