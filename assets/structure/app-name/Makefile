.DEFAULT_GOAL := help

UV ?= uv
TAPLO ?= RUST_LOG=error $(UV) run taplo

.PHONY: help install format lint typecheck test check build clean

help:
	@printf '%s\n' \
		'Available targets:' \
		'  install    Install dependencies and hooks if Git is initialized' \
		'  format     Format Python and TOML files' \
		'  lint       Lint Python files with Ruff' \
		'  typecheck  Run Pyright in strict mode' \
		'  test       Run pytest' \
		'  check      Run all verification commands' \
		'  build      Build a wheel and source distribution' \
		'  clean      Remove local build and tool artifacts'

install:
	$(UV) sync --all-groups
	@if [ -e .git ]; then \
		$(UV) run pre-commit install; \
	else \
		printf '%s\n' 'Dependencies ready. To enable commit hooks: git init && make install'; \
	fi

format:
	$(UV) run ruff format .
	$(TAPLO) fmt

lint:
	$(UV) run ruff check .

typecheck:
	$(UV) run pyright

test:
	$(UV) run pytest

check:
	$(UV) run ruff format --check .
	$(TAPLO) fmt --check
	$(UV) run ruff check .
	$(UV) run pyright
	$(UV) run pytest

build:
	$(UV) build

clean:
	rm -rf .coverage .coverage.* .mypy_cache .pytest_cache .pyright .ruff_cache build coverage.xml dist htmlcov wheels
	find . \
		-path ./.git -prune -o \
		-path ./.venv -prune -o \
		-type d -name __pycache__ -prune -exec rm -rf {} +
