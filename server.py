#!/usr/bin/env python3
"""A very simple calculator REST API server."""

import os
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import Engine
from sqlmodel import Field, Session, SQLModel, create_engine, select

from core import add, divide, multiply, subtract

# --- Database Setup ---

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///calculator.db")


def create_database_engine(database_url: str) -> Engine:
    """Create an engine suitable for the configured database URL."""
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, echo=False, connect_args=connect_args)


engine: Engine


def get_session() -> Iterator[Session]:
    """Yield a database session."""
    with Session(engine) as session:
        yield session


def _session_dependency(database_engine: Engine) -> Callable[[], Iterator[Session]]:
    """Create a session dependency bound to one application engine."""

    def session_dependency() -> Iterator[Session]:
        with Session(database_engine) as session:
            yield session

    return session_dependency


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

    @field_validator("created_at")
    @classmethod
    def make_legacy_timestamp_utc(cls, value: datetime) -> datetime:
        """Treat legacy naive SQLite timestamps as UTC in API responses."""
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value


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


router = APIRouter()

OPERATIONS: dict[str, Callable[[float, float], float]] = {
    "add": add,
    "sub": subtract,
    "mul": multiply,
    "div": divide,
}


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
    statement = select(Calculation).order_by(Calculation.created_at.desc(), Calculation.id.desc())
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


def create_app(database_url: str = DATABASE_URL) -> FastAPI:
    """Create a calculator application bound to the requested database."""
    application_engine = create_database_engine(database_url)
    application = FastAPI(title="Calculator API", version="0.1.0", lifespan=lifespan)
    application.state.engine = application_engine
    application.dependency_overrides[get_session] = _session_dependency(application_engine)
    application.include_router(router)
    return application


app = create_app()
engine = app.state.engine


def main() -> None:
    """Run the server."""
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
