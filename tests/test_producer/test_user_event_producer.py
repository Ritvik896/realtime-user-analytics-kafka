import pytest
import time
from src.producer.user_event_producer import UserEventProducer
from src.events.event_models import UserEvent, EventType
from unittest.mock import MagicMock, patch
from confluent_kafka import KafkaException


class FakeMsg:
    def __init__(self, value=b"{}", topic="t", partition=0, offset=0):
        self._value = value
        self._topic = topic
        self._partition = partition
        self._offset = offset
    def value(self): return self._value
    def topic(self): return self._topic
    def partition(self): return self._partition
    def offset(self): return self._offset


class FakeProducer:
    def __init__(self, *args, **kwargs):
        self.produced = []
        self.flushed = False
    def produce(self, topic, value, callback=None):
        self.produced.append((topic, value))
        if callback:
            callback(None, FakeMsg(value))
    def poll(self, timeout): return None
    def flush(self, timeout=10): self.flushed = True
    def close(self): self.flushed = True


@pytest.fixture
def producer(monkeypatch):
    # Patch Producer before instantiation
    monkeypatch.setattr("src.producer.user_event_producer.Producer", lambda cfg: FakeProducer())
    return UserEventProducer(bootstrap_servers="fake:9092", topic="test_topic")


def test_create_producer(monkeypatch):
    monkeypatch.setattr("src.producer.user_event_producer.Producer", lambda cfg: FakeProducer())
    p = UserEventProducer()
    assert isinstance(p.producer, FakeProducer)


def test_delivery_report_success(producer):
    msg = FakeMsg(value=b"hello")
    producer._delivery_report(None, msg)
    assert producer.events_sent == 1
    assert producer.total_bytes_sent == len(b"hello")


def test_delivery_report_failure(producer):
    producer._delivery_report(Exception("fail"), None)
    assert producer.events_failed == 1


def test_send_event_success(producer):
    event = UserEvent(user_id="u1", session_id="s1", event_type=EventType.LOGIN)
    ok = producer.send_event(event)
    assert ok is True
    assert producer.events_sent >= 1


def test_send_event_kafka_exception(monkeypatch):
    fake_producer = MagicMock()
    fake_producer.produce.side_effect = KafkaException("broker down")
    monkeypatch.setattr("src.producer.user_event_producer.Producer", lambda conf: fake_producer)

    producer = UserEventProducer(bootstrap_servers="localhost:9092", topic="user-events")
    ok = producer.send_event(UserEvent(user_id="u1", session_id="s1", event_type=EventType.LOGIN))
    assert ok is False
    assert producer.events_failed >= 1


def test_send_event_generic_exception(monkeypatch):
    fake_producer = MagicMock()
    fake_producer.produce.side_effect = Exception("unexpected")
    monkeypatch.setattr("src.producer.user_event_producer.Producer", lambda conf: fake_producer)

    producer = UserEventProducer(bootstrap_servers="localhost:9092", topic="user-events")
    ok = producer.send_event(UserEvent(user_id="u1", session_id="s1", event_type=EventType.LOGIN))
    assert ok is False
    assert producer.events_failed >= 1


def test_send_batch(producer):
    events = [UserEvent(user_id="u1", session_id="s1", event_type=EventType.LOGIN) for _ in range(3)]
    count = producer.send_batch(events)
    assert count == 3


def test_send_batch_partial_failures(monkeypatch):
    fake_producer = MagicMock()
    calls = {"count": 0}

    def produce_side_effect(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            raise KafkaException("partition error")

    fake_producer.produce.side_effect = produce_side_effect
    fake_producer.flush.return_value = 0
    monkeypatch.setattr("src.producer.user_event_producer.Producer", lambda conf: fake_producer)

    producer = UserEventProducer(bootstrap_servers="localhost:9092", topic="user-events")
    batch = [
        UserEvent(user_id="u1", session_id="s1", event_type=EventType.LOGIN),
        UserEvent(user_id="u2", session_id="s2", event_type=EventType.LOGOUT),
        UserEvent(user_id="u3", session_id="s3", event_type=EventType.PURCHASE),
    ]
    count = producer.send_batch(batch)
    # Expect 2 successes before failure
    assert count == 2
    assert producer.events_failed >= 1


def test_generate_and_send(monkeypatch, producer):
    monkeypatch.setattr(
        "src.events.event_generator.UserEventGenerator.generate_user_event",
        lambda user_id=None: UserEvent(user_id="u1", session_id="s1", event_type=EventType.LOGIN)
    )
    stats = producer.generate_and_send(event_count=5, events_per_second=0)
    assert stats["events_requested"] == 5
    assert stats["events_sent"] == 5
    assert stats["success_rate"] == 100.0


def test_continuous_stream(monkeypatch, producer):
    monkeypatch.setattr(
        "src.events.event_generator.UserEventGenerator.generate_user_event",
        lambda: UserEvent(user_id="u1", session_id="s1", event_type=EventType.LOGIN)
    )
    producer.continuous_stream(events_per_second=100, duration_minutes=0.0001)
    assert producer.events_sent > 0


def test_continuous_stream_stops_on_flag(monkeypatch):
    fake_producer = MagicMock()
    monkeypatch.setattr("src.producer.user_event_producer.Producer", lambda conf: fake_producer)

    # Patch the correct generator method
    monkeypatch.setattr(
        "src.events.event_generator.UserEventGenerator.generate_user_event",
        lambda: UserEvent(user_id="uX", session_id="sX", event_type=EventType.LOGIN)
    )

    producer = UserEventProducer(bootstrap_servers="localhost:9092", topic="user-events")
    with patch("time.sleep", lambda s: None):
        ok = producer.continuous_stream(events_per_second=10, duration_minutes=0.001)
        assert ok in (True, None)


def test_get_stats(producer):
    producer.events_sent = 10
    producer.events_failed = 5
    stats = producer.get_stats()
    assert stats["total_events"] == 15
    assert stats["success_rate"] == round(10/15*100, 2)


def test_close(producer):
    producer.close()
    assert producer.producer.flushed is True


def test_close_flush_failure(monkeypatch):
    fake_producer = MagicMock()
    fake_producer.flush.side_effect = Exception("flush failed")
    monkeypatch.setattr("src.producer.user_event_producer.Producer", lambda conf: fake_producer)

    producer = UserEventProducer(bootstrap_servers="localhost:9092", topic="user-events")
    producer.close()
    assert producer.producer is not None


def test_close_close_failure(monkeypatch):
    fake_producer = MagicMock()
    fake_producer.flush.return_value = 0
    fake_producer.close.side_effect = Exception("close failed")
    monkeypatch.setattr("src.producer.user_event_producer.Producer", lambda conf: fake_producer)

    producer = UserEventProducer(bootstrap_servers="localhost:9092", topic="user-events")
    producer.close()
    assert producer.producer is not None
