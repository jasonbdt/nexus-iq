import logging
import sys


def configure_logging(level: int = logging.NOTSET) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout
    )
    logger = get_logger(__name__)
    logger.info("Application Logger initialized")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
