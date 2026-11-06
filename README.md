# Calculator API

A FastAPI calculator service with immediate arithmetic endpoints and SQLite-backed
calculation history.

## Requirements

- Python 3.12 or newer

## Installation

Install the service in editable mode from the repository root:

```bash
python -m pip install -e .
```

To also install the test and development tooling:

```bash
python -m pip install -e ".[test,dev]"
```

## Testing

Run the test suite with `python -m pytest`. Pytest is configured to collect only from
`tests`, measure `core.py` and `server.py` with branch coverage, report missing lines,
and fail below 95% coverage. Each API test uses a fresh temporary SQLite database, so
no `calculator.db` is created.

Run the complete quality gate with:

```bash
ruff check . && pyright && python -m pytest
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///calculator.db` | SQLModel database URL used for calculation history |
| `PORT` | `8000` | HTTP port used by Uvicorn |

The server binds to `0.0.0.0`. The default SQLite database is created as
`calculator.db` in the current working directory.

## Running the service

Run the module directly:

```bash
python server.py
```

Or use the installed console entry point:

```bash
calculator-api
```

With the default configuration, the API is available at `http://localhost:8000`.
Importers can also use the exported ASGI application as `server.app`.

## Immediate calculations

Each endpoint accepts a JSON body containing numeric `a` and `b` fields and returns
`{"result": <number>}`.

| Method | Endpoint | Behavior | Success status |
|--------|----------|----------|----------------|
| POST | `/add` | Add `a` and `b` | 200 |
| POST | `/subtract` | Subtract `b` from `a` | 200 |
| POST | `/multiply` | Multiply `a` and `b` | 200 |
| POST | `/divide` | Divide `a` by `b` | 200 |

Division by zero returns HTTP 400 with detail `Cannot divide by zero`. Missing or
malformed request fields return FastAPI's HTTP 422 validation response.

Example:

```bash
curl -X POST http://localhost:8000/add \
  -H "Content-Type: application/json" \
  -d '{"a": 5, "b": 3}'
```

## Calculation history

Persisted calculations use exactly these operation codes:

| Code | Operation |
|------|-----------|
| `add` | Addition |
| `sub` | Subtraction |
| `mul` | Multiplication |
| `div` | Division |

| Method | Endpoint | Success response | Error behavior |
|--------|----------|------------------|----------------|
| POST | `/calculations` | HTTP 201 with `operation`, `a`, `b`, `result`, `id`, and `created_at` | HTTP 400 for an unknown operation or division by zero; HTTP 422 for invalid input |
| GET | `/calculations` | HTTP 200 list ordered by `created_at` descending | — |
| GET | `/calculations/{calculation_id}` | HTTP 200 with the matching calculation | HTTP 404 with `Calculation not found` |
| DELETE | `/calculations/{calculation_id}` | HTTP 204 with an empty body | HTTP 404 with `Calculation not found` |

Create a stored calculation:

```bash
curl -X POST http://localhost:8000/calculations \
  -H "Content-Type: application/json" \
  -d '{"operation": "mul", "a": 7, "b": 6}'
```

The SQLite schema is created when the application starts. Timestamps are stored and
serialized as naive UTC values for compatibility with existing data.

## Generated API documentation

Every endpoint is self-documented: each operation has a summary, description, documented
error responses and described model fields, rendered in Swagger UI (`/docs`) and ReDoc
(`/redoc`). FastAPI exposes all generated documentation routes:

- OpenAPI schema: `http://localhost:8000/openapi.json`
- Swagger UI: `http://localhost:8000/docs`
- Swagger OAuth redirect: `http://localhost:8000/docs/oauth2-redirect`
- ReDoc: `http://localhost:8000/redoc`

## Changelog

NOP
