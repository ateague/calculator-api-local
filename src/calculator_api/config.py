"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        database_url: SQLAlchemy database connection URL.
        port: Port number for the HTTP server.
    """

    database_url: str = "sqlite:///calculator.db"
    port: int = 8000
