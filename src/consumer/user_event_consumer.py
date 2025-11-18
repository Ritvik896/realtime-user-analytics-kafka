"""Main consumer script - reads Kafka events and stores in database.

This is the entry point for Phase 2. It orchestrates:
1. Database initialization
2. Kafka consumer connection
3. Event processing loop
4. Statistics tracking
5. Graceful shutdown

Run with: python -m src.consumer.user_event_consumer

Production Deployment:
- AWS ECS: Run as containerized service
- AWS Lambda: Trigger via event source mapping
- Local: Run in Docker via docker-compose
"""
import time
import signal
import logging
import argparse
import sys
from typing import Optional
from src.consumer.kafka_consumer_service import KafkaConsumerService
from src.consumer.event_storage_service import EventStorageService
from src.database.connection import SessionLocal, init_db, check_db_health, get_db_stats

# ============================================================================
# Setup Logging
# ============================================================================

# Configure logging with more detail for production debugging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),  # Console output
        # Could add file handler here for production
    ]
)

logger = logging.getLogger(__name__)

# ============================================================================
# Consumer State
# ============================================================================

class ConsumerState:
    """Track consumer statistics."""
    
    def __init__(self):
        self.processed = 0
        self.failed = 0
        self.duplicates = 0
        self.dlq_logged = 0
        self.start_time = time.time()
    
    def get_stats(self) -> dict:
        """Get consumer statistics."""
        elapsed = time.time() - self.start_time
        throughput = self.processed / elapsed if elapsed > 0 else 0
        
        return {
            "processed": self.processed,
            "failed": self.failed,
            "duplicates": self.duplicates,
            "dlq_logged": self.dlq_logged,
            "elapsed_seconds": int(elapsed),
            "throughput_events_per_sec": round(throughput, 2),
            "total_events": self.processed + self.failed + self.duplicates,
        }
    
    def log_stats(self):
        """Log current statistics."""
        stats = self.get_stats()
        logger.info(f"📊 Consumer Stats:")
        logger.info(f"   Processed: {stats['processed']}")
        logger.info(f"   Failed: {stats['failed']}")
        logger.info(f"   Duplicates: {stats['duplicates']}")
        logger.info(f"   DLQ Entries: {stats['dlq_logged']}")
        logger.info(f"   Throughput: {stats['throughput_events_per_sec']} events/sec")
        logger.info(f"   Elapsed: {stats['elapsed_seconds']}s")


# Global state for signal handling
consumer_state = ConsumerState()
kafka_consumer: Optional[KafkaConsumerService] = None
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle SIGTERM and SIGINT gracefully."""
    global shutdown_requested
    
    signal_name = signal.Signals(signum).name
    logger.info(f"\n⏹️  Received {signal_name} signal, shutting down gracefully...")
    shutdown_requested = True


def check_dependencies() -> bool:
    """
    Check all dependencies are available.
    
    Returns:
        bool: True if all good, False otherwise
    """
    logger.info("🔍 Checking dependencies...")
    
    # Check database
    logger.info("   Checking database connection...")
    if not check_db_health():
        logger.error("   ❌ Database unavailable")
        return False
    logger.info("   ✅ Database OK")
    
    # Could add Kafka health check here
    logger.info("   ✅ All dependencies OK")
    return True


def main(
    bootstrap_servers: str = "localhost:9092",
    group_id: str = "analytics-consumer-group",
    topics: str = "user-events",
    auto_init_db: bool = True,
    stats_interval: int = 30,
    max_events: Optional[int] = None,
):
    """
    Main consumer loop.
    
    Args:
        bootstrap_servers: Kafka brokers (comma-separated)
        group_id: Consumer group ID
        topics: Kafka topics (comma-separated)
        auto_init_db: Initialize database at startup
        stats_interval: Log statistics every N seconds
        max_events: Max events to process (None = unlimited)
    
    Process Flow:
    1. Check dependencies
    2. Initialize database
    3. Connect to Kafka
    4. Consume and process events
    5. Handle errors gracefully
    6. Shutdown cleanly
    """
    global kafka_consumer, shutdown_requested
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info("🚀 Starting Realtime User Analytics Consumer (Phase 2)")
    logger.info(f"   Bootstrap servers: {bootstrap_servers}")
    logger.info(f"   Consumer group: {group_id}")
    logger.info(f"   Topics: {topics}")
    
    # ========================================================================
    # 1. Check Dependencies
    # ========================================================================
    
    if not check_dependencies():
        logger.error("❌ Dependency check failed")
        return False
    
    # ========================================================================
    # 2. Initialize Database
    # ========================================================================
    
    if auto_init_db:
        logger.info("🔨 Initializing database...")
        try:
            if not check_db_health():
                logger.error("Database health check failed!")
                return False
            init_db()
            logger.info("✅ Database initialized")
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            return False
    
    # ========================================================================
    # 3. Create and Connect Kafka Consumer
    # ========================================================================
    
    kafka_consumer = KafkaConsumerService(
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        topics=topics.split(",")  # Support multiple topics
    )
    
    if not kafka_consumer.connect():
        logger.error("❌ Failed to connect to Kafka")
        return False
    
    logger.info("✅ Connected to Kafka")
    
    # ========================================================================
    # 4. Main Consumption Loop
    # ========================================================================
    
    logger.info("🎯 Consumer ready. Listening for events...")
    logger.info("   Press Ctrl+C to shutdown gracefully")
    
    last_stats_time = time.time()
    
    try:
        while not shutdown_requested:
            # Log statistics periodically
            current_time = time.time()
            if current_time - last_stats_time >= stats_interval:
                consumer_state.log_stats()
                
                # Log pool statistics
                try:
                    db_stats = get_db_stats()
                    logger.info(f"   DB Pool: checked_in={db_stats.get('checkedin')}, "
                               f"checked_out={db_stats.get('checked_out')}")
                except Exception as e:
                    logger.debug(f"Error getting DB stats: {e}")
                
                last_stats_time = current_time
            
            # Check if max events reached
            if max_events and consumer_state.processed >= max_events:
                logger.info(f"✅ Reached max events limit: {max_events}")
                break
            
            # ================================================================
            # Consume Message
            # ================================================================
            
            msg = kafka_consumer.consume_message(timeout_ms=1000)
            
            if msg is None:
                continue
            
            # ================================================================
            # Process Message
            # ================================================================
            
            db_session = None
            try:
                # Get database session
                db_session = SessionLocal()
                
                # Store event (this handles validation, user creation, stats update)
                event_id = EventStorageService.store_event(db_session, msg["value"])
                
                if event_id:
                    # Commit offset only after successful storage (exactly-once semantics)
                    if kafka_consumer.commit_offset(msg):
                        consumer_state.processed += 1
                    else:
                        logger.warning(f"Failed to commit offset for {event_id}")
                        consumer_state.failed += 1
                else:
                    # Event was duplicate (already processed)
                    consumer_state.duplicates += 1
                    kafka_consumer.commit_offset(msg)  # Still advance offset
            
            except ValueError as e:
                # Validation error
                logger.warning(f"⚠️  Validation error: {e}")
                db_session = SessionLocal()
                EventStorageService.log_dead_letter(
                    db_session,
                    msg["value"],
                    str(e),
                    "ValueError",
                    status="pending"
                )
                consumer_state.dlq_logged += 1
                consumer_state.failed += 1
                kafka_consumer.commit_offset(msg)
            
            except Exception as e:
                # Unexpected error
                logger.error(f"❌ Error processing event: {e}")
                
                # Log to dead letter queue
                try:
                    if db_session is None:
                        db_session = SessionLocal()
                    EventStorageService.log_dead_letter(
                        db_session,
                        msg["value"],
                        str(e),
                        type(e).__name__,
                        status="pending"
                    )
                    consumer_state.dlq_logged += 1
                except Exception as dlq_error:
                    logger.error(f"Failed to log to DLQ: {dlq_error}")
                
                consumer_state.failed += 1
                
                # Still commit offset to move forward (don't get stuck)
                # DLQ entry allows manual replay
                kafka_consumer.commit_offset(msg)
            
            finally:
                # Always close session
                if db_session:
                    db_session.close()
    
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received")
    
    except Exception as e:
        logger.error(f"❌ Unexpected error in main loop: {e}", exc_info=True)
        return False
    
    finally:
        # ====================================================================
        # Graceful Shutdown
        # ====================================================================
        
        logger.info("\n" + "="*70)
        logger.info("🛑 SHUTDOWN SEQUENCE")
        logger.info("="*70)
        
        # Final statistics
        logger.info("📊 Final Statistics:")
        consumer_state.log_stats()
        
        # Close Kafka consumer
        if kafka_consumer:
            kafka_consumer.close()
        
        logger.info("✅ Consumer shutdown complete")
    
    return True


# ============================================================================
# CLI Interface
# ============================================================================

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Realtime User Analytics Consumer (Phase 2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (connect to local Kafka)
  python -m src.consumer.user_event_consumer
  
  # Connect to AWS MSK
  python -m src.consumer.user_event_consumer \\
    --bootstrap-servers b-1.msk.xxxxx.kafka.us-east-1.amazonaws.com:9092,\\
b-2.msk.xxxxx.kafka.us-east-1.amazonaws.com:9092
  
  # Custom consumer group
  python -m src.consumer.user_event_consumer --group-id my-analytics-group
  
  # Process only 100 events (for testing)
  python -m src.consumer.user_event_consumer --max-events 100
        """
    )
    
    parser.add_argument(
        "--bootstrap-servers",
        default="localhost:9092",
        help="Kafka bootstrap servers (comma-separated for multiple brokers)"
    )
    
    parser.add_argument(
        "--group-id",
        default="analytics-consumer-group",
        help="Consumer group ID (multiple consumers with same ID share load)"
    )
    
    parser.add_argument(
        "--topics",
        default="user-events",
        help="Kafka topics to consume (comma-separated)"
    )
    
    parser.add_argument(
        "--no-auto-init",
        action="store_true",
        help="Don't auto-initialize database (use existing schema)"
    )
    
    parser.add_argument(
        "--stats-interval",
        type=int,
        default=30,
        help="Log statistics every N seconds"
    )
    
    parser.add_argument(
        "--max-events",
        type=int,
        default=None,
        help="Stop after processing N events (useful for testing)"
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    
    success = main(
        bootstrap_servers=args.bootstrap_servers,
        group_id=args.group_id,
        topics=args.topics,
        auto_init_db=not args.no_auto_init,
        stats_interval=args.stats_interval,
        max_events=args.max_events,
    )
    
    sys.exit(0 if success else 1)


# ============================================================================
# Docker Compose Integration
# ============================================================================

"""
Add this to docker-compose.yml for Phase 2:

  consumer:
    build: .
    image: realtime-analytics:latest
    command: python -m src.consumer.user_event_consumer
    environment:
      - KAFKA_BOOTSTRAP_SERVERS=kafka:29092
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/realtime_analytics
      - LOG_LEVEL=INFO
    depends_on:
      - kafka
      - postgres
    restart: unless-stopped
    networks:
      - realtime-analytics

Then run:
  docker-compose up consumer
"""

# ============================================================================
# AWS ECS Task Definition
# ============================================================================

"""
For ECS deployment, create task definition with:

{
  "family": "realtime-analytics-consumer",
  "containerDefinitions": [{
    "name": "consumer",
    "image": "ACCOUNT.dkr.ecr.REGION.amazonaws.com/realtime-analytics:latest",
    "command": ["python", "-m", "src.consumer.user_event_consumer"],
    "environment": [
      {
        "name": "KAFKA_BOOTSTRAP_SERVERS",
        "value": "b-1.msk.xxxxx.kafka.REGION.amazonaws.com:9092,b-2.msk.xxxxx.kafka.REGION.amazonaws.com:9092"
      },
      {
        "name": "DATABASE_URL",
        "value": "postgresql://username:password@rds-instance.REGION.rds.amazonaws.com:5432/realtime_analytics"
      }
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/realtime-analytics-consumer",
        "awslogs-region": "REGION",
        "awslogs-stream-prefix": "ecs"
      }
    }
  }],
  "requiresCompatibilities": ["FARGATE"],
  "networkMode": "awsvpc",
  "cpu": "256",
  "memory": "512"
}
"""