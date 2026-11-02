# Calculator API

A local FastAPI service with four stateless calculator operations and SQLite-backed
calculation history. The arithmetic implementation is included in this repository; the
service has no external calculator dependency.

## Setup

Python 3.12 is required. From the repository root, create and activate a local virtual
environment, then install the application and its test tools:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
```

On Windows PowerShell, activate the environment with `.\.venv\Scripts\Activate.ps1` before
running the install command.

## Project layout

The installed implementation uses a `src` package layout:

- `src/calculator_api/core.py` contains the stateless `add`, `subtract`, `multiply`, and
  `divide` functions.
- `src/calculator_api/models.py` defines the direct-operation request/result models and the
  calculation-history request, response, and SQLModel table models.
- `src/calculator_api/database.py` creates database engines and engine-bound session
  dependencies.
- `src/calculator_api/config.py` loads and validates `PORT` and `DATABASE_URL`.
- `src/calculator_api/api.py` owns the FastAPI application factory, routes, database lifespan,
  operation dispatch, default ASGI application, and Uvicorn entry point.
- Top-level `core.py` and `server.py` are compatibility shims for legacy imports and the
  `python server.py` launch path.
- `tests/` contains isolated domain, model, HTTP, persistence, lifecycle, configuration, and
  command-line tests.

Each application instance owns its database engine and request sessions. During application
startup, the FastAPI lifespan creates the calculation table in the configured database.

## Run

After installation, start the service with either supported launch path:

```bash
calculator-api
```

or:

```bash
python server.py
```

By default, Uvicorn listens on `0.0.0.0:8000`, so the service is available locally at
`http://localhost:8000`.

## Configuration

Configuration is read from the process environment. No `.env` file loader is required.

| Variable | Default | Behavior |
|---|---|---|
| `PORT` | `8000` | Uvicorn listening port; must be an integer from 1 through 65535. |
| `DATABASE_URL` | `sqlite:///calculator.db` | SQLAlchemy database URL used for calculation history. The default creates `calculator.db` relative to the working directory. |

Override either setting for a process, for example:

```bash
PORT=9000 DATABASE_URL='sqlite:////tmp/calculator-history.db' calculator-api
```

The same variables apply to the compatibility launch path:

```bash
PORT=9001 DATABASE_URL='sqlite:///local-calculator.db' python server.py
```

## API

All responses are JSON except a successful delete, which has an empty body. FastAPI returns
HTTP 422 for malformed JSON, missing or non-numeric required fields, and non-integer
calculation IDs.

### Direct calculator operations

Each direct route accepts `POST` with `{"a": <number>, "b": <number>}` and returns HTTP 200
with `{"result": <number>}`.

| Route | Calculation |
|---|---|
| `POST /add` | `a + b` |
| `POST /subtract` | `a - b` |
| `POST /multiply` | `a * b` |
| `POST /divide` | `a / b` |

Division by zero returns HTTP 400 with `{"detail":"Cannot divide by zero"}`.

Example:

```bash
curl -X POST http://localhost:8000/add \
  -H 'Content-Type: application/json' \
  -d '{"a": 5, "b": 3}'
```

Response:

```json
{"result":8.0}
```

### Calculation history

History creation accepts `{"operation": <key>, "a": <number>, "b": <number>}`. Returned
records contain `id`, `operation`, `a`, `b`, `result`, and `created_at`. The operation key must
be exactly one of:

| Key | Calculation |
|---|---|
| `add` | `a + b` |
| `sub` | `a - b` |
| `mul` | `a * b` |
| `div` | `a / b` |

The four history operations are:

| Method and route | Success behavior | Error behavior |
|---|---|---|
| `POST /calculations` | HTTP 201; computes, stores, and returns the complete record. | HTTP 400 for an unknown operation or division by zero; HTTP 422 for invalid input. Failed requests do not create a record. |
| `GET /calculations` | HTTP 200; returns all records as an array, newest first. A fresh database returns `[]`. | No application-specific error. |
| `GET /calculations/{calculation_id}` | HTTP 200; returns the selected record. | HTTP 404 with `{"detail":"Calculation not found"}` when absent. |
| `DELETE /calculations/{calculation_id}` | HTTP 204 with an empty body; deletes the selected record. | HTTP 404 with `{"detail":"Calculation not found"}` when absent. |

An unknown operation response names the supported keys, for example
`{"detail":"Unknown operation: mod. Use: ['add', 'sub', 'mul', 'div']"}`. A persisted `div`
request with `b` equal to zero returns the same HTTP 400 division error as the direct route.

Create and store a multiplication:

```bash
curl -X POST http://localhost:8000/calculations \
  -H 'Content-Type: application/json' \
  -d '{"operation": "mul", "a": 7, "b": 6}'
```

Example response:

```json
{
  "id": 1,
  "operation": "mul",
  "a": 7.0,
  "b": 6.0,
  "result": 42.0,
  "created_at": "2026-11-02T12:00:00"
}
```

List, read, or delete saved calculations:

```bash
curl http://localhost:8000/calculations
curl http://localhost:8000/calculations/1
curl -X DELETE http://localhost:8000/calculations/1
```

## Generated API documentation

FastAPI generates these HTTP 200 endpoints from the application routes:

- OpenAPI schema: `http://localhost:8000/openapi.json`
- Swagger UI: `http://localhost:8000/docs`
- Swagger UI OAuth redirect helper: `http://localhost:8000/docs/oauth2-redirect`
- ReDoc: `http://localhost:8000/redoc`

The generated API metadata uses the title `Calculator API` and version `0.1.0`.

## Quality checks

Run the provider-neutral quality commands from the repository root with the virtual
environment active:

```bash
ruff check .
pyright
pytest
```

The `pytest` configuration measures branch coverage across `calculator_api` and the top-level
`core.py` and `server.py` compatibility shims. It shows missing lines, writes the machine-readable
report to `coverage.xml`, and fails when total coverage is below 80%.
