"""FastAPI application factory and command-line entry point."""

from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from typing import Annotated

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, status
from sqlmodel import Session, SQLModel, col, select

from .config import Settings, load_settings
from .core import add, divide, multiply, subtract
from .database import SessionDependency, create_db_engine, create_session_dependency
from .models import (
    Calculation,
    CalculationCreate,
    CalculationRequest,
    CalculationResponse,
    ResultResponse,
)

Operation = Callable[[float, float], float]

OPERATIONS: dict[str, Operation] = {
    "add": add,
    "sub": subtract,
    "mul": multiply,
    "div": divide,
}


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Create database tables on the engine owned by the active application."""
    SQLModel.metadata.create_all(application.state.engine)
    yield


def _get_app_session(request: Request) -> Iterator[Session]:
    """Yield a session from the dependency owned by the request's application."""
    dependency: SessionDependency = request.app.state.get_session
    yield from dependency()


_router = APIRouter()


@_router.post("/add", response_model=ResultResponse)
def api_add(req: CalculationRequest) -> ResultResponse:
    """Add two numbers."""
    return ResultResponse(result=add(req.a, req.b))


@_router.post("/subtract", response_model=ResultResponse)
def api_subtract(req: CalculationRequest) -> ResultResponse:
    """Subtract ``b`` from ``a``."""
    return ResultResponse(result=subtract(req.a, req.b))


@_router.post("/multiply", response_model=ResultResponse)
def api_multiply(req: CalculationRequest) -> ResultResponse:
    """Multiply two numbers."""
    return ResultResponse(result=multiply(req.a, req.b))


@_router.post("/divide", response_model=ResultResponse)
def api_divide(req: CalculationRequest) -> ResultResponse:
    """Divide ``a`` by ``b``."""
    try:
        result = divide(req.a, req.b)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    return ResultResponse(result=result)


@_router.post(
    "/calculations",
    response_model=CalculationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_calculation(
    req: CalculationCreate,
    session: Annotated[Session, Depends(_get_app_session)],
) -> Calculation:
    """Compute and store a calculation."""
    operation = OPERATIONS.get(req.operation)
    if operation is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown operation: {req.operation}. Use: {list(OPERATIONS)}",
        )

    try:
        result = operation(req.a, req.b)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    calculation = Calculation(
        operation=req.operation,
        a=req.a,
        b=req.b,
        result=result,
    )
    session.add(calculation)
    session.commit()
    session.refresh(calculation)
    return calculation


@_router.get("/calculations", response_model=list[CalculationResponse])
def list_calculations(
    session: Annotated[Session, Depends(_get_app_session)],
) -> list[Calculation]:
    """List stored calculations from newest to oldest."""
    statement = select(Calculation).order_by(col(Calculation.created_at).desc())
    return list(session.exec(statement).all())


@_router.get("/calculations/{calculation_id}", response_model=CalculationResponse)
def get_calculation(
    calculation_id: int,
    session: Annotated[Session, Depends(_get_app_session)],
) -> Calculation:
    """Return one stored calculation."""
    calculation = session.get(Calculation, calculation_id)
    if calculation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found",
        )
    return calculation


@_router.delete(
    "/calculations/{calculation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_calculation(
    calculation_id: int,
    session: Annotated[Session, Depends(_get_app_session)],
) -> Response:
    """Delete one stored calculation."""
    calculation = session.get(Calculation, calculation_id)
    if calculation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calculation not found",
        )
    session.delete(calculation)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an application whose lifecycle and sessions share one engine."""
    selected_settings = load_settings() if settings is None else settings
    engine = create_db_engine(selected_settings.database_url)
    get_session = create_session_dependency(engine)

    application = FastAPI(title="Calculator API", version="0.1.0", lifespan=lifespan)
    application.state.settings = selected_settings
    application.state.engine = engine
    application.state.get_session = get_session
    application.include_router(_router)
    return application


app = create_app()


def main() -> None:
    """Run the default application with validated environment configuration."""
    settings = load_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.port)


__all__ = [
    "OPERATIONS",
    "Operation",
    "api_add",
    "api_divide",
    "api_multiply",
    "api_subtract",
    "app",
    "create_app",
    "create_calculation",
    "delete_calculation",
    "get_calculation",
    "lifespan",
    "list_calculations",
    "main",
]
