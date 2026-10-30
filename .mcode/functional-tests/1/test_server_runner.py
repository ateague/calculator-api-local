"""Regression tests for deterministic functional-server cleanup."""

from __future__ import annotations

import signal
import subprocess
from pathlib import Path

import pytest
import server_runner
from server_runner import ServerRunner


class FakeProcess:
    """Controllable Popen stand-in that records shutdown ordering."""

    def __init__(
        self,
        outcomes: list[tuple[str, str, int] | subprocess.TimeoutExpired],
    ) -> None:
        self.outcomes = outcomes
        self.actions: list[tuple[str, object | None]] = []
        self.returncode: int | None = None
        self.pid = 1234

    def poll(self) -> int | None:
        return self.returncode

    def send_signal(self, sig: int) -> None:
        self.actions.append(("send_signal", sig))

    def terminate(self) -> None:
        self.actions.append(("terminate", None))

    def kill(self) -> None:
        self.actions.append(("kill", None))

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        self.actions.append(("communicate", timeout))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, subprocess.TimeoutExpired):
            raise outcome
        stdout, stderr, self.returncode = outcome
        return stdout, stderr


@pytest.mark.parametrize(
    ("outcomes", "expected_actions", "expected_returncode"),
    [
        (
            [("graceful stdout", "graceful stderr", 0)],
            [("send_signal", signal.SIGINT), ("communicate", 10)],
            0,
        ),
        (
            [
                subprocess.TimeoutExpired("server", 10),
                ("terminated stdout", "terminated stderr", -15),
            ],
            [
                ("send_signal", signal.SIGINT),
                ("communicate", 10),
                ("terminate", None),
                ("communicate", 5),
            ],
            -15,
        ),
        (
            [
                subprocess.TimeoutExpired("server", 10),
                subprocess.TimeoutExpired("server", 5),
                ("killed stdout", "killed stderr", -9),
            ],
            [
                ("send_signal", signal.SIGINT),
                ("communicate", 10),
                ("terminate", None),
                ("communicate", 5),
                ("kill", None),
                ("communicate", None),
            ],
            -9,
        ),
    ],
)
def test_close_escalates_and_caches_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    outcomes: list[tuple[str, str, int] | subprocess.TimeoutExpired],
    expected_actions: list[tuple[str, object | None]],
    expected_returncode: int,
) -> None:
    process = FakeProcess(outcomes)
    popen_calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_popen(command: list[str], **kwargs: object) -> FakeProcess:
        popen_calls.append((command, kwargs))
        return process

    monkeypatch.setattr(server_runner.subprocess, "Popen", fake_popen)
    runner = ServerRunner(
        ["calculator-api"],
        cwd=tmp_path,
        env={"PORT": "8123"},
        port=8123,
        label="test server",
    )

    with runner as started:
        first_result = started.close()
        assert started.close() is first_result

    assert runner.result is first_result
    assert first_result.returncode == expected_returncode
    assert first_result.stdout.endswith("stdout")
    assert first_result.stderr.endswith("stderr")
    assert process.returncode is not None
    assert process.actions == expected_actions
    assert runner.base_url == "http://127.0.0.1:8123"
    assert popen_calls == [
        (
            ["calculator-api"],
            {
                "cwd": tmp_path,
                "env": {"PORT": "8123"},
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
            },
        )
    ]


def test_readiness_failure_reaps_process_and_reports_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    process = FakeProcess([("early stdout", "early stderr", 3)])
    process.returncode = 3
    monkeypatch.setattr(server_runner.subprocess, "Popen", lambda *args, **kwargs: process)
    runner = ServerRunner(
        ["calculator-api"], cwd=tmp_path, env={}, port=8123, label="test server"
    )

    with pytest.raises(
        AssertionError,
        match=r"test server exited before readiness \(3\)\nearly stdoutearly stderr",
    ):
        with runner as started:
            started.wait_until_ready(lambda: pytest.fail("request should not run"), lambda _: True)

    assert runner.result.returncode == 3
    assert process.actions == [("communicate", None)]
