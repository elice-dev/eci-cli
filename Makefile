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
build: build-wheel

.PHONY: build-wheel
build-wheel:
	@rm -f dist/*.whl dist/*.tar.gz
	uv build

.PHONY: build-standalone
build-standalone:
	@rm -rf dist/entry.build dist/entry.dist
	uv run python -m nuitka \
		--standalone \
		--output-filename=eci \
		--output-dir=dist \
		--include-package=app \
		--assume-yes-for-downloads \
		--remove-output \
		--no-progressbar \
		--disable-ccache \
		entry.py
