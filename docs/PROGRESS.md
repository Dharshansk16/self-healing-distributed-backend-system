# Project Progress: Autonomous Self-Healing Distributed System (MAPE-K)

## Current Status: Phase 0 (Audit) & Phase 1 (Target Microservice Mesh) Completed

The project has been refactored to align with the master specification in `BLUEPRINT.md`. All target microservices, shared telemetry middleware, naive liveness probes, deterministic chaos endpoints, local cluster runner, and Kubernetes/Docker configs are fully implemented and verified with automated tests.

---

## Implemented Features

### 1. Phase 0: Codebase Audit & Gap Analysis
- Audited legacy codebase across 5 pillars (Topology, Telemetry, Gray Failure Readiness, Chaos Hooks, Control Plane Compatibility).
- Restructured repository layout into the standardized `target-cluster/` directory layout.

### 2. Phase 1: Target Microservice Mesh (`target-cluster/`)
- **4-Tier Service Topology:**
  - `api-gateway` (Port `8000`): Primary entry point (`POST /api/v1/checkout`). Calls `auth-service` and `order-service`.
  - `auth-service` (Port `8001`): Token verification endpoint (`POST /verify` and `POST /api/v1/verify`).
  - `order-service` (Port `8002`): Order creation and coordination endpoint (`POST /orders` and `POST /api/v1/orders`), delegating payment to `payment-service`.
  - `payment-service` (Port `8003`): Downstream leaf payment charge endpoint (`POST /charge` and `POST /api/v1/charge`).
- **Shared Telemetry & Chaos Middleware (`target-cluster/common/telemetry_and_chaos.py`):**
  - `GET /health`: Naive liveness probe returning HTTP 200 in $< 5\text{ms}$ even under gray failures (simulates reactive orchestrator blindness).
  - `GET /metrics`: Standard Prometheus metrics with $p50/p95/p99$ latency histograms, request counters, CPU and memory gauges.
  - `GET /telemetry/snapshot`: JSON snapshot reporting `cpu_pct`, `mem_mb`, `rps`, `error_rate`, `latency_p50_ms`, `latency_p99_ms`, `active_faults`, and `recent_logs`.
  - **Deterministic Chaos Injection:**
    - `POST /debug/fault/latency`: Injects async sleep into business routes.
    - `POST /debug/fault/memory-leak`: Background memory allocation task.
    - `POST /debug/fault/cpu-burn`: Dedicated background worker burning CPU cycles without freezing asyncio.
    - `POST /debug/fault/error-spike`: Raises realistic exceptions with 500 status code.
    - `POST /debug/fault/reset`: Drains memory buffers, terminates fault workers, resets state, and logs `[REMEDIATION] Service state restored to healthy`.
  - **Distributed Tracing & Request Context:** Propagates `X-Request-ID` across all hop layers.
  - **Structured Log Ring Buffer:** In-memory circular buffer preserving the last 50 structured logs per service.

### 3. Orchestration & Local Tooling
- `run_local_cluster.py`: Single-command local launcher that boots and validates all 4 microservices with health checks and clean shutdown.
- `docker-compose.yml`: Multi-container stack including `api-gateway`, `auth-service`, `order-service`, `payment-service`, `prometheus`, and `jaeger`.
- `target-cluster/k8s-manifests/`: Full Kubernetes YAML manifests for deployments, services, namespace, Prometheus ConfigMap, and Jaeger.
- `Makefile`: Targets for `install`, `run-local`, `stop-local`, `status-local`, `test`, `docker-up`, `docker-down`.

### 4. Verification & Testing
- 18 automated tests in `tests/`:
  - `tests/test_microservices.py`: Unit and mock integration tests for all 4 microservices.
  - `tests/test_telemetry_and_chaos.py`: Validation of gray-failure latency, memory leak, CPU burn, error spike, Prometheus metrics, and JSON telemetry snapshots.
  - `tests/test_live_cascading.py`: End-to-end integration test demonstrating cascading latency from `payment-service` to `api-gateway` while `/health` probes remain fast (200 OK), followed by remediation recovery.

---

## Next Implementation Priorities (MAPE-K Control Plane)

1. **Phase 2: Monitor & Knowledge Base (`control-plane/monitor` & `control-plane/knowledge_base`)**
   - Prometheus scraper (`prometheus_collector.py`) collecting the 6D telemetry vector.
   - Jaeger topology collector (`jaeger_topology.py`) extracting the dynamic dependency graph $G=(V, E)$.
   - SQLite Knowledge Base store (`store.py`) persisting telemetry history and incident logs.

2. **Phase 3: Two-Stage Analyzer (`control-plane/analyzer`)**
   - Stage 1: Isolation Forest + temporal slope derivatives for proactive anomaly scoring.
   - Stage 2: Anomaly-Weighted Downstream PageRank RCA (`rca_engine.py`) to mathematically pinpoint root cause services.

3. **Phase 4: Planner, Log Agent & Actuator (`control-plane/planner` & `control-plane/executor`)**
   - Policy Decision Matrix with anti-flapping cooldown lock.
   - Log Diagnostic Agent (LLM / MCP with regex fallback).
   - Dual-mode Actuator (Kubernetes SDK + local reset endpoint fallback).

4. **Phase 5: Chaos Benchmarking & Research Plots (`chaos-experiments/`)**
   - Automated 3-way comparative benchmark (No Healing vs. Reactive K8s vs. Proposed MAPE-K).
   - 300-DPI IEEE research figure generator.

5. **Phase 6: Live Streamlit Dashboard (`dashboard/app.py`)**
   - Real-time topology graph, anomaly score line charts, and interactive chaos injection console.
