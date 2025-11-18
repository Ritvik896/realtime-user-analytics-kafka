# """Kafka consumer service for reading events reliably.

# Design Pattern: Consumer offset management for exactly-once processing
# - Manual offset commits: ensures we only commit after successful processing
# - Error handling: failed messages go to DLQ, not discarded
# - Scalability: consumer group allows multiple consumers to share load

# AWS MSK (Managed Streaming for Kafka):
# - Replace bootstrap.servers with MSK broker endpoints
# - Enable IAM authentication (Phase 6)
# - Use dedicated security group for MSK access
# """
# import json
# import logging
# from typing import Optional, Dict, Any
# from confluent_kafka import Consumer, OFFSET_BEGINNING, KafkaError, KafkaException

# logger = logging.getLogger(__name__)


# class KafkaConsumerService:
#     """
#     Manages Kafka consumer operations with offset management.
    
#     Key Features:
#     - Manual offset management (exactly-once semantics)
#     - Configurable consumer group for horizontal scaling
#     - Error handling and recovery
#     - Graceful shutdown
    
#     Exactly-Once Semantics:
#     - Don't commit offset until event is successfully stored
#     - If consumer crashes mid-processing, message is reprocessed
#     - Combined with idempotent producer = true end-to-end reliability
#     """
    
#     def __init__(
#         self,
#         bootstrap_servers: str = "localhost:9092",
#         group_id: str = "analytics-consumer-group",
#         topics: list = None,
#         auto_offset_reset: str = "earliest"
#     ):
#         """
#         Initialize consumer configuration.
        
#         Args:
#             bootstrap_servers: Kafka brokers (comma-separated)
#             group_id: Consumer group ID (multiple consumers share load)
#             topics: List of topics to consume
#             auto_offset_reset: "earliest" (from beginning) or "latest" (new messages)
        
#         Consumer Groups:
#             - All consumers with same group_id share the load
#             - Each partition assigned to one consumer
#             - Enables horizontal scaling
#             - Offset stored in __consumer_offsets topic
        
#         Example AWS MSK:
#             bootstrap_servers = "b-1.msk-cluster.xxxxx.kafka.us-east-1.amazonaws.com:9092," \
#                                "b-2.msk-cluster.xxxxx.kafka.us-east-1.amazonaws.com:9092"
#         """
#         self.bootstrap_servers = bootstrap_servers
#         self.group_id = group_id
#         self.topics = topics or ["user-events"]
#         self.auto_offset_reset = auto_offset_reset
#         self.consumer = None
#         self.is_connected = False
    
#     def connect(self) -> bool:
#         """
#         Establish connection to Kafka.
        
#         Configuration Details:
#         - auto.offset.reset: Where to start if offset not found
#         - enable.auto.commit: False = manual commits (we control when)
#         - session.timeout.ms: Time before consumer is considered dead
#         - heartbeat.interval.ms: Keepalive interval
#         - max.poll.records: Batch size per poll()
        
#         Returns:
#             bool: True if connected, False if failed
#         """
#         try:
#             conf = {
#                 # Connection
#                 "bootstrap.servers": self.bootstrap_servers,
#                 "group.id": self.group_id,
                
#                 # Offset Management
#                 "auto.offset.reset": self.auto_offset_reset,  # earliest or latest
#                 "enable.auto.commit": False,  # Manual commits (important!)
                
#                 # Session Management
#                 "session.timeout.ms": 30000,  # 30 seconds
#                 "heartbeat.interval.ms": 10000,  # 10 seconds
                
#                 # Performance
#                 "fetch.min.bytes": 1,  # Return immediately if 1 byte available
#                 "fetch.max.wait.ms": 500,  # Wait max 500ms for more data
#                 "max.poll.records": 500,  # Process up to 500 records per poll
                
#                 # Consumer
#                 "client.id": f"{self.group_id}-consumer",
#                 "statistics.interval.ms": 60000,  # Stats every minute
#             }
            
#             # Create consumer
#             self.consumer = Consumer(conf)
            
#             # Subscribe to topics
#             self.consumer.subscribe(self.topics)
#             self.is_connected = True
            
#             logger.info(f"✅ Consumer connected to {self.bootstrap_servers}")
#             logger.info(f"   Group: {self.group_id}")
#             logger.info(f"   Topics: {self.topics}")
            
#             return True
        
#         except KafkaException as e:
#             logger.error(f"❌ Kafka error during connection: {e}")
#             self.is_connected = False
#             return False
        
