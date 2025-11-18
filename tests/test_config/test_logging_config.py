import logging
import json
import sys
import pytest
from config import logging_config


def test_setup_logging_text_format(monkeypatch, caplog):
    # Force text format
    monkeypatch.setattr(logging_config, "LOG_FORMAT", "text")
    logger = logging_config.setup_logging("test_logger_text", level="INFO")

    with caplog.at_level(logging.INFO):
        logger.info("Hello Text")

    assert "Hello Text" in caplog.text
    assert logger.level == logging.INFO


def test_setup_logging_json_format(monkeypatch):
    # Force JSON format
    monkeypatch.setattr(logging_config, "LOG_FORMAT", "json")
    logger = logging_config.setup_logging("test_logger_json", level="DEBUG")

    # Create a record manually to test formatter output directly
    record = logging.LogRecord(
        name="test_logger_json",
        level=logging.DEBUG,
        pathname=__file__,
        lineno=10,
        msg="Hello JSON",
        args=(),
        exc_info=None,
        func=None
    )

    formatted = logger.handlers[0].formatter.format(record)
    log_data = json.loads(formatted)

    assert log_data["message"] == "Hello JSON"
    assert log_data["level"] == "DEBUG"
    assert log_data["logger"] == "test_logger_json"


def test_json_formatter_includes_exception():
    formatter = logging_config.JSONFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()  # (type, value, traceback)
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
            func=None
        )
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        assert "exception" in log_data
        assert log_data["message"] == "Error occurred"
        assert log_data["level"] == "ERROR"
