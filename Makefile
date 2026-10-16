PYTHON := python3

.PHONY: help install run-local stop-local status-local test docker-up docker-down clean

help:
	@echo "Available Makefile commands:"
	@echo "  make install       Install consolidated Python dependencies"
	@echo "  make run-local     Start 4 microservices locally in background"
	@echo "  make stop-local    Stop all locally running microservices"
	@echo "  make status-local  Check health of local microservices"
	@echo "  make test          Run pytest suite on target microservices"
	@echo "  make docker-up     Build and start Docker Compose stack"
	@echo "  make docker-down   Stop Docker Compose stack"
	@echo "  make clean         Remove cache and temporary files"

install:
	$(PYTHON) -m pip install -r requirements.txt

run-local:
	$(PYTHON) run_local_cluster.py start

stop-local:
	$(PYTHON) run_local_cluster.py stop

status-local:
	$(PYTHON) run_local_cluster.py status

test:
	$(PYTHON) -m pytest -v tests/

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -f .cluster_pids.json