#         except Exception as e:
#             logger.error(f"❌ Failed to connect consumer: {e}")
#             self.is_connected = False
#             return False
    
#     def consume_message(self, timeout_ms: int = 1000) -> Optional[Dict[str, Any]]:
#         """
#         Consume a single message from Kafka.
        
#         Args:
#             timeout_ms: Time to wait for message (milliseconds)
        
#         Returns:
#             dict with message data if successful:
#             {
#                 "topic": str,
#                 "partition": int,
#                 "offset": int,
#                 "timestamp": int,
#                 "key": str or None,
#                 "value": dict (parsed JSON),
#                 "kafka_msg": ConfluentKafkaMessage (for manual commit)
#             }
#             None if no message or error
        
#         Error Handling:
#             - Returns None on timeout (normal, keep polling)
#             - Logs warnings on partition EOF (normal, reached end)
#             - Logs errors on actual errors (check logs)
        
#         Processing Pattern:
#             msg = consumer.consume_message(timeout_ms=1000)
#             if msg is None:
#                 continue
#             try:
#                 store_event(msg["value"])
#                 consumer.commit_offset(msg)
#             except Exception as e:
#                 log_to_dlq(msg["value"], error=e)
#         """
#         if not self.consumer or not self.is_connected:
#             logger.warning("Consumer not connected")
#             return None
        
#         try:
#             msg = self.consumer.poll(timeout_ms)
            
#             # No message available (timeout)
#             if msg is None:
#                 return None
            
#             # Error occurred
#             if msg.error():
#                 error_code = msg.error().code()
                
#                 # Reached end of partition (normal)
#                 if error_code == KafkaError._PARTITION_EOF:
#                     logger.debug(f"Reached partition EOF")
#                     return None
                
#                 # Broker gone
#                 elif error_code == KafkaError._ALL_BROKERS_DOWN:
#                     logger.error("❌ All brokers are down!")
#                     self.is_connected = False
#                     return None
                
#                 # Other errors
#                 else:
#                     logger.error(f"Consumer error: {msg.error()}")
#                     return None
            
#             # Parse message
#             try:
#                 value = json.loads(msg.value().decode("utf-8"))
#             except json.JSONDecodeError as e:
#                 logger.error(f"Failed to parse JSON: {msg.value()}")
#                 logger.error(f"Error: {e}")
#                 return None
            
#             # Success - return parsed message
#             return {
#                 "topic": msg.topic(),
#                 "partition": msg.partition(),
#                 "offset": msg.offset(),
#                 "timestamp": msg.timestamp()[1],  # (type, timestamp_ms)
#                 "key": msg.key().decode("utf-8") if msg.key() else None,
#                 "value": value,
#                 "kafka_msg": msg  # Keep for manual commit
#             }
        
#         except Exception as e:
#             logger.error(f"Error consuming message: {e}")
#             return None
    
#     def commit_offset(self, msg: Dict[str, Any]) -> bool:
#         """
#         Manually commit offset after successful processing.
        
#         Args:
#             msg: Message dict from consume_message()
        
#         Returns:
#             bool: True if committed, False if failed
        
#         Exactly-Once Pattern:
#             1. Consume message
#             2. Process message (store in DB)
#             3. If successful: commit offset
#             4. If failed: don't commit (message will be reprocessed)
        
#         This ensures no events are lost or duplicated.
#         """
#         try:
#             if "kafka_msg" not in msg:
#                 logger.warning("No kafka_msg in message dict")
#                 return False
            
#             # Commit the offset (asynchronous=False for immediate commit)
#             self.consumer.commit(asynchronous=False)
            
#             logger.debug(f"✅ Offset committed: partition={msg['partition']}, offset={msg['offset']}")
#             return True
        
#         except KafkaException as e:
#             logger.error(f"Failed to commit offset: {e}")
#             return False
        
#         except Exception as e:
#             logger.error(f"Unexpected error committing offset: {e}")
#             return False
    
#     def seek_to_offset(self, partition: int, offset: int) -> bool:
#         """
#         Seek to specific offset in partition.
        
#         Useful for:
#         - Replaying messages (testing)
#         - Reprocessing after bug fix
#         - Starting from specific point
#         """
#         try:
#             from confluent_kafka import TopicPartition
            
#             tp = TopicPartition(self.topics[0], partition, offset)
#             self.consumer.assign([tp])
            
#             logger.info(f"✅ Seeked to partition {partition}, offset {offset}")
#             return True
        
#         except Exception as e:
#             logger.error(f"Failed to seek: {e}")
#             return False
    
