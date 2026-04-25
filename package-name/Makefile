.DEFAULT_GOAL := help

UV ?= uv
TAPLO ?= RUST_LOG=error $(UV) run taplo

.PHONY: help install format lint typecheck test check build clean

help:
	@printf '%s\n' \
		'Available targets:' \
		'  install    Install dependencies and git hooks' \
		'  format     Format Python and TOML files' \
		'  lint       Lint Python files with Ruff' \
		'  typecheck  Run Pyright in strict mode' \
		'  test       Run pytest' \
		'  check      Run all verification commands' \
		'  build      Build the package' \
		'  clean      Remove local build and tool artifacts'

install:
	$(UV) sync --all-groups
	$(UV) run pre-commit install


format:
	$(UV) run ruff format .
	$(TAPLO) fmt pyproject.toml

lint:
	$(UV) run ruff check .

typecheck:
	$(UV) run pyright

test:
	$(UV) run pytest

check:
	$(UV) run ruff format --check .
	$(TAPLO) fmt --check pyproject.toml
	$(UV) run ruff check .
	$(UV) run pyright
	$(UV) run pytest

build:
	$(UV) build --no-sources

clean:
	rm -rf .coverage .coverage.* .mypy_cache .pytest_cache .pyright .ruff_cache build coverage.xml dist htmlcov wheels
	find . \
		-path ./.git -prune -o \
		-path ./.venv -prune -o \
		-type d -name __pycache__ -prune -exec rm -rf {} +
