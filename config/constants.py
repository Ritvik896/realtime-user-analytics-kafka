"""
Project-wide constants and configuration values.
"""

import os
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_EVENTS = os.getenv("KAFKA_TOPIC_EVENTS", "user-events")
KAFKA_TOPIC_ANALYTICS = os.getenv("KAFKA_TOPIC_ANALYTICS", "user-analytics")
KAFKA_TOPIC_ANOMALIES = os.getenv("KAFKA_TOPIC_ANOMALIES", "user-anomalies")
KAFKA_CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "user-analytics-group")

# Database Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "user_analytics")
DB_USER = os.getenv("DB_USER", "analytics_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "analytics_pass")
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))

# Database URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# API Configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_DEBUG = os.getenv("API_DEBUG", "True").lower() == "true"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # or "text"

# Producer Configuration
PRODUCER_BATCH_SIZE = int(os.getenv("PRODUCER_BATCH_SIZE", "100"))
PRODUCER_RATE_PER_SECOND = float(os.getenv("PRODUCER_RATE_PER_SECOND", "10"))

# Consumer Configuration
CONSUMER_BATCH_SIZE = int(os.getenv("CONSUMER_BATCH_SIZE", "100"))
CONSUMER_TIMEOUT_MS = int(os.getenv("CONSUMER_TIMEOUT_MS", "10000"))

# ML Configuration (Phase 5)
ML_ANOMALY_THRESHOLD = float(os.getenv("ML_ANOMALY_THRESHOLD", "0.7"))
ML_MODEL_UPDATE_INTERVAL = int(os.getenv("ML_MODEL_UPDATE_INTERVAL", "3600"))

# AWS Configuration (Future)
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_MSK_CLUSTER_ARN = os.getenv("AWS_MSK_CLUSTER_ARN", "")