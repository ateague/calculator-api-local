#!/usr/bin/env python3
"""A very simple calculator REST API server.

The module exposes a FastAPI application, ``app``, with two groups of routes:

* Immediate arithmetic endpoints (``/add``, ``/subtract``, ``/multiply``, ``/divide``) that
  compute a result without storing anything.
* Calculation history endpoints (``/calculations``) that compute, persist, list, fetch and
  delete calculations in a SQLite database through SQLModel.

Configuration comes from the ``DATABASE_URL`` environment variable (database location) and the
``PORT`` environment variable (listening port, read by ``main``).
"""

import os
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, NaiveDatetime
from sqlmodel import Field, Session, SQLModel, col, create_engine, select

from core import add, divide, multiply, subtract

# --- Database Setup ---

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///calculator.db")
engine = create_engine(DATABASE_URL, echo=False)


def get_session() -> Generator[Session, None, None]:
    """Yield a database session for one request.

    The session is opened on the module-level ``engine`` and closed when the request finishes.
    Intended for use as a FastAPI dependency.

    Yields:
    A SQLModel ``Session`` bound to ``engine``.
    """
    with Session(engine) as session:
        yield session


# --- Models ---


class CalculationBase(SQLModel):
    """Fields shared by stored and returned calculations.

    Attributes:
        operation: Operation code that was applied: ``add``, ``sub``, ``mul`` or ``div``.
        a: The first operand.
        b: The second operand.
        result: The computed result of applying the operation to ``a`` and ``b``.
    """

    operation: str = Field(
        description="Operation code applied: `add`, `sub`, `mul` or `div`.",
        schema_extra={"examples": ["mul"]},
    )
    a: float = Field(description="First operand.", schema_extra={"examples": [7]})
    b: float = Field(description="Second operand.", schema_extra={"examples": [6]})
    result: float = Field(
        description="Result of applying the operation to `a` and `b`.",
        schema_extra={"examples": [42]},
    )


def naive_utc_now() -> datetime:
    """Return the current UTC time without timezone metadata.

    Timestamps are stored and serialized as naive UTC values for compatibility with existing
    SQLite data.

    Returns:
        The current UTC time as a naive ``datetime`` (``tzinfo`` is ``None``).
    """
    return datetime.now(UTC).replace(tzinfo=None)


class Calculation(CalculationBase, table=True):
    """Database model for stored calculations, mapped to the ``calculation`` table.

    Attributes:
        id: Auto-assigned primary key; ``None`` until the row is inserted.
        created_at: Naive UTC creation timestamp, set when the object is created.
    """

    id: int | None = Field(default=None, primary_key=True)
    created_at: NaiveDatetime = Field(default_factory=naive_utc_now)


class CalculationCreate(BaseModel):
    """Request body for creating a stored calculation.

    Attributes:
        operation: Operation code. One of ``add`` (addition), ``sub`` (subtraction),
            ``mul`` (multiplication) or ``div`` (division).
        a: The first operand.
        b: The second operand.
    """

    operation: str = Field(
        description=(
            "Operation code: `add` (addition), `sub` (subtraction), "
            "`mul` (multiplication) or `div` (division)."
        ),
        schema_extra={"examples": ["mul"]},
    )
    a: float = Field(description="First operand.", schema_extra={"examples": [7]})
    b: float = Field(description="Second operand.", schema_extra={"examples": [6]})


class CalculationResponse(CalculationBase):
    """Response model for a stored calculation.

    Attributes:
        id: Unique identifier of the stored calculation.
        created_at: Naive UTC timestamp of when the calculation was stored.
    """

    id: int = Field(description="Unique identifier of the stored calculation.")
    created_at: datetime = Field(
        description="Naive UTC timestamp of when the calculation was stored."
    )


class CalculationRequest(BaseModel):
    """Request body for the immediate arithmetic endpoints.

    Attributes:
        a: The first operand.
        b: The second operand.
    """

    a: float = Field(description="First operand.", schema_extra={"examples": [5]})
    b: float = Field(description="Second operand.", schema_extra={"examples": [3]})


class ResultResponse(BaseModel):
    """Response body for the immediate arithmetic endpoints.

    Attributes:
        result: The computed result.
    """

    result: float = Field(description="Computed result.", schema_extra={"examples": [8]})


