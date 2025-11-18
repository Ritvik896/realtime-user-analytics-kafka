"""Service for storing events in database and updating statistics.

This module handles:
1. Event validation and deduplication
2. User creation/update
3. Event storage (append-only)
4. Real-time statistics aggregation
5. Error handling with Dead Letter Queue

Design Pattern: Event Sourcing + CQRS
- Events are the source of truth (append-only)
- Statistics are derived views (can be rebuilt)
- Errors captured for debugging and replay
"""
import logging
from datetime import datetime, timezone  # ✅ FIXED: Added timezone import
from decimal import Decimal  # ✅ CHANGE 1: Added import for Decimal
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from src.database.models import User, UserEvent, UserStats, DeadLetterQueue

logger = logging.getLogger(__name__)


class EventStorageService:
    """
    Service for storing events and maintaining statistics.
    
    Key Responsibilities:
    1. Validate incoming event data
    2. Create/update user record
    3. Store event atomically
    4. Update user statistics
    5. Log errors to DLQ
    
    Atomicity Guarantee:
    - All operations in single transaction
    - If any fails, entire transaction rolls back
    - No partial data in database
    """
    
    # Required fields for all events
    REQUIRED_FIELDS = {"user_id", "event_id", "event_type", "timestamp"}
    
    # Event types we expect (for validation)
    VALID_EVENT_TYPES = {"click", "purchase", "view", "search", "login", "logout", "video", "other"}
    
    @staticmethod
    def validate_event(event_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate event data.
        
        Args:
            event_data: Event payload from Kafka
        
        Returns:
            (is_valid, error_message)
        
        Validation Rules:
        1. All required fields present
        2. event_id is unique (prevents duplicates)
        3. timestamp is valid ISO format
        4. event_type is recognized
        5. Amount is positive (for purchases)
        """
        try:
            # Check required fields
            missing = EventStorageService.REQUIRED_FIELDS - set(event_data.keys())
            if missing:
                return False, f"Missing required fields: {missing}"
            
            # Validate timestamp
            try:
                datetime.fromisoformat(event_data["timestamp"])
            except ValueError:
                return False, f"Invalid timestamp format: {event_data['timestamp']}"
            
            # Validate event_type
            event_type = event_data.get("event_type")
            if event_type not in EventStorageService.VALID_EVENT_TYPES:
                logger.warning(f"Unknown event type: {event_type} (will be stored as 'other')")
            
            # Validate amount for purchase events
            if event_type == "purchase":
                amount = event_data.get("amount")
                if amount is None:
                    return False, "Purchase event missing 'amount'"
                try:
                    amount = float(amount)
                    if amount <= 0:
                        return False, f"Invalid amount: {amount} (must be positive)"
                except (TypeError, ValueError):
                    return False, f"Amount not numeric: {amount}"
            
            return True, None
        
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    @staticmethod
    def store_event(db: Session, event_data: Dict[str, Any]) -> Optional[str]:
        """
        Store event in database and update user statistics.
        
        Args:
            db: Database session
            event_data: Event from Kafka
        
        Returns:
            event_id if successful, None if failed
        
        Process:
        1. Validate event
        2. Get or create user
        3. Create event record
        4. Update statistics
        5. Commit transaction
        
        If any step fails, entire transaction rolls back.
        
        Example Success:
            event_id = store_event(db, {
                "user_id": "user123",
                "event_id": "evt_001",
                "event_type": "purchase",
                "timestamp": "2024-01-15T10:30:00",
                "amount": 99.99,
                "event_metadata": {"product_id": "p123", "category": "electronics"}
            })
        """
        try:
            # Step 1: Validate event
            is_valid, error_msg = EventStorageService.validate_event(event_data)
            if not is_valid:
                logger.warning(f"⚠️  Event validation failed: {error_msg}")
                raise ValueError(error_msg)
            
            user_id = event_data.get("user_id")
            event_id = event_data.get("event_id")
            event_type = event_data.get("event_type")
            timestamp_str = event_data.get("timestamp")
            
            # Step 2: Check for duplicate event
            existing_event = db.query(UserEvent).filter(
                UserEvent.event_id == event_id
            ).first()
            
            if existing_event:
                logger.warning(f"⚠️  Duplicate event detected: {event_id} (idempotent, ignoring)")
                return event_id  # Already processed, return success
            
            # Step 3: Get or create user
            user = db.query(User).filter(User.user_id == user_id).first()
            
            if not user:
                # Create new user
                user = User(
                    user_id=user_id,
                    email=event_data.get("email"),
                    first_name=event_data.get("first_name"),
                    last_name=event_data.get("last_name"),
                    country=event_data.get("country"),
                    signup_date=datetime.fromisoformat(timestamp_str),
                    is_active=True,
                )
                db.add(user)
                db.flush()  # Flush to get user ID, but don't commit yet
                logger.info(f"✅ Created new user: {user_id}")
            
            # Step 4a: Pre-calculate average duration info BEFORE adding event
            timestamp = datetime.fromisoformat(timestamp_str)
            duration_value = event_data.get("duration")
            
            if duration_value:
                duration = float(duration_value)
                
                # ✅ CHANGE 3: Count how many events with duration we've seen (BEFORE this event)
                old_duration_count = db.query(UserEvent).filter(
                    UserEvent.user_id == user_id,
                    UserEvent.duration.isnot(None)
                ).count()
            else:
                duration = None
                old_duration_count = None
            
            # Step 4b: Create event record
            user_event = UserEvent(
                event_id=event_id,
                user_id=user_id,
                event_type=event_type,
                timestamp=timestamp,
                duration=event_data.get("duration"),
                event_metadata=event_data.get("event_metadata", {}),  # FIXED: renamed from 'metadata'
            )
            db.add(user_event)
            db.flush()
            
            # Step 5: Update user statistics
            stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
            
            if not stats:
                # Create new stats record
                stats = UserStats(user_id=user_id)
                db.add(stats)
                db.flush()  # ✅ ADD THIS - ensures total_events is initialized to 0
            
            # ✅ CHANGE 3: Update average duration FIRST (before incrementing total_events)
            if duration is not None and old_duration_count is not None:
                if old_duration_count > 0:
                    # ✅ CHANGE 3a: Use running average formula with duration-event count
                    old_avg = stats.avg_session_duration
                    stats.avg_session_duration = (
                        (old_avg * old_duration_count + duration) / (old_duration_count + 1)
                    )
                else:
                    # ✅ CHANGE 3b: First event with duration - just use its value
                    stats.avg_session_duration = duration
            
            # Always increment
            stats.total_events += 1
            stats.last_active = timestamp
            
            # Type-specific updates
            # ✅ CHANGE 2: Fixed purchase event handling - Convert amount to Decimal
            if event_type == "purchase":
                stats.total_purchases += 1
                amount = Decimal(str(event_data.get("amount", 0)))  # ✅ CHANGE 2a: Convert to Decimal
                stats.total_spent += amount  # ✅ CHANGE 2b: Now Decimal + Decimal works correctly
                stats.last_purchase = timestamp
                logger.debug(f"Purchase event: user={user_id}, amount=${float(amount):.2f}")
            
            # Calculate engagement score (simple formula for now)
            # Phase 5 will have more sophisticated ML-based scoring
            stats.engagement_score = min(
                100.0,
                (stats.total_events * 0.5) + (stats.total_purchases * 5.0)
            )
            
            # Step 6: Commit transaction
            db.commit()
            
            logger.info(f"✅ Event stored: {event_id} (Type: {event_type}, User: {user_id})")
            return event_id
        
        except IntegrityError as e:
            db.rollback()
            logger.error(f"❌ Integrity error (duplicate key?): {e}")
            
            # Check if it's a duplicate event_id
            if "unique constraint" in str(e).lower() or "duplicate key" in str(e).lower():
                logger.warning(f"Likely duplicate event_id: {event_data.get('event_id')}")
                return None
            raise
        
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"❌ Database error: {e}")
            raise
        
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Error storing event: {e}")
            raise
    
    @staticmethod
    def log_dead_letter(
        db: Session,
        event_data: Dict[str, Any],
        error_message: str,
        error_type: str,
        status: str = "pending"
    ) -> bool:
        """
        Log failed event to Dead Letter Queue for debugging.
        
        Args:
            db: Database session
            event_data: Event that failed
            error_message: Error details
            error_type: Exception class name
            status: "pending" (needs retry) or "dead" (given up)
        
        Returns:
            True if logged successfully, False otherwise
        
        DLQ Purpose:
        - Capture errors for analysis
        - Enable manual retry/replay
        - Compliance: audit trail of failures
        - Alert triggers when errors occur
        
        AWS Integration:
        - CloudWatch can query DLQ table
        - SNS alerts for new DLQ entries
        - Lambda can auto-retry promising entries
        
        Example DLQ Entry:
        {
            "event_id": "evt_001",
            "error_type": "ValueError",
            "error_message": "Missing required fields: {'amount'}",
            "status": "pending",
            "retry_count": 0,
            "created_at": "2024-01-15T10:30:00"
        }
        """
        try:
            dlq_entry = DeadLetterQueue(
                event_id=event_data.get("event_id"),
                event_data=event_data,  # Store full event for replay
                error_message=error_message,
                error_type=error_type,
                status=status,
                retry_count=0,
            )
            db.add(dlq_entry)
            db.commit()
            
            logger.warning(f"📋 Event logged to DLQ: {event_data.get('event_id')} "
                          f"({error_type})")
            return True
        
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to log to DLQ: {e}")
            return False
    
    @staticmethod
    def get_user_stats(db: Session, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user statistics.
        
        Args:
            db: Database session
            user_id: User ID
        
        Returns:
            Dictionary with user stats or None
        
        Used by Phase 4 API to return user analytics.
        """
        try:
            stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
            
            if not stats:
                return None
            
            return {
                "user_id": user_id,
                "total_events": stats.total_events,
                "total_purchases": stats.total_purchases,
                "total_spent": float(stats.total_spent),
                "last_active": stats.last_active.isoformat() if stats.last_active else None,
                "last_purchase": stats.last_purchase.isoformat() if stats.last_purchase else None,
                "avg_session_duration": stats.avg_session_duration,
                "engagement_score": stats.engagement_score,
                "churn_risk": stats.churn_risk,
            }
        
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            return None
    
    @staticmethod
    def get_user_profile(db: Session, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get complete user profile (info + stats).
        
        Used by Phase 4 API dashboard.
        """
        try:
            user = db.query(User).filter(User.user_id == user_id).first()
            
            if not user:
                return None
            
            stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
            
            profile = {
                "user_id": user.user_id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "country": user.country,
                "is_active": user.is_active,
                "signup_date": user.signup_date.isoformat() if user.signup_date else None,
                "created_at": user.created_at.isoformat(),
            }
            
            if stats:
                profile["stats"] = {
                    "total_events": stats.total_events,
                    "total_purchases": stats.total_purchases,
                    "total_spent": float(stats.total_spent),
                    "engagement_score": stats.engagement_score,
                    "churn_risk": stats.churn_risk,
                }
            
            return profile
        
        except Exception as e:
            logger.error(f"Error fetching profile: {e}")
            return None
    
    @staticmethod
    def get_dlq_summary(db: Session) -> Dict[str, Any]:
        """
        Get summary of dead letter queue.
        
        Useful for monitoring dashboard.
        
        Returns:
            {
                "total_failed": int,
                "by_error_type": {error_type: count},
                "recent_entries": [list of recent failures]
            }
        """
        try:
            from sqlalchemy import func
            
            total_failed = db.query(func.count(DeadLetterQueue.id)).scalar()
            
            errors_by_type = db.query(
                DeadLetterQueue.error_type,
                func.count(DeadLetterQueue.id).label("count")
            ).group_by(DeadLetterQueue.error_type).all()
            
            recent = db.query(DeadLetterQueue).order_by(
                DeadLetterQueue.created_at.desc()
            ).limit(10).all()
            
            return {
                "total_failed": total_failed,
                "by_error_type": {error: count for error, count in errors_by_type},
                "recent_entries": [
                    {
                        "event_id": e.event_id,
                        "error_type": e.error_type,
                        "created_at": e.created_at.isoformat(),
                    }
                    for e in recent
                ]
            }
        
        except Exception as e:
            logger.error(f"Error getting DLQ summary: {e}")
            return {"error": str(e)}


# ============================================================================
# Statistics Calculation Examples (for Phase 3 Stream Processing)
# ============================================================================

"""
Real-Time Statistics Being Calculated:
1. total_events: Incremented on every event
2. total_purchases: Incremented on purchase events
3. total_spent: Sum of purchase amounts
4. last_active: Updated to latest event timestamp
5. avg_session_duration: Running average of session durations
6. engagement_score: Derived from activity (Phase 3 will enhance)
7. churn_risk: ML prediction (Phase 5)

Example Queries (Phase 4 API):
1. Top 10 customers by spending:
   SELECT user_id, total_spent FROM user_stats 
   ORDER BY total_spent DESC LIMIT 10

2. At-risk users (no activity in 30 days):
   SELECT u.user_id FROM users u
   JOIN user_stats us ON u.user_id = us.user_id
   WHERE us.last_active < NOW() - INTERVAL '30 days'

3. High-engagement users (engagement_score > 50):
   SELECT user_id, engagement_score FROM user_stats
   WHERE engagement_score > 50

4. Recent purchasers:
   SELECT user_id, last_purchase, total_spent 
   FROM user_stats
   WHERE last_purchase > NOW() - INTERVAL '7 days'
   ORDER BY last_purchase DESC
"""