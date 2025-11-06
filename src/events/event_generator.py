"""
Mock event generator for simulating real user behavior.
Generates realistic user activity without needing real users or IoT hardware.

Phase 1: Foundation
"""

import random
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from src.events.event_models import (
    UserEvent, PurchaseEvent, VideoWatchEvent, ClickEvent, SearchEvent,
    EventType, DeviceType
)


class UserEventGenerator:
    """
    Generates realistic mock user events for testing and learning.
    Simulates various user behaviors and interactions.
    
    This is completely mock data - no real users or hardware needed!
    """
    
    # Sample data for realistic simulation
    USERS = [f"user_{i:05d}" for i in range(1, 51)]  # 50 test users
    
    PAGES = [
        "/", "/dashboard", "/products", "/cart", "/checkout",
        "/profile", "/settings", "/search", "/video", "/blog"
    ]
    
    COUNTRIES = ["IN", "US", "UK", "CA", "AU", "SG", "DE", "FR"]
    
    PRODUCTS = [
        {"id": "prod_001", "name": "Laptop", "category": "electronics", "price_range": (50000, 150000)},
        {"id": "prod_002", "name": "Phone", "category": "electronics", "price_range": (20000, 100000)},
        {"id": "prod_003", "name": "Headphones", "category": "electronics", "price_range": (2000, 15000)},
        {"id": "prod_004", "name": "Book", "category": "books", "price_range": (200, 1000)},
        {"id": "prod_005", "name": "T-Shirt", "category": "clothing", "price_range": (500, 2000)},
    ]
    
    VIDEOS = [
        {"id": "vid_001", "title": "Python Basics", "duration": 3600},
        {"id": "vid_002", "title": "Kafka Tutorial", "duration": 7200},
        {"id": "vid_003", "title": "DevOps Journey", "duration": 5400},
        {"id": "vid_004", "title": "ML Fundamentals", "duration": 4800},
    ]
    
    UI_ELEMENTS = [
        {"id": "btn_signin", "type": "button"},
        {"id": "btn_purchase", "type": "button"},
        {"id": "link_product", "type": "link"},
        {"id": "banner_promo", "type": "banner"},
    ]
    
    SEARCH_QUERIES = [
        "laptop", "phone", "headphones", "python", "kafka",
        "devops", "machine learning", "aws", "docker", "kubernetes"
    ]
    
    @classmethod
    def generate_user_event(
        cls,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        event_type: Optional[EventType] = None,
        timestamp: Optional[datetime] = None
    ) -> UserEvent:
        """
        Generate a random user event.
        
        Args:
            user_id: User ID (random if not provided)
            session_id: Session ID (random if not provided)
            event_type: Type of event (random if not provided)
            timestamp: Event timestamp (current time if not provided)
        
        Returns:
            UserEvent: Generated event
            
        Example:
            >>> event = UserEventGenerator.generate_user_event()
            >>> print(event.user_id, event.event_type)
            user_00001 login
        """
        
        if user_id is None:
            user_id = random.choice(cls.USERS)
        
        if session_id is None:
            session_id = f"sess_{uuid.uuid4().hex[:12]}"
        
        if event_type is None:
            event_type = random.choice(list(EventType))
        
        if timestamp is None:
            # Add some randomness: event from last 24 hours
            timestamp = datetime.utcnow() - timedelta(seconds=random.randint(0, 86400))
        
        base_event = {
            "user_id": user_id,
            "session_id": session_id,
            "event_type": event_type,
            "timestamp": timestamp,
            "device": random.choice(list(DeviceType)),
            "country": random.choice(cls.COUNTRIES),
            "page": random.choice(cls.PAGES),
            "ip_address": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"
        }
        
        # Add event-specific data based on event type
        if event_type == EventType.PURCHASE:
            product = random.choice(cls.PRODUCTS)
            price = random.uniform(*product["price_range"])
            return PurchaseEvent(
                **base_event,
                value=round(price, 2),
                currency="INR",
                product_id=product["id"],
                quantity=random.randint(1, 3),
                category=product["category"]
            )
        
        elif event_type == EventType.VIDEO_WATCH:
            video = random.choice(cls.VIDEOS)
            watched_seconds = random.randint(30, video["duration"])
            return VideoWatchEvent(
                **base_event,
                video_id=video["id"],
                duration_seconds=watched_seconds,
                watched_percentage=round((watched_seconds / video["duration"]) * 100, 2),
                video_duration=video["duration"]
            )
        
        elif event_type == EventType.CLICK:
            element = random.choice(cls.UI_ELEMENTS)
            return ClickEvent(
                **base_event,
                element_id=element["id"],
                element_type=element["type"],
                x_coordinate=random.randint(0, 1920),
                y_coordinate=random.randint(0, 1080)
            )
        
        elif event_type == EventType.SEARCH:
            return SearchEvent(
                **base_event,
                query=random.choice(cls.SEARCH_QUERIES),
                results_count=random.randint(0, 1000),
                category=random.choice(["products", "videos", "articles"])
            )
        
        else:
            # Generic event for LOGIN, LOGOUT, PAGE_VIEW, CART_ADD, etc.
            return UserEvent(**base_event)
    
    @classmethod
    def generate_batch(
        cls,
        count: int = 10,
        user_id: Optional[str] = None
    ) -> List[UserEvent]:
        """
        Generate a batch of events.
        
        Args:
            count: Number of events to generate
            user_id: Optional user ID (if None, events for random users)
        
        Returns:
            List of UserEvent objects
            
        Example:
            >>> events = UserEventGenerator.generate_batch(count=50)
            >>> print(len(events), "events generated")
            50 events generated
        """
        events = []
        for _ in range(count):
            event = cls.generate_user_event(user_id=user_id)
            events.append(event)
        return events
    
    @classmethod
    def generate_user_session(
        cls,
        user_id: Optional[str] = None,
        event_count: int = 20
    ) -> tuple[str, List[UserEvent]]:
        """
        Generate a realistic user session with multiple events.
        
        Sessions typically start with LOGIN and end with LOGOUT.
        Events are distributed across the session with realistic proportions.
        
        Args:
            user_id: User ID for the session (random if None)
            event_count: Number of events in the session
        
        Returns:
            Tuple of (session_id, list of events)
            
        Example:
            >>> session_id, events = UserEventGenerator.generate_user_session(event_count=15)
            >>> print(f"Session {session_id}: {len(events)} events")
            Session sess_abc123: 15 events
        """
        
        if user_id is None:
            user_id = random.choice(cls.USERS)
        
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        events = []
        
        # Sessions typically start sometime and last a while
        session_start = datetime.utcnow() - timedelta(hours=random.randint(1, 24))
        
        for i in range(event_count):
            # Spread events across the session duration (1 event every ~5 minutes)
            event_time = session_start + timedelta(minutes=i * 5)
            
            # Make sessions realistic: more page views, fewer purchases
            if i == 0:
                # First event is LOGIN
                event_type = EventType.LOGIN
            elif i == event_count - 1:
                # Last event is LOGOUT
                event_type = EventType.LOGOUT
            else:
                # Weighted distribution of events
                weights = {
                    EventType.PAGE_VIEW: 40,
                    EventType.CLICK: 30,
                    EventType.VIDEO_WATCH: 15,
                    EventType.SEARCH: 10,
                    EventType.PURCHASE: 5,
                }
                event_type = random.choices(
                    list(weights.keys()),
                    weights=list(weights.values())
                )[0]
            
            event = cls.generate_user_event(
                user_id=user_id,
                session_id=session_id,
                event_type=event_type,
                timestamp=event_time
            )
            events.append(event)
        
        return session_id, events
    
    @classmethod
    def generate_anomalous_event(
        cls,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> UserEvent:
        """
        Generate an anomalous event for testing anomaly detection (Phase 5).
        These are events that deviate significantly from normal user behavior.
        
        Anomaly types:
        - High-value purchase (fraud indicator)
        - Rapid bulk purchases
        - Unusual behavior patterns
        
        Args:
            user_id: User ID for the anomaly (random if None)
            session_id: Session ID (generated if None)
        
        Returns:
            An anomalous UserEvent
            
        Example:
            >>> anomaly = UserEventGenerator.generate_anomalous_event()
            >>> print(f"Anomaly: {anomaly.value} purchase (suspicious!)")
        """
        
        if user_id is None:
            user_id = random.choice(cls.USERS)
        
        if session_id is None:
            session_id = f"sess_{uuid.uuid4().hex[:12]}"
        
        # Anomaly types
        anomaly_type = random.choice([
            "high_value_purchase",
            "rapid_purchases",
            "unusual_location",
            "unusual_time"
        ])
        
        timestamp = datetime.utcnow()
        
        if anomaly_type == "high_value_purchase":
            # Extremely high-value purchase
            product = random.choice(cls.PRODUCTS)
            return PurchaseEvent(
                user_id=user_id,
                session_id=session_id,
                timestamp=timestamp,
                value=999999.99,  # Extremely high
                currency="INR",
                product_id=product["id"],
                quantity=100,  # Bulk
                category=product["category"],
                device=random.choice(list(DeviceType)),
                country=random.choice(cls.COUNTRIES),
                page="/checkout",
                metadata={"anomaly_score": 0.95}
            )
        
        elif anomaly_type == "rapid_purchases":
            # Multiple large purchases in one session
            product = random.choice(cls.PRODUCTS)
            return PurchaseEvent(
                user_id=user_id,
                session_id=session_id,
                timestamp=timestamp,
                value=random.uniform(50000, 100000),
                currency="INR",
                product_id=product["id"],
                quantity=random.randint(50, 200),
                category=product["category"],
                device=random.choice(list(DeviceType)),
                country=random.choice(cls.COUNTRIES),
                page="/checkout",
                metadata={"rapid_purchase": True, "anomaly_score": 0.85}
            )
        
        else:
            # Generic anomalous event
            return UserEvent(
                user_id=user_id,
                session_id=session_id,
                event_type=EventType.PAGE_VIEW,
                timestamp=timestamp,
                device=random.choice(list(DeviceType)),
                country=random.choice(cls.COUNTRIES),
                page="/anomaly",
                metadata={"anomaly_type": anomaly_type, "anomaly_score": 0.8}
            )
    
    @classmethod
    def get_sample_events_summary(cls) -> dict:
        """
        Get a summary of available sample data.
        
        Returns:
            Dictionary with counts of available samples
        """
        return {
            "users": len(cls.USERS),
            "pages": len(cls.PAGES),
            "countries": len(cls.COUNTRIES),
            "products": len(cls.PRODUCTS),
            "videos": len(cls.VIDEOS),
            "ui_elements": len(cls.UI_ELEMENTS),
            "search_queries": len(cls.SEARCH_QUERIES),
            "event_types": len(list(EventType)),
            "device_types": len(list(DeviceType))
        }