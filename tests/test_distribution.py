"""Installed-wheel regression coverage for the compatibility modules."""

import json
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

IMPORT_PROBE = """
import importlib
import json
import pathlib
import sys

installation = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(installation))
modules = {
    name: importlib.import_module(name)
    for name in ("calculator_api", "core", "server")
}
paths = {
    name: pathlib.Path(module.__file__).resolve()
    for name, module in modules.items()
}
assert all(path.is_relative_to(installation) for path in paths.values()), paths
assert modules["core"].add(2, 3) == 5
assert modules["server"].app.title == "Calculator API"
print(json.dumps({name: str(path) for name, path in paths.items()}))
"""


def test_built_wheel_installs_compatibility_modules_outside_checkout(tmp_path: Path) -> None:
    """Build and install the wheel before importing it from an isolated process."""
    wheel_directory = tmp_path / "wheel"
    installation = tmp_path / "installation"
    wheel_directory.mkdir()

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_directory),
            str(REPOSITORY_ROOT),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = list(wheel_directory.glob("calculator_api-*.whl"))
    assert len(wheels) == 1

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-compile",
            "--no-deps",
            "--target",
            str(installation),
            str(wheels[0]),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    probe = subprocess.run(
        [sys.executable, "-I", "-c", IMPORT_PROBE, str(installation)],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert probe.returncode == 0, probe.stderr
    imported_paths = json.loads(probe.stdout)
    assert set(imported_paths) == {"calculator_api", "core", "server"}
