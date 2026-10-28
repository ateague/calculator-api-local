"""Unit tests for pure arithmetic operations."""

from collections.abc import Callable

import pytest

from core import add, divide, multiply, subtract


@pytest.mark.parametrize(
    ("operation", "a", "b", "expected"),
    [
        pytest.param(add, 6.0, 4.0, 10.0, id="add-integer-valued-floats"),
        pytest.param(add, 0.25, 0.5, 0.75, id="add-fractions"),
        pytest.param(add, 0.0, 7.0, 7.0, id="add-zero"),
        pytest.param(add, -6.0, -4.0, -10.0, id="add-negatives"),
        pytest.param(subtract, 6.0, 4.0, 2.0, id="subtract-integer-valued-floats"),
        pytest.param(subtract, 0.75, 0.25, 0.5, id="subtract-fractions"),
        pytest.param(subtract, 0.0, 7.0, -7.0, id="subtract-zero"),
        pytest.param(subtract, -6.0, -4.0, -2.0, id="subtract-negatives"),
        pytest.param(multiply, 6.0, 4.0, 24.0, id="multiply-integer-valued-floats"),
        pytest.param(multiply, 0.25, 0.5, 0.125, id="multiply-fractions"),
        pytest.param(multiply, 0.0, 7.0, 0.0, id="multiply-zero"),
        pytest.param(multiply, -6.0, -4.0, 24.0, id="multiply-negatives"),
        pytest.param(divide, 6.0, 4.0, 1.5, id="divide-integer-valued-floats"),
        pytest.param(divide, 0.5, 0.25, 2.0, id="divide-fractions"),
        pytest.param(divide, 0.0, 7.0, 0.0, id="divide-zero-numerator"),
        pytest.param(divide, -6.0, -4.0, 1.5, id="divide-negatives"),
    ],
)
def test_arithmetic_operations(
    operation: Callable[[float, float], float], a: float, b: float, expected: float
) -> None:
    assert operation(a, b) == pytest.approx(expected)


@pytest.mark.parametrize("zero", [0.0, -0.0])
def test_divide_by_zero_has_exact_error(zero: float) -> None:
    with pytest.raises(ValueError) as exc_info:
        divide(9.0, zero)

    assert str(exc_info.value) == "Cannot divide by zero"
