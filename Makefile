.PHONY: up down build logs migrate revision test lint

# ── Docker ────────────────────────────────────────────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f api

shell:
	docker compose exec api bash

# ── Database ──────────────────────────────────────────────────────────────────
migrate:
	docker compose exec api alembic upgrade head

downgrade:
	docker compose exec api alembic downgrade -1

# m="describe change"
revision:
	docker compose exec api alembic revision --autogenerate -m "$(m)"

# ── Local dev (no Docker) ─────────────────────────────────────────────────────
install:
	pip install -r requirements.txt

run-local:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate-local:
	alembic upgrade head

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	pytest -v

test-unit:
	pytest tests/unit -v

test-integration:
	pytest tests/integration -v

# ── Lint ──────────────────────────────────────────────────────────────────────
lint:
	ruff check app tests
	mypy app
