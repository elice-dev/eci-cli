.PHONY: all
all:

.PHONY: format
format:
	uv run ruff format app/ tests/
	uv run ruff check --fix app/ tests/
	uv run mypy app/ tests/

.PHONY: check
check:
	uv run ruff format --check app/ tests/
	uv run ruff check app/ tests/
	uv run mypy app/ tests/

.PHONY: test
test:
	uv run pytest --cov=app --cov-report=term --cov-report=html --cov-report=xml tests/

.PHONY: build
build:
	@rm -rf dist/
	uv build
