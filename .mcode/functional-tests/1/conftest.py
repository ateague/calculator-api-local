"""Shared helpers for live calculator functional tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import requests

ARTIFACT_DIR = Path(__file__).parent
EVIDENCE_PATH = ARTIFACT_DIR / "evidence.json"
EVIDENCE: dict[str, dict[str, Any]] = {}


@pytest.fixture
def record_rest():
    """Capture the exact response body/status used by a REST assertion."""

    def capture(name: str, response: requests.Response) -> None:
        EVIDENCE[name] = {
            "actual_status": response.status_code,
            "actual_output": response.text,
        }

    return capture


@pytest.fixture
def record_rest_sequence():
    """Capture unmodified bodies from a multi-request behavior in request order."""

    def capture(name: str, responses: list[requests.Response]) -> None:
        EVIDENCE[name] = {
            "actual_status": responses[-1].status_code,
            "actual_output": "\n".join(response.text for response in responses),
        }

    return capture


@pytest.fixture
def record_cli():
    """Capture exact combined process output and exit status for a launcher."""

    def capture(name: str, returncode: int, stdout: str, stderr: str) -> None:
        EVIDENCE[name] = {
            "actual_exit_code": returncode,
            "actual_output": stdout + stderr,
        }

    return capture


def pytest_sessionfinish() -> None:
    """Write evidence atomically enough for the result-recording pass."""
    EVIDENCE_PATH.write_text(
        json.dumps(EVIDENCE, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
