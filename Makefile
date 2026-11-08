.PHONY: up down logs test test-integration ingest-samples eval
up: ; cp -n .env.example .env || true; docker compose up --build -d
down: ; docker compose down
logs: ; docker compose logs -f api
test: ; cd backend && pip install -q -r requirements-dev.txt && pytest -q
ingest-samples: ; python scripts/upload.py samples/*
test-integration: ; cd backend && TEST_DATABASE_URL=$(TEST_DATABASE_URL) pytest tests_integration -q
eval: ; python scripts/eval.py --golden samples/golden_sample.jsonl --e2e --gate eval/thresholds.json
