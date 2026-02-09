.PHONY: lint test test-parallel test-serial bench bench-save bench-compare clean docs-serve docs-build docs-sync

test: test-parallel test-serial

bench:
	uv run pytest benchmarks/ -v

bench-save:
	uv run pytest benchmarks/ -v --benchmark-save=baseline

bench-compare:
	uv run pytest benchmarks/ -v --benchmark-compare=baseline

lint:
	uvx --with tox-uv tox -e lint

docs-sync:
	cp CHANGELOG.md docs/changelog.md

docs-serve: docs-sync
	uv run --group docs mkdocs serve

docs-build: docs-sync
	uv run --group docs mkdocs build

test-parallel:
	uvx --with tox-uv tox -p auto -- -m "not serial"

test-serial:
	uvx --with tox-uv tox -- -m serial

clean:
	rm -rf .tox
	rm -rf .pytest_cache
	rm -rf dist
	rm -rf site
	find . -type d -name "__pycache__" -exec rm -rf {} +
