"""Tests that every callable, class and route is documented."""

import ast
import inspect
from pathlib import Path
from typing import Any

import core
import server

ROOT = Path(__file__).resolve().parent.parent
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _defined_here(module: Any, obj: Any) -> bool:
    return getattr(obj, "__module__", None) == module.__name__


def _public_members(module: Any) -> list[tuple[str, Any]]:
    return [
        (name, obj)
        for name, obj in vars(module).items()
        if not name.startswith("_")
        and (inspect.isfunction(obj) or inspect.isclass(obj))
        and _defined_here(module, obj)
    ]


def test_public_members_have_docstrings() -> None:
    for module in (core, server):
        assert (module.__doc__ or "").strip(), f"{module.__name__} lacks a module docstring"
        members = _public_members(module)
        assert members
        for name, obj in members:
            assert (inspect.getdoc(obj) or "").strip(), f"{module.__name__}.{name} undocumented"


def test_every_definition_in_source_has_docstring() -> None:
    for filename in ("core.py", "server.py"):
        tree = ast.parse((ROOT / filename).read_text())
        for node in ast.walk(tree):
            if isinstance(
                node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
            ):
                assert (ast.get_docstring(node) or "").strip(), f"{filename}:{node.name}"


def test_openapi_operations_have_summary_and_description() -> None:
    schema = server.app.openapi()
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            if method not in HTTP_METHODS:
                continue
            assert operation.get("summary", "").strip(), f"{method.upper()} {path} summary"
            assert operation.get("description", "").strip(), f"{method.upper()} {path} description"


def test_openapi_paths_and_status_codes_unchanged() -> None:
    schema = server.app.openapi()
    statuses = {
        (path, method): set(operation["responses"])
        for path, item in schema["paths"].items()
        for method, operation in item.items()
    }
    assert statuses == {
        ("/add", "post"): {"200", "422"},
        ("/subtract", "post"): {"200", "422"},
        ("/multiply", "post"): {"200", "422"},
        ("/divide", "post"): {"200", "400", "422"},
        ("/calculations", "post"): {"201", "400", "422"},
        ("/calculations", "get"): {"200"},
        ("/calculations/{calculation_id}", "get"): {"200", "404", "422"},
        ("/calculations/{calculation_id}", "delete"): {"204", "404", "422"},
    }


def test_model_fields_are_described() -> None:
    schemas = server.app.openapi()["components"]["schemas"]
    for name in ("CalculationCreate", "CalculationResponse", "CalculationRequest", "ResultResponse"):
        for field, prop in schemas[name]["properties"].items():
            assert prop.get("description"), f"{name}.{field}"
