"""Pydantic and SQLModel schemas for the Calculator API."""

from datetime import datetime

from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class CalculationBase(SQLModel):
    """Base model for calculation fields shared across request and response schemas.

    Attributes:
        operation: The arithmetic operation name (e.g. ``"add"``).
        a: The first operand.
        b: The second operand.
        result: The computed result of the operation.
    """

    operation: str
    a: float
    b: float
    result: float


class Calculation(CalculationBase, table=True):
    """Database model for a stored calculation.

    Attributes:
        id: Auto-incremented primary key.
        created_at: Timestamp when the calculation was created.
    """

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CalculationCreate(BaseModel):
    """Request body for creating a calculation via the CRUD endpoint.

    Attributes:
        operation: The arithmetic operation name.
        a: The first operand.
        b: The second operand.
    """

    operation: str
    a: float
    b: float


class CalculationResponse(CalculationBase):
    """Response model for a calculation, including persistence metadata.

    Attributes:
        id: The calculation's database identifier.
        created_at: Timestamp when the calculation was created.
    """

    id: int
    created_at: datetime


class CalculationRequest(BaseModel):
    """Request body for the arithmetic endpoints.

    Attributes:
        a: The first operand.
        b: The second operand.
    """

    a: float
    b: float


class ResultResponse(BaseModel):
    """Response body containing a single computed result.

    Attributes:
        result: The computed result value.
    """

    result: float
