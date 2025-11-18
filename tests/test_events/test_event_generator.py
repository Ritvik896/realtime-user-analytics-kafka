import pytest
from datetime import datetime
from src.events.event_generator import UserEventGenerator
from src.events.event_models import (
    UserEvent, PurchaseEvent, VideoWatchEvent, ClickEvent, SearchEvent,
    EventType
)


def test_generate_purchase_event():
    event = UserEventGenerator.generate_user_event(event_type=EventType.PURCHASE, user_id="u1")
    assert isinstance(event, PurchaseEvent)
    assert event.value > 0
    assert event.currency == "INR"
    assert event.product_id.startswith("prod_")


def test_generate_video_watch_event():
    event = UserEventGenerator.generate_user_event(event_type=EventType.VIDEO_WATCH, user_id="u2")
    assert isinstance(event, VideoWatchEvent)
    assert 0 < event.duration_seconds <= event.video_duration
    assert 0 <= event.watched_percentage <= 100


def test_generate_click_event():
    event = UserEventGenerator.generate_user_event(event_type=EventType.CLICK, user_id="u3")
    assert isinstance(event, ClickEvent)
    assert hasattr(event, "element_id")
    assert hasattr(event, "x_coordinate")


def test_generate_search_event():
    event = UserEventGenerator.generate_user_event(event_type=EventType.SEARCH, user_id="u4")
    assert isinstance(event, SearchEvent)
    assert isinstance(event.query, str)
    assert isinstance(event.results_count, int)


def test_generate_generic_event():
    event = UserEventGenerator.generate_user_event(event_type=EventType.LOGIN, user_id="u5")
    assert isinstance(event, UserEvent)
    assert event.event_type == EventType.LOGIN


def test_generate_batch_count():
    events = UserEventGenerator.generate_batch(count=5, user_id="u6")
    assert len(events) == 5
    assert all(isinstance(e, UserEvent) for e in events)


def test_generate_user_session_structure():
    session_id, events = UserEventGenerator.generate_user_session(user_id="u7", event_count=10)
    assert session_id.startswith("sess_")
    assert len(events) == 10
    assert events[0].event_type == EventType.LOGIN
    assert events[-1].event_type == EventType.LOGOUT


def test_generate_anomalous_event_high_value(monkeypatch):
    # Force anomaly type
    monkeypatch.setattr("random.choice", lambda seq: "high_value_purchase" if "high_value_purchase" in seq else seq[0])
    event = UserEventGenerator.generate_anomalous_event(user_id="u8")
    assert isinstance(event, PurchaseEvent)
    assert event.value == 999999.99
    assert event.quantity == 100
    assert "anomaly_score" in event.metadata


def test_generate_anomalous_event_rapid(monkeypatch):
    monkeypatch.setattr("random.choice", lambda seq: "rapid_purchases" if "rapid_purchases" in seq else seq[0])
    event = UserEventGenerator.generate_anomalous_event(user_id="u9")
    assert isinstance(event, PurchaseEvent)
    assert event.quantity >= 50
    assert event.metadata.get("rapid_purchase") is True


def test_generate_anomalous_event_generic(monkeypatch):
    monkeypatch.setattr("random.choice", lambda seq: "unusual_location" if "unusual_location" in seq else seq[0])
    event = UserEventGenerator.generate_anomalous_event(user_id="u10")
    assert isinstance(event, UserEvent)
    assert event.page == "/anomaly"
    assert "anomaly_type" in event.metadata


def test_get_sample_events_summary():
    summary = UserEventGenerator.get_sample_events_summary()
    assert summary["users"] == 50
    assert summary["products"] >= 1
    assert "event_types" in summary
    assert "device_types" in summary
