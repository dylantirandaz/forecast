# Forecast

AI-powered forecasting platform built with FastAPI, Celery, and a Node/React frontend.

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose

## Quick Start

```bash
# 1. Copy the example env file and fill in your values
cp .env.example .env

# 2. Start infrastructure (Postgres + Redis)
make docker-up

# 3. Install dependencies, run migrations, and seed data
make setup

# 4. Start the dev servers (backend on :8000, frontend on :3000)
make dev
```

## Useful Commands

| Command            | Description                          |
|--------------------|--------------------------------------|
| `make install`     | Install Python and Node dependencies |
| `make migrate`     | Run database migrations              |
| `make seed`        | Seed the database                    |
| `make test`        | Run all tests                        |
| `make lint`        | Lint backend and frontend            |
| `make format`      | Auto-format code                     |
| `make docker-up`   | Start all services via Docker        |
| `make docker-down` | Stop services and remove volumes     |
