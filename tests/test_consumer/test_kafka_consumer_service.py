"""
Unit tests for KafkaConsumerService (src/consumer/kafka_consumer_service.py)

These tests use unittest.mock to simulate Kafka Consumer behavior.
Run with: pytest tests/test_consumer/test_kafka_consumer_service.py -v
"""

import pytest
import json
from unittest.mock import MagicMock, patch
from confluent_kafka import KafkaError
from src.consumer.kafka_consumer_service import KafkaConsumerService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_consumer():
    """Return a mocked Kafka Consumer object."""
    return MagicMock()


@pytest.fixture
def service(mock_consumer):
    """Return a KafkaConsumerService with mocked consumer injected."""
    svc = KafkaConsumerService()
    svc.consumer = mock_consumer
    svc.is_connected = True
    return svc


# ============================================================================
# Tests: Connection
# ============================================================================


def test_connect_success(monkeypatch):
    fake_consumer = MagicMock()
    # Patch the Consumer constructor inside kafka_consumer_service
    monkeypatch.setattr("src.consumer.kafka_consumer_service.Consumer", lambda conf: fake_consumer)

    svc = KafkaConsumerService()
    result = svc.connect()

    assert result is True
    assert svc.is_connected is True
    assert svc.consumer == fake_consumer



@patch("src.consumer.kafka_consumer_service.Consumer", side_effect=Exception("fail"))
def test_connect_failure(mock_consumer_class):
    svc = KafkaConsumerService()
    assert svc.connect() is False
    assert svc.is_connected is False


# ============================================================================
# Tests: consume_message
# ============================================================================

def test_consume_message_none(service, mock_consumer):
    mock_consumer.poll.return_value = None
    assert service.consume_message() is None


def test_consume_message_partition_eof(service, mock_consumer):
    msg = MagicMock()
    msg.error.return_value = MagicMock(code=lambda: KafkaError._PARTITION_EOF)
    mock_consumer.poll.return_value = msg
    assert service.consume_message() is None


def test_consume_message_all_brokers_down(service, mock_consumer):
    msg = MagicMock()
    msg.error.return_value = MagicMock(code=lambda: KafkaError._ALL_BROKERS_DOWN)
    mock_consumer.poll.return_value = msg
    result = service.consume_message()
    assert result is None
    assert service.is_connected is False


def test_consume_message_json_success(monkeypatch):
    svc = KafkaConsumerService()
    svc.consumer = MagicMock()
    svc.is_connected = True

    msg = MagicMock()
    msg.error.return_value = None
    msg.value.return_value = b'{"foo":"bar"}'
    msg.topic.return_value = "user-events"
    msg.partition.return_value = 0
    msg.offset.return_value = 5
    msg.timestamp.return_value = (0, 123456789)
    msg.key.return_value = b"key1"

    svc.consumer.poll.return_value = msg

    result = svc.consume_message()
    assert result["value"]["foo"] == "bar"
    assert result["offset"] == 5



def test_consume_message_json_failure(service, mock_consumer):
    msg = MagicMock()
    msg.error.return_value = None
    msg.value.return_value = b"not-json"
    mock_consumer.poll.return_value = msg
    assert service.consume_message() is None


# ============================================================================
# Tests: commit_offset
# ============================================================================

def test_commit_offset_success(service, mock_consumer):
    msg = {"kafka_msg": MagicMock(), "partition": 0, "offset": 10}
    assert service.commit_offset(msg) is True
    mock_consumer.commit.assert_called_once()


def test_commit_offset_missing_kafka_msg(service):
    msg = {"partition": 0, "offset": 10}
    assert service.commit_offset(msg) is False


def test_commit_offset_exception(service, mock_consumer):
    mock_consumer.commit.side_effect = Exception("fail")
    msg = {"kafka_msg": MagicMock(), "partition": 0, "offset": 10}
    assert service.commit_offset(msg) is False


