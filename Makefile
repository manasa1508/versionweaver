.PHONY: install format lint type test web-install web-check web-dev build check run compose

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

web-install:
	npm --prefix web ci

web-check:
	npm --prefix web run check
	npm --prefix web run test
	npm --prefix web run build

web-dev:
	npm --prefix web run dev

build: web-check

check: lint type test web-check

run:
	uv run versionweaver serve

compose:
	docker compose up --build
