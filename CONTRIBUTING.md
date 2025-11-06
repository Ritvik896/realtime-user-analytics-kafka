# Contributing to Real-time User Analytics

Thank you for your interest in contributing! This guide will help you get started.

## Development Workflow

### 1. Setup Development Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements/local.txt

# Setup pre-commit hooks (optional)
pre-commit install
```

### 2. Git Workflow - Phase-Based Development

We follow a phase-based branching strategy:

#### Create Feature Branch
```bash
# Always branch from main
git checkout main
git pull origin main

# Create phase branch
git checkout -b feature/phase-X-name

# Example:
git checkout -b feature/phase-2-consumer
```

#### Make Commits
Follow commit message conventions:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `chore`: Maintenance, dependencies
- `test`: Tests
- `refactor`: Code refactoring

**Examples:**
```bash
git commit -m "feat(consumer): Add Kafka consumer with error handling

- Implement reliable message consumption
- Add batch processing
- Include comprehensive logging"

git commit -m "chore(deps): Update kafka-python to 2.0.2"

git commit -m "docs: Add Phase 2 setup guide"
```

#### Push and Create PR
```bash
# Push feature branch
git push -u origin feature/phase-X-name

# Create Pull Request on GitHub
# Fill in title and description
# Link to any related issues
```

#### Merge to Main
```bash
# After review and testing:
# Merge via GitHub UI (Recommended)
# Or locally:
git checkout main
git pull origin main
git merge feature/phase-X-name
git push origin main

# Delete feature branch
git branch -d feature/phase-X-name
git push origin --delete feature/phase-X-name
```

### 3. Code Quality

#### Linting
```bash
# Check code style
flake8 src tests

# Type checking
mypy src

# Additional linting
pylint src
```

#### Formatting
```bash
# Format code
black src tests

# Sort imports
isort src tests
```

#### Run Before Committing
```bash
# Run tests
pytest tests/ -v

# Check formatting
black --check src tests

# Run linting
flake8 src
```

### 4. Testing

#### Write Tests
- Place tests in `tests/` folder
- Use pytest framework
- One test file per module

#### Run Tests
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src

# Run specific test
pytest tests/test_producer.py -v
```

## Phase Naming Convention

| Phase | Branch Name | Focus |
|-------|------------|-------|
| 1 | `feature/phase-1-foundation` | Events, Producer, Docker |
| 2 | `feature/phase-2-consumer` | Consumer, Database |
| 3 | `feature/phase-3-stream-processor` | Stream Processing |
| 4 | `feature/phase-4-api` | REST API |
| 5 | `feature/phase-5-ml-integration` | ML Models |
| 6 | `feature/phase-6-monitoring` | Monitoring, Grafana |
| 7 | `feature/phase-7-testing-cicd` | Tests, CI/CD |

## Requirements Management

### Adding Dependencies

1. Install package
   ```bash
   pip install new-package==1.2.3
   ```

2. Add to appropriate requirements file
   - Core: `requirements/base.txt`
   - Dev only: `requirements/dev.txt`
   - Production only: `requirements/prod.txt`

3. Update root requirements.txt by referencing structure

4. Commit with message
   ```bash
   git commit -m "chore(deps): Add new-package==1.2.3 for feature X"
   ```

### Updating Dependencies

```bash
# Check outdated packages
pip list --outdated

# Update specific package
pip install --upgrade package-name

# Update requirements file
pip freeze > requirements/frozen.txt

# Commit
git commit -m "chore(deps): Update package-name to X.Y.Z"
```

## Docker

### Local Development
```bash
# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f <service>

# Stop services
docker-compose down
```

### After Code Changes
```bash
# Rebuild containers if needed
docker-compose up -d --build

# Restart specific service
docker-compose restart kafka
```

## Documentation

- Add docstrings to all functions and classes
- Update README.md for major changes
- Add new docs in `docs/` folder
- Keep PHASES.md updated

## Debugging Tips

```bash
# View Kafka topics
docker exec kafka kafka-topics --list --bootstrap-server kafka:9092

# View consumer groups
docker exec kafka kafka-consumer-groups --list --bootstrap-server kafka:9092

# Check database
psql -h localhost -U analytics_user -d user_analytics

# View logs
docker-compose logs -f
```

## Common Issues

### Virtual Environment Not Activating
```bash
# Windows PowerShell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\venv\Scripts\Activate.ps1
```

### Kafka Not Starting
```bash
# Check logs
docker-compose logs kafka

# Restart
docker-compose restart kafka

# Full reset
docker-compose down -v
docker-compose up -d
```

### Tests Failing
```bash
# Check if Docker is running
docker-compose ps

# Clear pytest cache
rm -rf .pytest_cache

# Run with verbose output
pytest tests/ -vv -s
```
## Quick Reference Commands

### One-Time Setup
```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements/local.txt
docker-compose up -d
```

### Daily Development
```bash
# Activate venv (do this first!)
source venv/bin/activate

# Run tests before committing
pytest tests/ -v

# Format code
black src tests

# Lint code
flake8 src

# Commit and push
git add .
git commit -m "feat(scope): description"
git push origin feature/phase-X-name
```

### Docker Management
```bash
docker-compose ps          # Check status
docker-compose logs -f     # View logs
docker-compose restart     # Restart all
docker-compose down        # Stop all
```


## Questions?

- Check docs/ folder for detailed guides
- Look at existing code for examples
- Ask in issues/PRs

Happy coding! 🚀
