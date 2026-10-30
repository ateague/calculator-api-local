#!/usr/bin/env python3
"""A very simple calculator REST API server."""

import os
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, NaiveDatetime
from sqlalchemy.engine import Engine
from sqlmodel import Field, Session, SQLModel, col, create_engine, select

from core import add, divide, multiply, subtract

# --- Database Setup ---

DEFAULT_DATABASE_URL = "sqlite:///calculator.db"
DEFAULT_PORT = 8000


@dataclass(frozen=True)
class Settings:
    """Environment-backed application settings."""

    database_url: str = DEFAULT_DATABASE_URL
    port: int = DEFAULT_PORT

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from the current process environment."""
        return cls(
            database_url=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
            port=int(os.environ.get("PORT", str(DEFAULT_PORT))),
        )


def load_settings() -> Settings:
    """Load a fresh immutable settings value."""
    return Settings.from_env()


def create_database_engine(database_url: str) -> Engine:
    """Create the SQLModel engine used by an application instance."""
    return create_engine(database_url, echo=False)


def get_session(request: Request) -> Iterator[Session]:
    """Yield a database session."""
    with Session(request.app.state.engine) as session:
        yield session


# --- Models ---


class CalculationBase(SQLModel):
    """Base model for calculations."""

    operation: str
    a: float
    b: float
    result: float


class Calculation(CalculationBase, table=True):
    """Database model for stored calculations."""

    id: int | None = Field(default=None, primary_key=True)
    created_at: NaiveDatetime = Field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None)
    )


class CalculationCreate(BaseModel):
    """Request body for creating a calculation."""

    operation: str
    a: float
    b: float


class CalculationResponse(CalculationBase):
    """Response model for a calculation."""

    id: int
    created_at: datetime


class CalculationRequest(BaseModel):
    """Request body for calculation endpoints."""

    a: float
    b: float


class ResultResponse(BaseModel):
    """Response body for calculation endpoints."""

    result: float


# --- App Setup ---


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create database tables on startup."""
    SQLModel.metadata.create_all(app.state.engine)
    yield


OPERATIONS: dict[str, Callable[[float, float], float]] = {
    "add": add,
    "sub": subtract,
    "mul": multiply,
    "div": divide,
}

router = APIRouter()


# --- Calculator Endpoints ---


@router.post("/add", response_model=ResultResponse)
def api_add(req: CalculationRequest) -> ResultResponse:
    """Add two numbers."""
    return ResultResponse(result=add(req.a, req.b))


@router.post("/subtract", response_model=ResultResponse)
def api_subtract(req: CalculationRequest) -> ResultResponse:
    """Subtract b from a."""
    return ResultResponse(result=subtract(req.a, req.b))


@router.post("/multiply", response_model=ResultResponse)
def api_multiply(req: CalculationRequest) -> ResultResponse:
    """Multiply two numbers."""
    return ResultResponse(result=multiply(req.a, req.b))


@router.post("/divide", response_model=ResultResponse)
def api_divide(req: CalculationRequest) -> ResultResponse:
    """Divide a by b."""
    try:
        return ResultResponse(result=divide(req.a, req.b))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# --- CRUD Endpoints for Calculations ---


@router.post("/calculations", response_model=CalculationResponse, status_code=201)
def create_calculation(
    req: CalculationCreate, session: Session = Depends(get_session)
) -> Calculation:
    """Create and store a new calculation."""
    if req.operation not in OPERATIONS:
        raise HTTPException(
            status_code=400, detail=f"Unknown operation: {req.operation}. Use: {list(OPERATIONS)}"
        )

    try:
        result = OPERATIONS[req.operation](req.a, req.b)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    calculation = Calculation(operation=req.operation, a=req.a, b=req.b, result=result)
    session.add(calculation)
    session.commit()
    session.refresh(calculation)
    return calculation


@router.get("/calculations", response_model=list[CalculationResponse])
def list_calculations(session: Session = Depends(get_session)) -> list[Calculation]:
    """List all stored calculations."""
    statement = select(Calculation).order_by(col(Calculation.created_at).desc())
    return list(session.exec(statement).all())


@router.get("/calculations/{calculation_id}", response_model=CalculationResponse)
def get_calculation(calculation_id: int, session: Session = Depends(get_session)) -> Calculation:
    """Get a specific calculation by ID."""
    calculation = session.get(Calculation, calculation_id)
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")
    return calculation


@router.delete("/calculations/{calculation_id}", status_code=204)
def delete_calculation(calculation_id: int, session: Session = Depends(get_session)) -> None:
    """Delete a calculation by ID."""
    calculation = session.get(Calculation, calculation_id)
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")
    session.delete(calculation)
    session.commit()


def create_app(engine: Engine | None = None, settings: Settings | None = None) -> FastAPI:
    """Create an application bound to one configuration and database engine."""
    app_settings = settings if settings is not None else load_settings()
    app_engine = (
        engine if engine is not None else create_database_engine(app_settings.database_url)
    )
    application = FastAPI(title="Calculator API", version="0.1.0", lifespan=lifespan)
    application.state.engine = app_engine
    application.state.settings = app_settings
    application.include_router(router)
    return application


app = create_app()


def main() -> None:
    """Run the server."""
    settings = load_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
