# AVI Project Makefile
# Comprehensive local development commands

.PHONY: help install install-dev clean format lint type-check test test-smoke test-coverage
.PHONY: run run-api run-ui run-all stop init-project init-data health-check
.PHONY: docker-build docker-up docker-down docker-logs benchmark project-tree

# Default target
.DEFAULT_GOAL := help

# Variables
PYTHON := python3
PYTEST := PYTHONPATH=src python3 -m pytest
PIP := pip
UVICORN := uvicorn
NPM := npm
DOCKER_COMPOSE := docker-compose

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

##@ Help

help: ## Display this help message
	@echo "$(GREEN)AVI Project - Available Commands$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Installation

install: install-cpu ## Install production dependencies (CPU version, default)

install-cpu: ## Install CPU-only version (~200 MB, recommended for dev)
	@echo "$(GREEN)Installing CPU-only dependencies via pyproject.toml...$(NC)"
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -e ".[vector-db,ml-cpu,monitoring]"
	@echo "$(GREEN)✓ CPU-only dependencies installed (saves 3.2 GB vs GPU!)$(NC)"
	@echo "$(BLUE)Installed: base + vector-db + ml-cpu + monitoring$(NC)"

install-gpu: ## Install GPU version (3.4 GB torch with CUDA, for production)
	@echo "$(GREEN)Installing GPU dependencies via pyproject.toml...$(NC)"
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -e ".[vector-db,ml-gpu,monitoring]"
	@echo "$(GREEN)✓ GPU dependencies installed$(NC)"
	@echo "$(BLUE)Installed: base + vector-db + ml-gpu + monitoring$(NC)"

install-dev: install ## Install development dependencies
	@echo "$(GREEN)Installing development dependencies via pyproject.toml...$(NC)"
	$(PIP) install -e ".[dev,test]"
	@echo "$(GREEN)✓ Development dependencies installed$(NC)"
	@echo "$(BLUE)Installed: base + dev + test tools$(NC)"

install-research: ## Install research and experimentation tools
	@echo "$(GREEN)Installing research dependencies via pyproject.toml...$(NC)"
	$(PIP) install -e ".[research]"
	@echo "$(GREEN)✓ Research dependencies installed (includes Jupyter, datasets, etc.)$(NC)"

install-all: ## Install all dependencies (recommended for local development)
	@echo "$(GREEN)Installing ALL dependencies via pyproject.toml...$(NC)"
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -e ".[all]"
	@echo "$(GREEN)✓ All dependencies installed$(NC)"
	@echo "$(BLUE)Installed: all optional dependencies$(NC)"

install-hooks: ## Install Git hooks (pre-commit, pre-push)
	@echo "$(GREEN)Installing Git hooks...$(NC)"
	@./scripts/install-hooks.sh
	@echo "$(GREEN)✓ Git hooks installed$(NC)"

init-project: ## Initialize project structure (directories, templates)
	@echo "$(GREEN)Initializing project structure...$(NC)"
	@mkdir -p data/raw data/processed data/indexes/qdrant data/indexes/chroma data/feedback data/mlruns data/redis logs
	@if [ ! -f data/raw/filter_rules.csv ]; then \
		echo "text,category,risk_level,threshold" > data/raw/filter_rules.csv; \
		echo "$(GREEN)✓ Created filter_rules.csv template$(NC)"; \
	fi
	@if [ ! -f data/raw/vector_documents.csv ]; then \
		echo "document_id,text,metadata" > data/raw/vector_documents.csv; \
		echo "$(GREEN)✓ Created vector_documents.csv template$(NC)"; \
	fi
	@if [ ! -f .env ]; then \
		cp .env.example .env 2>/dev/null || echo "# AVI Configuration\nVECTOR_DB_PROVIDER=memory\nDEBUG=true" > .env; \
		echo "$(GREEN)✓ Created .env file$(NC)"; \
	fi
	@echo "$(GREEN)✓ Project structure initialized$(NC)"

