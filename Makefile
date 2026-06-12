.PHONY: setup run eval eval-live test fetch-corpus frontend lint format typecheck verify clean

# Prefer the project venv when present so `make test` works after `make setup`.
PY ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

setup:
	$(PY) -m pip install --break-system-packages -r requirements.txt

run:
	$(PY) -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload

eval:
	$(PY) -m scripts.score

eval-live:
	$(PY) -m scripts.eval_live

test:
	$(PY) -m pytest -q

fetch-corpus:
	$(PY) -m scripts.fetch_corpus

frontend:
	cd frontend && npm run dev

lint:
	$(PY) -m ruff check backend scripts tests

format:
	$(PY) -m ruff format backend scripts tests

typecheck:
	$(PY) -m mypy backend

verify: lint format-check typecheck test eval
	cd frontend && npm run build

format-check:
	$(PY) -m ruff format --check backend scripts tests

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	rm -f backend/governance/audit_log.jsonl
	rm -f data/pharos.db
	rm -rf frontend/node_modules frontend/dist
