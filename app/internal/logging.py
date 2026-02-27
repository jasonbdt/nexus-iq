"""Logging configuration and logger factory."""

import logging
import sys


def configure_logging(level: int = logging.NOTSET) -> None:
    """Configure the root logger with a standard format and the given level."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout
    )
    logger = get_logger(__name__)
    logger.debug("Application Logger initialized")


def get_logger(name: str) -> logging.Logger:
    """Return a named logger instance."""
    return logging.getLogger(name)
