"""FastAPI application factory."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from sqlmodel import SQLModel

from calculator_api.config import Settings
from calculator_api.database import init_engine
from calculator_api.routes import router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Initializes the database engine, registers the lifespan handler that
    creates tables on startup, and includes all API routers.

    Args:
        settings: Application settings used to configure the app. If ``None``,
            a default ``Settings`` instance is created (loading values from
            environment variables where available).

    Returns:
        A fully configured ``FastAPI`` application instance.
    """
    if settings is None:
        settings = Settings()
    init_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Create database tables on startup.

        Args:
            app: The FastAPI application instance.

        Yields:
            Control back to the application after table creation.
        """
        from calculator_api.database import engine as _engine

        SQLModel.metadata.create_all(_engine)
        yield

    app = FastAPI(title="Calculator API", version="0.1.0", lifespan=lifespan)
    app.include_router(router)
    return app
