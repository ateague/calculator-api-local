"""Shared lifecycle management for functional-test server subprocesses."""

from __future__ import annotations

import signal
import socket
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import requests


@dataclass(frozen=True)
class ServerResult:
    """Captured output and status from a reaped server process."""

    returncode: int
    stdout: str
    stderr: str


def free_port() -> int:
    """Reserve an available loopback port for a subsequently started server."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ServerRunner:
    """Start, probe, and deterministically reap one live server process."""

    def __init__(
        self,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        port: int,
        label: str,
    ) -> None:
        self.command = command
        self.cwd = cwd
        self.env = env
        self.port = port
        self.label = label
        self.base_url = f"http://127.0.0.1:{port}"
        self._process: subprocess.Popen[str] | None = None
        self._result: ServerResult | None = None

    def __enter__(self) -> ServerRunner:
        self._process = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        print(
            f"{self.label} PID={self._process.pid} command={self.command[0]}"
        )
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @property
    def result(self) -> ServerResult:
        """Return the cached result after the server has been closed."""
        if self._result is None:
            raise RuntimeError(f"{self.label} has not been closed")
        return self._result

    def wait_until_ready(
        self,
        request: Callable[[], requests.Response],
        is_ready: Callable[[requests.Response], bool],
    ) -> requests.Response:
        """Poll for readiness and return the first accepted response."""
        process = self._require_process()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if process.poll() is not None:
                result = self.close()
                raise AssertionError(
                    f"{self.label} exited before readiness ({result.returncode})\n"
                    f"{result.stdout}{result.stderr}"
                )
            try:
                response = request()
                if is_ready(response):
                    return response
            except requests.RequestException:
                pass
            time.sleep(0.05)

        result = self.close()
        raise AssertionError(
            f"{self.label} did not become ready within 15 seconds\n"
            f"{result.stdout}{result.stderr}"
        )

    def close(self) -> ServerResult:
        """Stop and reap the server, escalating when graceful shutdown hangs."""
        if self._result is not None:
            return self._result

        process = self._require_process()
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                stdout, stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
        else:
            stdout, stderr = process.communicate()

        if process.returncode is None:
            raise AssertionError(f"{self.label} was not reaped")
        self._result = ServerResult(process.returncode, stdout, stderr)
        return self._result

    def _require_process(self) -> subprocess.Popen[str]:
        if self._process is None:
            raise RuntimeError(f"{self.label} has not been started")
        return self._process
