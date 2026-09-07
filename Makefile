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

audit:  ## Check dependencies for known vulnerabilities (free, no account)
	uv run --with pip-audit pip-audit --skip-editable
	cd web && npm audit --omit=dev

benchmark:  ## Regenerate every number the project claims
	uv run caguard benchmark --out docs/RESULTS.md

docker:  ## Build and run the self-hosted image on 127.0.0.1:3000
	docker compose up --build

check: lint types test audit  ## The gate every phase must pass

data:  ## Download the VynFi corpus (Apache-2.0, ~34 MB, never committed)
	@mkdir -p data/external
	@for i in 0 1 2; do \
		test -f data/external/shard$$i.parquet || \
		curl -sSL -o data/external/shard$$i.parquet \
		"https://huggingface.co/datasets/VynFi/vynfi-journal-entries-1m/resolve/main/data/train-0000$$i-of-00003.parquet"; \
	done
	@ls -lh data/external/

model-install:  ## Install Ollama + Qwen3 1.7B (free, local, ~1.4 GB). Needs ~2 GB free RAM.
	@echo "Checking available memory before downloading anything..."
	@uv run python -c "import sys;sys.path.insert(0,'src');from caguard.explain.memory import require_headroom;require_headroom()"
	brew install ollama
	brew services start ollama
	ollama pull qwen3:1.7b
	@echo "Done. Try: uv run caguard explain data/generated/*.parquet --model qwen3:1.7b"

model-check:  ## Report whether this machine can run the local model right now
	@uv run python -c "import sys;sys.path.insert(0,'src');from caguard.explain.memory import report;print(report())"

generate:  ## Generate the seeded Indian benchmark ledger
	uv run caguard generate

web-install:  ## Install the workspace UI dependencies (free, no accounts)
	cd web && npm install

web:  ## Build and run the workspace UI (needs `make serve` in another terminal)
	cd web && npm run build && npm run start

serve:  ## Run the local API on 127.0.0.1:8000
	uv run caguard serve

clean:  ## Remove caches and generated data
	rm -rf .pytest_cache .ruff_cache data/generated
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
