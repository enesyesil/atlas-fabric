.PHONY: setup generate run-api test test-unit test-integration evals lint mongo-up mongo-down

VENV   := .venv
PYTHON := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip
PYTEST := PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(VENV)/bin/pytest
SRC    := agents api cli evals geo knowledge storage tests

setup:
	python3.12 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	mkdir -p data
	@echo "Setup complete. Copy .env.example to .env and fill in values. CLI, API, and evals will load .env automatically."

generate:
	$(PYTHON) -m cli.main generate $(ARGS)

run-api:
	$(PYTHON) -m uvicorn api.app:create_app --factory \
		--host 0.0.0.0 --port $${PORT:-8080} --reload

test:
	$(PYTEST) tests/unit tests/integration/test_api.py -v

test-unit:
	$(PYTEST) tests/unit tests/integration/test_api.py -v

test-integration:
	$(PYTEST) tests/integration/test_pipeline.py -v

evals:
	$(PYTHON) -m evals.runner

lint:
	$(VENV)/bin/ruff check $(SRC)
	$(VENV)/bin/mypy agents api cli evals geo knowledge storage --ignore-missing-imports --no-site-packages

mongo-up:
	docker compose up -d mongo

mongo-down:
	docker compose down
