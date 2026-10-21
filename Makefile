.PHONY: install typography lint typecheck architecture test build release-check check

install:
	python -m pip install -e ".[dev]"

typography:
	python scripts/check_typography.py

lint:
	ruff check .

typecheck:
	mypy src tests scripts examples

architecture:
	lint-imports
	pytest tests/architecture tests/contracts

test:
	pytest --cov=pytradekit --cov-report=term-missing

build:
	python -m build

release-check:
	python scripts/qualify_release.py

check: typography lint typecheck architecture test release-check
