🤝 How to Contribute
This project welcomes contributions! Whether you're fixing bugs, adding features, or improving documentation, here's how to get involved.

🏗️ Development Setup
Prerequisites

Python 3.12+
Docker & Docker Compose
Git
Make (optional)

Initial Setup
bash# 1. Clone repository
git clone https://github.com/Ritvik896/realtime-user-analytics-kafka.git
cd realtime-user-analytics-kafka

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements/local.txt

# 4. Start Docker services
docker-compose up -d

# 5. Initialize database
make db-init

# 6. Verify setup
make test

🌿 Git Workflow
Creating a Feature Branch
bash# 1. Update master
git checkout master
git pull origin master

# 2. Create feature branch
# Format: feature/phase-X-description or fix/description
git checkout -b feature/phase-2-consumer-database

# 3. Verify branch
git branch
# * feature/phase-2-consumer-database
Committing Changes
bash# 1. Check status
git status

# 2. Stage changes
git add .

# 3. Commit with meaningful message
git commit -m "feat(phase-2): implement consumer with offset management

- Add Kafka consumer service with manual offset commits
- Implement event storage with deduplication
- Add real-time statistics aggregation
- Create 50+ unit tests
- Add Dead Letter Queue for error handling"

# 4. Push to remote
git push -u origin feature/phase-2-consumer-database
Commit Message Format
Follow conventional commits:
feat(category): short description

Longer explanation of what changed and why.
- Bullet point 1
- Bullet point 2

Fixes #123
Types:

feat: New feature
fix: Bug fix
docs: Documentation
test: Tests
refactor: Code refactoring
perf: Performance
chore: Build, deps, etc.


📋 Before Submitting PR
1. Code Quality
bash# Format code
make format

# Check linting
make lint

# Type checking
mypy src

# All tests pass
make test
2. Documentation

 Update docstrings
 Update README.md if needed
 Add comments for complex logic
 Update relevant docs in docs/

3. Testing
bash# Unit tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src

# Integration test
make pipeline-test

# Target: 80%+ coverage

🔀 Creating a Pull Request
On GitHub

Go to repository

https://github.com/Ritvik896/realtime-user-analytics-kafka


Click "Pull requests" tab
Click "New pull request"
Select

Base: master
Compare: feature/phase-2-consumer-database


Click "Create pull request"
Fill in PR details

markdown   # Title: Phase 2: Consumer & Database Storage
   
   ## Description
   Implements Kafka consumer with exactly-once semantics and real-time statistics.
   
   ## Changes
   - Adds consumer service with offset management
   - Creates database models (User, Event, Stats, DLQ)
   - Implements event storage and deduplication
   - Adds real-time statistics aggregation
   - Includes 50+ unit tests
   
   ## Testing
   - All tests passing: `pytest tests/ -v`
   - Integration test passing: `make pipeline-test`
   - Coverage: 85%
   
   ## Checklist
   - [x] Code formatted with Black
   - [x] Tests passing
   - [x] Documentation updated
   - [x] No breaking changes
   
   Closes #N/A

Request reviewers (if available)
Wait for approval


📝 Code Standards
Python Style
python# 1. Type hints required
from typing import Dict, Optional, List

def process_event(event_data: Dict[str, Any]) -> Optional[str]:
    """Process event and return ID."""
    pass

# 2. Docstrings for functions
def validate_event(event: Dict) -> bool:
    """
    Validate event data.
    
    Args:
        event: Event dictionary
    
    Returns:
        True if valid, False otherwise
    
    Example:
        >>> validate_event({"user_id": "123"})
        True
    """
    pass

# 3. Comments for complex logic
# Calculate running average to avoid storing all values
old_avg = stats.avg_session_duration
new_count = stats.total_events
stats.avg_session_duration = (
    (old_avg * (new_count - 1) + duration) / new_count
)

# 4. Constants in UPPER_CASE
MAX_RETRIES = 3
TIMEOUT_MS = 10000

# 5. Private methods with _prefix
def _internal_helper() -> None:
    pass

# 6. Imports organized
# Standard library
import os
from datetime import datetime
from typing import Dict

# Third-party
from sqlalchemy import create_engine
from pydantic import BaseModel

# Local
from src.database.models import User
File Organization
python"""
Module docstring describing purpose.

Example:
    Usage example here
"""

