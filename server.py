#!/usr/bin/env python3
"""A very simple calculator REST API server."""

import os
from collections.abc import AsyncIterator, Callable, Generator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import TypeAlias

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import ArgumentError
from sqlmodel import Field, Session, SQLModel, col, create_engine, select

from core import add, divide, multiply, subtract

DEFAULT_DATABASE_URL = "sqlite:///calculator.db"


def get_session(request: Request) -> Generator[Session, None, None]:
    """Yield a database session owned by the active application."""
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


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


Operation: TypeAlias = Callable[[float, float], float]
OPERATIONS: dict[str, Operation] = {
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


def _create_engine(database_url: str) -> Engine:
    """Create an engine from a validated database URL."""
    try:
        url = make_url(database_url)
        connect_args = {"check_same_thread": False} if url.get_backend_name() == "sqlite" else {}
        return create_engine(url, echo=False, connect_args=connect_args)
    except (ArgumentError, ModuleNotFoundError, ValueError):
        raise ValueError(
            "Invalid DATABASE_URL: provide a valid SQLAlchemy database URL"
        ) from None


def create_app(database_url: str | None = None) -> FastAPI:
    """Create an independently configured calculator application."""
    resolved_database_url = (
        database_url
        if database_url is not None
        else os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    )
    engine = _create_engine(resolved_database_url)

    @asynccontextmanager
    async def lifespan(active_app: FastAPI) -> AsyncIterator[None]:
        """Create database tables for this application on startup."""
        SQLModel.metadata.create_all(active_app.state.engine)
        yield

    application = FastAPI(title="Calculator API", version="0.1.0", lifespan=lifespan)
    application.state.engine = engine
    application.include_router(router)
    return application


app = create_app()


def main() -> None:
    """Run the server."""
    raw_port = os.environ.get("PORT", "8000")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError(
            f"Invalid PORT value {raw_port!r}: expected an integer between 1 and 65535"
        ) from exc
    if not 1 <= port <= 65535:
        raise ValueError(
            f"Invalid PORT value {raw_port!r}: expected an integer between 1 and 65535"
        )
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
