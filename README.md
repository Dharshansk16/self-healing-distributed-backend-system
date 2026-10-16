# Autonomous Self-Healing Distributed System (MAPE-K Architecture)

A research-grade autonomous self-healing distributed system designed to detect and proactively remediate **gray failures**, **cascading latency spikes**, and **memory leaks** before container crashes occur.

---

## 1. Project Overview & Research Context

Standard container orchestrators (such as Kubernetes) detect and heal hard crashes (e.g. process exits or failing liveness probes). However, they suffer from:
1. **Gray Failures (Silent Degradation):** When a service suffers from high tail latency ($p99 > 3000\text{ms}$) or memory creep, its `/health` liveness probe continues returning `HTTP 200 OK`. Standard orchestrators take zero action while user requests time out.
2. **Cascading Alerts & Root Cause Blindness:** When a downstream leaf service (`payment-service`) degrades, upstream callers (`order-service` and `api-gateway`) also experience high latency and errors. Rule-based auto-healers naively restart healthy upstream pods rather than isolating the true downstream root cause.
3. **Static Threshold Inflexibility:** Reactive rules (`CPU > 80%`) trigger too late during memory creep or miss high-latency low-CPU gray failures.

This project implements an autonomous out-of-cluster **MAPE-K (Monitor, Analyze, Plan, Execute + Knowledge Base)** Control Plane.

---

## 2. Phase 0 Audit Matrix (Readiness Assessment)

| Readiness Pillar | Status | Findings & Implementation |
| :--- | :---: | :--- |
| **1. Topology** | ✅ **Ready** | 4-tier microservice call chain: `api-gateway` (8000) $\rightarrow$ `auth-service` (8001) & `order-service` (8002) $\rightarrow$ `payment-service` (8003). |
| **2. Telemetry** | ✅ **Ready** | Every microservice exposes Prometheus metrics (`/metrics`) with $p50/p95/p99$ latency histograms, plus real-time JSON snapshots (`/telemetry/snapshot`). |
| **3. Gray Failure Readiness** | ✅ **Ready** | `GET /health` acts as a naive liveness probe returning `200 OK` in $< 5\text{ms}$ even under severe latency or memory faults, enabling direct comparison between reactive orchestrators and MAPE-K. |
| **4. Deterministic Chaos Hooks** | ✅ **Ready** | Unified endpoints (`/debug/fault/*`) across all services for async latency, memory leak, CPU burn, error spikes, and instant remediation reset. |
| **5. Control Plane Compatibility** | ✅ **Ready** | Standardized `/telemetry/snapshot` and `/debug/fault/reset` actuator endpoints ready for consumption by Prometheus, Jaeger, and the MAPE-K loop. |

---

## 3. Architecture & Topology (`target-cluster/`)

```text
[ Client / Locust Load ]
          |
          v
[ API Gateway :8000 ]  ---> [ Auth Service :8001 ]
          |
          v
[ Order Service :8002 ] ---> [ Payment Service :8003 ] (Downstream Leaf)
          |                            |
          +--------------+-------------+
                         | (Metrics, Logs, Snapshots)
                         v
     [ MAPE-K Control Plane / Prometheus / Jaeger ]
```

### Microservice Directory Layout

```text
self-healing-distributed-system/
├── README.md                           # Master specification and documentation
├── requirements.txt                    # Consolidated Python dependencies
├── docker-compose.yml                  # Services + Prometheus + Jaeger stack
├── Makefile                            # Build, test, and execution targets
├── run_local_cluster.py                # Single-command local launcher
│
├── target-cluster/                     # PLANE 1: Target Microservice Mesh
│   ├── common/
│   │   └── telemetry_and_chaos.py      # Shared middleware for Prometheus, telemetry snapshots, and chaos hooks
│   ├── services/
│   │   ├── api-gateway/                # Port 8000: Calls auth-service & order-service
│   │   ├── auth-service/               # Port 8001: Token verification
│   │   ├── order-service/              # Port 8002: Coordinates orders, calls payment-service
│   │   └── payment-service/            # Port 8003: Downstream leaf payment processor
│   └── k8s-manifests/                  # Kubernetes YAML manifests (namespace, microservices, prometheus, jaeger)
│
└── tests/                              # Automated test suite
    ├── conftest.py
    ├── test_microservices.py           # Unit and mock integration tests
    ├── test_telemetry_and_chaos.py     # Gray failure and chaos endpoint tests
    └── test_live_cascading.py          # End-to-end live network cascading latency test
```

---

## 4. API Reference

### Business Endpoints

| Service | Method & Path | Description |
| :--- | :--- | :--- |
| **API Gateway** | `POST /api/v1/checkout` | Authenticates with Auth Service and creates order via Order Service |
| **Auth Service** | `POST /verify` | Validates session/bearer auth token (returns 401 if invalid) |
| **Order Service** | `POST /orders` | Places order and charges payment via Payment Service |
| **Payment Service** | `POST /charge` | Processes payment charge (returns 402 if declined) |

### Observability & Deterministic Chaos Endpoints (Available on ALL Services)

| Endpoint | Method | Payload / Description |
| :--- | :--- | :--- |
| `/health` | `GET` | Naive liveness probe; returns `HTTP 200 OK` in $< 5\text{ms}$ even under gray failure |
| `/metrics` | `GET` | Prometheus scrape metrics (Counters, Gauges, Histograms) |
| `/telemetry/snapshot` | `GET` | JSON snapshot (`cpu_pct`, `mem_mb`, `rps`, `error_rate`, `latency_p50_ms`, `latency_p99_ms`, `active_faults`, `recent_logs`) |
| `/debug/fault/latency` | `POST` | `{"delay_ms": 1200, "jitter_ms": 150, "enabled": true}` |
| `/debug/fault/memory-leak` | `POST` | `{"rate_mb_per_sec": 4.0, "enabled": true}` |
| `/debug/fault/cpu-burn` | `POST` | `{"utilization_target": 0.85, "enabled": true}` |
| `/debug/fault/error-spike` | `POST` | `{"failure_rate": 0.60, "http_code": 500, "exception_type": "DatabaseConnectionPoolExhaustedError", "enabled": true}` |
| `/debug/fault/reset` | `POST` | Restores service to healthy state, drains memory buffers, cancels fault tasks |
| `/debug/fault/status` | `GET` | Returns active fault configurations |

---

## 5. Quick Start & Execution

### Option A: Local Run (via `uv` or standard Python)

Install dependencies:
```bash
# Using uv (recommended, fast & reproducible)
uv sync

# Or using standard pip
pip install -r requirements.txt
```

Start all 4 microservices locally:
```bash
# Using uv
uv run python run_local_cluster.py start

# Or using Makefile
make run-local
```
Check health and status:
```bash
uv run python run_local_cluster.py status
```
Test checkout request:
```bash
curl -i -X POST http://localhost:8000/api/v1/checkout \
  -H "Content-Type: application/json" \
  -d '{"user_id": "alice", "auth_token": "valid_token", "product_id": "prod_1", "quantity": 2, "amount": 99.99}'
```
Stop the local cluster:
```bash
uv run python run_local_cluster.py stop
```

### Option B: Docker Compose

```bash
docker compose up --build -d
```
- API Gateway: `http://localhost:8000`
- Prometheus UI: `http://localhost:9090`
- Jaeger Tracing UI: `http://localhost:16686`

Stop the containers:
```bash
docker compose down
```

---

## 6. Running Automated Tests

Run the full pytest suite (18 unit, gray-failure, and live cascading tests):
```bash
# Using uv
uv run pytest -v tests/

# Or using Makefile
make test
```
