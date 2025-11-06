System Architecture
Complete technical architecture of the Real-time User Analytics platform.

🏗️ High-Level Architecture
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERACTION LAYER                    │
├─────────────────────────────────────────────────────────────┤
│  Users click, purchase, watch videos, search, etc.          │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              PHASE 1: EVENT GENERATION                       │
├─────────────────────────────────────────────────────────────┤
│  Mock Event Generator (Pydantic Models)                     │
│  - UserEvent (base)                                         │
│  - PurchaseEvent, VideoWatchEvent, ClickEvent, etc.        │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              PHASE 1: KAFKA PRODUCER                         │
├─────────────────────────────────────────────────────────────┤
│  Validates & sends events to Kafka                          │
│  - Error handling & retries                                 │
│  - Delivery confirmation                                    │
│  - Metrics tracking                                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│         KAFKA MESSAGE BROKER (Central Hub)                   │
├─────────────────────────────────────────────────────────────┤
│  Topics:                                                     │
│  - user-events (all raw events)                             │
│  - user-analytics (processed events)                        │
│  - user-anomalies (flagged events)                          │
│                                                              │
│  Properties:                                                 │
│  - Scalable: 1M+ events/sec                                │
│  - Reliable: No message loss                               │
│  - Distributed: Partitioned & replicated                   │
└─┬─────────────────────┬──────────────────┬─────────────────┘
  │                     │                  │
  │ (Partition 0)       │ (Partition 1)    │ (Partition 2)
  │                     │                  │
  ▼                     ▼                  ▼
┌──────────────────────────────────────────────────────────────┐
│              PHASE 2: KAFKA CONSUMERS                         │
├─────────────────────────────────────────────────────────────┤
│  Consumer 1    Consumer 2    Consumer 3                     │
│  ├─ Read       ├─ Read       ├─ Read                        │
│  ├─ Validate   ├─ Validate   ├─ Validate                    │
│  └─ Process    └─ Process    └─ Process                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│          PHASE 2: DATABASE LAYER                             │
├─────────────────────────────────────────────────────────────┤
│  PostgreSQL (Primary Storage)                               │
│  ├─ events (1M+ rows) - All user events                    │
│  ├─ users - User profiles & stats                          │
│  ├─ failed_events - Dead-letter queue                      │
│  └─ daily_stats - Aggregated data                          │
│                                                              │
│  Features:                                                   │
│  - Connection pooling (20 connections)                      │
│  - Indexed queries (user_id, timestamp, type)              │
│  - ACID transactions                                        │
│  - Migrations (Alembic)                                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │ PHASE 3:     │  │ PHASE 4:     │  │ PHASE 5:     │
  │ STREAM       │  │ REST API     │  │ ML PIPELINE  │
  │ PROCESSOR    │  │              │  │              │
  ├──────────────┤  ├──────────────┤  ├──────────────┤
  │ Aggregations │  │ FastAPI      │  │ Anomaly      │
  │ Windowing    │  │ Endpoints    │  │ Detection    │
  │ Enrichment   │  │ Validation   │  │ Churn Pred   │
  │ Metrics      │  │ Docs (Swagger)  │ Scoring      │
  └──────────────┘  └──────────────┘  └──────────────┘
          │                │                │
          └────────────────┼────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              PHASE 6: MONITORING & VISUALIZATION             │
├─────────────────────────────────────────────────────────────┤
│  Prometheus (Metrics Collection)                            │
│  ├─ Event throughput                                        │
│  ├─ Kafka consumer lag                                      │
│  ├─ Database latency                                        │
│  └─ Error rates                                             │
│                                                              │
│  Grafana (Dashboards)                                       │
│  ├─ Overview dashboard                                      │
│  ├─ Kafka metrics                                           │
│  ├─ Business KPIs                                           │
│  └─ System health                                           │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              PHASE 7: TESTING & CI/CD                        │
├─────────────────────────────────────────────────────────────┤
│  Unit Tests → Integration Tests → E2E Tests                 │
│  GitHub Actions → Automated Deployment                      │
└──────────────────────────────────────────────────────────────┘

🔄 Data Flow Example
Scenario: User makes a purchase
1. USER ACTION (10:30:45 AM)
   └─ User clicks "Buy Now" button

2. EVENT GENERATION (Phase 1)
   ├─ Event object created (PurchaseEvent)
   ├─ Pydantic validation
   └─ Sent to Kafka Producer

3. KAFKA PRODUCER (Phase 1)
   ├─ Serialized to JSON
   ├─ Sent to Kafka topic: user-events
   ├─ Partition 2, Offset 1000234
   └─ Replicated to 3 brokers

4. KAFKA BROKER
   ├─ Event stored in partition
   └─ Available for consumers

5. KAFKA CONSUMER (Phase 2)
   ├─ Read from partition
   ├─ Deserialize JSON
   └─ Parse to UserEvent

