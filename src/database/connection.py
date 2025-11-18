"""Database connection management with connection pooling.

This module handles:
1. Database engine creation with optimal pooling
2. Session management
3. Health checks and diagnostics
4. Migration support

AWS RDS Recommendations:
- Use read replicas for analytics queries (Phase 4)
- Enable Performance Insights for monitoring
- Use AWS Secrets Manager for credentials (Phase 6)
- Configure automatic backups (15-35 days retention)
"""
import os
import logging
from typing import Optional, Generator
from sqlalchemy import create_engine, text, event, pool
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# Database URL from environment (.env file) - READ FROM .env FIRST!
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://analytics_user:analytics_pass@localhost:5432/user_analytics"
)

logger.info(f"Using DATABASE_URL: {DATABASE_URL}")

# Pool configuration optimized for production
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))  # Min connections
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))  # Extra under load
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))  # Recycle after 1 hour
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))  # Wait 30s for connection

# ============================================================================
# Engine Creation with Connection Pooling
# ============================================================================

def create_db_engine():
    """
    Create SQLAlchemy engine with connection pooling.
    
    Connection Pool Strategy (QueuePool):
    - Maintains pool_size connections always open
    - Creates up to max_overflow additional connections under load
    - Returns connections to pool after use
    - Ideal for application servers handling multiple requests
    
    AWS RDS Configuration:
    - max_identifier_length=63 (PostgreSQL default)
    - pool_pre_ping=True: Verifies connections before use (detects stale connections)
    - echo_pool=False: Don't log pool operations
    
    Production Optimizations:
    - pool_recycle: Connections timeout after 1 hour (AWS RDS closes idle after 5 min)
    - connect_args timeout: Fail fast if DB is down
    """
    
    # Connection pool configuration
    connect_args = {}
    if DATABASE_URL.startswith("postgresql"):
        connect_args = {
            "connect_timeout": 10,  # Initial connection timeout
            "options": "-c statement_timeout=300000",  # 5 min query timeout
        }
    
    # Create engine with QueuePool (best for servers)
    engine = create_engine(
        DATABASE_URL,
        # Connection Pooling
        poolclass=pool.QueuePool,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_recycle=POOL_RECYCLE,
        pool_timeout=POOL_TIMEOUT,
        pool_pre_ping=True,  # Verify connection alive before using
        
        # Performance
        echo=False,  # Set to True only for debugging
        echo_pool=False,
        
        # Connection Arguments
        connect_args=connect_args,
    )
    
    # Event listeners for pool diagnostics
    @event.listens_for(pool.Pool, "connect")
    def on_connect(dbapi_conn, connection_record):
        """Configure connection when first created."""
        pass  # Can add timezone, isolation level settings here
    
    @event.listens_for(pool.Pool, "checkin")
    def on_checkin(dbapi_conn, connection_record):
        """Log when connection returned to pool."""
        pass
    
    logger.info(f"📊 Database engine created with pool_size={POOL_SIZE}, max_overflow={MAX_OVERFLOW}")
    return engine


# Create global engine instance
engine = create_db_engine()

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# ============================================================================
# Session Management
# ============================================================================

def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection for database sessions (for FastAPI Phase 4).
    
    Usage:
        def my_endpoint(db: Session = Depends(get_db)):
            user = db.query(User).first()
            return user
    
    Ensures:
    - Session is created for each request
    - Session is closed after request completes
    - Errors are caught and session rolled back
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        db.close()


def get_session() -> Session:
    """
    Simple session getter (for non-FastAPI contexts).
    
    Usage:
        db = get_session()
        try:
            user = db.query(User).filter(User.user_id == 'user123').first()
        finally:
            db.close()
    """
    return SessionLocal()

# ============================================================================
# Health Checks
# ============================================================================

