# __project_name__

A typed Python application, managed with [uv](https://docs.astral.sh/uv/).

## Get started

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and `make`, then:

```sh
make install
make check
make run
```

`uv` downloads Python **__python_version__** if needed and creates `.venv` with the
project and developer tools. `.python-version` selects Python __python_version__,
and `pyproject.toml` allows any __python_version__.x patch release. Ruff and Pyright
target Python __python_minor__.

To enable pre-commit hooks, run `git init` followed by `make install`.
Commit the generated `uv.lock` to keep dependency versions reproducible.

## Develop

```sh
make sync       # Install project and developer dependencies
make run        # Run the application
make format     # Format Python and TOML
make lint       # Lint with Ruff
make typecheck  # Check types with Pyright in strict mode
make test       # Run pytest
make check      # Check formatting, lint, types, and tests
make build      # Build a wheel and source distribution in dist/
```

Add dependencies with `uv add <package>` or `uv add --dev <package>`.
You can also run the app with `uv run __project_name__` or
`uv run python -m __package_name__`.

## Structure

```text
src/__package_name__/
  __init__.py       Package
  __main__.py       python -m entry point
  main.py           Application and greeting example
  py.typed          Type information marker
  utils/logger.py   Shared logging setup
tests/
  test_main.py      Example tests
```

Tool settings live in `pyproject.toml`, `.taplo.toml`, and `.pre-commit-config.yaml`.

## License

__license_readme__
