"""
Logging configuration for structured logging.
"""

import logging
import json
from config.constants import LOG_LEVEL, LOG_FORMAT


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(name: str, level: str = LOG_LEVEL) -> logging.Logger:
    """
    Setup logger with appropriate formatter.

    Args:
        name: Logger name (usually __name__)
        level: Log level (INFO, DEBUG, ERROR, etc.)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))

    if not logger.handlers:
        handler = logging.StreamHandler()

        if LOG_FORMAT == "json":
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger