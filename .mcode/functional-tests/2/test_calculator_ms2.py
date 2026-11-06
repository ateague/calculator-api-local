import os
import uuid
from pathlib import Path

import pytest
import requests

BASE = os.environ.get("FT_BASE_URL", "http://127.0.0.1:18035")
REPO = Path(__file__).resolve().parents[3]
T = 10


def post(p, body):
    return requests.post(BASE + p, json=body, timeout=T)


@pytest.mark.parametrize("path,a,b,exp", [
    ("/add", 2, 3, 5.0), ("/subtract", 2, 3, -1.0),
    ("/multiply", 4, 2.5, 10.0), ("/divide", 9, 3, 3.0)])
def test_immediate_ops(path, a, b, exp):
    r = post(path, {"a": a, "b": b})
    assert r.status_code == 200
    assert r.json() == {"result": exp}


def test_divide_by_zero():
    assert post("/divide", {"a": 1, "b": 0}).status_code == 400


@pytest.mark.parametrize("path", ["/add", "/subtract", "/multiply", "/divide"])
def test_immediate_validation(path):
    assert post(path, {"a": "x", "b": 1}).status_code == 422
    assert post(path, {"a": 1}).status_code == 422


@pytest.mark.parametrize("op,a,b,exp", [
    ("add", 1, 2, 3.0), ("sub", 5, 2, 3.0), ("mul", 3, 4, 12.0), ("div", 8, 2, 4.0)])
def test_calc_crud(op, a, b, exp):
    r = post("/calculations", {"operation": op, "a": a, "b": b})
    assert r.status_code == 201
    j = r.json()
    assert j["result"] == exp and j["operation"] == op and "created_at" in j
    cid = j["id"]
    g = requests.get(f"{BASE}/calculations/{cid}", timeout=T)
    assert g.status_code == 200 and g.json()["id"] == cid
    assert requests.delete(f"{BASE}/calculations/{cid}", timeout=T).status_code == 204
    assert requests.get(f"{BASE}/calculations/{cid}", timeout=T).status_code == 404
    assert requests.delete(f"{BASE}/calculations/{cid}", timeout=T).status_code == 404


def test_calc_errors():
    assert post("/calculations", {"operation": "pow", "a": 1, "b": 2}).status_code == 400
    assert post("/calculations", {"operation": "div", "a": 1, "b": 0}).status_code == 400
    assert post("/calculations", {"operation": "add", "a": "x", "b": 2}).status_code == 422
    assert post("/calculations", {"operation": "add"}).status_code == 422
    assert requests.get(f"{BASE}/calculations/99999999", timeout=T).status_code == 404
    assert requests.get(f"{BASE}/calculations/abc", timeout=T).status_code == 422


def test_list_descending():
    ids = [post("/calculations", {"operation": "add", "a": i, "b": 1}).json()["id"] for i in range(3)]
    lst = requests.get(BASE + "/calculations", timeout=T)
    assert lst.status_code == 200
    got = [c["id"] for c in lst.json() if c["id"] in ids]
    assert got == sorted(ids, reverse=True)
    for i in ids:
        requests.delete(f"{BASE}/calculations/{i}", timeout=T)


def test_openapi():
    r = requests.get(BASE + "/openapi.json", timeout=T)
    assert r.status_code == 200
    j = r.json()
    assert j["info"]["title"] == "Calculator API"
    for p in ["/add", "/subtract", "/multiply", "/divide", "/calculations", "/calculations/{calculation_id}"]:
        assert p in j["paths"]


def test_docs():
    r = requests.get(BASE + "/docs", timeout=T)
    assert r.status_code == 200 and "swagger" in r.text.lower()


def test_oauth2_redirect():
    assert requests.get(BASE + "/docs/oauth2-redirect", timeout=T).status_code == 200


def test_redoc():
    r = requests.get(BASE + "/redoc", timeout=T)
    assert r.status_code == 200 and "redoc" in r.text.lower()


def test_no_repo_db():
    assert not (REPO / "calculator.db").exists()