init-data: ## Download and setup benchmark datasets
	@echo "$(GREEN)Setting up benchmark data...$(NC)"
	PYTHONPATH=. $(PYTHON) -m avi.cli setup-data
	@echo "$(GREEN)✓ Benchmark data initialized$(NC)"

##@ Gradio Chat UI

run-ui: ## Run Gradio chat interface
	@echo "$(GREEN)Starting Gradio chat interface...$(NC)"
	@echo "$(BLUE)Chat UI will be available at:$(NC) http://localhost:7860"
	@echo "$(YELLOW)Note: Make sure API is running on port 8000$(NC)"
	$(PYTHON) gradio_ui.py

##@ Code Quality

format: ## Format code with black and isort
	@echo "$(GREEN)Formatting code...$(NC)"
	isort src tests scripts
	black src tests scripts
	@echo "$(GREEN)✓ Code formatted$(NC)"

lint: ## Run linting with ruff
	@echo "$(GREEN)Running linter...$(NC)"
	ruff check src tests scripts
	@echo "$(GREEN)✓ Linting completed$(NC)"

lint-fix: ## Run linting with auto-fix
	@echo "$(GREEN)Running linter with auto-fix...$(NC)"
	ruff check src tests scripts --fix
	@echo "$(GREEN)✓ Linting fixed$(NC)"

type-check: ## Run type checking with mypy
	@echo "$(GREEN)Running type checker...$(NC)"
	mypy --config-file pyproject.toml
	@echo "$(GREEN)✓ Type checking completed$(NC)"

##@ Testing

test: ## Run all tests
	@echo "$(GREEN)Running all tests...$(NC)"
	$(PYTEST) tests/ -v --maxfail=5
	@echo "$(GREEN)✓ All tests completed$(NC)"

test-smoke: ## Run smoke tests only
	@echo "$(GREEN)Running smoke tests...$(NC)"
	$(PYTEST) tests/ -m smoke -v
	@echo "$(GREEN)✓ Smoke tests completed$(NC)"

test-coverage: ## Run tests with coverage report
	@echo "$(GREEN)Running tests with coverage...$(NC)"
	$(PYTEST) tests/ --cov=src --cov-report=html --cov-report=term-missing
	@echo "$(GREEN)✓ Coverage report generated in htmlcov/$(NC)"

test-watch: ## Run tests in watch mode (requires pytest-watch)
	@echo "$(GREEN)Running tests in watch mode...$(NC)"
	$(PYTEST) tests/ -f

##@ Running Services

run-api: ## Run FastAPI server locally
	@echo "$(GREEN)Starting FastAPI server...$(NC)"
	PYTHONPATH=. $(UVICORN) main:app --host 0.0.0.0 --port 8000 --reload

run-safety-service: ## Run safety microservice locally
	@echo "$(GREEN)Starting safety microservice...$(NC)"
	cd safety_service && PYTHONPATH=. $(PYTHON) main.py

run-all: ## Run all services locally (requires tmux or separate terminals)
	@echo "$(YELLOW)Starting all services...$(NC)"
	@echo "$(YELLOW)Note: This requires multiple terminal windows.$(NC)"
	@echo "$(BLUE)Terminal 1:$(NC) make run-api"
	@echo "$(BLUE)Terminal 2:$(NC) make run-safety-service"
	@echo "$(BLUE)Terminal 3:$(NC) make run-ui"
	@echo "$(BLUE)Chat UI will be available at:$(NC) http://localhost:7860"

health-check: ## Check health of all services
	@echo "$(GREEN)Checking service health...$(NC)"
	@echo "$(BLUE)API Health:$(NC)"
	@curl -s http://localhost:8000/health | jq . || echo "$(RED)✗ API not responding$(NC)"
	@echo "$(BLUE)Qdrant Health:$(NC)"
	@curl -s http://localhost:6333/healthz || echo "$(RED)✗ Qdrant not responding$(NC)"
	@echo "$(BLUE)Redis Health:$(NC)"
	@redis-cli ping || echo "$(RED)✗ Redis not responding$(NC)"

