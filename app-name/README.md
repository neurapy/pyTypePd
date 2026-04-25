# app-name

Simple uv-managed application boilerplate.

## Requirements

- `git`
- `make`
- `uv`

## Setup

```bash
git init
make install
make check
```

## Run

```bash
make run
```

This runs `uv run src/main.py`.

## Workflow

```bash
make install    # Install dependencies and pre-commit hooks
make sync       # Install project and developer dependencies
make run        # Run the app
make format     # Format Python files with Ruff and pyproject.toml with Taplo
make lint       # Lint Python files with Ruff
make typecheck  # Run Pyright in strict mode
make test       # Run pytest
make check      # Run format check, lint, typecheck, and tests
```

## Structure

- `src/main.py` is the application entrypoint.
- `src/utils/logger.py` contains the shared app logger setup.
- `tests/` contains pytest tests.
- `pyproject.toml` manages dependencies and tool configuration.

This template is a uv virtual project, so it does not build or install itself as
a package.
