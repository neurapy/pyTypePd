"""Python Projects, made fun again."""

from utils.logger import configure_logging, get_logger

LOGGER = get_logger("main.py")


def greeting() -> str:
    """Return the default app greeting."""
    return "Hello from app-name!"


def main() -> None:
    """Run the application."""
    configure_logging()
    LOGGER.info(greeting())


if __name__ == "__main__":
    main()
