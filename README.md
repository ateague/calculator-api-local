# Calculator API

A very simple REST API server that reuses functionality from `calculator-cli`.

## Setup

```bash
pip install -e .
```

## Run

```bash
python server.py
```

Or after installing:

```bash
calculator-api
```

The server runs on `http://localhost:8000`.

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

Store calculations in a SQLite database.

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

Response: `{"operation": "mul", "a": 7.0, "b": 6.0, "result": 42.0, "id": 1, "created_at": "..."}`

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