# --- App Setup ---


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create the database schema when the application starts.

    Calls ``SQLModel.metadata.create_all`` on ``engine``, which creates any missing tables
    (such as ``calculation``) and leaves existing tables and rows untouched.

    Args:
        app: The FastAPI application being started. Unused.

    Yields:
        Control to the application for its lifetime.
    """
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title="Calculator API", version="0.1.0", lifespan=lifespan)

OPERATIONS: dict[str, Callable[[float, float], float]] = {
    "add": add,
    "sub": subtract,
    "mul": multiply,
    "div": divide,
}


# --- Calculator Endpoints ---


@app.post(
    "/add",
    response_model=ResultResponse,
    summary="Add two numbers",
    description="Return the sum of `a` and `b`. Nothing is stored.",
)
def api_add(req: CalculationRequest) -> ResultResponse:
    """Add two numbers without storing the result.

    Args:
        req: Request body with operands ``a`` and ``b``.

    Returns:
        A ``ResultResponse`` holding ``a + b``.
    """
    return ResultResponse(result=add(req.a, req.b))


@app.post(
    "/subtract",
    response_model=ResultResponse,
    summary="Subtract two numbers",
    description="Return `a - b`. Nothing is stored.",
)
def api_subtract(req: CalculationRequest) -> ResultResponse:
    """Subtract one number from another without storing the result.

    Args:
        req: Request body with operands ``a`` and ``b``.

    Returns:
        A ``ResultResponse`` holding ``a - b``.
    """
    return ResultResponse(result=subtract(req.a, req.b))


@app.post(
    "/multiply",
    response_model=ResultResponse,
    summary="Multiply two numbers",
    description="Return the product of `a` and `b`. Nothing is stored.",
)
def api_multiply(req: CalculationRequest) -> ResultResponse:
    """Multiply two numbers without storing the result.

    Args:
        req: Request body with operands ``a`` and ``b``.

    Returns:
        A ``ResultResponse`` holding ``a * b``.
    """
    return ResultResponse(result=multiply(req.a, req.b))


@app.post(
    "/divide",
    response_model=ResultResponse,
    summary="Divide two numbers",
    description="Return `a / b`. Nothing is stored.",
    responses={400: {"description": "Division by zero: detail is `Cannot divide by zero`."}},
)
def api_divide(req: CalculationRequest) -> ResultResponse:
    """Divide one number by another without storing the result.

    Args:
        req: Request body with operands ``a`` (dividend) and ``b`` (divisor).

    Returns:
        A ``ResultResponse`` holding ``a / b``.

    Raises:
        HTTPException: With status 400 and detail ``"Cannot divide by zero"`` if ``b`` is zero.
    """
    try:
        return ResultResponse(result=divide(req.a, req.b))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# --- CRUD Endpoints for Calculations ---


@app.post(
    "/calculations",
    response_model=CalculationResponse,
    status_code=201,
    summary="Create a calculation",
    description=(
        "Apply the operation (`add`, `sub`, `mul` or `div`) to `a` and `b`, store the "
        "calculation and return it with its generated `id` and `created_at` timestamp."
    ),
    responses={
        400: {"description": "Unknown operation code, or division by zero."},
    },
)
def create_calculation(
    req: CalculationCreate, session: Session = Depends(get_session)
) -> Calculation:
    """Compute a calculation, persist it and return the stored row.

    Args:
        req: Request body with the operation code and operands.
        session: Database session injected by FastAPI.

    Returns:
        The newly stored ``Calculation``, including its generated ``id`` and ``created_at``.

    Raises:
        HTTPException: With status 400 if the operation is not one of ``OPERATIONS`` or the
            operation raises ``ValueError`` (division by zero). Nothing is stored in that case.
    """
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


@app.get(
    "/calculations",
    response_model=list[CalculationResponse],
    summary="List calculations",
    description="Return all stored calculations, newest first (`created_at` descending).",
)
def list_calculations(session: Session = Depends(get_session)) -> list[Calculation]:
    """List all stored calculations, newest first.

    Args:
        session: Database session injected by FastAPI.

    Returns:
        Every stored ``Calculation`` ordered by ``created_at`` descending. Empty if none exist.
    """
    statement = select(Calculation).order_by(col(Calculation.created_at).desc())
    return list(session.exec(statement).all())


@app.get(
    "/calculations/{calculation_id}",
    response_model=CalculationResponse,
    summary="Get a calculation",
    description="Return the stored calculation with the given `calculation_id`.",
    responses={
        404: {"description": "No calculation with this ID: detail is `Calculation not found`."}
    },
)
def get_calculation(calculation_id: int, session: Session = Depends(get_session)) -> Calculation:
    """Fetch one stored calculation by ID.

    Args:
        calculation_id: Primary key of the calculation to fetch.
        session: Database session injected by FastAPI.

    Returns:
        The matching ``Calculation``.

    Raises:
        HTTPException: With status 404 and detail ``"Calculation not found"`` if no row has
            the given ID.
    """
    calculation = session.get(Calculation, calculation_id)
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")
    return calculation


@app.delete(
    "/calculations/{calculation_id}",
    status_code=204,
    summary="Delete a calculation",
    description=(
        "Delete the stored calculation with the given `calculation_id`. "
        "Responds with an empty body on success."
    ),
    responses={
        404: {"description": "No calculation with this ID: detail is `Calculation not found`."}
    },
)
def delete_calculation(calculation_id: int, session: Session = Depends(get_session)) -> None:
    """Delete one stored calculation by ID.

    Args:
        calculation_id: Primary key of the calculation to delete.
        session: Database session injected by FastAPI.

    Raises:
        HTTPException: With status 404 and detail ``"Calculation not found"`` if no row has
            the given ID.

    Side effects:
        Removes the row from the database and commits the transaction. The response is HTTP
        204 with an empty body.
    """
    calculation = session.get(Calculation, calculation_id)
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")
    session.delete(calculation)
    session.commit()


def main() -> None:
    """Run the API with Uvicorn.

    Reads the listening port from the ``PORT`` environment variable (default ``8000``) and
    serves ``app`` on all interfaces (``0.0.0.0``). Blocks until the server stops.

    Raises:
        ValueError: If ``PORT`` is set to a value that is not an integer.
    """
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
