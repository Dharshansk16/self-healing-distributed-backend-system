UV := $(shell which uv 2>/dev/null)

.PHONY: help install run-local stop-local status-local test docker-up docker-down clean

help:
	@echo "Available Makefile commands:"
	@echo "  make install       Install dependencies (via uv sync, with pip fallback)"
	@echo "  make run-local     Start 4 microservices locally in background (via uv run)"
	@echo "  make stop-local    Stop all locally running microservices"
	@echo "  make status-local  Check health of local microservices"
	@echo "  make test          Run pytest suite on target microservices"
	@echo "  make docker-up     Build and start Docker Compose stack"
	@echo "  make docker-down   Stop Docker Compose stack"
	@echo "  make clean         Remove cache and temporary files"

install:
ifdef UV
	uv sync
else
	python3 -m pip install -r requirements.txt
endif

run-local:
ifdef UV
	uv run python run_local_cluster.py start
else
	python3 run_local_cluster.py start
endif

stop-local:
ifdef UV
	uv run python run_local_cluster.py stop
else
	python3 run_local_cluster.py stop
endif

status-local:
ifdef UV
	uv run python run_local_cluster.py status
else
	python3 run_local_cluster.py status
endif

test:
ifdef UV
	uv run pytest -v tests/
else
	python3 -m pytest -v tests/
endif

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".DS_Store" -delete
	rm -rf .pytest_cache .ruff_cache
	rm -f .cluster_pids.json
