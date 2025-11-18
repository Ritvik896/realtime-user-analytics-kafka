import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base, UserStats
from src.events.event_generator import UserEventGenerator
from src.consumer.event_storage_service import EventStorageService
from datetime import datetime, timezone  


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_pipeline_user_creation_and_flush(db_session):
    event = UserEventGenerator.generate_user_event(user_id="new_user")
    EventStorageService.store_event(db_session, event.to_dict())

    stats = EventStorageService.get_user_stats(db_session, "new_user")
    assert stats["total_events"] >= 1


def test_pipeline_engagement_score_cap(db_session):
    # Generate valid purchase events with amount to inflate engagement
    for i in range(200):
        event = {
            "user_id": "u1",
            "event_id": f"evt_{i}",
            "event_type": "purchase",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "amount": 10.0,
            "event_metadata": {"product_id": f"p{i}"}
        }
        EventStorageService.store_event(db_session, event)

    capped = EventStorageService.get_user_stats(db_session, "u1")
    assert capped["engagement_score"] <= 100
    


def test_pipeline_dlq_summary_exception(monkeypatch, db_session):
    def bad_query(*a, **kw): raise Exception("boom")
    monkeypatch.setattr(db_session, "query", bad_query)

    summary = EventStorageService.get_dlq_summary(db_session)
    assert "error" in summary


def test_pipeline_store_event_exception(monkeypatch, db_session):
    def bad_commit(*a, **kw): raise
    

def test_pipeline_dlq_on_bad_event(db_session, monkeypatch):
    from src.consumer.event_storage_service import EventStorageService
    from src.database.models import DeadLetterQueue

    # Fake consumer message with invalid dict (missing required fields)
    bad_msg = {"value": {"invalid": "data"}}

    # Patch consume_message to always return bad_msg
    monkeypatch.setattr(
        "src.consumer.kafka_consumer_service.KafkaConsumerService.consume_message",
        lambda self, timeout_ms=200: bad_msg
    )

    # Run pipeline logic
    try:
        EventStorageService.store_event(db_session, bad_msg["value"])
    except Exception as e:
        EventStorageService.log_dead_letter(
            db_session, bad_msg["value"], str(e), type(e).__name__
        )

    dlq = db_session.query(DeadLetterQueue).all()
    assert len(dlq) >= 1

