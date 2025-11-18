"""SQLAlchemy ORM models for database.

This module defines the database schema using SQLAlchemy ORM.
All models are designed for AWS RDS PostgreSQL with performance indexes.

Industry Use Case: E-commerce SaaS Analytics
- Track user clicks, purchases, video watches, searches
- Calculate KPIs: revenue, user engagement, churn prediction
- Store raw events for compliance (GDPR retention)
"""
from datetime import datetime, timezone  # ✅ FIXED: Added timezone import
from decimal import Decimal  # ✅ FIXED: Added Decimal import
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, JSON, 
    ForeignKey, Index, Boolean, Numeric, BigInteger
)
from sqlalchemy.orm import declarative_base  # ✅ FIXED: Modern import path
from sqlalchemy.orm import relationship
import uuid

Base = declarative_base()


class User(Base):
    """
    User model - stores customer information.
    
    Fields:
        id: Internal UUID (Primary Key)
        user_id: External identifier (from producer)
        email: User email (unique, queryable)
        first_name, last_name: User name
        country: Geographic location
        signup_date: Account creation date
        is_active: Current status
        created_at, updated_at: Audit timestamps
    
    Indexes:
        - user_id: Fast lookups by external ID
        - email: Prevent duplicates, enable email searches
        - created_at: Time-series queries
    
    AWS Considerations:
        - UUID primary key avoids sequential IDs (security)
        - user_id indexed (most common query pattern)
        - Soft deletes via is_active (GDPR compliance)
    """
    __tablename__ = "users"

    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # External Identifier
    user_id = Column(String(100), unique=True, nullable=False, index=True)
    
    # User Information
    email = Column(String(255), unique=True, nullable=True, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    country = Column(String(50), nullable=True, index=True)  # For geo analytics
    
    # Account Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    signup_date = Column(DateTime, nullable=True)
    
    # Audit Fields
    # ✅ FIXED: Changed from datetime.utcnow to datetime.now(timezone.utc)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    events = relationship("UserEvent", back_populates="user", cascade="all, delete-orphan")
    stats = relationship("UserStats", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    # Composite Indexes for common queries
    __table_args__ = (
        Index("idx_user_created_at", "created_at"),
        Index("idx_user_email_active", "email", "is_active"),
        Index("idx_user_country_active", "country", "is_active"),
    )

    def __repr__(self):
        return f"<User(user_id={self.user_id}, email={self.email})>"


class UserEvent(Base):
    """
    User event model - immutable event log.
    
    Fields:
        id: Internal UUID
        event_id: External event identifier (from producer)
        user_id: Foreign key to user
        event_type: click, purchase, view, search, login, logout
        timestamp: When event occurred (server time)
        duration: Duration in seconds (for video/session events)
        event_metadata: JSON for flexible event properties (renamed from 'metadata')
        created_at: When record was inserted
    
    Design Patterns:
        - Immutable: Events are never updated (append-only log)
        - Partitionable: timestamp used for table partitioning (Phase 6)
        - Searchable: Composite indexes on user_id + timestamp
    
    AWS Considerations:
        - Time-series data: partition by created_at monthly
        - event_id: Prevents duplicate processing (idempotency)
        - Composite index: Optimize "get user events in date range"
        - JSON event_metadata: Store event-specific data without schema changes
    
    Example Events:
        - Click: {page: "product", section: "recommendations"}
        - Purchase: {product_id: "123", amount: 99.99, currency: "USD"}
        - View: {video_id: "456", duration: 3600}
        - Search: {query: "laptop", results: 145}
    """
    __tablename__ = "user_events"

    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Event Identifiers
    event_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(String(100), ForeignKey("users.user_id"), nullable=False, index=True)
    
    # Event Classification
    event_type = Column(String(50), nullable=False, index=True)  # click, purchase, view, etc.
    
    # Event Timing
    timestamp = Column(DateTime, nullable=False, index=True)  # When event occurred
    duration = Column(Float, nullable=True)  # Event duration in seconds
    
    # Flexible Event Data (renamed from 'metadata' to avoid SQLAlchemy conflict)
    event_metadata = Column(JSON, nullable=True)  # {page: "home", section: "header", ...}
    
    # Audit
    # ✅ FIXED: Changed from datetime.utcnow to datetime.now(timezone.utc)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="events")
    
    # Composite indexes for common query patterns
    __table_args__ = (
        # "Get all events for user during time period"
        Index("idx_event_user_timestamp", "user_id", "timestamp"),
        # "Get all events of type during time period"
        Index("idx_event_type_timestamp", "event_type", "timestamp"),
        # "Find specific event quickly"
        Index("idx_event_id_user", "event_id", "user_id"),
    )

    def __repr__(self):
        return f"<UserEvent(event_id={self.event_id}, event_type={self.event_type})>"


class UserStats(Base):
    """
    Aggregated user statistics - real-time KPIs.
    
    Fields:
        user_id: Foreign key to user (unique, one-to-one)
        total_events: Count of all events
        total_purchases: Count of purchase events
        total_spent: Sum of purchase amounts (USD)
        last_active: Most recent event timestamp
        last_purchase: Most recent purchase timestamp
        avg_session_duration: Running average
        engagement_score: 0-100 (Phase 3)
        churn_risk: 0.0-1.0 (Phase 5 ML)
    
    Purpose:
        - Cache for fast queries (no aggregation needed)
        - Dashboard data (KPIs update in real-time)
        - Churn prediction input (Phase 5)
    
    Update Strategy:
        - Updated via trigger or application logic
        - Always consistent with user_events table
        - Can be rebuilt from user_events if needed
    
    AWS Considerations:
        - Single row per user (fast lookup)
        - Updated frequently (consider Redis cache Phase 3)
        - Good candidate for ElastiCache (Phase 6)
        - Include engagement_score for personalization
    
    KPI Examples:
        - total_spent > 500: High-value customer
        - days_since_last_active > 30: At-risk customer
        - total_purchases > 10: Loyal customer
    """
    __tablename__ = "user_stats"

    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign Key (unique = one-to-one relationship)
    user_id = Column(String(100), ForeignKey("users.user_id"), unique=True, nullable=False, index=True)
    
    # Event Aggregates
    total_events = Column(Integer, default=0, nullable=False)
    total_purchases = Column(Integer, default=0, nullable=False)
    total_spent = Column(Numeric(10, 2), default=Decimal('0.00'), nullable=False)  # ✅ FIXED: Decimal default
    
    # Time-based Metrics
    last_active = Column(DateTime, nullable=True, index=True)
    last_purchase = Column(DateTime, nullable=True, index=True)
    
    # Behavioral Metrics
    avg_session_duration = Column(Float, default=0.0, nullable=False)
    engagement_score = Column(Float, default=0.0, nullable=False)  # 0-100, Phase 3
    
    # ML Prediction (Phase 5)
    churn_risk = Column(Float, default=0.0, nullable=False)  # 0.0-1.0 probability
    
    # Audit
    # ✅ FIXED: Changed from datetime.utcnow to datetime.now(timezone.utc)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationships
    user = relationship("User", back_populates="stats")
    
    __table_args__ = (
        Index("idx_stats_last_active", "last_active"),
        Index("idx_stats_churn_risk", "churn_risk"),  # For "at-risk users" queries
    )

    def __repr__(self):
        return f"<UserStats(user_id={self.user_id}, total_spent=${self.total_spent})>"


class DeadLetterQueue(Base):
    """
    Dead Letter Queue (DLQ) - failed event storage.
    
    Purpose:
        - Capture events that failed processing
        - Enable debugging and analysis
        - Support retry mechanisms
        - Compliance (audit trail)
    
    Fields:
        event_id: Original event identifier
        event_data: Full event payload (JSON)
        error_message: Error details
        error_type: Exception class name
        retry_count: Number of retry attempts
        status: pending, retrying, dead, resolved
        created_at, updated_at: Timestamps
    
    Workflow:
        1. Event fails to process → logged to DLQ (status: pending)
        2. Retry service attempts → status: retrying
        3. After max retries → status: dead (alerts triggered)
        4. Manual resolution → status: resolved
    
    AWS Considerations:
        - Archive old DLQ entries to S3 (Phase 6)
        - CloudWatch alerts on DLQ entries
        - Use for incident investigation
        - Monitor error types for patterns
    
    Example Errors:
        - ValueError: Missing required fields
        - SQLAlchemyError: Database connection lost
        - JSONDecodeError: Malformed event
        - UniqueViolationError: Duplicate event_id
    """
    __tablename__ = "dead_letter_queue"

    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Original Event Info
    event_id = Column(String(100), nullable=True, index=True)
    event_data = Column(JSON, nullable=False)  # Full event for manual replay
    
    # Error Details
    error_message = Column(Text, nullable=False)
    error_type = Column(String(100), nullable=False, index=True)
    
    # Retry Information
    retry_count = Column(Integer, default=0, nullable=False)
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending, retrying, dead, resolved
    
    # Audit
    # ✅ FIXED: Changed from datetime.utcnow to datetime.now(timezone.utc)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index("idx_dlq_created_at", "created_at"),
        Index("idx_dlq_status_created", "status", "created_at"),  # Find recent dead letters
    )

    def __repr__(self):
        return f"<DeadLetterQueue(event_id={self.event_id}, error_type={self.error_type})>"


# Summary of Relationships
"""
User (1) ──────── (Many) UserEvent
  │
  └────── (1) UserStats

DeadLetterQueue is independent (stores failed events)

Query Examples (Phase 4 API):
1. Get user profile with stats:
   SELECT u.*, us.* FROM users u 
   LEFT JOIN user_stats us ON u.user_id = us.user_id 
   WHERE u.user_id = 'user123'

2. Get user activity timeline:
   SELECT * FROM user_events 
   WHERE user_id = 'user123' 
   ORDER BY timestamp DESC 
   LIMIT 100

3. Get high-value customers (top 10 by spending):
   SELECT us.user_id, us.total_spent, us.total_purchases 
   FROM user_stats us 
   ORDER BY us.total_spent DESC 
   LIMIT 10

4. Find at-risk customers (no activity in 30 days):
   SELECT u.user_id, us.last_active 
   FROM user_stats us 
   JOIN users u ON us.user_id = u.user_id 
   WHERE us.last_active < NOW() - INTERVAL '30 days' 
   AND u.is_active = true

5. Monitor failed events:
   SELECT error_type, COUNT(*) as count 
   FROM dead_letter_queue 
   WHERE created_at > NOW() - INTERVAL '1 hour' 
   GROUP BY error_type
"""