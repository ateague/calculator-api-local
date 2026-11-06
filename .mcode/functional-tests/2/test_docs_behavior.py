"""Live checks that documentation changes exposed metadata and left behavior unchanged."""
import os

import requests

BASE = os.environ.get("FT_BASE_URL", "http://127.0.0.1:18035")
T = 10


def spec():
    return requests.get(f"{BASE}/openapi.json", timeout=T).json()


def test_add_subtract_multiply_divide():
    cases = [("add", 5, 3, 8), ("subtract", 5, 3, 2), ("multiply", 7, 6, 42), ("divide", 6, 3, 2)]
    for path, a, b, exp in cases:
        r = requests.post(f"{BASE}/{path}", json={"a": a, "b": b}, timeout=T)
        assert r.status_code == 200, path
        assert r.json() == {"result": exp}


def test_divide_by_zero_400():
    r = requests.post(f"{BASE}/divide", json={"a": 1, "b": 0}, timeout=T)
    assert r.status_code == 400
    assert r.json() == {"detail": "Cannot divide by zero"}


def test_validation_422():
    assert requests.post(f"{BASE}/add", json={"a": "x"}, timeout=T).status_code == 422


def test_calculation_lifecycle():
    r = requests.post(f"{BASE}/calculations", json={"operation": "mul", "a": 7, "b": 6}, timeout=T)
    assert r.status_code == 201
    body = r.json()
    assert body["result"] == 42 and body["operation"] == "mul"
    cid = body["id"]
    assert requests.get(f"{BASE}/calculations/{cid}", timeout=T).status_code == 200
    lst = requests.get(f"{BASE}/calculations", timeout=T)
    assert lst.status_code == 200 and any(c["id"] == cid for c in lst.json())
    assert requests.delete(f"{BASE}/calculations/{cid}", timeout=T).status_code == 204
    g = requests.get(f"{BASE}/calculations/{cid}", timeout=T)
    assert g.status_code == 404 and g.json() == {"detail": "Calculation not found"}


def test_unknown_operation_400():
    r = requests.post(f"{BASE}/calculations", json={"operation": "pow", "a": 1, "b": 2}, timeout=T)
    assert r.status_code == 400


def test_delete_missing_404():
    assert requests.delete(f"{BASE}/calculations/99999999", timeout=T).status_code == 404


def test_openapi_summaries_descriptions():
    s = spec()
    ops = [(p, m) for p, v in s["paths"].items() for m in v]
    assert len(ops) >= 8
    for p, m in ops:
        op = s["paths"][p][m]
        assert op.get("summary"), (p, m)
        assert op.get("description"), (p, m)


def test_openapi_error_responses():
    s = spec()["paths"]
    assert "400" in s["/divide"]["post"]["responses"]
    assert "400" in s["/calculations"]["post"]["responses"]
    by_id = s.get("/calculations/{calculation_id}")
    assert by_id is None or "404" in by_id["get"]["responses"]
    for p, v in s.items():
        if p.startswith("/calculations/"):
            assert "404" in v["get"]["responses"]
            assert "404" in v["delete"]["responses"]


def test_openapi_field_descriptions_examples():
    schemas = spec()["components"]["schemas"]
    for name in ("CalculationRequest", "CalculationCreate"):
        for f, d in schemas[name]["properties"].items():
            assert d.get("description"), (name, f)
            assert d.get("examples"), (name, f)


def test_docs_pages():
    for p in ("/docs", "/redoc"):
        r = requests.get(f"{BASE}{p}", timeout=T)
        assert r.status_code == 200 and "html" in r.headers["content-type"]