##@ Docker Operations

docker-build: docker-build-cpu ## Build Docker images (CPU version, default)

docker-build-cpu: ## Build CPU-only Docker image (multi-platform: amd64, arm64)
	@echo "$(GREEN)Building CPU-only Docker image...$(NC)"
	docker build --target cpu -t avi:cpu --platform linux/amd64,linux/arm64 . || \
	docker build --target cpu -t avi:cpu .
	@echo "$(GREEN)✓ CPU Docker image built (supports Apple Silicon!)$(NC)"

docker-build-gpu: ## Build GPU Docker image (linux/amd64 only)
	@echo "$(GREEN)Building GPU Docker image...$(NC)"
	docker build --target gpu -t avi:gpu --platform linux/amd64 .
	@echo "$(GREEN)✓ GPU Docker image built$(NC)"

docker-up: ## Start all services with Docker Compose
	@echo "$(GREEN)Starting Docker services...$(NC)"
	$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "$(BLUE)API:$(NC) http://localhost:8000"
	@echo "$(BLUE)Grafana:$(NC) http://localhost:3000"
	@echo "$(BLUE)Prometheus:$(NC) http://localhost:9090"
	@echo "$(BLUE)Jaeger:$(NC) http://localhost:16686"
	@echo "$(BLUE)MLflow:$(NC) http://localhost:5000"

docker-down: ## Stop all Docker services
	@echo "$(GREEN)Stopping Docker services...$(NC)"
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)✓ Services stopped$(NC)"

docker-logs: ## Show Docker logs (tail)
	@echo "$(GREEN)Showing Docker logs...$(NC)"
	$(DOCKER_COMPOSE) logs -f --tail=100

docker-clean: ## Remove Docker containers and volumes
	@echo "$(YELLOW)Removing Docker containers and volumes...$(NC)"
	$(DOCKER_COMPOSE) down -v
	@echo "$(GREEN)✓ Docker cleaned$(NC)"

##@ Benchmarking

benchmark: ## Run indexing performance benchmark
	@echo "$(GREEN)Running indexing benchmark...$(NC)"
	PYTHONPATH=. $(PYTHON) scripts/benchmark_indexing.py

setup-data: ## Download and setup benchmark datasets from HuggingFace
	@echo "$(GREEN)Setting up benchmark data...$(NC)"
	PYTHONPATH=. $(PYTHON) scripts/setup_data.py
	@echo "$(GREEN)✓ Benchmark data initialized$(NC)"

##@ Database Operations

index-data: ## Index data into vector database
	@echo "$(GREEN)Indexing data...$(NC)"
	PYTHONPATH=. $(PYTHON) -m avi.cli index-data
	@echo "$(GREEN)✓ Data indexed$(NC)"

reset-db: ## Reset vector database (WARNING: deletes all data)
	@echo "$(RED)WARNING: This will delete all vector database data!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf data/indexes/qdrant/* data/indexes/chroma/*; \
		echo "$(GREEN)✓ Database reset$(NC)"; \
	else \
		echo "$(YELLOW)Cancelled$(NC)"; \
	fi

##@ Maintenance

clean: ## Clean up generated files
	@echo "$(GREEN)Cleaning up...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage 2>/dev/null || true
	rm -rf dist/ build/ 2>/dev/null || true
	rm -rf __pycache__/ 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup completed$(NC)"

