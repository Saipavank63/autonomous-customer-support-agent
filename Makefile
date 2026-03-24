# =============================================================================
# Autonomous Customer Support Agent — Makefile
# =============================================================================
# Common commands for development, testing, and deployment.
# Run `make help` to see all available targets.
# =============================================================================

.DEFAULT_GOAL := help
.PHONY: help install run dev test lint format typecheck docker-up docker-down docker-logs db-up db-reset clean

PYTHON   ?= python3
APP_HOST ?= 0.0.0.0
APP_PORT ?= 8000

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
install: ## Install Python dependencies into the active virtualenv
	pip install --upgrade pip
	pip install -r requirements.txt

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
run: ## Start the FastAPI server (production-like, no reload)
	uvicorn src.api.main:app --host $(APP_HOST) --port $(APP_PORT)

dev: ## Start the FastAPI server with hot-reload for development
	uvicorn src.api.main:app --host $(APP_HOST) --port $(APP_PORT) --reload

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------
test: ## Run the test suite with pytest
	pytest tests/ -v --tb=short

test-cov: ## Run tests with coverage report
	pytest tests/ -v --tb=short --cov=src --cov-report=term-missing

lint: ## Run ruff linter on the source tree
	ruff check src/ tests/

format: ## Auto-format code with ruff
	ruff format src/ tests/

typecheck: ## Run mypy static type checking
	mypy src/ --ignore-missing-imports

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------
docker-up: ## Build and start all services (app + Postgres) via Docker Compose
	docker compose up --build -d

docker-down: ## Stop and remove all Docker Compose services
	docker compose down

docker-logs: ## Tail logs for all Docker Compose services
	docker compose logs -f

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
db-up: ## Start only the Postgres container
	docker compose up postgres -d

db-reset: ## Drop and recreate all tables (development only!)
	@echo "WARNING: This will destroy all data in the local database."
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	$(PYTHON) -c "from src.db.connection import engine; from src.db.models import Base; \
		import asyncio; \
		async def reset(): \
			async with engine.begin() as c: \
				await c.run_sync(Base.metadata.drop_all); \
				await c.run_sync(Base.metadata.create_all); \
			print('Database reset complete.'); \
		asyncio.run(reset())"

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
clean: ## Remove caches, bytecode, and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .coverage htmlcov/
