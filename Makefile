.PHONY: setup install migrate seed dev test lint docker-up docker-down format

setup: install migrate seed
	@echo "Setup complete."

install:
	cd backend && pip install -e ".[dev]"
	cd frontend && npm install

migrate:
	cd backend && alembic upgrade head

seed:
	cd backend && python -m app.seed

dev:
	docker compose up -d postgres redis
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
	cd frontend && npm run dev &

test:
	cd backend && pytest
	cd frontend && npm test

lint:
	cd backend && ruff check .
	cd frontend && npm run lint

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down -v

format:
	cd backend && ruff format .
	cd frontend && npm run format

# Evaluation targets
eval:
	cd backend && python -m app.core.eval_cli run --set $(or $(SET),all) --cutoffs $(or $(CUTOFFS),90,30,7) $(if $(NAME),--name $(NAME))

ablation:
	cd backend && python -m app.core.eval_cli ablation --set $(or $(SET),all) --configs $(or $(CONFIGS),all) --cutoffs $(or $(CUTOFFS),90,30,7)

eval-report:
	cd backend && python -m app.core.eval_cli run --set $(or $(SET),all) --output results/eval_$(shell date +%Y%m%d_%H%M%S).json

seed-eval:
	cd backend && python -m app.core.seed_eval
