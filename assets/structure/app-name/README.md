# __project_name__

A typed Python application, managed with [uv](https://docs.astral.sh/uv/).

## Get started

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and `make`, then:

```sh
git init
make install
make check
# make necessary initial changes
git add . && git commit -m "Initial Commit"
```

`uv` downloads Python `__python_version__` if needed and creates `.venv` with the
project and developer tools. `.python-version` selects Python __python_version__,
and `pyproject.toml` allows any __python_version__.x patch release. Ruff and Pyright
target Python __python_minor__.

`make install` enables pre-commit hooks when Git is initialized. Include the
generated `uv.lock` in the initial commit to keep dependency versions reproducible.

## Develop

```sh
make install    # Install project, developer dependencies, and Git hooks
make format     # Format Python and TOML
make lint       # Lint with Ruff
make typecheck  # Check types with Pyright in strict mode
make test       # Run pytest
make check      # Check formatting, lint, types, and tests
make build      # Build a wheel and source distribution in dist/
```

Add dependencies with `uv add <package>` or `uv add --dev <package>`.
Run the installed app with `uv run __project_name__` or
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
