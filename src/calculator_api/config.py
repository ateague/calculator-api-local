"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        database_url: SQLAlchemy database connection URL.
        port: Port number for the HTTP server.
        app_title: Display title for the FastAPI application.
        app_version: Semantic version string for the API.
    """

    database_url: str = "sqlite:///calculator.db"
    port: int = 8000
    app_title: str = "Calculator API"
    app_version: str = "0.1.0"
