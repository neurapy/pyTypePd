"""Strict package-name package."""

import logging

logging.getLogger(__name__).addHandler(logging.NullHandler())


def hello() -> str:
    """Return a sample greeting."""
    return "Hello from package-name!"


__all__ = ["hello"]
