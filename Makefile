.PHONY: install dev run migrate revision test lint fmt frontend-install frontend-dev

install:
	pip install -r requirements.txt

frontend-install:
	cd frontend && npm install

dev: install
	uvicorn app.main:app --reload --app-dir backend

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend

migrate:
	alembic upgrade head

revision:
	alembic revision --autogenerate -m "$(m)"

test:
	pytest

lint:
	ruff check backend

fmt:
	black backend

frontend-dev:
	cd frontend && npm run dev
