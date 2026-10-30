"""Direct behavior tests for the calculator core."""

from collections.abc import Callable

import pytest

from core import add, divide, multiply, subtract


@pytest.mark.parametrize(
    ("operation", "a", "b", "expected"),
    [
        pytest.param(add, 2.0, 3.0, 5.0, id="add-positive"),
        pytest.param(add, -2.0, -3.0, -5.0, id="add-negative"),
        pytest.param(add, 0.5, 1.25, 1.75, id="add-fractional"),
        pytest.param(add, 0.0, 9.0, 9.0, id="add-zero"),
        pytest.param(subtract, 7.0, 2.0, 5.0, id="subtract-positive"),
        pytest.param(subtract, -7.0, -2.0, -5.0, id="subtract-negative"),
        pytest.param(subtract, 2.5, 0.75, 1.75, id="subtract-fractional"),
        pytest.param(subtract, 0.0, 5.0, -5.0, id="subtract-zero"),
        pytest.param(multiply, 3.0, 4.0, 12.0, id="multiply-positive"),
        pytest.param(multiply, -3.0, 4.0, -12.0, id="multiply-negative"),
        pytest.param(multiply, 0.5, 1.5, 0.75, id="multiply-fractional"),
        pytest.param(multiply, 0.0, 12.0, 0.0, id="multiply-zero"),
        pytest.param(divide, 8.0, 2.0, 4.0, id="divide-positive"),
        pytest.param(divide, -8.0, 2.0, -4.0, id="divide-negative"),
        pytest.param(divide, 1.5, 0.5, 3.0, id="divide-fractional"),
        pytest.param(divide, 0.0, 5.0, 0.0, id="divide-zero-numerator"),
    ],
)
def test_arithmetic_behaviors(
    operation: Callable[[float, float], float],
    a: float,
    b: float,
    expected: float,
) -> None:
    assert operation(a, b) == expected


def test_divide_rejects_zero_divisor_with_exact_error() -> None:
    with pytest.raises(ValueError, match="^Cannot divide by zero$") as error:
        divide(4.0, 0.0)

    assert type(error.value) is ValueError
    assert str(error.value) == "Cannot divide by zero"
