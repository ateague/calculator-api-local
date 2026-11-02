"""Environment-backed configuration for the Calculator API."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_PORT = 8000
DEFAULT_DATABASE_URL = "sqlite:///calculator.db"
MIN_PORT = 1
MAX_PORT = 65535

_INVALID_PORT_MESSAGE = "PORT must be an integer between 1 and 65535"


def validate_port(value: int | str) -> int:
    """Return a valid TCP port or raise a deterministic configuration error."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(_INVALID_PORT_MESSAGE)

    try:
        port = int(value)
    except ValueError as error:
        raise ValueError(_INVALID_PORT_MESSAGE) from error

    if not MIN_PORT <= port <= MAX_PORT:
        raise ValueError(_INVALID_PORT_MESSAGE)
    return port


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated application settings that can be supplied directly in tests."""

    port: int = DEFAULT_PORT
    database_url: str = DEFAULT_DATABASE_URL

    def __post_init__(self) -> None:
        object.__setattr__(self, "port", validate_port(self.port))


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Load settings from an explicit mapping or the process environment."""
    source = os.environ if environ is None else environ
    return Settings(
        port=validate_port(source.get("PORT", str(DEFAULT_PORT))),
        database_url=source.get("DATABASE_URL", DEFAULT_DATABASE_URL),
    )
