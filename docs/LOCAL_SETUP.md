# Local Setup Guide

Complete step-by-step guide to set up the project locally on your machine.

---

## 📋 Prerequisites

Before starting, verify you have:

```bash
# Check Python 3.12
python --version
# Should show: Python 3.12.x

# Check Docker
docker --version
docker-compose --version

# Check Git
git --version
```

If any are missing, install them first.

---

## 🚀 QUICKEST SETUP (2 minutes)

### One Command Setup

```bash
# Run this single command
make quick-setup

# Then activate venv
source venv/bin/activate

# You're done!
```

---

## 📝 STEP-BY-STEP SETUP (5 minutes)

### Step 1: Clone Repository

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/realtime-user-analytics-kafka.git
cd realtime-user-analytics-kafka

# Verify you're in correct directory
pwd
# Should end with: realtime-user-analytics-kafka
```

### Step 2: Create Virtual Environment

```bash
# Create venv
python3.12 -m venv venv

# Activate it
source venv/bin/activate  # Linux/macOS
# OR
venv\Scripts\activate  # Windows

# Verify (should show (venv) prefix in terminal)
python --version
# Should show: Python 3.12.x
```

### Step 3: Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install all requirements
pip install -r requirements/local.txt

# Verify key packages
python -c 'from confluent_kafka import Producer; print("OK")'
python -c 'from src.events.event_models import UserEvent; print("OK")'
```

### Step 4: Create Monitoring Config

```bash
# Create monitoring directory
mkdir -p monitoring

# Create prometheus.yml
cat > monitoring/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    monitor: 'kafka-analytics-monitor'

alerting:
  alertmanagers:
    - static_configs:
        - targets: []

rule_files:

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'kafka'
    static_configs:
      - targets: ['kafka:9101']
    metrics_path: '/metrics'
    scrape_interval: 30s
EOF

# Verify file created
ls -la monitoring/prometheus.yml
```

### Step 5: Start Docker Services

```bash
# Start all services
docker-compose up -d

# Wait for startup
sleep 10

# Check all services are healthy
docker-compose ps

# Expected output: All services show "Up (healthy)"
```

### Step 6: Initialize Database

```bash
# Activate venv first
source venv/bin/activate

# Create database tables
python << 'EOF'
from src.database.connection import init_db, check_db_health

if check_db_health():
    print("Database connected OK")
    try:
        init_db()
        print("Database tables created OK")
    except Exception as e:
        print(f"Error: {e}")
else:
    print("Cannot connect to database")
EOF
```

### Step 7: Verify Setup

```bash
# Test 1: Check Docker services
docker-compose ps
# All should show: Up

# Test 2: Generate test events
python -m src.producer.user_event_producer --events 10 --rate 10
# Should show: success_rate: 100.0%

# Test 3: Check Kafka UI
# Open: http://localhost:8080
# Should see messages in user-events topic

# Test 4: Check database
psql -h localhost -U analytics_user -d user_analytics -c "SELECT COUNT(*) FROM events;"
# Should return: 10
```

---

## 📊 Access Points After Setup

| Service | URL | Credentials |
|---------|-----|-------------|
| Kafka UI | http://localhost:8080 | None |
| Prometheus | http://localhost:9090 | None |
| Grafana | http://localhost:3000 | admin/admin |
| PostgreSQL | localhost:5432 | analytics_user/analytics_pass |

---

## 🛠️ Common Tasks

### Generate Events

```bash
# Generate 100 events at 10/sec
python -m src.producer.user_event_producer --events 100 --rate 10

# Generate 50 events for specific user
python -m src.producer.user_event_producer --user-id user_00001 --events 50 --rate 10

# Continuous stream for 5 minutes
python -m src.producer.user_event_producer --continuous --duration 5
```

### View Docker Logs

```bash
# View all logs
docker-compose logs -f

# View specific service
docker-compose logs -f kafka
docker-compose logs -f postgres
docker-compose logs -f prometheus
```

### Check Database

```bash
# Connect to database
psql -h localhost -U analytics_user -d user_analytics

# Inside psql:
SELECT COUNT(*) FROM events;
SELECT * FROM users LIMIT 5;
SELECT COUNT(*) FROM failed_events;
\q  # Exit
```

### Verify Kafka Messages

```bash
# Check Kafka has messages
docker exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic user-events \
  --from-beginning \
  --max-messages 5
```

---

## 🧹 Cleanup

### Stop Services (Keep Data)

```bash
docker-compose down
# Data persists in volumes
```

### Stop and Remove Everything (Clean Start)

```bash
docker-compose down -v
# Removes all containers and volumes
# Data is deleted
```

### Clean Python Cache

```bash
make clean
# Removes __pycache__, .pytest_cache, etc.
```

### Reset Everything

```bash
# Stop Docker
docker-compose down -v

# Remove venv
rm -rf venv

# Start fresh
make quick-setup
```

---

## ❌ Troubleshooting

### Issue: "ModuleNotFoundError: confluent_kafka"

```bash
# Solution:
pip uninstall confluent-kafka -y
pip install confluent-kafka==2.3.0
```

### Issue: "Cannot connect to database"

```bash
# Solution: Verify PostgreSQL is running
docker-compose ps postgres
# Should show: Up (healthy)

# If not, restart:
docker-compose restart postgres
sleep 5
```

### Issue: "Kafka not responding"

```bash
# Solution: Restart Kafka
docker-compose restart kafka
sleep 5
docker-compose ps kafka
```

### Issue: "Docker services not starting"

```bash
# Solution: Restart Docker
docker-compose down
docker-compose up -d
sleep 10
docker-compose ps
```

### Issue: "prometheus.yml not found"

```bash
# Solution: Create it manually
mkdir -p monitoring
# Copy content from Step 4 above
```

---

## ✅ Setup Verification Checklist

- [ ] Python 3.12 installed
- [ ] Virtual environment created and activated
- [ ] All dependencies installed (pip install -r requirements/local.txt)
- [ ] monitoring/prometheus.yml created
- [ ] Docker services running (docker-compose ps shows all Up)
- [ ] Database initialized
- [ ] Test events generated (50+ events)
- [ ] Events visible in Kafka UI (http://localhost:8080)
- [ ] PostgreSQL has 50 events (SELECT COUNT(*) FROM events;)
- [ ] All access points working

---

## 🎯 Next Steps

After successful setup:

1. **Learn Phase 1**: Read `docs/PHASE_1_LEARNING.md`
2. **Explore Kafka**: Generate more events, view in Kafka UI
3. **Check Database**: Explore tables with psql
4. **View Dashboards**: 
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3000

---

## 📞 Getting Help

If you encounter issues:

1. Check `docs/TROUBLESHOOTING.md`
2. Review `CONTRIBUTING.md` for development setup
3. Check Docker logs: `docker-compose logs -f`
4. Verify all prerequisites are met

---

**Setup complete! Ready for Phase 1 learning.** 🚀