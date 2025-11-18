import pytest
from datetime import datetime
from src.events.event_models import (
    UserEvent, PurchaseEvent, VideoWatchEvent, ClickEvent, SearchEvent, EventBatch, EventType
)

def test_user_event_validation_user_id():
    with pytest.raises(ValueError):
        UserEvent(user_id="", session_id="sess1", event_type=EventType.LOGIN)

def test_user_event_validation_session_id():
    with pytest.raises(ValueError):
        UserEvent(user_id="u1", session_id="", event_type=EventType.LOGIN)

def test_user_event_negative_value():
    with pytest.raises(ValueError):
        UserEvent(user_id="u1", session_id="sess1", event_type=EventType.PURCHASE, value=-10)

def test_purchase_event_quantity_validation():
    with pytest.raises(ValueError):
        PurchaseEvent(user_id="u1", session_id="sess1", product_id="p1", value=100, quantity=0)

def test_video_watch_event_percentage_validation():
    with pytest.raises(ValueError):
        VideoWatchEvent(user_id="u1", session_id="sess1", video_id="v1",
                        duration_seconds=100, watched_percentage=150, video_duration=200)

def test_click_event_creation():
    event = ClickEvent(user_id="u1", session_id="sess1", element_id="btn1", element_type="button")
    assert event.event_type == EventType.CLICK
    assert event.element_id == "btn1"

def test_search_event_creation():
    event = SearchEvent(user_id="u1", session_id="sess1", query="python", results_count=10)
    assert event.event_type == EventType.SEARCH
    assert event.results_count == 10

def test_event_batch_to_list_and_str():
    e1 = UserEvent(user_id="u1", session_id="sess1", event_type=EventType.LOGIN)
    e2 = UserEvent(user_id="u2", session_id="sess2", event_type=EventType.LOGOUT)
    batch = EventBatch(events=[e1, e2])
    lst = batch.to_list()
    assert isinstance(lst, list)
    assert len(lst) == 2
    assert "event_id" in lst[0]
    assert "EventBatch" in str(batch)
