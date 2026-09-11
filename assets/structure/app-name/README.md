# __project_name__

A typed Python application, managed with [uv](https://docs.astral.sh/uv/).

## Get started

Make sure `uv` and `make` are installed. Then:

```sh
make install
make check
```

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
