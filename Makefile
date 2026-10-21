.PHONY: install typography lint typecheck test build check

install:
	python -m pip install -e ".[dev]"

typography:
	python scripts/check_typography.py

lint:
	ruff check .

typecheck:
	mypy src tests scripts

test:
	pytest --cov=pytradekit --cov-report=term-missing

build:
	python -m build

check: typography lint typecheck test build
