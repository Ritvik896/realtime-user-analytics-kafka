import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from datetime import datetime
from src.consumer.event_storage_service import EventStorageService
from src.database.models import UserStats
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base, UserStats

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

# Fixture to provide a fake stats object with safe defaults
@pytest.fixture
def fake_stats():
    stats = MagicMock()
    stats.total_events = 0
    stats.total_purchases = 0
    stats.total_spent = Decimal("0")
    stats.avg_session_duration = 0
    stats.engagement_score = 0
    stats.churn_risk = 0
    return stats

# Fixture to simulate db.query().filter().first calls
@pytest.fixture
def mock_first_chain(fake_stats):
    def side_effect(*args, **kwargs):
        if not hasattr(side_effect, "calls"):
            side_effect.calls = 0
        side_effect.calls += 1
        if side_effect.calls in (1, 2):  # UserEvent, User
            return None
        return fake_stats  # UserStats
    return side_effect



# ----------------------------
# validate_event tests
# ----------------------------
def test_validate_event_generic_exception(monkeypatch):
    # Patch the datetime reference inside event_storage_service, not the built-in
    monkeypatch.setattr(
        "src.consumer.event_storage_service.datetime",
        MagicMock(fromisoformat=lambda x: (_ for _ in ()).throw(RuntimeError("boom")))
    )

    event = {
        "user_id": "u1",
        "event_id": "e1",
        "event_type": "click",
        "timestamp": "2025-11-13T12:00:00"
    }
    is_valid, error = EventStorageService.validate_event(event)
    assert not is_valid
    assert "Validation error" in error



def test_missing_required_fields():
    event = {"user_id": "u1"}  # missing event_id, event_type, timestamp
    is_valid, error = EventStorageService.validate_event(event)
    assert not is_valid
    assert "Missing required fields" in error

def test_invalid_timestamp():
    event = {"user_id": "u1", "event_id": "e1", "event_type": "click", "timestamp": "bad-date"}
    is_valid, error = EventStorageService.validate_event(event)
    assert not is_valid
    assert "Invalid timestamp format" in error

def test_unknown_event_type(caplog):
    event = {"user_id": "u1", "event_id": "e1", "event_type": "unknown", "timestamp": "2025-11-13T12:00:00"}
    is_valid, error = EventStorageService.validate_event(event)
    assert is_valid
    assert error is None
    assert "Unknown event type" in caplog.text

def test_purchase_missing_amount():
    event = {"user_id": "u1", "event_id": "e1", "event_type": "purchase", "timestamp": "2025-11-13T12:00:00"}
    is_valid, error = EventStorageService.validate_event(event)
    assert not is_valid
    assert "missing 'amount'" in error

def test_purchase_amount_not_numeric():
    event = {"user_id": "u1", "event_id": "e1", "event_type": "purchase", "timestamp": "2025-11-13T12:00:00", "amount": "abc"}
    is_valid, error = EventStorageService.validate_event(event)
    assert not is_valid
    assert "Amount not numeric" in error

def test_purchase_amount_negative():
    event = {"user_id": "u1", "event_id": "e1", "event_type": "purchase", "timestamp": "2025-11-13T12:00:00", "amount": -5}
    is_valid, error = EventStorageService.validate_event(event)
    assert not is_valid
    assert "must be positive" in error

def test_valid_event():
    event = {"user_id": "u1", "event_id": "e1", "event_type": "click", "timestamp": "2025-11-13T12:00:00"}
    is_valid, error = EventStorageService.validate_event(event)
    assert is_valid
    assert error is None

# ----------------------------
# store_event tests
# ----------------------------
def test_store_event_generic_exception(fake_stats, mock_first_chain):
    db = MagicMock()
    db.query().filter().first.side_effect = mock_first_chain
    db.add.side_effect = Exception("boom")
    event = {"user_id": "u1", "event_id": "e1", "event_type": "click", "timestamp": "2025-11-13T12:00:00"}
    with pytest.raises(Exception):
        EventStorageService.store_event(db, event)
    db.rollback.assert_called_once()


def test_store_event_validation_failure():
    db = MagicMock()
    bad_event = {"user_id": "u1"}  # missing fields
    with pytest.raises(ValueError):
        EventStorageService.store_event(db, bad_event)

def test_store_event_duplicate_event():
    db = MagicMock()
    db.query().filter().first.return_value = MagicMock()  # existing event
    event = {"user_id": "u1", "event_id": "e1", "event_type": "click", "timestamp": "2025-11-13T12:00:00"}
    result = EventStorageService.store_event(db, event)
    assert result == "e1"

def test_store_event_new_user_and_purchase(monkeypatch):
    db = MagicMock()
    db.query().filter().first.side_effect = [None, None]  # no event, no user
    db.query().filter().count.return_value = 0
    stats = MagicMock(total_events=0, total_purchases=0, total_spent=Decimal("0"), avg_session_duration=0)
    db.query().filter().first.side_effect = [None, None, stats]  # simulate stats creation
    event = {
        "user_id": "u1",
        "event_id": "e1",
        "event_type": "purchase",
        "timestamp": "2025-11-13T12:00:00",
        "amount": 10.5,
    }
    result = EventStorageService.store_event(db, event)
    assert result == "e1"
    db.commit.assert_called_once()