# 1. Imports (organized by type)
# 2. Constants
# 3. Helper functions
# 4. Main classes
# 5. Public functions

🧪 Testing Standards
Unit Test Requirements
python# 1. Descriptive test names
def test_validate_event_missing_required_fields():
    """Test that validation fails when required fields missing."""
    pass

# 2. Arrange-Act-Assert pattern
def test_store_event_creates_user():
    # Arrange
    event = {"user_id": "123", "event_id": "evt_001", ...}
    
    # Act
    result = store_event(db, event)
    
    # Assert
    assert result is not None
    user = db.query(User).first()
    assert user is not None

# 3. Use fixtures
@pytest.fixture
def db_session():
    """Create test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()

# 4. Test edge cases
def test_negative_amount_rejected():
    """Test that negative purchase amounts are rejected."""
    pass

def test_empty_event_rejected():
    """Test that empty events are rejected."""
    pass
Test File Structure
tests/
├── __init__.py
├── test_storage.py        # Storage tests
├── test_consumer.py       # Consumer tests
├── test_api.py            # API tests (Phase 4+)
└── fixtures/
    └── conftest.py        # Shared fixtures

🐛 Bug Reports
Creating a Bug Report
When reporting bugs:

Title: Concise description
Version: Which version/phase?
Steps to reproduce
Expected behavior
Actual behavior
Error logs
Environment

Example:
Title: Consumer crashes on invalid timestamp

Steps:
1. Start consumer
2. Send event with timestamp "2024-01-32"
3. Check logs

Expected: Event logged to DLQ
Actual: Consumer crashes with KeyError

Error: KeyError: 'timestamp'

📚 Documentation Standards
Docstring Format
pythondef function_name(param1: str, param2: int) -> bool:
    """
    Short description (one line).
    
    Longer description explaining what it does,
    why you'd use it, and how to use it.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Description of return value
    
    Raises:
        ValueError: When validation fails
        KeyError: When key not found
    
    Example:
        >>> function_name("test", 123)
        True
        
        >>> function_name("invalid", -1)
        Traceback (most recent call last):
            ...
        ValueError: param2 must be positive
    """
    pass
README Sections
For new features, update README.md:

Feature description
Usage example
API documentation (if applicable)
Performance metrics
Known limitations


🔍 Code Review Checklist
When reviewing PRs, check:
Code Quality

 Type hints present
 Docstrings complete
 Comments explain why, not what
 No dead code
 Error handling present

Testing

 Tests passing
 Edge cases covered
 Coverage ≥80%
 Test names descriptive

Performance

 No N+1 queries
 Connection pooling used
 Efficient algorithms
 No memory leaks

Security

 Input validation
 SQL injection prevented
 Secrets not in code
 Proper error handling

Documentation

 README updated
 Docstrings present
 Examples provided
 Breaking changes noted


🚀 Deployment Process
Staging Deployment
bash# 1. Test on staging branch
git checkout -b staging/test
# Make changes
make test

# 2. Deploy to staging
git push origin staging/test
# CI/CD runs automated tests

# 3. Manual testing
# Test on staging environment

# 4. Approve for production
Production Deployment
bash# 1. Tag release
git tag v0.2.0
git push origin v0.2.0

# 2. Create release notes
# Document changes, bug fixes, features

# 3. Deploy to production
# Manual or automated via CI/CD

# 4. Monitor
# Check logs, metrics, errors
# Be ready to rollback if issues

📞 Getting Help

Questions: Review docs/ folder
Issues: Check GitHub issues
Code Review: Ask maintainers
Architecture: See ARCHITECTURE.md


🎯 Development Checklist
Before each PR:

 Code formatted: make format
 Linting passed: make lint
 Tests passing: make test
 Type check: mypy src
 Coverage ≥80%: pytest --cov
 Docstrings added
 README updated (if needed)
 No breaking changes
 Commit message follows conventions


📊 Code Review SLA

Priority: Critical (24h), High (48h), Normal (1 week)
Approval: At least 1 maintainer
Changes: Address all feedback
Merge: Squash merge to keep history clean


🤗 Community Guidelines

Respectful: Assume good intentions
Inclusive: Welcome all backgrounds
Constructive: Helpful feedback only
Collaborative: We're building together


Thank you for contributing! 🎉
Questions? Open an issue or start a discussion.