#     def seek_to_beginning(self) -> bool:
#         """
#         Seek to beginning of all partitions.
        
#         Useful for:
#         - Reprocessing all events (testing)
#         - Recovery scenarios
#         - Full replay
#         """
#         try:
#             self.consumer.seek_to_beginning()
#             logger.info("✅ Seeked to beginning of all partitions")
#             return True
        
#         except Exception as e:
#             logger.error(f"Failed to seek to beginning: {e}")
#             return False
    
#     def get_consumer_lag(self) -> Optional[Dict[str, int]]:
#         """
#         Get consumer lag per partition.
        
#         Consumer Lag = Latest offset - Current offset
        
#         Useful for:
#         - Monitoring: if lag > threshold, alert
#         - Performance: indicates if consumer can keep up
#         - Scaling: high lag indicates need for more consumers
        
#         Returns:
#             dict mapping partition to lag
#         """
#         try:
#             from confluent_kafka import TopicPartition
            
#             lag_info = {}
            
#             # Get current assignments
#             assignments = self.consumer.assignment()
            
#             if not assignments:
#                 logger.warning("No partitions assigned")
#                 return None
            
#             # Get high water mark for each partition
#             for partition in assignments:
#                 low, high = self.consumer.get_watermark_offsets(partition)
#                 committed = self.consumer.committed([partition])[0].offset
                
#                 if committed == -1:
#                     committed = low
                
#                 lag = high - committed
#                 lag_info[partition.partition] = lag
                
#                 logger.info(f"Partition {partition.partition}: "
#                            f"low={low}, high={high}, committed={committed}, lag={lag}")
            
#             return lag_info
        
#         except Exception as e:
#             logger.error(f"Error getting consumer lag: {e}")
#             return None
    
#     def close(self):
#         """
#         Close consumer connection gracefully.
        
#         Cleanup:
#         - Commit any pending offsets
#         - Revoke partition assignments
#         - Close connection
#         """
#         if self.consumer:
#             try:
#                 # Commit pending offsets
#                 self.consumer.commit(asynchronous=False)
#                 logger.info("✅ Final offset committed")
#             except Exception as e:
#                 logger.warning(f"Error during final commit: {e}")
            
#             try:
#                 self.consumer.close()
#                 logger.info("✅ Consumer closed")
#             except Exception as e:
#                 logger.error(f"Error closing consumer: {e}")
            
#             self.is_connected = False


# ============================================================================
# Usage Examples
# ============================================================================

"""
Example 1: Basic consumption loop
    consumer = KafkaConsumerService()
    if consumer.connect():
        while True:
            msg = consumer.consume_message(timeout_ms=1000)
            if msg:
                try:
                    process_event(msg["value"])
                    consumer.commit_offset(msg)
                except Exception as e:
                    log_to_dlq(msg["value"], error=e)

Example 2: AWS MSK with multiple brokers
    consumer = KafkaConsumerService(
        bootstrap_servers="b-1.msk.xxxxx.kafka.us-east-1.amazonaws.com:9092," \
                         "b-2.msk.xxxxx.kafka.us-east-1.amazonaws.com:9092"
    )

Example 3: Multiple consumer groups (scale horizontally)
    # Consumer 1
    consumer1 = KafkaConsumerService(group_id="analytics-group-1")
    
    # Consumer 2 (on different server)
    consumer2 = KafkaConsumerService(group_id="analytics-group-1")
    
    # Kafka automatically divides partitions between consumers

Example 4: Replay messages (testing)
    consumer = KafkaConsumerService(auto_offset_reset="earliest")
    consumer.connect()
    consumer.seek_to_beginning()
    # Now consumes from beginning
"""

import json
import logging
from typing import Optional, Dict, Any
from confluent_kafka import Consumer, OFFSET_BEGINNING, KafkaError, KafkaException

logger = logging.getLogger(__name__)


