# Calculator API

A very simple REST API server that reuses functionality from `calculator-cli`.

## Requirements

Python 3.12 or newer is required.

## Installation

```bash
python -m pip install -e '.[test,dev]'
```

This editable installation includes the API, test and coverage dependencies, Ruff, and Pyright.

## Configuration

The service reads its configuration from environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `sqlite:///calculator.db` | SQLAlchemy database URL used for calculation history |
| `PORT` | `8000` | TCP port used by Uvicorn |

The default database is the local SQLite file `calculator.db`. Set either variable in the
environment before launching the service to override its default. For example, this uses another
local SQLite file and port without placing configuration in source control:

```bash
DATABASE_URL=sqlite:///development.db PORT=9000 python server.py
```

Keep database credentials and other sensitive values in the environment; do not commit them.

## Run

Launch the service directly:

```bash
python server.py
```

Or use the installed console command:

```bash
calculator-api
```

With the default configuration, the server runs on `http://localhost:8000` and creates the SQLite
history table at startup.

## Endpoints

### Calculator Operations

All calculator endpoints accept `POST` with a JSON body shaped as
`{"a": <number>, "b": <number>}` and return `{"result": <number>}`.

| Method | Endpoint | Description | Success |
|--------|----------|-------------|---------|
| POST | `/add` | Add two numbers | `200 OK` |
| POST | `/subtract` | Subtract b from a | `200 OK` |
| POST | `/multiply` | Multiply two numbers | `200 OK` |
| POST | `/divide` | Divide a by b | `200 OK` |

Malformed requests, missing operands, and nonnumeric operands return `422 Unprocessable Entity`.
Division by zero returns `400 Bad Request` with `{"detail": "Cannot divide by zero"}`.

### Calculation History (CRUD)

Calculations can be stored in the configured SQLite database. The creation request is
`{"operation": <token>, "a": <number>, "b": <number>}`. Supported operation tokens are `add`,
`sub`, `mul`, and `div`.

| Method | Endpoint | Description | Status behavior |
|--------|----------|-------------|-----------------|
| POST | `/calculations` | Create and store a calculation | `201 Created`; `400` for an unknown operation or division by zero; `422` for an invalid request |
| GET | `/calculations` | List all stored calculations, newest first | `200 OK` with a JSON array, including `[]` when empty |
| GET | `/calculations/{id}` | Get a specific calculation | `200 OK`; `404 Not Found` when the ID does not exist |
| DELETE | `/calculations/{id}` | Delete a calculation | `204 No Content`; `404 Not Found` when the ID does not exist |

Stored calculation responses contain `operation`, `a`, `b`, `result`, the generated integer `id`,
and the UTC `created_at` timestamp. Missing history records return
`{"detail": "Calculation not found"}`.

## Examples

**Quick calculation:**

```bash
curl -X POST http://localhost:8000/add \
  -H "Content-Type: application/json" \
  -d '{"a": 5, "b": 3}'
```

Response: `{"result": 8.0}`

**Save a calculation to the database:**

```bash
curl -X POST http://localhost:8000/calculations \
  -H "Content-Type: application/json" \
  -d '{"operation": "mul", "a": 7, "b": 6}'
```

Response: `{"operation": "mul", "a": 7.0, "b": 6.0, "result": 42.0, "id": 1, "created_at": "..."}`

**List all saved calculations:**

```bash
curl http://localhost:8000/calculations
```

**Delete a calculation:**

```bash
curl -X DELETE http://localhost:8000/calculations/1
```

## Quality Checks

Run the repository's configured test and coverage gate:

```bash
python -m pytest
```

This command measures statement and branch coverage for `core.py` and `server.py`, reports missing
lines, writes `coverage.xml`, and fails if aggregate coverage is below 80%.

Run linting and type checking separately:

```bash
python -m ruff check .
pyright
```

## API Docs

FastAPI auto-generates docs at:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
