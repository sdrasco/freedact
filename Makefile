.PHONY: format lint type test check

format:
	black .

lint:
	ruff .

type:
	mypy .

test:
	pytest -q

check: lint type test
