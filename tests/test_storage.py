"""Unit tests for Phase 2: Consumer and Storage Service.

Run tests with: pytest tests/test_storage.py -v

These tests verify:
1. Event validation
2. User creation
3. Event storage
4. Statistics aggregation
5. Duplicate handling
6. Error logging to DLQ

Using in-memory SQLite for fast, isolated testing.
"""
import pytest
from datetime import datetime, timezone  # ✅ FIXED: Added timezone import
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.database.models import Base, User, UserEvent, UserStats, DeadLetterQueue
from src.consumer.event_storage_service import EventStorageService


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def db_session() -> Session:
    """Create in-memory database for each test."""
    # Use SQLite for fast testing
    engine = create_engine("sqlite:///:memory:")
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    # Create session factory
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    # Cleanup
    session.close()


# ============================================================================
# Test: Event Validation
# ============================================================================

class TestEventValidation:
    """Test event validation logic."""
    
    def test_valid_event(self):
        """Test that valid events pass validation."""
        event = {
            "user_id": "user123",
            "event_id": "evt_001",
            "event_type": "click",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
        }
        
        is_valid, error = EventStorageService.validate_event(event)
        assert is_valid is True
        assert error is None
    
    def test_missing_required_fields(self):
        """Test that missing required fields fail validation."""
        event = {
            "user_id": "user123",
            "event_id": "evt_001",
            # Missing: event_type, timestamp
        }
        
        is_valid, error = EventStorageService.validate_event(event)
        assert is_valid is False
        assert "Missing required fields" in error
    
    def test_invalid_timestamp_format(self):
        """Test that invalid timestamp format fails."""
        event = {
            "user_id": "user123",
            "event_id": "evt_001",
            "event_type": "click",
            "timestamp": "not-a-timestamp",
        }
        
        is_valid, error = EventStorageService.validate_event(event)
        assert is_valid is False
        assert "Invalid timestamp format" in error
    
    def test_purchase_missing_amount(self):
        """Test that purchase events require amount."""
        event = {
            "user_id": "user123",
            "event_id": "evt_001",
            "event_type": "purchase",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            # Missing: amount
        }
        
        is_valid, error = EventStorageService.validate_event(event)
        assert is_valid is False
        assert "amount" in error.lower()
    
    def test_purchase_invalid_amount(self):
        """Test that purchase amounts must be positive."""
        event = {
            "user_id": "user123",
            "event_id": "evt_001",
            "event_type": "purchase",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            "amount": -50.00,  # Negative
        }
        
        is_valid, error = EventStorageService.validate_event(event)
        assert is_valid is False
        assert "positive" in error.lower()


# ============================================================================
# Test: User Creation
# ============================================================================

class TestUserCreation:
    """Test user creation during event storage."""
    
    def test_create_user_on_first_event(self, db_session):
        """Test that user is created on first event."""
        event = {
            "user_id": "user123",
            "event_id": "evt_001",
            "event_type": "click",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            "email": "user@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "country": "US",
        }
        
        EventStorageService.store_event(db_session, event)
        
        # Verify user was created
        user = db_session.query(User).filter(User.user_id == "user123").first()
        assert user is not None
        assert user.email == "user@example.com"
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.country == "US"
        assert user.is_active is True
    
    def test_reuse_existing_user(self, db_session):
        """Test that existing user is reused."""
        event1 = {
            "user_id": "user123",
            "event_id": "evt_001",
            "event_type": "click",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            "email": "user@example.com",
        }
        
        event2 = {
            "user_id": "user123",
            "event_id": "evt_002",
            "event_type": "purchase",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            "amount": 50.00,
        }
        
        EventStorageService.store_event(db_session, event1)
        EventStorageService.store_event(db_session, event2)
        
        # Verify only one user exists
        users = db_session.query(User).filter(User.user_id == "user123").all()
        assert len(users) == 1


# ============================================================================
# Test: Event Storage
# ============================================================================

class TestEventStorage:
    """Test event storage functionality."""
    
    def test_store_click_event(self, db_session):
        """Test storing a click event."""
        event = {
            "user_id": "user123",
            "event_id": "evt_001",
            "event_type": "click",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            "event_metadata": {"page": "home", "section": "hero"},
        }
        
        event_id = EventStorageService.store_event(db_session, event)
        
        assert event_id == "evt_001"
        
        # Verify event was stored
        stored_event = db_session.query(UserEvent).filter(
            UserEvent.event_id == "evt_001"
        ).first()
        assert stored_event is not None
        assert stored_event.event_type == "click"
        assert stored_event.user_id == "user123"
    
    def test_store_purchase_event(self, db_session):
        """Test storing a purchase event."""
        event = {
            "user_id": "user123",
            "event_id": "evt_001",
            "event_type": "purchase",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            "amount": 99.99,
            "event_metadata": {"product_id": "p123", "category": "electronics"},
        }
        
        EventStorageService.store_event(db_session, event)
        
        stored_event = db_session.query(UserEvent).first()
        assert stored_event.event_type == "purchase"
        assert stored_event.event_metadata["product_id"] == "p123"
    
    def test_store_video_event_with_duration(self, db_session):
        """Test storing a video event with duration."""
        event = {
            "user_id": "user123",
            "event_id": "evt_001",
            "event_type": "video",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            "duration": 300.5,  # 5 minutes
            "event_metadata": {"video_id": "v123"},
        }
        
        EventStorageService.store_event(db_session, event)
        
        stored_event = db_session.query(UserEvent).first()
        assert stored_event.duration == 300.5


