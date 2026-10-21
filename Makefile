.PHONY: install lint typecheck test build check

install:
	python -m pip install -e ".[dev]"

lint:
	ruff check .

typecheck:
	mypy src tests

test:
	pytest --cov=pytradekit --cov-report=term-missing

build:
	python -m build

check: lint typecheck test build
