# Calculator API

A compact FastAPI service for direct arithmetic and SQLite-backed calculation history. The
service runs on CPython 3.12 and uses the calculator functions in this repository's `core.py`.

## Setup

Install CPython 3.12.16, then create a repository-local virtual environment and install the
application with its development tools:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

## Configuration

The service reads two optional environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `sqlite:///calculator.db` | SQLModel database URL used for calculation history |
| `PORT` | `8000` | TCP port used by Uvicorn |

For example, run on port 8080 with a database under `data/`:

```bash
DATABASE_URL=sqlite:///data/calculator.db PORT=8080 python server.py
```

## Run

Start the service directly:

```bash
python server.py
```

Or use the installed console command:

```bash
calculator-api
```

The server listens on `0.0.0.0:8000` by default and is available locally at
`http://localhost:8000`.

## Verify

Run the foundation quality checks from the repository root:

```bash
ruff check .
pyright
```

## Endpoints

### Calculator Operations

All calculator endpoints accept POST with JSON body `{"a": <number>, "b": <number>}`.

| Endpoint | Description |
|----------|-------------|
| `/add` | Add two numbers |
| `/subtract` | Subtract b from a |
| `/multiply` | Multiply two numbers |
| `/divide` | Divide a by b |

### Calculation History (CRUD)

Store calculations in the configured SQLite database. Accepted operation identifiers for
`POST /calculations` are exactly `add`, `sub`, `mul`, and `div`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/calculations` | Create & store a calculation |
| GET | `/calculations` | List all stored calculations |
| GET | `/calculations/{id}` | Get a specific calculation |
| DELETE | `/calculations/{id}` | Delete a calculation |

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

New timestamps are recorded in UTC and serialized with an explicit UTC offset.

Response: `{"operation": "mul", "a": 7.0, "b": 6.0, "result": 42.0, "id": 1, "created_at": "2026-11-03T21:00:00Z"}`

**List all saved calculations:**

```bash
curl http://localhost:8000/calculations
```

**Delete a calculation:**

```bash
curl -X DELETE http://localhost:8000/calculations/1
```

## API Docs

FastAPI auto-generates docs at:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Changes

NOP

## Changes

NOP
NOP2
