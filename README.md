# Python Project Boilerplates

Working on big python projects can be painful.
Python is awesome but the typing system sometimes makes me wish I would be
writing in  Rust or Typescript.
With this the experience might be even better :)

> I just created this and im sure I will find a lot of improvements/changes once
I start using it.

## Requirements

You only need pre installed:

- `git`
- `make`
- `uv`

## The Idea

`uv` is used to manage everything it can handle the entire build environment.

It uses `Ruff`, `Taplo`, `Pyright`, `Pytest` and `pre-commit` for a nice and
consistent experience.

To speed up and simplify dev workflows there is a Makefile.
(I don't know if this is Haram in Python but its much nicer)

## Setup a new Repo

```bash
# 1. Copy either the App or Package Boilerplate
# 2. Change Project Metadata (and Python version if needed to regress) in pyproject.toml
# 3. Change the Folder Names to your Project Name
git init
make install
make check
```

I would recommend you to then pin a python version with
something like `uv pin python 3.14`

## Workflow

Shared targets:

```bash
make install    # Install dependencies and pre-commit hooks
make format     # Format Python files with Ruff and pyproject.toml with Taplo
make lint       # Lint Python files with Ruff
make typecheck  # Run Pyright in strict mode
make test       # Run pytest
make check      # Run format check, lint, typecheck, and tests
```

App-only target:

```bash
make run        # Run the app template
```

Package-only target:

```bash
make build      # Build the package template with uv_build
```

## Virtualenv

`uv` manages the project virtualenv at `.venv/`. Prefer `uv run ...` or the
Make targets for repeatable commands:

Activation is optional for interactive shell work:

```bash
# To activate
source .venv/bin/activate 
# To deactivate
deactivate
```

---

That's it. Now some additional advice to package/ and app/

## Package

Use when you want to be able to import it.

### Examples

When using the package structure use `examples/` for runnable experiments
that import the package like a user would.
Here for example print() is allowed because quick tests wouldn't require a logger

### Typing

The package includes `py.typed`, so downstream users and type checkers can
treat it as a typed package. Pyright runs in strict mode over both `src` and
`tests`.

## App

Use for normal projects. The app template is a uv virtual project with
`src/main.py` as its entrypoint, so it can be run with `make run` and does not
define a package build. App helpers live under `src/`, including the default
logger setup in `src/utils/logger.py`.
