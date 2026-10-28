# Calculator API

A small FastAPI service for direct arithmetic and SQLite-backed calculation history.

## Prerequisites and setup

Python 3.12 is required. From the repository root, create and activate an isolated virtual
environment, then install the application and its test tools:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test]"
```

On Windows, activate the environment with `.venv\Scripts\activate` instead.

## Run the service

Either supported launch mode starts the same application:

```bash
python server.py
```

Or, after installation:

```bash
calculator-api
```

Uvicorn binds to `0.0.0.0` on port `8000` by default. Use
`http://localhost:8000` from the local machine. A non-mutating startup healthcheck is:

```bash
curl http://localhost:8000/openapi.json
```

### Configuration

| Variable | Default | Behavior |
| --- | --- | --- |
| `PORT` | `8000` | Listening port. It must be an integer from 1 through 65535; any other value stops startup with a clear `Invalid PORT value ...` error. |
| `DATABASE_URL` | `sqlite:///calculator.db` | SQLAlchemy database URL used when the application is created. An invalid URL stops application creation with a clear `Invalid DATABASE_URL ...` error. |

For example:

```bash
PORT=8080 DATABASE_URL=sqlite:///development.db python server.py
```

The default SQLite database is `calculator.db` in the current working directory. Its table is
created during application startup.

## HTTP API

All request and response bodies below are JSON unless noted otherwise. Numeric operands are
returned as floating-point values.

### Direct arithmetic

Each direct route accepts `{"a": <number>, "b": <number>}` and returns HTTP 200 with
`{"result": <number>}`.

| Method | Endpoint | Operation | Success example |
| --- | --- | --- | --- |
| `POST` | `/add` | `a + b` | `{"result": 8.0}` |
| `POST` | `/subtract` | `a - b` | `{"result": 2.0}` |
| `POST` | `/multiply` | `a * b` | `{"result": 15.0}` |
| `POST` | `/divide` | `a / b` | `{"result": 2.5}` |

`POST /divide` with `b` equal to zero returns HTTP 400:

```json
{"detail": "Cannot divide by zero"}
```

Example:

```bash
curl -X POST http://localhost:8000/add \
  -H "Content-Type: application/json" \
  -d '{"a": 5, "b": 3}'
```

### Persisted calculations

The `operation` field for `POST /calculations` accepts these exact codes:

| Code | Calculation |
| --- | --- |
| `add` | `a + b` |
| `sub` | `a - b` |
| `mul` | `a * b` |
| `div` | `a / b` |

| Method | Endpoint | Request | Success |
| --- | --- | --- | --- |
| `POST` | `/calculations` | `{"operation": "add|sub|mul|div", "a": <number>, "b": <number>}` | HTTP 201 with the stored calculation |
| `GET` | `/calculations` | None | HTTP 200 with an array of calculations, newest first; an empty database returns `[]` |
| `GET` | `/calculations/{calculation_id}` | None | HTTP 200 with the requested calculation |
| `DELETE` | `/calculations/{calculation_id}` | None | HTTP 204 with an empty body |

A stored calculation has this response shape:

```json
{
  "operation": "mul",
  "a": 7.0,
  "b": 6.0,
  "result": 42.0,
  "id": 1,
  "created_at": "2026-01-01T12:00:00"
}
```

An unknown operation returns HTTP 400. For example, `pow` returns:

```json
{"detail": "Unknown operation: pow. Use: ['add', 'sub', 'mul', 'div']"}
```

A persisted `div` request with a zero divisor also returns HTTP 400 with
`{"detail": "Cannot divide by zero"}`. Failed requests are not stored.

Both get and delete return HTTP 404 with `{"detail": "Calculation not found"}` when the integer
ID does not exist.

#### Persistence lifecycle example

Create a row:

```bash
curl -X POST http://localhost:8000/calculations \
  -H "Content-Type: application/json" \
  -d '{"operation": "mul", "a": 7, "b": 6}'
```

List all rows in newest-first order:

```bash
curl http://localhost:8000/calculations
```

Get row 1:

```bash
curl http://localhost:8000/calculations/1
```

Delete row 1:

```bash
curl -X DELETE http://localhost:8000/calculations/1
```

### Request validation

FastAPI returns HTTP 422 for invalid request data. This includes missing required fields,
nonnumeric operands, malformed JSON, and a noninteger `calculation_id` path value. The response
contains FastAPI's validation-error details.

## Generated API documentation

With the service running locally, FastAPI exposes:

| Resource | URL |
| --- | --- |
| OpenAPI JSON | http://localhost:8000/openapi.json |
| Swagger UI | http://localhost:8000/docs |
| Swagger UI OAuth redirect | http://localhost:8000/docs/oauth2-redirect |
| ReDoc | http://localhost:8000/redoc |

## Quality checks

Run the local quality gates from the repository root:

```bash
ruff check .
pyright
pytest
```

For focused work, the test layers are:

```bash
pytest --no-cov tests/unit/test_core.py
pytest --no-cov tests/integration/test_api.py
pytest --no-cov tests/test_main.py
```

Focused runs disable the project-wide coverage gate because they intentionally execute only one
layer. The shared `pyproject.toml` configuration makes plain `pytest` measure branch coverage across
`core.py` and `server.py`, show missing lines in the terminal, write `coverage.xml`, and fail
below 80% combined coverage.

Build a wheel through the declared setuptools PEP 517 backend with:

```bash
python -m pip wheel . --no-deps
```

GitHub Actions runs on every pull request and pushes to `main` with Python 3.12. It installs
`.[test]`, builds a wheel with `python -m pip wheel . --no-deps`, then runs `ruff check .`,
`pyright`, and `pytest`; a failed gate fails the job.
The workflow uploads `coverage.xml` as the `coverage-report` artifact when the report is
available.
