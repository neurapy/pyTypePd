"""Python Projects, made fun again."""

from __package_name__.utils import logger

LOGGER = logger.get_logger(__name__)


def greeting() -> str:
    """Return the default app greeting."""
    return "Hello from __project_name__!"


def main() -> None:
    """Run the application."""
    logger.configure_logging()
    LOGGER.info(greeting())


if __name__ == "__main__":
    main()