class KafkaConsumerService:
    """
    Manages Kafka consumer operations with offset management.
    """

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        group_id: str = "analytics-consumer-group",
        topics: list = None,
        auto_offset_reset: str = "earliest"
    ):
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.topics = topics or ["user-events"]
        self.auto_offset_reset = auto_offset_reset
        self.consumer = None
        self.is_connected = False

    def connect(self) -> bool:
        try:
            conf = {
                "bootstrap.servers": self.bootstrap_servers,
                "group.id": self.group_id,

                # Offset Management
                "auto.offset.reset": self.auto_offset_reset,
                "enable.auto.commit": False,

                # Session Management
                "session.timeout.ms": 30000,
                "heartbeat.interval.ms": 10000,

                # Performance (valid for confluent-kafka-python)
                "fetch.min.bytes": 1,
                "fetch.wait.max.ms": 500,   # ✅ corrected spelling
                # "max.poll.records": 500,  # ❌ remove (Java-only)

                # Consumer
                "client.id": f"{self.group_id}-consumer",
                "statistics.interval.ms": 60000,
            }

            self.consumer = Consumer(conf)
            self.consumer.subscribe(self.topics)
            self.is_connected = True

            logger.info(f"✅ Consumer connected to {self.bootstrap_servers}")
            logger.info(f"   Group: {self.group_id}")
            logger.info(f"   Topics: {self.topics}")
            return True

        except KafkaException as e:
            logger.error(f"❌ Kafka error during connection: {e}")
            self.is_connected = False
            return False

        except Exception as e:
            logger.error(f"❌ Failed to connect consumer: {e}")
            self.is_connected = False
            return False

    def consume_message(self, timeout_ms: int = 1000) -> Optional[Dict[str, Any]]:
        if not self.consumer or not self.is_connected:
            logger.warning("Consumer not connected")
            return None

        try:
            msg = self.consumer.poll(timeout_ms)
            if msg is None:
                return None

            if msg.error():
                error_code = msg.error().code()
                if error_code == KafkaError._PARTITION_EOF:
                    logger.debug("Reached partition EOF")
                    return None
                elif error_code == KafkaError._ALL_BROKERS_DOWN:
                    logger.error("❌ All brokers are down!")
                    self.is_connected = False
                    return None
                else:
                    logger.error(f"Consumer error: {msg.error()}")
                    return None

            try:
                value = json.loads(msg.value().decode("utf-8"))
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {msg.value()}")
                logger.error(f"Error: {e}")
                return None

            return {
                "topic": msg.topic(),
                "partition": msg.partition(),
                "offset": msg.offset(),
                "timestamp": msg.timestamp()[1],
                "key": msg.key().decode("utf-8") if msg.key() else None,
                "value": value,
                "kafka_msg": msg
            }

        except Exception as e:
            logger.error(f"Error consuming message: {e}")
            return None

    def commit_offset(self, msg: Dict[str, Any]) -> bool:
        try:
            if "kafka_msg" not in msg:
                logger.warning("No kafka_msg in message dict")
                return False
            self.consumer.commit(asynchronous=False)
            logger.debug(f"✅ Offset committed: partition={msg['partition']}, offset={msg['offset']}")
            return True
        except KafkaException as e:
            logger.error(f"Failed to commit offset: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error committing offset: {e}")
            return False

    def seek_to_offset(self, partition: int, offset: int) -> bool:
        try:
            from confluent_kafka import TopicPartition
            tp = TopicPartition(self.topics[0], partition, offset)
            self.consumer.assign([tp])
            logger.info(f"✅ Seeked to partition {partition}, offset {offset}")
            return True
        except Exception as e:
            logger.error(f"Failed to seek: {e}")
            return False

    def seek_to_beginning(self) -> bool:
        try:
            self.consumer.seek_to_beginning()
            logger.info("✅ Seeked to beginning of all partitions")
            return True
        except Exception as e:
            logger.error(f"Failed to seek to beginning: {e}")
            return False

    def get_consumer_lag(self) -> Optional[Dict[str, int]]:
        try:
            from confluent_kafka import TopicPartition
            lag_info = {}
            assignments = self.consumer.assignment()
            if not assignments:
                logger.warning("No partitions assigned")
                return None
            for partition in assignments:
                low, high = self.consumer.get_watermark_offsets(partition)
                committed = self.consumer.committed([partition])[0].offset
                if committed == -1:
                    committed = low
                lag = high - committed
                lag_info[partition.partition] = lag
                logger.info(f"Partition {partition.partition}: low={low}, high={high}, committed={committed}, lag={lag}")
            return lag_info
        except Exception as e:
            logger.error(f"Error getting consumer lag: {e}")
            return None

    def close(self):
        if self.consumer:
            try:
                self.consumer.commit(asynchronous=False)
                logger.info("✅ Final offset committed")
            except Exception as e:
                logger.warning(f"Error during final commit: {e}")
            try:
                self.consumer.close()
                logger.info("✅ Consumer closed")
            except Exception as e:
                logger.error(f"Error closing consumer: {e}")
            self.is_connected = False
