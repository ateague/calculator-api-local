"""Validation, defaults, coercion, and serialization coverage for all models."""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from calculator_api.models import (
    Calculation,
    CalculationBase,
    CalculationCreate,
    CalculationRequest,
    CalculationResponse,
    ResultResponse,
)


def test_all_six_models_instantiate_and_serialize() -> None:
    timestamp = datetime(2026, 1, 2, 3, 4, 5)
    base = CalculationBase(operation="add", a=1, b=2, result=3)
    calculation = Calculation.model_validate(
        {
            "id": 7,
            "operation": "sub",
            "a": 5,
            "b": 2,
            "result": 3,
            "created_at": timestamp,
        }
    )
    creation = CalculationCreate(operation="mul", a=3, b=4)
    response = CalculationResponse(
        id=8,
        operation="div",
        a=8,
        b=2,
        result=4,
        created_at=timestamp,
    )
    request = CalculationRequest(a=9, b=6)
    result = ResultResponse(result=15)

    assert base.model_dump() == {"operation": "add", "a": 1.0, "b": 2.0, "result": 3.0}
    assert calculation.model_dump() == {
        "operation": "sub",
        "a": 5.0,
        "b": 2.0,
        "result": 3.0,
        "id": 7,
        "created_at": timestamp,
    }
    assert creation.model_dump() == {"operation": "mul", "a": 3.0, "b": 4.0}
    assert response.model_dump(mode="json") == {
        "operation": "div",
        "a": 8.0,
        "b": 2.0,
        "result": 4.0,
        "id": 8,
        "created_at": "2026-01-02T03:04:05",
    }
    assert request.model_dump() == {"a": 9.0, "b": 6.0}
    assert result.model_dump() == {"result": 15.0}


def test_calculation_has_pre_persistence_id_and_utc_timestamp_defaults() -> None:
    before = datetime.now(UTC).replace(tzinfo=None)
    calculation = Calculation(operation="add", a=1, b=2, result=3)
    after = datetime.now(UTC).replace(tzinfo=None)

    assert calculation.id is None
    assert before <= calculation.created_at <= after
    assert calculation.created_at.tzinfo is None


@pytest.mark.parametrize(
    ("model", "payload", "expected"),
    [
        (
            CalculationBase,
            {"operation": "add", "a": "1.25", "b": "2", "result": "3.25"},
            {"a": 1.25, "b": 2.0, "result": 3.25},
        ),
        (
            Calculation,
            {"operation": "sub", "a": "5", "b": "2", "result": "3"},
            {"a": 5.0, "b": 2.0, "result": 3.0},
        ),
        (
            CalculationCreate,
            {"operation": "mul", "a": "1.5", "b": "4"},
            {"a": 1.5, "b": 4.0},
        ),
        (
            CalculationResponse,
            {
                "id": "12",
                "operation": "div",
                "a": "9",
                "b": "3",
                "result": "3",
                "created_at": "2026-01-02T03:04:05",
            },
            {"id": 12, "a": 9.0, "b": 3.0, "result": 3.0},
        ),
        (CalculationRequest, {"a": "-2.5", "b": "4"}, {"a": -2.5, "b": 4.0}),
        (ResultResponse, {"result": "7.5"}, {"result": 7.5}),
    ],
)
def test_all_models_coerce_numeric_strings(
    model: type[Any],
    payload: dict[str, Any],
    expected: dict[str, float | int],
) -> None:
    serialized = model.model_validate(payload).model_dump()
    assert {key: serialized[key] for key in expected} == expected


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (CalculationBase, {"operation": "add", "a": 1, "b": 2}),
        (Calculation, {"a": 1, "b": 2, "result": 3}),
        (CalculationCreate, {"operation": "add", "a": 1}),
        (
            CalculationResponse,
            {
                "operation": "add",
                "a": 1,
                "b": 2,
                "result": 3,
                "created_at": "2026-01-02T03:04:05",
            },
        ),
        (CalculationRequest, {"a": 1}),
        (ResultResponse, {}),
    ],
)
def test_all_models_reject_missing_required_fields(
    model: type[Any], payload: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (
            CalculationBase,
            {"operation": "add", "a": "invalid", "b": 2, "result": 3},
        ),
        (
            Calculation,
            {"operation": "add", "a": 1, "b": "invalid", "result": 3},
        ),
        (CalculationCreate, {"operation": "add", "a": 1, "b": "invalid"}),
        (
            CalculationResponse,
            {
                "id": 1,
                "operation": "add",
                "a": 1,
                "b": 2,
                "result": "invalid",
                "created_at": "2026-01-02T03:04:05",
            },
        ),
        (CalculationRequest, {"a": "invalid", "b": 2}),
        (ResultResponse, {"result": "invalid"}),
    ],
)
def test_all_models_reject_non_numeric_fields(
    model: type[Any], payload: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)
