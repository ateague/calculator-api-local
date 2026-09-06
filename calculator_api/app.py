"""FastAPI application factory and entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI

from calculator_api.config import get_settings
from calculator_api.database import init_db
from calculator_api.routes.calculations import router as calculations_router
from calculator_api.routes.calculator import router as calculator_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create database tables on startup."""
    init_db()
    yield


app = FastAPI(title="Calculator API", version="0.1.0", lifespan=lifespan)
app.include_router(calculator_router)
app.include_router(calculations_router)


def main() -> None:
    """Run the server."""
    port = get_settings().port
    uvicorn.run(app, host="0.0.0.0", port=port)