# ============================================================================
# Test: Statistics Aggregation
# ============================================================================

class TestStatisticsAggregation:
    """Test real-time statistics aggregation."""
    
    def test_create_stats_on_first_event(self, db_session):
        """Test that stats are created on first event."""
        event = {
            "user_id": "user123",
            "event_id": "evt_001",
            "event_type": "click",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
        }
        
        EventStorageService.store_event(db_session, event)
        
        stats = db_session.query(UserStats).filter(
            UserStats.user_id == "user123"
        ).first()
        assert stats is not None
        assert stats.total_events == 1
        assert stats.total_purchases == 0
        assert float(stats.total_spent) == 0.0
    
    def test_increment_total_events(self, db_session):
        """Test that total_events increments."""
        for i in range(5):
            event = {
                "user_id": "user123",
                "event_id": f"evt_{i:03d}",
                "event_type": "click",
                "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            }
            EventStorageService.store_event(db_session, event)
        
        stats = db_session.query(UserStats).first()
        assert stats.total_events == 5
    
    def test_track_purchase_statistics(self, db_session):
        """Test that purchase events update spending."""
        # First event: non-purchase
        event1 = {
            "user_id": "user123",
            "event_id": "evt_001",
            "event_type": "click",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
        }
        EventStorageService.store_event(db_session, event1)
        
        # Second event: purchase $50
        event2 = {
            "user_id": "user123",
            "event_id": "evt_002",
            "event_type": "purchase",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            "amount": 50.00,
        }
        EventStorageService.store_event(db_session, event2)
        
        # Third event: purchase $30
        event3 = {
            "user_id": "user123",
            "event_id": "evt_003",
            "event_type": "purchase",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            "amount": 30.00,
        }
        EventStorageService.store_event(db_session, event3)
        
        stats = db_session.query(UserStats).first()
        assert stats.total_events == 3
        assert stats.total_purchases == 2
        assert float(stats.total_spent) == 80.00
    
    def test_update_last_active_timestamp(self, db_session):
        """Test that last_active is updated."""
        # ✅ FIXED: Use naive datetime for SQLite compatibility
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        event = {
            "user_id": "user123",
            "event_id": "evt_001",
            "event_type": "click",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        EventStorageService.store_event(db_session, event)
        
        stats = db_session.query(UserStats).first()
        assert stats.last_active is not None
        # Allow small time difference (5 seconds for test execution)
        assert abs((stats.last_active - now).total_seconds()) < 5
    
    def test_calculate_average_duration(self, db_session):
        """Test that average duration is calculated correctly."""
        # Event 1: 10s
        event1 = {
            "user_id": "user123",
            "event_id": "evt_001",
            "event_type": "video",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            "duration": 10.0,
        }
        EventStorageService.store_event(db_session, event1)
        
        # Event 2: 20s
        event2 = {
            "user_id": "user123",
            "event_id": "evt_002",
            "event_type": "video",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            "duration": 20.0,
        }
        EventStorageService.store_event(db_session, event2)
        
        # Event 3: 30s
        event3 = {
            "user_id": "user123",
            "event_id": "evt_003",
            "event_type": "video",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            "duration": 30.0,
        }
        EventStorageService.store_event(db_session, event3)
        
        stats = db_session.query(UserStats).first()
        expected_avg = (10 + 20 + 30) / 3
        assert abs(stats.avg_session_duration - expected_avg) < 0.01


# ============================================================================
# Test: Duplicate Handling
# ============================================================================

class TestDuplicateHandling:
    """Test idempotent event processing."""
    
    def test_duplicate_event_returns_same_id(self, db_session):
        """Test that duplicate events are handled gracefully."""
        event = {
            "user_id": "user123",
            "event_id": "evt_001",
            "event_type": "click",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
        }
        
        # Store first time
        id1 = EventStorageService.store_event(db_session, event)
        
        # Store again (duplicate)
        id2 = EventStorageService.store_event(db_session, event)
        
        assert id1 == id2
        assert id1 == "evt_001"
    
    def test_duplicate_not_stored_twice(self, db_session):
        """Test that duplicate events don't create multiple records."""
        event = {
            "user_id": "user123",
            "event_id": "evt_001",
            "event_type": "click",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
        }
        
        EventStorageService.store_event(db_session, event)
        EventStorageService.store_event(db_session, event)  # Duplicate
        
        # Verify only one event in database
        count = db_session.query(UserEvent).filter(
            UserEvent.event_id == "evt_001"
        ).count()
        assert count == 1
    
    def test_duplicate_doesnt_update_stats_twice(self, db_session):
        """Test that stats aren't incremented for duplicates."""
        event = {
            "user_id": "user123",
            "event_id": "evt_001",
            "event_type": "click",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
        }
        
        EventStorageService.store_event(db_session, event)
        EventStorageService.store_event(db_session, event)  # Duplicate
        
        stats = db_session.query(UserStats).first()
        assert stats.total_events == 1  # Not incremented twice


# ============================================================================
# Test: Dead Letter Queue
# ============================================================================

class TestDeadLetterQueue:
    """Test error handling with DLQ."""
    
    def test_log_validation_error_to_dlq(self, db_session):
        """Test that validation errors are logged to DLQ."""
        event_data = {
            "user_id": "user123",
            "event_id": "evt_001",
            # Missing: event_type, timestamp
        }
        
        error_msg = "Missing required fields"
        EventStorageService.log_dead_letter(
            db_session,
            event_data,
            error_msg,
            "ValueError"
        )
        
        dlq_entry = db_session.query(DeadLetterQueue).first()
        assert dlq_entry is not None
        assert dlq_entry.event_id == "evt_001"
        assert dlq_entry.error_type == "ValueError"
        assert dlq_entry.status == "pending"
        assert dlq_entry.retry_count == 0
    
    def test_dlq_stores_full_event_data(self, db_session):
        """Test that full event data is stored for replay."""
        event_data = {
            "user_id": "user123",
            "event_id": "evt_001",
            "event_type": "purchase",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            "amount": 99.99,
            "event_metadata": {"product": "laptop"},
        }
        
        EventStorageService.log_dead_letter(
            db_session,
            event_data,
            "Some error",
            "RuntimeError"
        )
        
        dlq_entry = db_session.query(DeadLetterQueue).first()
        assert dlq_entry.event_data == event_data
        assert dlq_entry.event_data["amount"] == 99.99


# ============================================================================
# Test: User Stats Retrieval
# ============================================================================

class TestStatsRetrieval:
    """Test retrieving user statistics."""
    
    def test_get_user_stats(self, db_session):
        """Test getting user statistics."""
        # Create some events
        for i in range(3):
            event = {
                "user_id": "user123",
                "event_id": f"evt_{i:03d}",
                "event_type": "click",
                "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            }
            EventStorageService.store_event(db_session, event)
        
        stats = EventStorageService.get_user_stats(db_session, "user123")
        
        assert stats is not None
        assert stats["user_id"] == "user123"
        assert stats["total_events"] == 3
        assert stats["total_purchases"] == 0
        assert stats["total_spent"] == 0.0
    
    def test_get_nonexistent_user_stats(self, db_session):
        """Test getting stats for nonexistent user."""
        stats = EventStorageService.get_user_stats(db_session, "nonexistent")
        assert stats is None


# ============================================================================
# Test: Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests combining multiple features."""
    
    def test_full_user_journey(self, db_session):
        """Test complete user journey with multiple event types."""
        # User signs up
        event1 = {
            "user_id": "user123",
            "event_id": "evt_001",
            "event_type": "login",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            "email": "user@example.com",
            "first_name": "Jane",
            "country": "CA",
        }
        EventStorageService.store_event(db_session, event1)
        
        # User browses
        event2 = {
            "user_id": "user123",
            "event_id": "evt_002",
            "event_type": "click",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            "event_metadata": {"page": "products"},
        }
        EventStorageService.store_event(db_session, event2)
        
        # User watches video
        event3 = {
            "user_id": "user123",
            "event_id": "evt_003",
            "event_type": "video",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            "duration": 120.0,
        }
        EventStorageService.store_event(db_session, event3)
        
        # User makes purchase
        event4 = {
            "user_id": "user123",
            "event_id": "evt_004",
            "event_type": "purchase",
            "timestamp": datetime.now(timezone.utc).isoformat(),  # ✅ FIXED
            "amount": 199.99,
        }
        EventStorageService.store_event(db_session, event4)
        
        # Verify user profile
        user = db_session.query(User).first()
        assert user.email == "user@example.com"
        assert user.first_name == "Jane"
        assert user.country == "CA"
        
        # Verify events
        events = db_session.query(UserEvent).all()
        assert len(events) == 4
        
        # Verify stats
        stats = db_session.query(UserStats).first()
        assert stats.total_events == 4
        assert stats.total_purchases == 1
        assert float(stats.total_spent) == 199.99
        assert abs(stats.avg_session_duration - 120.0) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])