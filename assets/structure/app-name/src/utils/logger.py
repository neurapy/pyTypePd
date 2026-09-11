"""Application logging helpers."""

import logging

DEFAULT_LOG_FORMAT = "%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s | %(message)s"
DEFAULT_DATE_FORMAT = "%H:%M:%S"
DEFAULT_LOG_LEVEL = "INFO"


def configure_logging(
    *,
    level: int | str | None = DEFAULT_LOG_LEVEL,
    log_format: str = DEFAULT_LOG_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT,
    force: bool = False,
) -> None:
    logging.basicConfig(datefmt=date_format, force=force, format=log_format, level=level)


def get_logger(name: str) -> logging.Logger:
    """Return a named application logger."""
    return logging.getLogger(name)
