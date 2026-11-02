"""Request, response, and persistence models for calculator operations."""

from datetime import datetime

from pydantic import BaseModel, NaiveDatetime
from sqlmodel import Field, SQLModel


class CalculationBase(SQLModel):
    """Shared fields for persisted calculations and their responses."""

    operation: str
    a: float
    b: float
    result: float


class Calculation(CalculationBase, table=True):
    """Database model for a stored calculation."""

    id: int | None = Field(default=None, primary_key=True)
    created_at: NaiveDatetime = Field(default_factory=datetime.utcnow)


class CalculationCreate(BaseModel):
    """Request body for creating a persisted calculation."""

    operation: str
    a: float
    b: float


class CalculationResponse(CalculationBase):
    """Response body for a persisted calculation."""

    id: int
    created_at: datetime


class CalculationRequest(BaseModel):
    """Request body for a stateless calculator operation."""

    a: float
    b: float


class ResultResponse(BaseModel):
    """Response body for a stateless calculator operation."""

    result: float
