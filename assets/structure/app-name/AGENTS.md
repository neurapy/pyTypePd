# Project guidelines

- Keep code short, clean, and easy to read. Prefer small functions and
  straightforward solutions over unnecessary abstractions.
- Follow the existing structure and conventions. Keep changes focused on the task.
- Use accurate type annotations and keep strict typing checks enabled.
- Before adding `# type: ignore`, `# pyright: ignore`, or disabling typing rules,
  check whether a maintained type-stub package or suitable `.pyi` stubs would
  solve the problem. Prefer proper types and stubs. If an ignore is unavoidable,
  limit its scope and explain why.
- Manage dependencies with `uv`. Add type stubs and development tools with
  `uv add --dev`.
- After code changes, run `make check`. Add or update focused tests when behavior
  changes.
