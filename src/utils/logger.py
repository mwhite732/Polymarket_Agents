"""Logging configuration and utilities."""

import sys
from typing import Optional

from loguru import logger

from ..config import get_settings


def setup_logger(log_level: Optional[str] = None) -> logger:
    """
    Configure application logger.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    settings = get_settings()
    level = log_level or settings.log_level

    # Remove default handler
    logger.remove()

    # Add custom handler with formatting
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=level,
        colorize=True
    )

    # Add file handler for errors
    logger.add(
        "logs/errors.log",
        level="ERROR",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )

    # Add file handler for all logs
    logger.add(
        "logs/app.log",
        level="INFO",
        rotation="50 MB",
        retention="7 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )

    return logger


def get_logger(name: Optional[str] = None) -> logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    if name:
        return logger.bind(name=name)
    return logger
