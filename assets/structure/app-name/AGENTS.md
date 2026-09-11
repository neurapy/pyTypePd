# Project guidelines

- Keep code short, clean, and easy to read. Prefer small functions and
  straightforward solutions over unnecessary abstractions.
- Follow the existing structure and conventions. Keep changes focused on the task.
- Consider changes to be breaking changes. The goal is to get to a maximally
  clean code state. When depreciating/changing a feature, there is no need for
  legacy support unless explicitly requested.
- Use accurate type annotations and keep strict typing checks enabled.
- Before adding `# type: ignore`, `# pyright: ignore`, or disabling typing rules,
  check whether a maintained type-stub package or suitable `.pyi` stubs would
  solve the problem. Prefer proper types and stubs. If an ignore is unavoidable,
  limit its scope.
- Write tests only for cases, that are necessary to test. No redundant tests.
