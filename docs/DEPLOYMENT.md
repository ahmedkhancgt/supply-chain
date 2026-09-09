# Deployment Guide

## Quick Local Run (Zero-Dependency SQLite Mode)

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Seed SQLite database
python database/seeds/seed_db.py

# 3. Start FastAPI Backend
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# 4. Start React Frontend (in another terminal)
cd frontend
npm install
npm run dev
```

## Docker Compose Deployment (PostgreSQL Mode)

```bash
# 1. Configure environment variables in .env
cp .env.example .env

# 2. Build and start containers
docker-compose up --build -d

# 3. Verify backend status
curl http://localhost:8000/
```
