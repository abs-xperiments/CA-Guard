# Everything here runs locally and costs nothing.
.PHONY: help install lint fmt types test test-all data generate check clean

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Create the venv and install everything
	uv sync --all-extras

lint:  ## Check formatting and lint rules
	uv run ruff check .
	uv run ruff format --check .

fmt:  ## Apply formatting and safe fixes
	uv run ruff check --fix .
	uv run ruff format .

types:  ## Type-check with pyright
	uv run pyright

test:  ## Fast offline tests
	uv run pytest -m "not slow"

test-all:  ## Every test, including the full VynFi corpus (needs `make data`)
	uv run pytest

check: lint types test  ## The gate every phase must pass

data:  ## Download the VynFi corpus (Apache-2.0, ~34 MB, never committed)
	@mkdir -p data/external
	@for i in 0 1 2; do \
		test -f data/external/shard$$i.parquet || \
		curl -sSL -o data/external/shard$$i.parquet \
		"https://huggingface.co/datasets/VynFi/vynfi-journal-entries-1m/resolve/main/data/train-0000$$i-of-00003.parquet"; \
	done
	@ls -lh data/external/

generate:  ## Generate the seeded Indian benchmark ledger
	uv run caguard generate

clean:  ## Remove caches and generated data
	rm -rf .pytest_cache .ruff_cache data/generated
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
