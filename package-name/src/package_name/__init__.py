"""Strict package-name package."""

import logging

from package_name.utils.logger import configure_logging

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())
configure_logging()


def hello() -> str:
    """Return a sample greeting."""
    LOGGER.info("Now returning hello...")
    return "Hello from package-name!"


__all__ = ["hello"]
