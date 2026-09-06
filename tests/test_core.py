"""Unit tests for the pure arithmetic functions in calculator_api.core."""

import pytest

from calculator_api.core import add, divide, multiply, subtract


def test_add_positive_numbers() -> None:
    """add returns the sum of two positive integers."""
    assert add(2, 3) == 5


def test_add_negative_and_zero() -> None:
    """add handles negative operands and zero without special-casing."""
    assert add(-4, 10) == 6
    assert add(0, 0) == 0
    assert add(-1, -1) == -2


def test_add_floats() -> None:
    """add produces a float result when given float operands."""
    assert add(0.1, 0.2) == pytest.approx(0.3)


def test_subtract_basic() -> None:
    """subtract returns the difference a - b."""
    assert subtract(10, 4) == 6
    assert subtract(0, 5) == -5
    assert subtract(-3, -7) == 4


def test_subtract_floats() -> None:
    """subtract handles float operands correctly."""
    assert subtract(1.5, 0.5) == pytest.approx(1.0)


def test_multiply_basic() -> None:
    """multiply returns the product of two numbers, including sign handling."""
    assert multiply(3, 4) == 12
    assert multiply(-2, 5) == -10
    assert multiply(0, 999) == 0


def test_multiply_floats() -> None:
    """multiply handles float operands correctly."""
    assert multiply(2.5, 4) == pytest.approx(10.0)


def test_divide_basic() -> None:
    """divide returns the quotient a / b for non-zero divisors."""
    assert divide(10, 2) == 5
    assert divide(-9, 3) == -3
    assert divide(7, 2) == pytest.approx(3.5)


def test_divide_by_zero_raises_value_error() -> None:
    """divide raises ValueError when the divisor is zero."""
    with pytest.raises(ValueError):
        divide(1, 0)


def test_divide_zero_dividend() -> None:
    """divide returns 0 when the dividend is zero and divisor is non-zero."""
    assert divide(0, 5) == 0
