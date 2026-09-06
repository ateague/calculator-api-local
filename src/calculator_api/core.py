"""Core calculator functions providing pure arithmetic operations."""


def add(a: float, b: float) -> float:
    """Add two numbers.

    Args:
        a: The first operand.
        b: The second operand.

    Returns:
        The sum of *a* and *b*.
    """
    return a + b


def subtract(a: float, b: float) -> float:
    """Subtract b from a.

    Args:
        a: The first operand.
        b: The second operand.

    Returns:
        The difference *a* minus *b*.
    """
    return a - b


def multiply(a: float, b: float) -> float:
    """Multiply two numbers.

    Args:
        a: The first operand.
        b: The second operand.

    Returns:
        The product of *a* and *b*.
    """
    return a * b


def divide(a: float, b: float) -> float:
    """Divide a by b.

    Args:
        a: The dividend.
        b: The divisor.

    Returns:
        The quotient *a* divided by *b*.

    Raises:
        ValueError: If *b* is zero.
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
