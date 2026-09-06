"""Unit tests for calculator_api.core math functions."""

import pytest

from calculator_api.core import add, divide, multiply, subtract


# --- add ---


def test_add_positive_numbers():
    assert add(2, 3) == 5


def test_add_negative_numbers():
    assert add(-1, -2) == -3


def test_add_with_zero():
    assert add(0, 5) == 5
    assert add(5, 0) == 5


def test_add_floats():
    assert add(1.5, 2.5) == 4.0


# --- subtract ---


def test_subtract_positive_numbers():
    assert subtract(10, 4) == 6


def test_subtract_negative_numbers():
    assert subtract(-3, -7) == 4


def test_subtract_with_zero():
    assert subtract(5, 0) == 5
    assert subtract(0, 5) == -5


def test_subtract_floats():
    assert subtract(5.5, 2.5) == 3.0


# --- multiply ---


def test_multiply_positive_numbers():
    assert multiply(3, 7) == 21


def test_multiply_negative_numbers():
    assert multiply(-2, -3) == 6


def test_multiply_with_zero():
    assert multiply(5, 0) == 0
    assert multiply(0, 5) == 0


def test_multiply_floats():
    assert multiply(2.5, 4.0) == 10.0


# --- divide ---


def test_divide_positive_numbers():
    assert divide(10, 2) == 5.0


def test_divide_negative_numbers():
    assert divide(-10, 2) == -5.0


def test_divide_floats():
    assert divide(7.5, 2.5) == 3.0


def test_divide_by_zero():
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(1, 0)