def test_store_event_engagement_score_cap(fake_stats, mock_first_chain):
    db = MagicMock()
    fake_stats.total_events = 500
    fake_stats.total_purchases = 50
    db.query().filter().first.side_effect = mock_first_chain
    event = {"user_id": "u1", "event_id": "e1", "event_type": "click", "timestamp": "2025-11-13T12:00:00"}
    result = EventStorageService.store_event(db, event)
    assert result == "e1"
    assert fake_stats.engagement_score == 100.0


def test_store_event_integrity_error(fake_stats, mock_first_chain):
    from sqlalchemy.exc import IntegrityError
    db = MagicMock()
    db.query().filter().first.side_effect = mock_first_chain
    db.commit.side_effect = IntegrityError("duplicate key", None, None)

    event = {"user_id": "u1", "event_id": "e1", "event_type": "click", "timestamp": "2025-11-13T12:00:00"}
    result = EventStorageService.store_event(db, event)
    assert result is None
    db.rollback.assert_called_once()


def test_store_event_sqlalchemy_error(fake_stats, mock_first_chain):
    from sqlalchemy.exc import SQLAlchemyError
    db = MagicMock()
    db.query().filter().first.side_effect = mock_first_chain
    db.commit.side_effect = SQLAlchemyError("db error")

    event = {"user_id": "u1", "event_id": "e1", "event_type": "click", "timestamp": "2025-11-13T12:00:00"}
    with pytest.raises(SQLAlchemyError):
        EventStorageService.store_event(db, event)

    db.rollback.assert_called_once()



# ----------------------------
# log_dead_letter tests
# ----------------------------

def test_log_dead_letter_success():
    db = MagicMock()
    event = {"event_id": "e1"}
    result = EventStorageService.log_dead_letter(db, event, "error", "ValueError")
    assert result is True
    db.commit.assert_called_once()

def test_log_dead_letter_failure():
    db = MagicMock()
    db.add.side_effect = Exception("fail")
    event = {"event_id": "e1"}
    result = EventStorageService.log_dead_letter(db, event, "error", "ValueError")
    assert result is False

# ----------------------------
# get_user_stats tests
# ----------------------------
def test_user_stats_defaults(db_session):
    stats = UserStats(user_id="u1")
    db_session.add(stats)
    db_session.commit()
    db_session.refresh(stats)
    assert stats.total_events == 0
    assert stats.total_spent == 0



def test_get_user_stats_success():
    db = MagicMock()
    stats = MagicMock(
        total_events=5,
        total_purchases=2,
        total_spent=Decimal("20.5"),
        last_active=datetime(2025, 11, 13, 12, 0),
        last_purchase=datetime(2025, 11, 13, 13, 0),
        avg_session_duration=30.0,
        engagement_score=75.0,
        churn_risk=0.2,
    )
    db.query().filter().first.return_value = stats
    result = EventStorageService.get_user_stats(db, "u1")
    assert result["total_events"] == 5
    assert result["total_spent"] == 20.5

def test_get_user_stats_none():
    db = MagicMock()
    db.query().filter().first.return_value = None
    result = EventStorageService.get_user_stats(db, "u1")
    assert result is None

# ----------------------------
# get_user_profile tests
# ----------------------------

def test_get_user_profile_success():
    db = MagicMock()
    user = MagicMock(
        user_id="u1",
        email="test@example.com",
        first_name="Test",
        last_name="User",
        country="IN",
        is_active=True,
        signup_date=datetime(2025, 11, 13, 12, 0),
        created_at=datetime(2025, 11, 13, 12, 0),
    )
    stats = MagicMock(
        total_events=5,
        total_purchases=2,
        total_spent=Decimal("20.5"),
        engagement_score=75.0,
        churn_risk=0.2,
    )
    db.query().filter().first.side_effect = [user, stats]
    result = EventStorageService.get_user_profile(db, "u1")
    assert result["user_id"] == "u1"
    assert result["stats"]["total_spent"] == 20.5

def test_get_user_profile_none():
    db = MagicMock()
    db.query().filter().first.return_value = None
    result = EventStorageService.get_user_profile(db, "u1")
    assert result is None

# ----------------------------
# get_dlq_summary tests
# ----------------------------

def test_get_dlq_summary_success():
    db = MagicMock()
    db.query().scalar.return_value = 3
    db.query().group_by().all.return_value = [("ValueError", 2), ("SQLAlchemyError", 1)]
    recent_entry = MagicMock(event_id="e1", error_type="ValueError", created_at=datetime(2025, 11, 13, 12, 0))
    db.query().order_by().limit().all.return_value = [recent_entry]
    result = EventStorageService.get_dlq_summary
    
def test_get_dlq_summary_exception():
    db = MagicMock()
    db.query.side_effect = Exception("fail")
    result = EventStorageService.get_dlq_summary(db)
    assert "error" in result
