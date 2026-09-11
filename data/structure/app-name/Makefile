.DEFAULT_GOAL := help

UV ?= uv
TAPLO ?= RUST_LOG=error $(UV) run taplo

.PHONY: help install run format lint typecheck test check clean

help:
	@printf '%s\n' \
		'Available targets:' \
		'  install    Install dependencies and git hooks' \
		'  run        Run the app' \
		'  format     Format Python and TOML files' \
		'  lint       Lint Python files with Ruff' \
		'  typecheck  Run Pyright in strict mode' \
		'  test       Run pytest' \
		'  check      Run all verification commands' \
		'  clean      Remove local build and tool artifacts'

install: 
	$(UV) sync --all-groups
	$(UV) run pre-commit install


run:
	$(UV) run src/main.py

format:
	$(UV) run ruff format .
	$(UV) run taplo fmt pyproject.toml

lint:
	$(UV) run ruff check .

typecheck:
	$(UV) run pyright

test:
	$(UV) run pytest

check:
	$(UV) run ruff format --check .
	$(UV) run taplo fmt --check pyproject.toml
	$(UV) run ruff check .
	$(UV) run pyright
	$(UV) run pytest

clean:
	rm -rf .coverage .coverage.* .mypy_cache .pytest_cache .pyright .ruff_cache build coverage.xml dist htmlcov wheels
	find . \
		-path ./.git -prune -o \
		-path ./.venv -prune -o \
		-type d -name __pycache__ -prune -exec rm -rf {} +
