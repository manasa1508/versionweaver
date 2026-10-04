.PHONY: install format lint type test check run compose

install:
	uv sync --extra dev

format:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff format --check .
	uv run ruff check .

type:
	uv run mypy src

test:
	uv run pytest --cov=versionweaver --cov-report=term-missing

check: lint type test

run:
	uv run versionweaver serve

compose:
	docker compose up --build

