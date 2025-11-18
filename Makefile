# ============================================================
# FILE: Makefile
# ============================================================
# Common development commands
# Usage: make <target>

.PHONY: help venv install dev test lint format clean docker-up docker-down docker-logs quick-setup

help:
	@echo "Real-time User Analytics - Available Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make venv              - Create virtual environment"
	@echo "  make install           - Install dependencies"
	@echo "  make dev               - Complete setup (venv + install + docker-up)"
	@echo "  make quick-setup       - FASTEST: One command setup"
	@echo ""
	@echo "Development:"
	@echo "  make producer          - Run event producer"
	@echo "  make test              - Run tests"
	@echo "  make lint              - Run linters (flake8, mypy, pylint)"
	@echo "  make format            - Format code (black, isort)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up         - Start all Docker services"
	@echo "  make docker-down       - Stop all Docker services"
	@echo "  make docker-logs       - View Docker logs (Ctrl+C to exit)"
	@echo "  make docker-clean      - Stop and remove all containers/volumes"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean             - Clean up artifacts (__pycache__, .pytest_cache, etc.)"
	@echo "  make freeze            - Freeze current environment to frozen.txt"
	@echo ""

# ============================================================
# Setup Targets
# ============================================================

venv:
	python3 -m venv venv
	@echo "✅ Virtual environment created"
	@echo "📝 Activate with: source venv/bin/activate"

install:
	pip install --upgrade pip setuptools wheel
	pip install -r requirements/local.txt
	@echo "✅ Dependencies installed"

dev: venv install docker-up
	@echo ""
	@echo "✅ Development environment ready!"
	@echo "📝 Activate venv: source venv/bin/activate"
	@echo "🐳 Docker services started (check with: docker-compose ps)"
	@echo ""

quick-setup:
	@echo "🚀 Quick Setup Starting..."
	@echo ""
	@echo "Step 1: Creating virtual environment..."
	python3 -m venv venv
	@echo "✅ venv created"
	@echo ""
	@echo "Step 2: Activating venv and upgrading pip..."
	. venv/bin/activate && pip install --upgrade pip setuptools wheel > /dev/null 2>&1
	@echo "✅ pip upgraded"
	@echo ""
	@echo "Step 3: Installing dependencies..."
	. venv/bin/activate && pip install -r requirements/local.txt > /dev/null 2>&1
	@echo "✅ dependencies installed"
	@echo ""
	@echo "Step 4: Creating monitoring config..."
	@mkdir -p monitoring
	@echo 'global:\n  scrape_interval: 15s\n  evaluation_interval: 15s\n  external_labels:\n    monitor: "kafka-analytics-monitor"\n\nalertmanager:\n  alertmanagers:\n    - static_configs:\n        - targets: []\n\nrule_files:\n\nscrape_configs:\n  - job_name: "prometheus"\n    static_configs:\n      - targets: ["localhost:9090"]\n\n  - job_name: "kafka"\n    static_configs:\n      - targets: ["kafka:9101"]\n    metrics_path: "/metrics"\n    scrape_interval: 30s' > monitoring/prometheus.yml
	@echo "✅ prometheus.yml created"
	@echo ""
	@echo "Step 5: Starting Docker services..."
	docker-compose up -d
	@echo "✅ Docker services starting..."
	@echo ""
	@echo "Step 6: Waiting for services to be healthy..."
	@sleep 10
	@echo "✅ Services should be ready"
	@echo ""
	@echo "=========================================="
	@echo "✅ QUICK SETUP COMPLETE!"
	@echo "=========================================="
	@echo ""
	@echo "Next steps:"
	@echo "1. Activate virtual environment:"
	@echo "   source venv/bin/activate"
	@echo ""
	@echo "2. Verify Docker services:"
	@echo "   docker-compose ps"
	@echo ""
	@echo "3. Generate test events:"
	@echo "   python -m src.producer.user_event_producer --events 50 --rate 10"
	@echo ""
	@echo "4. View events in Kafka UI:"
	@echo "   http://localhost:8080"
	@echo ""

# ============================================================
# Development Targets
# ============================================================

producer:
	python -m src.producer.user_event_producer --events 1000 --rate 10

producer-continuous:
	python -m src.producer.user_event_producer --continuous --duration 60

producer-specific-user:
	python -m src.producer.user_event_producer --user-id user_00001 --events 100

# ============================================================
# Phase 2: Consumer & Database Targets
# ============================================================

consumer:
	python -m src.consumer.user_event_consumer

consumer-test:
	python -m src.consumer.user_event_consumer --max-events 100

consumer-docker:
	docker-compose up consumer -d

db-init:
	python -c "from src.database.connection import init_db; init_db()"

db-reset:
	python -c "from src.database.connection import drop_db, init_db; drop_db(); init_db()"

db-check:
	python -c "from src.database.connection import check_db_health, get_db_stats; print('Health:', check_db_health()); print('Stats:', get_db_stats())"

db-query:
	psql postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}

# ============================================================
# Full Pipeline Testing
# ============================================================

pipeline-test: db-init
	@echo "🚀 Starting full pipeline test..."
	@echo "Terminal 1: Starting consumer..."
	@python -m src.consumer.user_event_consumer --max-events 50 &
	@sleep 3
	@echo "Terminal 2: Starting producer..."
	@python -m src.producer.user_event_producer --events 50 --rate 5
	@echo "✅ Pipeline test complete"

# ============================================================
# Testing & Quality Targets
# ============================================================

test:
	pytest tests/ -v

test-coverage:
	pytest tests/ -v --cov=src --cov-report=html
	@echo "✅ Coverage report generated: htmlcov/index.html"

lint:
	@echo "🔍 Running linters..."
	flake8 src tests
	mypy src
	@echo "✅ Linting passed"

format:
	@echo "📝 Formatting code..."
	black src tests
	isort src tests
	@echo "✅ Code formatted"

# ============================================================
# Docker Targets
# ============================================================

docker-up:
	docker-compose up -d
	@echo "✅ Docker services starting..."
	@sleep 5
	@echo "📊 Kafka UI: http://localhost:8080"
	@echo "📈 Prometheus: http://localhost:9090"
	@echo "📉 Grafana: http://localhost:3000 (admin/admin)"
	@echo "💾 PostgreSQL: localhost:5432"

docker-down:
	docker-compose down
	@echo "✅ Docker services stopped"

docker-logs:
	docker-compose logs -f

docker-logs-kafka:
	docker-compose logs -f kafka

docker-logs-postgres:
	docker-compose logs -f postgres

docker-clean:
	docker-compose down -v
	@echo "✅ All containers and volumes removed"

docker-status:
	@echo "Docker Services Status:"
	@docker-compose ps

# ============================================================
# Cleanup Targets
# ============================================================

clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".DS_Store" -delete
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache .tox
	@echo "✅ Cleanup complete"

freeze:
	pip freeze > requirements/frozen.txt
	@echo "✅ Current environment frozen to requirements/frozen.txt"