6. VALIDATION (Phase 2)
   ├─ Check all required fields
   ├─ Validate data types
   └─ Reject if invalid

7. DATABASE STORAGE (Phase 2)
   ├─ INSERT INTO events
   ├─ UPDATE users table
   └─ Index for fast queries

8. STREAM PROCESSING (Phase 3)
   ├─ Real-time aggregation
   ├─ Update daily stats
   └─ Calculate metrics

9. ML PIPELINE (Phase 5)
   ├─ Feature extraction
   ├─ Anomaly detection
   ├─ Fraud scoring: 0.05 (normal)
   └─ Store result

10. CACHE & API (Phase 4)
    ├─ Data available
    ├─ Endpoint ready
    └─ Response < 100ms

11. MONITORING (Phase 6)
    ├─ Metrics recorded
    ├─ Throughput updated
    └─ Dashboard refreshed

12. RESULT
    └─ Event processed end-to-end in < 100ms

🛠️ Technology Stack by Layer
Event Generation Layer

Pydantic: Data validation
Python 3.12: Core language
UUID: Unique identifiers

Message Queue Layer

Apache Kafka: Distributed message broker
Zookeeper: Cluster coordination
Confluent Kafka: Python client

Stream Processing Layer

Kafka Streams / Custom Python: Processing logic
Window operations: Time-based aggregations
State management: Tracking metrics

Storage Layer

PostgreSQL: Primary database
SQLAlchemy: ORM
Alembic: Schema migrations
Connection pooling: Performance

ML Layer

scikit-learn: Machine learning
Isolation Forest: Anomaly detection
Model persistence: Joblib

API Layer

FastAPI: Web framework
Pydantic: Request/response validation
Swagger/OpenAPI: Documentation

Monitoring Layer

Prometheus: Metrics collection
Grafana: Visualization
Custom metrics: Application-level

Infrastructure Layer

Docker: Containerization
Docker Compose: Orchestration
Terraform: Infrastructure as Code (Phase 7)


📊 Data Model
Events Table
sqlCREATE TABLE events (
    event_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(50) INDEXED,
    session_id VARCHAR(36),
    event_type VARCHAR(50) INDEXED,
    timestamp DATETIME INDEXED,
    device VARCHAR(20),
    country VARCHAR(2) INDEXED,
    value DECIMAL(15, 2),
    data JSON,
    created_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
Users Table
sqlCREATE TABLE users (
    user_id VARCHAR(50) PRIMARY KEY,
    first_seen DATETIME,
    last_seen DATETIME,
    total_events INTEGER,
    total_purchases DECIMAL(15, 2),
    total_spent DECIMAL(15, 2),
    country VARCHAR(2) INDEXED,
    metadata JSON
);
Failed Events (Dead-Letter Queue)
sqlCREATE TABLE failed_events (
    id INTEGER PRIMARY KEY,
    event_id VARCHAR(36),
    error_reason TEXT,
    error_type VARCHAR(100),
    raw_data TEXT,
    timestamp DATETIME INDEXED
);

⚡ Performance Characteristics
Throughput

Target: 1M+ events/second
Current (Phase 1): 10.2 events/sec (mock)
Bottleneck: Network → Kafka → Database

Latency

End-to-end: < 100ms from event to database
Producer: < 10ms
Kafka: < 50ms
Consumer: < 20ms
Database: < 20ms

Reliability

Message loss: 0 (acks=all)
Duplicate handling: Consumer group tracking
Error handling: Dead-letter queue

Storage

Events/day: 1-2 million
Storage/year: ~500GB (uncompressed)
Retention: 24 hours to 1 year (configurable)


🔐 Security Considerations
Authentication

Kafka SASL/SCRAM (production)
PostgreSQL password authentication
API key validation (Phase 4)

Authorization

Role-based access control
Topic ACLs in Kafka
Database user permissions

Data Protection

Encryption in transit (TLS)
Encryption at rest (full-disk)
PII data handling


🚀 Scaling Strategy
Horizontal Scaling

Add Kafka partitions (more parallelism)
Add consumer instances (load balancing)
Add database replicas (read scaling)

Vertical Scaling

Increase machine resources
Optimize database queries
Tune connection pools

Caching

Redis for hot data
In-memory caches
Query result caching


🔄 Deployment Patterns
Local Development

Docker Compose (all services)
Direct service communication
Mock data generation

Staging

Kubernetes cluster
Small node pool
Real data sample

Production

Multi-zone Kubernetes
Load balancers
Auto-scaling groups
Backup & disaster recovery


📈 Monitoring & Observability
Metrics

Event throughput (events/sec)
Consumer lag (messages behind)
Database latency (ms)
Error rates (%)

Logging

Structured JSON logging
Centralized log aggregation
Searchable by user_id, event_id

Tracing

Request tracing (future)
End-to-end latency tracking
Performance bottleneck identification


Architecture designed for production scalability and reliability! 🚀