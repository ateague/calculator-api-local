"""Core calculator functions.

This module holds the pure arithmetic used by the HTTP layer in ``server``. The functions
take and return floats, have no side effects, and perform no I/O.
"""


def add(a: float, b: float) -> float:
    """Add two numbers.

    Args:
        a: The first addend.
        b: The second addend.

    Returns:
        The sum ``a + b``.
    """
    return a + b


def subtract(a: float, b: float) -> float:
    """Subtract one number from another.

    Args:
        a: The minuend, the number to subtract from.
        b: The subtrahend, the number to subtract.

    Returns:
        The difference ``a - b``.
    """
    return a - b


def multiply(a: float, b: float) -> float:
    """Multiply two numbers.

    Args:
        a: The first factor.
        b: The second factor.

    Returns:
        The product ``a * b``.
    """
    return a * b


def divide(a: float, b: float) -> float:
    """Divide one number by another.

    Args:
        a: The dividend, the number to divide.
        b: The divisor, the number to divide by. Must not be zero.

    Returns:
        The quotient ``a / b``.

    Raises:
        ValueError: If ``b`` is zero. The message is ``"Cannot divide by zero"``.
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
