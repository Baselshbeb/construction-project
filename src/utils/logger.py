"""
Logging setup using loguru.

Coach Simple explains:
    "Logs are like a diary for the program. Every time something happens
    (file opened, calculation done, error found), we write it down.
    This helps us understand what happened and debug problems."

Usage:
    from src.utils.logger import get_logger
    logger = get_logger("my_module")
    logger.info("Something happened")
"""

from __future__ import annotations

import sys

from loguru import logger


def setup_logger(level: str = "INFO") -> None:
    """Configure the global logger."""
    logger.remove()  # Remove default handler
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )
    logger.add(
        "logs/metraj.log",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name} | {message}",
    )


def get_logger(name: str) -> logger.__class__:
    """Get a named logger instance."""
    return logger.bind(name=name)


# Set up on import
setup_logger()