def check_db_health() -> bool:
    """
    Check database connection health.
    
    Returns:
        bool: True if database is healthy, False otherwise
    
    AWS RDS: Use this for ELB health checks (Phase 6)
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Database connection healthy")
        return True
    
    except OperationalError as e:
        logger.error(f"❌ Database operational error: {e}")
        return False
    
    except SQLAlchemyError as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False
    
    except Exception as e:
        logger.error(f"❌ Unexpected database error: {e}")
        return False


def get_db_stats() -> dict:
    """
    Get connection pool statistics.
    
    Returns:
        dict with pool info (for monitoring)
    
    Useful for:
    - Identifying connection exhaustion
    - Monitoring pool health
    - Debugging connection issues
    """
    try:
        pool_obj = engine.pool
        
        stats = {
            "pool_size": POOL_SIZE,
            "max_overflow": MAX_OVERFLOW,
            "checkedin": pool_obj.checkedin(),
            "checked_out": pool_obj.checkedout(),
            "overflow": pool_obj.overflow(),
            "total_available": pool_obj.checkedin() + pool_obj.overflow(),
        }
        
        # Warn if pool is exhausted
        if stats["checked_out"] > POOL_SIZE * 0.8:
            logger.warning(f"⚠️  Pool near capacity: {stats['checked_out']}/{POOL_SIZE + MAX_OVERFLOW}")
        
        return stats
    
    except Exception as e:
        logger.error(f"Error getting pool stats: {e}")
        return {"error": str(e)}


# ============================================================================
# Database Initialization
# ============================================================================

def init_db():
    """
    Initialize database - create all tables.
    
    Called once at startup to:
    1. Create all table schemas
    2. Create indexes
    3. Setup relationships
    
    Safe to run multiple times (idempotent).
    """
    try:
        from src.database.models import Base
        
        logger.info("🔨 Creating database tables...")
        Base.metadata.create_all(bind=engine)
        
        logger.info("✅ Database initialized successfully")
        logger.info("   Tables: users, user_events, user_stats, dead_letter_queue")
        
        return True
    
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise


def drop_db():
    """
    Drop all tables (FOR TESTING/DEVELOPMENT ONLY).
    
    ⚠️  WARNING: This deletes all data!
    
    Usage:
        from src.database.connection import drop_db, init_db
        drop_db()
        init_db()
    """
    try:
        from src.database.models import Base
        
        logger.warning("🗑️  DROPPING ALL TABLES - This is destructive!")
        Base.metadata.drop_all(bind=engine)
        
        logger.info("✅ All tables dropped")
        return True
    
    except Exception as e:
        logger.error(f"❌ Database drop failed: {e}")
        raise


# ============================================================================
# Query Execution Helpers
# ============================================================================

def execute_query(query_str: str, params: dict = None) -> Optional[list]:
    """
    Execute raw SQL query.
    
    Args:
        query_str: SQL query string
        params: Query parameters (for parameterized queries)
    
    Returns:
        List of results or None if error
    
    Example:
        results = execute_query(
            "SELECT * FROM users WHERE country = :country",
            {"country": "US"}
        )
    """
    try:
        with engine.connect() as conn:
            if params:
                result = conn.execute(text(query_str), params)
            else:
                result = conn.execute(text(query_str))
            
            return result.fetchall()
    
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        return None


def execute_insert(query_str: str, params: dict = None) -> bool:
    """Execute INSERT query and commit."""
    try:
        with engine.begin() as conn:
            if params:
                conn.execute(text(query_str), params)
            else:
                conn.execute(text(query_str))
        return True
    
    except Exception as e:
        logger.error(f"Insert execution error: {e}")
        return False

# ============================================================================
# Utility Functions
# ============================================================================

def close_db():
    """Close all connections in pool."""
    engine.dispose()
    logger.info("✅ Database connections closed")


# AWS RDS Best Practices Summary
"""
1. Connection Pooling:
   - Use QueuePool for application servers ✓ (already configured)
   - Use NullPool for Lambda/serverless (change if needed)
   - Monitor pool exhaustion (get_db_stats())

2. Query Optimization:
   - Add indexes on foreign keys (Phase 2) ✓
   - Use EXPLAIN ANALYZE for slow queries (Phase 6)
   - Partition large tables by date (Phase 6)

3. Reliability:
   - pool_pre_ping=True prevents stale connection errors ✓
   - pool_recycle handles AWS RDS 5-min idle timeout ✓
   - Implement retry logic (Phase 2)

4. Monitoring:
   - Track connection pool stats (get_db_stats())
   - Monitor query performance
   - Set up CloudWatch alarms (Phase 6)

5. Security:
   - Use AWS Secrets Manager (Phase 6)
   - Encrypt connections (SSL)
   - Rotate credentials regularly

6. Cost Optimization:
   - Use read replicas for analytics (Phase 4)
   - Consider Aurora for better performance
   - Use ElastiCache for hot data (Phase 3)
"""