# ============================================================================
# Tests: seek_to_offset / seek_to_beginning
# ============================================================================

def test_seek_to_offset_success(service, mock_consumer):
    assert service.seek_to_offset(partition=0, offset=5) is True
    mock_consumer.assign.assert_called_once()


def test_seek_to_offset_failure(service, mock_consumer):
    mock_consumer.assign.side_effect = Exception("fail")
    assert service.seek_to_offset(partition=0, offset=5) is False


def test_seek_to_beginning_success(service, mock_consumer):
    assert service.seek_to_beginning() is True
    mock_consumer.seek_to_beginning.assert_called_once()


def test_seek_to_beginning_failure(service, mock_consumer):
    mock_consumer.seek_to_beginning.side_effect = Exception("fail")
    assert service.seek_to_beginning() is False


# ============================================================================
# Tests: get_consumer_lag
# ============================================================================

def test_get_consumer_lag_success(service, mock_consumer):
    tp = MagicMock()
    tp.partition = 0
    mock_consumer.assignment.return_value = [tp]
    mock_consumer.get_watermark_offsets.return_value = (0, 100)
    committed_tp = MagicMock()
    committed_tp.offset = 90
    mock_consumer.committed.return_value = [committed_tp]

    lag_info = service.get_consumer_lag()
    assert lag_info[0] == 10


def test_get_consumer_lag_no_assignments(service, mock_consumer):
    mock_consumer.assignment.return_value = []
    assert service.get_consumer_lag() is None


def test_get_consumer_lag_exception(service, mock_consumer):
    mock_consumer.assignment.side_effect = Exception("fail")
    assert service.get_consumer_lag() is None


# ============================================================================
# Tests: close
# ============================================================================

def test_close_success(service, mock_consumer):
    service.close()
    mock_consumer.commit.assert_called_once()
    mock_consumer.close.assert_called_once()
    assert service.is_connected is False


def test_close_commit_failure(service, mock_consumer):
    mock_consumer.commit.side_effect = Exception("fail")
    service.close()
    mock_consumer.close.assert_called_once()
    assert service.is_connected is False


def test_close_close_failure(service, mock_consumer):
    mock_consumer.close.side_effect = Exception("fail")
    service.close()
    mock_consumer.commit.assert_called_once()
    assert service.is_connected is False
    
    
def test_close_both_commit_and_close_fail(service, mock_consumer):
    # Simulate both commit and close failing
    mock_consumer.commit.side_effect = Exception("commit fail")
    mock_consumer.close.side_effect = Exception("close fail")

    service.close()

    # Even if both fail, service should mark itself disconnected
    assert service.is_connected is False


def test_get_consumer_lag_committed_minus_one(service, mock_consumer):
    from unittest.mock import MagicMock
    tp = MagicMock()
    tp.partition = 1
    mock_consumer.assignment.return_value = [tp]

    # Simulate watermark offsets
    mock_consumer.get_watermark_offsets.return_value = (5, 50)

    # Simulate committed offset = -1 (branch that falls back to low)
    committed_tp = MagicMock()
    committed_tp.offset = -1
    mock_consumer.committed.return_value = [committed_tp]

    lag = service.get_consumer_lag()
    assert lag[1] == 45  # high - low

def test_close_both_commit_and_close_fail(service, mock_consumer):
    mock_consumer.commit.side_effect = Exception("commit fail")
    mock_consumer.close.side_effect = Exception("close fail")

    service.close()
    assert service.is_connected is False


def test_get_consumer_lag_committed_minus_one(service, mock_consumer):
    from unittest.mock import MagicMock
    tp = MagicMock()
    tp.partition = 1
    mock_consumer.assignment.return_value = [tp]
    mock_consumer.get_watermark_offsets.return_value = (5, 50)

    committed_tp = MagicMock()
    committed_tp.offset = -1
    mock_consumer.committed.return_value = [committed_tp]

    lag = service.get_consumer_lag()
    assert lag[1] == 45

