.PHONY: install test lint format check type safety clean

install:
	pip install -e .
	pip install ruff mypy black pytest-cov bandit pre-commit

test:
	python3 -m pytest tests/ -v

test-cov:
	python3 -m pytest tests/ --cov=harvest -v

test-quick:
	python3 tests/test_all.py

lint:
	ruff check .

lint-fix:
	ruff check --fix .

format:
	ruff format .

format-check:
	ruff format --check .

check: lint format-check test-quick

type:
	mypy harvest/ --ignore-missing-imports

safety:
	bandit -r harvest/ -c pyproject.toml

all: lint format-check type safety test-quick

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache
	find . -name "*.pyc" -delete

precommit:
	pre-commit run --all-files
