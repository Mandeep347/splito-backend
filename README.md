# Splito — Backend

Expense-splitting backend built with **FastAPI + PostgreSQL + SQLAlchemy + Alembic**.

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI (async) |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Auth | JWT (access + refresh tokens) |
| Containers | Docker Compose |

## Quick Start

```bash
# 1. Clone and copy env
cp .env.example .env          # edit secrets as needed

# 2. Start services
make up

# 3. Run migrations
make migrate

# 4. Open Swagger UI
open http://localhost:8000/api/v1/docs
```

## Project Structure

```
app/
├── api/v1/endpoints/     # HTTP layer — thin controllers only
├── core/                 # config, security, exceptions
├── db/                   # engine, session, base mixins, model registry
├── domain/               # SQLAlchemy models by bounded context
│   ├── user/
│   ├── group/
│   ├── expense/
│   ├── settlement/
│   └── balance/
├── middleware/           # auth dependency, exception handlers
├── schemas/              # Pydantic request/response DTOs
├── services/             # application services (business logic)
└── main.py               # app factory
alembic/                  # migrations
tests/
├── unit/                 # pure logic tests (no DB)
└── integration/          # endpoint tests (in-memory SQLite)
```

## Development Commands

```bash
make test              # run all tests
make test-unit         # unit tests only
make test-integration  # integration tests only
make migrate           # run pending migrations
make revision m="add column"   # autogenerate migration
make logs              # tail API logs
```

## Auth Flow

```
POST /api/v1/auth/register   → 201 {id, name, email, ...}
POST /api/v1/auth/login      → 200 {access_token, refresh_token}
POST /api/v1/auth/refresh    → 200 {access_token, refresh_token}
GET  /api/v1/users/me        → 200 {id, name, email, ...}  [Bearer required]
PATCH /api/v1/users/me       → 200 {updated user}           [Bearer required]
```

## Error Contract

All errors follow the standard format:

```json
{
  "timestamp": "2026-05-20T10:00:00Z",
  "status": 422,
  "error": "INVALID_SPLIT_TOTAL",
  "message": "Sum of participant amounts must equal expense total",
  "path": "/api/v1/groups/1/expenses",
  "trace_id": "uuid"
}
```

## Phase Roadmap

- [x] **Phase 1** — Foundation (FastAPI, PostgreSQL, Alembic, Docker, Auth)
- [ ] **Phase 2** — Groups, Expenses, Splits, Balances, Settlements
- [ ] **Phase 3** — Debt simplification, notifications, activity feed
- [ ] **Phase 4** — Redis caching, event-driven design
