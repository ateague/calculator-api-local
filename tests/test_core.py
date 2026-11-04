"""Unit tests for the calculator's arithmetic functions."""

from collections.abc import Callable

import pytest

from core import add, divide, multiply, subtract


@pytest.mark.parametrize(
    ("operation", "a", "b", "expected"),
    [
        pytest.param(add, 2.0, 3.0, 5.0, id="add-integer-like-floats"),
        pytest.param(add, -2.0, 3.0, 1.0, id="add-signed-values"),
        pytest.param(add, 0.25, 0.5, 0.75, id="add-fractional-values"),
        pytest.param(subtract, 5.0, 3.0, 2.0, id="subtract-integer-like-floats"),
        pytest.param(subtract, -2.0, -3.0, 1.0, id="subtract-signed-values"),
        pytest.param(subtract, 0.75, 0.25, 0.5, id="subtract-fractional-values"),
        pytest.param(multiply, 2.0, 3.0, 6.0, id="multiply-integer-like-floats"),
        pytest.param(multiply, -2.0, 3.0, -6.0, id="multiply-signed-values"),
        pytest.param(multiply, 0.25, 0.5, 0.125, id="multiply-fractional-values"),
        pytest.param(divide, 6.0, 3.0, 2.0, id="divide-integer-like-floats"),
        pytest.param(divide, -6.0, 3.0, -2.0, id="divide-signed-values"),
        pytest.param(divide, 0.75, 0.25, 3.0, id="divide-fractional-values"),
    ],
)
def test_arithmetic_success(
    operation: Callable[[float, float], float],
    a: float,
    b: float,
    expected: float,
) -> None:
    assert operation(a, b) == expected


@pytest.mark.parametrize("zero", [0.0, -0.0], ids=["positive-zero", "negative-zero"])
def test_divide_by_zero_raises_exact_value_error(zero: float) -> None:
    with pytest.raises(ValueError) as exc_info:
        divide(1.0, zero)

    assert type(exc_info.value) is ValueError
    assert exc_info.value.args == ("Cannot divide by zero",)
    assert str(exc_info.value) == "Cannot divide by zero"
