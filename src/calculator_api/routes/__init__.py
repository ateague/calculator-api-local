"""Aggregated API routers for the Calculator API."""

from fastapi import APIRouter

from calculator_api.routes.calculator import router as calculator_router
from calculator_api.routes.history import router as history_router

router = APIRouter()
router.include_router(calculator_router)
router.include_router(history_router)
