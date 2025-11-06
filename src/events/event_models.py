"""
Event data models using Pydantic for validation and serialization.
These models define the structure of all events flowing through Kafka.

Phase 1: Foundation
"""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import uuid


class EventType(str, Enum):
    """All possible event types in the system"""
    LOGIN = "login"
    LOGOUT = "logout"
    PAGE_VIEW = "page_view"
    CLICK = "click"
    PURCHASE = "purchase"
    VIDEO_WATCH = "video_watch"
    SEARCH = "search"
    CART_ADD = "cart_add"
    CART_REMOVE = "cart_remove"
    SHARE = "share"


class DeviceType(str, Enum):
    """Device types for events"""
    WEB = "web"
    MOBILE = "mobile"
    TABLET = "tablet"
    DESKTOP = "desktop"


class UserEvent(BaseModel):
    """
    Core user event model.
    Every event in the system follows this structure.
    
    This is the foundation of all events. Specialized events
    inherit from this class and add specific fields.
    """
    
    # Core identifiers
    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique event ID"
    )
    user_id: str = Field(..., description="Unique user identifier")
    session_id: str = Field(..., description="Session identifier")
    
    # Event details
    event_type: EventType = Field(..., description="Type of event")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Event timestamp (UTC)"
    )
    
    # User context
    device: DeviceType = Field(default=DeviceType.WEB, description="Device type")
    country: str = Field(default="IN", description="Country code (ISO 3166)")
    ip_address: Optional[str] = Field(default=None, description="User IP address")
    
    # Event-specific data
    page: Optional[str] = Field(default=None, description="Page URL or identifier")
    referrer: Optional[str] = Field(default=None, description="Referrer page")
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Duration in seconds (for watch/session events)"
    )
    value: Optional[float] = Field(default=None, description="Monetary value (for purchases)")
    currency: Optional[str] = Field(default="USD", description="Currency code")
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional event data"
    )
    
    # Validation
    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v):
        """User ID must not be empty"""
        if not v or len(v.strip()) == 0:
            raise ValueError("user_id cannot be empty")
        return v
    
    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v):
        """Session ID must not be empty"""
        if not v or len(v.strip()) == 0:
            raise ValueError("session_id cannot be empty")
        return v
    
    @field_validator('value')
    @classmethod
    def validate_value(cls, v):
        """Value must be positive if provided"""
        if v is not None and v < 0:
            raise ValueError("value cannot be negative")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user_00001",
                "session_id": "sess_abc123xyz",
                "event_type": "purchase",
                "timestamp": "2024-01-15T10:30:45.123456Z",
                "device": "mobile",
                "country": "IN",
                "page": "/checkout",
                "value": 99.99,
                "currency": "USD",
                "metadata": {"product_id": "prod_123", "quantity": 2}
            }
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Kafka serialization"""
        return self.model_dump(mode='json')
    
    def __str__(self) -> str:
        """String representation"""
        return f"UserEvent(user={self.user_id}, type={self.event_type}, ts={self.timestamp})"


class PurchaseEvent(UserEvent):
    """
    Specialized event for purchases.
    Extends UserEvent with purchase-specific fields.
    """
    
    event_type: EventType = Field(default=EventType.PURCHASE)
    value: float = Field(..., description="Purchase amount (required)")
    currency: str = Field(default="USD", description="Currency code")
    product_id: str = Field(..., description="Product identifier")
    quantity: int = Field(default=1, description="Quantity purchased")
    category: Optional[str] = Field(default=None, description="Product category")
    
    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v):
        """Quantity must be positive"""
        if v <= 0:
            raise ValueError("quantity must be greater than 0")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user_00001",
                "session_id": "sess_abc123xyz",
                "event_type": "purchase",
                "timestamp": "2024-01-15T10:30:45.123456Z",
                "device": "mobile",
                "country": "IN",
                "value": 2499.99,
                "currency": "INR",
                "product_id": "prod_laptop_001",
                "quantity": 1,
                "category": "electronics"
            }
        }


class VideoWatchEvent(UserEvent):
    """
    Specialized event for video watching.
    Tracks video consumption metrics.
    """
    
    event_type: EventType = Field(default=EventType.VIDEO_WATCH)
    video_id: str = Field(..., description="Video identifier")
    duration_seconds: float = Field(..., description="Watch duration (required)")
    watched_percentage: float = Field(..., description="Percentage of video watched (0-100)")
    video_duration: float = Field(..., description="Total video duration in seconds")
    
    @field_validator('watched_percentage')
    @classmethod
    def validate_watched_percentage(cls, v):
        """Watched percentage must be between 0 and 100"""
        if not 0 <= v <= 100:
            raise ValueError("watched_percentage must be between 0 and 100")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user_00001",
                "session_id": "sess_abc123xyz",
                "event_type": "video_watch",
                "timestamp": "2024-01-15T10:30:45.123456Z",
                "device": "web",
                "country": "IN",
                "video_id": "vid_kafka_tutorial",
                "duration_seconds": 1200,
                "watched_percentage": 85.5,
                "video_duration": 3600
            }
        }


class ClickEvent(UserEvent):
    """
    Specialized event for clicks.
    Tracks UI interactions.
    """
    
    event_type: EventType = Field(default=EventType.CLICK)
    element_id: str = Field(..., description="Element identifier that was clicked")
    element_type: str = Field(..., description="Type of element (button, link, image, etc.)")
    x_coordinate: Optional[int] = Field(default=None, description="X coordinate on screen")
    y_coordinate: Optional[int] = Field(default=None, description="Y coordinate on screen")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user_00001",
                "session_id": "sess_abc123xyz",
                "event_type": "click",
                "timestamp": "2024-01-15T10:30:45.123456Z",
                "device": "mobile",
                "country": "IN",
                "element_id": "btn_purchase",
                "element_type": "button",
                "x_coordinate": 150,
                "y_coordinate": 250
            }
        }


class SearchEvent(UserEvent):
    """
    Specialized event for searches.
    Tracks user search queries and results.
    """
    
    event_type: EventType = Field(default=EventType.SEARCH)
    query: str = Field(..., description="Search query string")
    results_count: int = Field(default=0, description="Number of results returned")
    category: Optional[str] = Field(default=None, description="Search category")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user_00001",
                "session_id": "sess_abc123xyz",
                "event_type": "search",
                "timestamp": "2024-01-15T10:30:45.123456Z",
                "device": "web",
                "country": "IN",
                "query": "python kafka tutorial",
                "results_count": 1250,
                "category": "videos"
            }
        }


class EventBatch(BaseModel):
    """
    Batch of multiple events for efficient processing.
    Useful for batch operations.
    """
    
    batch_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique batch ID"
    )
    events: list[UserEvent] = Field(..., description="List of events")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Batch creation time"
    )
    
    def to_list(self) -> list[Dict[str, Any]]:
        """Convert batch to list of dictionaries"""
        return [event.to_dict() for event in self.events]
    
    def __str__(self) -> str:
        """String representation"""
        return f"EventBatch(id={self.batch_id}, events={len(self.events)}, created={self.created_at})"