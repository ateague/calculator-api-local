#!/usr/bin/env python3
"""Compatibility entry point for the packaged Calculator API.

The HTTP application and persistence delegates are added by the API foundation
layer. Keeping imports here limited to the completed package modules leaves this
shim importable while that layer is assembled.
"""

from importlib import import_module

from calculator_api.config import (
    DEFAULT_DATABASE_URL,
    DEFAULT_PORT,
    Settings,
    load_settings,
)
from calculator_api.core import add, divide, multiply, subtract
from calculator_api.models import (
    Calculation,
    CalculationBase,
    CalculationCreate,
    CalculationRequest,
    CalculationResponse,
    ResultResponse,
)

DATABASE_URL = DEFAULT_DATABASE_URL
PORT = DEFAULT_PORT

__all__ = [
    "DATABASE_URL",
    "PORT",
    "Calculation",
    "CalculationBase",
    "CalculationCreate",
    "CalculationRequest",
    "CalculationResponse",
    "ResultResponse",
    "Settings",
    "add",
    "divide",
    "load_settings",
    "main",
    "multiply",
    "subtract",
]


def main() -> None:
    """Delegate server startup to the installed application package."""
    import_module("calculator_api.api").main()


if __name__ == "__main__":
    main()
