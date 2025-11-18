import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base, User, UserEvent, UserStats, DeadLetterQueue
from datetime import datetime, timezone


@pytest.fixture
def db_session():
    # Use in-memory SQLite for tests
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_user_creation_and_repr(db_session):
    user = User(user_id="u1", email="alice@example.com", first_name="Alice", last_name="Smith")
    db_session.add(user)
    db_session.commit()
    fetched = db_session.query(User).filter_by(user_id="u1").first()
    assert fetched.email == "alice@example.com"
    assert "User" in repr(fetched)


def test_user_event_creation_and_relationship(db_session):
    user = User(user_id="u2")
    db_session.add(user)
    db_session.commit()

    event = UserEvent(event_id="e1", user_id="u2", event_type="click", timestamp=datetime.now(timezone.utc))
    db_session.add(event)
    db_session.commit()

    fetched_event = db_session.query(UserEvent).filter_by(event_id="e1").first()
    assert fetched_event.event_type == "click"
    assert fetched_event.user.user_id == "u2"
    assert "UserEvent" in repr(fetched_event)


def test_user_stats_defaults_and_repr(db_session):
    user = User(user_id="u3")
    db_session.add(user)
    db_session.commit()

    stats = UserStats(user_id="u3")
    db_session.add(stats)
    db_session.commit()
    db_session.refresh(stats)

    # These defaults are the missed lines
    assert stats.total_events == 0
    assert stats.total_purchases == 0
    assert float(stats.total_spent) == 0.0
    assert stats.avg_session_duration == 0.0
    assert stats.engagement_score == 0.0
    assert stats.churn_risk == 0.0
    assert "UserStats" in repr(stats)


def test_dead_letter_queue_creation_and_repr(db_session):
    dlq = DeadLetterQueue(
        event_id="e2",
        event_data={"foo": "bar"},
        error_message="Validation failed",
        error_type="ValueError",
    )
    db_session.add(dlq)
    db_session.commit()

    fetched = db_session.query(DeadLetterQueue).filter_by(event_id="e2").first()
    assert fetched.error_type == "ValueError"
    assert fetched.status == "pending"  # default
    assert "DeadLetterQueue" in repr(fetched)
