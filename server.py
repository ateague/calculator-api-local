#!/usr/bin/env python3
"""Compatibility exports and script entry point for the Calculator API."""

from sqlalchemy.engine import Engine

from calculator_api.api import (
    OPERATIONS,
    api_add,
    api_divide,
    api_multiply,
    api_subtract,
    app,
    create_app,
    create_calculation,
    delete_calculation,
    get_calculation,
    lifespan,
    list_calculations,
    main,
)
from calculator_api.config import (
    DEFAULT_DATABASE_URL,
    DEFAULT_PORT,
    Settings,
    load_settings,
)
from calculator_api.core import add, divide, multiply, subtract
from calculator_api.database import (
    SessionDependency,
    create_db_engine,
    create_session_dependency,
)
from calculator_api.models import (
    Calculation,
    CalculationBase,
    CalculationCreate,
    CalculationRequest,
    CalculationResponse,
    ResultResponse,
)

DATABASE_URL: str = app.state.settings.database_url
PORT: int = app.state.settings.port
get_session: SessionDependency = app.state.get_session
engine: Engine

__all__ = [
    "DATABASE_URL",
    "DEFAULT_DATABASE_URL",
    "DEFAULT_PORT",
    "OPERATIONS",
    "PORT",
    "Calculation",
    "CalculationBase",
    "CalculationCreate",
    "CalculationRequest",
    "CalculationResponse",
    "ResultResponse",
    "SessionDependency",
    "Settings",
    "add",
    "api_add",
    "api_divide",
    "api_multiply",
    "api_subtract",
    "app",
    "create_app",
    "create_calculation",
    "create_db_engine",
    "create_session_dependency",
    "delete_calculation",
    "divide",
    "engine",
    "get_calculation",
    "get_session",
    "lifespan",
    "list_calculations",
    "load_settings",
    "main",
    "multiply",
    "subtract",
]


def __getattr__(name: str) -> object:
    """Expose the default app's engine without owning a second global engine."""
    if name == "engine":
        return app.state.engine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    main()
