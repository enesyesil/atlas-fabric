.PHONY: setup generate run-api test test-unit test-integration lint mongo-up mongo-down

VENV   := .venv
PYTHON := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip

setup:
	python3.12 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	mkdir -p data
	@echo "Setup complete. Copy .env.example to .env and fill in values."

generate:
	$(PYTHON) -m cli.main generate $(ARGS)

run-api:
	$(PYTHON) -m uvicorn api.app:create_app --factory \
		--host 0.0.0.0 --port $${PORT:-8080} --reload

test:
	$(VENV)/bin/pytest tests/ -v

test-unit:
	$(VENV)/bin/pytest tests/unit/ -v

test-integration:
	$(VENV)/bin/pytest tests/integration/ -v

lint:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/mypy .

mongo-up:
	docker compose up -d mongo

mongo-down:
	docker compose down
