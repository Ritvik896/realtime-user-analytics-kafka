"""
Main Kafka producer for user events using confluent-kafka.
Sends mock user events to Kafka topics in real-time with proper error handling.

Phase 1: Foundation
"""

import json
import logging
import time
from typing import Optional, Dict, Any
from confluent_kafka import Producer, KafkaException
from datetime import datetime
from src.events.event_models import UserEvent
from src.events.event_generator import UserEventGenerator
from config.logging_config import setup_logging
from config.constants import KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC_EVENTS

# Setup logging
logger = setup_logging(__name__)


class UserEventProducer:
    """
    Produces user events to Kafka using confluent-kafka.
    
    Features:
    - Reliable message delivery
    - Error handling and logging
    - Performance metrics tracking
    - Rate limiting support
    - Batch processing
    """
    
    def __init__(
        self,
        bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS,
        topic: str = KAFKA_TOPIC_EVENTS,
    ):
        """
        Initialize the producer.
        
        Args:
            bootstrap_servers: Kafka bootstrap servers (comma-separated)
            topic: Topic to produce to
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        
        # Metrics tracking
        self.events_sent = 0
        self.events_failed = 0
        self.total_bytes_sent = 0
        self.start_time = None
        
        # Initialize Kafka producer
        self.producer = self._create_producer()
        logger.info(f"Producer initialized for topic: {topic} | Servers: {bootstrap_servers}")
    
    def _create_producer(self) -> Producer:
        """
        Create and configure Kafka producer with reliability settings.
        
        Returns:
            Configured Producer instance
        """
        producer_config = {
            'bootstrap.servers': self.bootstrap_servers,
            'client.id': 'user-event-producer',
            'acks': 'all',
            'retries': 3,
            'compression.type': 'snappy',
            'message.max.bytes': 1000000,
        }
        
        return Producer(producer_config)
    
    def _delivery_report(self, err, msg):
        """
        Callback for delivery reports.
        
        Args:
            err: Error if any
            msg: Message that was delivered
        """
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
            self.events_failed += 1
        else:
            self.events_sent += 1
            self.total_bytes_sent += len(msg.value())
            
            if self.events_sent % 100 == 0:
                logger.debug(
                    f"Events sent: {self.events_sent} | "
                    f"Topic: {msg.topic()} | "
                    f"Partition: {msg.partition()} | "
                    f"Offset: {msg.offset()}"
                )
    
    def send_event(self, event: UserEvent) -> bool:
        """
        Send a single user event to Kafka.
        
        Args:
            event: UserEvent to send
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            event_dict = event.to_dict()
            event_json = json.dumps(event_dict, default=str, ensure_ascii=False).encode('utf-8')
            
            # Send with delivery report callback
            self.producer.produce(
                self.topic,
                value=event_json,
                callback=self._delivery_report
            )
            
            # Poll to trigger callbacks
            self.producer.poll(0)
            
            return True
        
        except KafkaException as e:
            logger.error(f"Kafka error sending event: {e}")
            self.events_failed += 1
            return False
        
        except Exception as e:
            logger.error(f"Error sending event: {e}")
            self.events_failed += 1
            return False
    
    def send_batch(self, events: list[UserEvent]) -> int:
        """
        Send multiple events to Kafka.
        
        Args:
            events: List of UserEvent objects
        
        Returns:
            Number of events sent successfully
        """
        sent_count = 0
        for event in events:
            if self.send_event(event):
                sent_count += 1
        return sent_count
    
    def generate_and_send(
        self,
        event_count: int = 100,
        events_per_second: float = 10,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate and send events.
        
        Args:
            event_count: Number of events to generate and send
            events_per_second: Rate of event generation (default: 10/sec)
            user_id: Optional specific user (if None, random users)
        
        Returns:
            Dictionary with statistics
        """
        logger.info(
            f"Starting event generation: {event_count} events "
            f"at {events_per_second} events/sec"
        )
        
        self.start_time = time.time()
        interval = 1.0 / events_per_second if events_per_second > 0 else 0
        
        for i in range(event_count):
            # Generate event
            event = UserEventGenerator.generate_user_event(user_id=user_id)
            
            # Send event
            self.send_event(event)
            
            # Rate limiting
            if events_per_second > 0:
                elapsed = time.time() - self.start_time - (i * interval)
                if elapsed < 0:
                    time.sleep(-elapsed)
            
            # Progress logging
            if (i + 1) % 100 == 0:
                logger.info(f"Progress: {i + 1}/{event_count} events sent")
        
        # Ensure all messages are sent
        self.producer.flush(timeout=10)
        
        elapsed_time = time.time() - self.start_time
        
        stats = {
            "events_requested": event_count,
            "events_sent": self.events_sent,
            "events_failed": self.events_failed,
            "elapsed_seconds": round(elapsed_time, 2),
            "throughput_events_per_sec": round(
                self.events_sent / elapsed_time if elapsed_time > 0 else 0, 2
            ),
            "total_bytes_sent": self.total_bytes_sent,
            "success_rate": round(
                (self.events_sent / event_count * 100) if event_count > 0 else 0, 2
            )
        }
        
        logger.info(f"Generation complete!")
        logger.info(f"Stats: {stats}")
        return stats
    
    def continuous_stream(
        self,
        events_per_second: float = 10,
        duration_minutes: Optional[float] = None
    ):
        """
        Continuously generate and send events.
        Useful for long-running streams.
        
        Args:
            events_per_second: Rate of event generation
            duration_minutes: How long to run (None = infinite)
        """
        logger.info(
            f"Starting continuous stream: {events_per_second} events/sec "
            f"for {duration_minutes or 'infinite'} minutes"
        )
        
        self.start_time = time.time()
        end_time = None
        if duration_minutes:
            end_time = self.start_time + (duration_minutes * 60)
        
        interval = 1.0 / events_per_second
        event_count = 0
        
        try:
            while True:
                if end_time and time.time() >= end_time:
                    logger.info("Duration reached, stopping stream")
                    break
                
                # Generate and send event
                event = UserEventGenerator.generate_user_event()
                self.send_event(event)
                event_count += 1
                
                # Rate limiting
                time.sleep(interval)
                
                # Progress logging
                if event_count % 1000 == 0:
                    elapsed = time.time() - self.start_time
                    logger.info(
                        f"Streamed {event_count} events in {elapsed:.1f}s "
                        f"({event_count/elapsed:.1f} events/sec)"
                    )
        
        except KeyboardInterrupt:
            logger.info("Stream interrupted by user")
        
        finally:
            self.producer.flush(timeout=10)
            elapsed = time.time() - self.start_time
            logger.info(
                f"Stream stopped. Total events: {event_count}, "
                f"Duration: {elapsed:.1f}s"
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current producer statistics"""
        total = self.events_sent + self.events_failed
        success_rate = (self.events_sent / total * 100) if total > 0 else 0
        
        return {
            "events_sent": self.events_sent,
            "events_failed": self.events_failed,
            "total_events": total,
            "total_bytes_sent": self.total_bytes_sent,
            "success_rate": round(success_rate, 2)
        }
    
    def close(self):
        """Close the producer and release resources"""
        logger.info("Closing producer...")
        try:
            self.producer.flush(timeout=10)
            logger.info("Producer closed successfully")
        except Exception as e:
            logger.error(f"Error closing producer: {e}")


def main():
    """Main entry point for running the producer"""
    
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Kafka User Event Producer - Generate and send mock events"
    )
    parser.add_argument(
        "--bootstrap-servers",
        default=KAFKA_BOOTSTRAP_SERVERS,
        help=f"Kafka bootstrap servers (default: {KAFKA_BOOTSTRAP_SERVERS})"
    )
    parser.add_argument(
        "--topic",
        default=KAFKA_TOPIC_EVENTS,
        help=f"Topic to produce to (default: {KAFKA_TOPIC_EVENTS})"
    )
    parser.add_argument(
        "--events",
        type=int,
        default=1000,
        help="Number of events to generate (default: 1000)"
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=10,
        help="Events per second (default: 10)"
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuous stream instead of fixed count"
    )
    parser.add_argument(
        "--duration",
        type=float,
        help="Duration in minutes (for continuous mode)"
    )
    parser.add_argument(
        "--user-id",
        help="Specific user ID to generate events for (if not specified, random users)"
    )
    
    args = parser.parse_args()
    
    producer = UserEventProducer(
        bootstrap_servers=args.bootstrap_servers,
        topic=args.topic
    )
    
    try:
        if args.continuous:
            producer.continuous_stream(
                events_per_second=args.rate,
                duration_minutes=args.duration
            )
        else:
            stats = producer.generate_and_send(
                event_count=args.events,
                events_per_second=args.rate,
                user_id=args.user_id
            )
            print("\n" + "="*50)
            print("PRODUCTION SUMMARY")
            print("="*50)
            for key, value in stats.items():
                print(f"{key:.<30} {value}")
            print("="*50)
    
    finally:
        producer.close()


if __name__ == "__main__":
    main()