clean-logs: ## Clean up log files
	@echo "$(GREEN)Cleaning logs...$(NC)"
	rm -rf logs/*.log
	@echo "$(GREEN)✓ Logs cleaned$(NC)"

project-tree: ## Generate project tree documentation
	@echo "$(GREEN)Generating project tree...$(NC)"
	$(PYTHON) scripts/project_tree.py --root . --output tree.txt
	@echo "$(GREEN)✓ Project tree generated: tree.txt$(NC)"

##@ Quick Start

quickstart: install-dev init-project test-smoke ## Quick start: install, initialize, and test
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════$(NC)"
	@echo "$(GREEN)✓ Quick start completed!$(NC)"
	@echo "$(GREEN)═══════════════════════════════════════$(NC)"
	@echo ""
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Configure .env file with your API keys"
	@echo "  2. Run: $(BLUE)make run-api$(NC) to start the API"
	@echo "  3. Run: $(BLUE)make run-ui$(NC) in a separate terminal for chat interface"
	@echo ""

dev-setup: install-dev init-project init-data ## Complete development setup
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════$(NC)"
	@echo "$(GREEN)✓ Development environment ready!$(NC)"
	@echo "$(GREEN)═══════════════════════════════════════$(NC)"
	@echo ""

##@ Validation Pipeline

validate: ## Run full validation pipeline (API, code quality, Docker)
	@echo "$(GREEN)Running validation pipeline...$(NC)"
	$(PYTHON) validate.py
	@echo "$(GREEN)✓ Validation completed$(NC)"

validate-api: ## Validate API consistency between backend and frontend
	@echo "$(GREEN)Validating API consistency...$(NC)"
	$(PYTHON) validate.py --only api
	@echo "$(GREEN)✓ API validation completed$(NC)"

validate-code: ## Validate code quality and duplicates
	@echo "$(GREEN)Validating code quality...$(NC)"
	$(PYTHON) validate.py --only code
	@echo "$(GREEN)✓ Code validation completed$(NC)"

validate-docker: ## Validate Docker configuration
	@echo "$(GREEN)Validating Docker configuration...$(NC)"
	$(PYTHON) validate.py --only docker
	@echo "$(GREEN)✓ Docker validation completed$(NC)"

validate-ci: ## Run validation for CI/CD (JSON output only)
	@echo "$(GREEN)Running validation for CI/CD...$(NC)"
	$(PYTHON) validate.py --format json
	@echo "$(GREEN)✓ Validation completed - check validation_pipeline/reports/output/$(NC)"

validate-report: ## Generate validation reports (all formats)
	@echo "$(GREEN)Generating validation reports...$(NC)"
	$(PYTHON) validate.py --format console json markdown
	@echo "$(GREEN)✓ Reports generated in validation_pipeline/reports/output/$(NC)"
	@echo "$(BLUE)View reports:$(NC)"
	@echo "  - JSON: validation_pipeline/reports/output/validation_report.json"
	@echo "  - Markdown: validation_pipeline/reports/output/validation_report.md"

##@ Git Operations

git-status: ## Show git status with helpful info
	@echo "$(GREEN)Git Status:$(NC)"
	@git status
	@echo ""
	@echo "$(BLUE)Current branch:$(NC) $$(git branch --show-current)"
	@echo "$(BLUE)Recent commits:$(NC)"
	@git log --oneline -5

git-branches: ## List all git branches
	@echo "$(GREEN)Git Branches:$(NC)"
	@git branch -a

##@ Phase Management

phase-1-start: ## Start Phase 1 (Critical fixes)
	@echo "$(GREEN)Starting Phase 1: Critical Fixes$(NC)"
	@git checkout -b phase-1/critical-fixes 2>/dev/null || git checkout phase-1/critical-fixes
	@echo "$(GREEN)✓ Switched to phase-1/critical-fixes branch$(NC)"

phase-2-start: ## Start Phase 2 (Important fixes)
	@echo "$(GREEN)Starting Phase 2: Important Fixes$(NC)"
	@git checkout -b phase-2/important-fixes 2>/dev/null || git checkout phase-2/important-fixes
	@echo "$(GREEN)✓ Switched to phase-2/important-fixes branch$(NC)"

phase-3-start: ## Start Phase 3 (Enhancements)
	@echo "$(GREEN)Starting Phase 3: Enhancements$(NC)"
	@git checkout -b phase-3/enhancements 2>/dev/null || git checkout phase-3/enhancements
	@echo "$(GREEN)✓ Switched to phase-3/enhancements branch$(NC)"
