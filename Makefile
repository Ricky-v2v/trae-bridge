.PHONY: help install dev test test-all clean run client inspect format lint

# Default target
help:
	@echo "Trae Bridge - Available Commands:"
	@echo ""
	@echo "  make install     - Install package and dependencies"
	@echo "  make dev         - Install with development dependencies"
	@echo "  make test        - Run integration and system tests"
	@echo "  make test-all    - Run all tests (requires Trae running)"
	@echo "  make run         - Start the API server"
	@echo "  make client      - Run interactive client"
	@echo "  make inspect     - Run DOM inspector (requires Trae)"
	@echo "  make format      - Format code with black"
	@echo "  make lint        - Lint code with ruff"
	@echo "  make clean       - Remove cached files"
	@echo ""

# Installation
install:
	pip install -e .

dev:
	pip install -e ".[dev]"

# Testing
test:
	@echo "Running integration and system tests..."
	python scripts/test_integration.py
	python scripts/test_system.py

test-all:
	@echo "Running all tests (requires Trae with CDP)..."
	bash scripts/test_all.sh

# Running the application
run:
	python scripts/bridge.py

client:
	python scripts/client.py interactive

inspect:
	python scripts/inspect_dom.py

# Code quality
format:
	@echo "Formatting code..."
	black src/ scripts/ --line-length 100

lint:
	@echo "Linting code..."
	ruff check src/ scripts/

# Cleanup
clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
	rm -rf logs/*.log 2>/dev/null || true
	@echo "Clean complete"
