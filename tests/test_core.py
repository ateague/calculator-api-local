"""Unit tests for the calculator's arithmetic functions."""

import pytest

from core import add, divide, multiply, subtract


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        pytest.param(2.0, 3.0, 5.0, id="integer-like-floats"),
        pytest.param(-2.0, 3.0, 1.0, id="signed-values"),
        pytest.param(0.25, 0.5, 0.75, id="fractional-values"),
    ],
)
def test_add(a: float, b: float, expected: float) -> None:
    assert add(a, b) == expected


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        pytest.param(5.0, 3.0, 2.0, id="integer-like-floats"),
        pytest.param(-2.0, -3.0, 1.0, id="signed-values"),
        pytest.param(0.75, 0.25, 0.5, id="fractional-values"),
    ],
)
def test_subtract(a: float, b: float, expected: float) -> None:
    assert subtract(a, b) == expected


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        pytest.param(2.0, 3.0, 6.0, id="integer-like-floats"),
        pytest.param(-2.0, 3.0, -6.0, id="signed-values"),
        pytest.param(0.25, 0.5, 0.125, id="fractional-values"),
    ],
)
def test_multiply(a: float, b: float, expected: float) -> None:
    assert multiply(a, b) == expected


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        pytest.param(6.0, 3.0, 2.0, id="integer-like-floats"),
        pytest.param(-6.0, 3.0, -2.0, id="signed-values"),
        pytest.param(0.75, 0.25, 3.0, id="fractional-values"),
    ],
)
def test_divide(a: float, b: float, expected: float) -> None:
    assert divide(a, b) == expected


@pytest.mark.parametrize("zero", [0.0, -0.0], ids=["positive-zero", "negative-zero"])
def test_divide_by_zero_raises_exact_value_error(zero: float) -> None:
    with pytest.raises(ValueError) as exc_info:
        divide(1.0, zero)

    assert type(exc_info.value) is ValueError
    assert exc_info.value.args == ("Cannot divide by zero",)
    assert str(exc_info.value) == "Cannot divide by zero"
