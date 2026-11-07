.PHONY: up down logs test ingest-samples
up: ; cp -n .env.example .env || true; docker compose up --build -d
down: ; docker compose down
logs: ; docker compose logs -f api
test: ; cd backend && pip install -q -r requirements-dev.txt && pytest -q
ingest-samples: ; python scripts/upload.py samples/*
