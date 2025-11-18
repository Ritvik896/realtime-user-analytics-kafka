# tests/test_config/test_constants.py
import os
import importlib
import pytest

@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    """Ensure environment variables are cleared before each test."""
    keys = [
        "KAFKA_BOOTSTRAP_SERVERS", "KAFKA_TOPIC_EVENTS", "DB_HOST",
        "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_POOL_SIZE",
        "API_HOST", "API_PORT", "API_DEBUG", "LOG_LEVEL", "LOG_FORMAT",
        "PRODUCER_BATCH_SIZE", "PRODUCER_RATE_PER_SECOND",
        "CONSUMER_BATCH_SIZE", "CONSUMER_TIMEOUT_MS",
        "ML_ANOMALY_THRESHOLD", "ML_MODEL_UPDATE_INTERVAL",
        "AWS_REGION", "AWS_MSK_CLUSTER_ARN"
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)
    yield

def reload_constants():
    """Reload constants module to apply env changes."""
    return importlib.reload(importlib.import_module("config.constants"))

def test_default_kafka_values():
    constants = reload_constants()
    assert constants.KAFKA_BOOTSTRAP_SERVERS == "localhost:9092"
    assert constants.KAFKA_TOPIC_EVENTS == "user-events"

def test_override_kafka_values(monkeypatch):
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    monkeypatch.setenv("KAFKA_TOPIC_EVENTS", "custom-events")
    constants = reload_constants()
    assert constants.KAFKA_BOOTSTRAP_SERVERS == "kafka:29092"
    assert constants.KAFKA_TOPIC_EVENTS == "custom-events"

def test_database_url_default():
    constants = reload_constants()
    assert constants.DATABASE_URL == (
        "postgresql://analytics_user:analytics_pass@localhost:5432/user_analytics"
    )

def test_database_url_override(monkeypatch):
    monkeypatch.setenv("DB_USER", "test_user")
    monkeypatch.setenv("DB_PASSWORD", "test_pass")
    monkeypatch.setenv("DB_HOST", "db.example.com")
    monkeypatch.setenv("DB_PORT", "6543")
    monkeypatch.setenv("DB_NAME", "test_db")
    constants = reload_constants()
    assert constants.DATABASE_URL == (
        "postgresql://test_user:test_pass@db.example.com:6543/test_db"
    )

def test_api_debug_true(monkeypatch):
    monkeypatch.setenv("API_DEBUG", "True")
    constants = reload_constants()
    assert constants.API_DEBUG is True

def test_api_debug_false(monkeypatch):
    monkeypatch.setenv("API_DEBUG", "False")
    constants = reload_constants()
    assert constants.API_DEBUG is False

def test_ml_threshold(monkeypatch):
    monkeypatch.setenv("ML_ANOMALY_THRESHOLD", "0.9")
    constants = reload_constants()
    assert constants.ML_ANOMALY_THRESHOLD == 0.9
