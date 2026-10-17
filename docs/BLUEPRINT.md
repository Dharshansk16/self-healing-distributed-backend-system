# Autonomous Self-Healing Distributed System (MAPE-K Architecture)
### Master Project Specification, AI Coding Agent Blueprint & Research Paper Guide

> **AGENT INSTRUCTION MANUAL & SYSTEM SPECIFICATION**  
> **Role:** You are an expert Distributed Systems & Machine Learning Engineer.  
> **Directive:** Use this document as the single source of truth to audit, extend, and build this repository into a research-grade, autonomous self-healing distributed system. Implement features strictly **Phase by Phase** (Phases 0 through 6). Before writing code for any phase, inspect the existing repository to reuse or adapt any microservices, Dockerfiles, or Kubernetes manifests already present.

---

## Part 1: Problem Statement & Research Novelty

### 1.1 Why Standard Orchestrators Fail (The Real-World Problem)
While container orchestrators like Kubernetes handle basic **hard failures** (e.g., restarting a crashed container when a process exits or fails a liveness probe), modern cloud-native microservice architectures suffer from **gray failures** and **cascading outages** that reactive orchestrators cannot solve:
1. **Gray Failures (Silent Degradation):** A service does not crash, so its `/health` endpoint continues returning `HTTP 200 OK`. However, a gradual memory leak, thread pool exhaustion, or downstream lock causes its $p99$ tail latency to spike from `40ms` to `3,500ms`. Standard auto-healers take zero action while user requests time out.
2. **Cascading Alerts & Root Cause Blindness:** When a downstream service (`payment-service`) degrades, upstream callers (`order-service` and `api-gateway`) also experience high latency and error spikes. Naive rule-based auto-healers restart healthy upstream pods instead of isolating the actual downstream root cause.
3. **Static Threshold Blindness:** Reactive rules (e.g., `CPU > 80%`) act too late during sudden traffic surges or fail to detect multi-metric anomalies where CPU is low (`30%`) but tail latency is critically high.

### 1.2 Core Research Contribution
This project implements an autonomous, out-of-cluster **MAPE-K (Monitor, Analyze, Plan, Execute + Knowledge Base)** Control Plane in Python that:
- **Monitors** multi-signal observability data (Prometheus metrics + OpenTelemetry/Jaeger distributed traces + container logs).
- **Analyzes** system health via a **Two-Stage Engine**:
  - *Stage 1 (Proactive Anomaly Detection):* Unsupervised Machine Learning (**Isolation Forest** + temporal slope derivatives) to catch memory creep and latency anomalies *before* `OOMKilled` crashes occur.
  - *Stage 2 (Topological Root Cause Localization):* Dynamic **Service Dependency Graph + Anomaly-Weighted Personalized PageRank** (`NetworkX`) to isolate the exact root-cause microservice across cascading call chains.
- **Plans** optimal recovery actions using a **Policy Decision Matrix + Log Diagnostic Agent (LLM/MCP with deterministic regex fallback)** protected by anti-flapping cooldown locks.
- **Executes** targeted remediation (`Graceful Rolling Restart`, `Proactive Horizontal Scale-Out`, `Circuit Breaking / State Reset`, `Deployment Rollback`) via the **Kubernetes Python SDK** (with a local Docker/Process execution fallback).
- **Validates** empirical performance using an automated **Chaos Engineering & Load Testing Benchmark** that outputs publication-ready graphs comparing **No Healing**, **Reactive Baseline (Standard K8s)**, and **Proposed Proactive MAPE-K**.

---

## Part 2: System Architecture & Tech Stack

### 2.1 High-Level Architecture Diagram

```text
+-----------------------------------------------------------------------------------+
|                        CHAOS & EVALUATION PLANE (Research Data)                   |
|   [ Locust Traffic Generator ]               [ Chaos Fault Injector CLI / API ]   |
+-----------------|----------------------------------------------|------------------+
                  | (1. Simulated User Load)                     | (2. Inject Faults)
                  v                                              v
+-----------------------------------------------------------------------------------+
|                      TARGET PLANE (k3d Kubernetes / Docker Mesh)                  |
|                                                                                   |
|   [ API Gateway :8000 ] ---> [ Auth Svc :8001 ]                                   |
|             |                                                                     |
|             +--------------> [ Order Svc :8002 ] ---> [ Payment Svc :8003 ]       |
|                                      |                         |                  |
|                                      +------------+------------+                  |
|                                                   | (Metrics, Logs, OTel Traces)  |
+---------------------------------------------------|-------------------------------+
                                                    v
+-----------------------------------------------------------------------------------+
|                  AUTONOMOUS SELF-HEALING CONTROL PLANE (MAPE-K)                   |
|                                                                                   |
|  +------------------+   +-----------------------+   +--------------------------+  |
|  |   1. MONITOR     |   |      2. ANALYZE       |   |         3. PLAN          |  |
|  |                  |   |                       |   |                          |  |
|  | - Prometheus     |-->| - Stage A: Isolation  |-->| - Policy Decision Matrix |  |
|  |   Scraper (5s)   |   |   Forest + Slopes     |   | - Log Diagnostic Agent   |  |
|  | - Jaeger Trace   |   | - Stage B: NetworkX   |   |   (LLM/MCP + Regex)      |  |
|  |   Topology Sync  |   |   Weighted PageRank   |   | - Cooldown Safety Lock   |  |
|  +------------------+   +-----------------------+   +-------------+------------+  |
|                                ^                                  |               |
|                                | (Reads/Writes State)             v               |
|                         +------+----------------+   +-------------+------------+  |
|                         |    KNOWLEDGE BASE     |   |        4. EXECUTE        |  |
|                         |                       |   |                          |  |
|                         | - SQLite Incident DB  |   | - Kubernetes Python SDK  |  |
|                         | - Dependency Graph G  |<--| - Local Docker/Process   |  |
|                         | - Cooldown Timestamps |   |   Actuator Fallback      |  |
|                         +-----------------------+   +-------------+------------+  |
+-------------------------------------------------------------------|---------------+
                                                                    |
                                         (3. Autonomous Healing API Call)
                                                                    v
                                                     [ Back to Target Plane ]
```

### 2.2 Recommended Tech Stack (Optimized for Single Laptop Execution)

| Layer | Tool / Library | Purpose |
| :--- | :--- | :--- |
| **Container & Cluster** | **k3d** (K3s in Docker) / **Docker Compose** | Runs the entire multi-service cluster locally using $< 2\text{GB}$ RAM. |
| **Target Microservices** | **Python 3.11+**, **FastAPI**, `uvicorn`, `httpx` | High-performance async services with built-in telemetry & chaos hooks. |
| **Metrics Monitoring** | **Prometheus** + `prometheus_client` | Collects request rates, error rates, memory usage, and $p95/p99$ latency histograms. |
| **Distributed Tracing** | **OpenTelemetry** + **Jaeger All-in-One** | Captures inter-service call graphs automatically. |
| **Anomaly & RCA Engine** | `scikit-learn` (`IsolationForest`), `networkx`, `numpy`, `pandas` | Performs unsupervised anomaly scoring and graph PageRank root cause isolation in $< 50\text{ms}$ on CPU. |
| **Log Diagnostic Agent** | `langchain` / `mcp` + Regex Fallback | Inspects container stack traces to confirm fault signatures. |
| **Remediation Executor** | Official `kubernetes` Python SDK + Local Process/Docker API | Executes rolling restarts, horizontal scaling, and circuit-breaking resets. |
| **Chaos & Benchmarking** | **Locust** + Custom Chaos Controller + `matplotlib`/`seaborn` | Generates synthetic load, injects gray failures, computes MTTD/MTTR, and plots IEEE paper charts. |
| **Live Demo UI** | **Streamlit** (`dashboard/app.py`) | Real-time visualization of the dependency graph, anomaly scores, and healing audit trail. |

---

## Part 3: Target Repository Directory Structure

The coding agent must organize or adapt the repository into this exact structure:

```text
self-healing-distributed-system/
├── README.md                           # This master specification
├── pyproject.toml                      # Project metadata and dependencies (uv)
├── uv.lock                             # Pinned reproducible dependency lockfile
├── docker-compose.yml                  # Local multi-container stack (Services + Prometheus + Jaeger)
├── Makefile                            # One-command build, run, test, and benchmark targets
├── run_local_cluster.py                # Single-command local launcher (runs full mesh without K8s issues)
│
├── target-cluster/                     # PLANE 1: The Victim Microservice Mesh
│   ├── common/
│   │   └── telemetry_and_chaos.py      # Shared middleware for Prometheus, OTel, and /debug/fault/* hooks
│   ├── services/
│   │   ├── api-gateway/
│   │   │   ├── app.py                  # Port 8000: Calls auth-service & order-service
│   │   │   └── Dockerfile
│   │   ├── auth-service/
│   │   │   ├── app.py                  # Port 8001: Validates tokens
│   │   │   └── Dockerfile
│   │   ├── order-service/
│   │   │   ├── app.py                  # Port 8002: Calls payment-service
│   │   │   └── Dockerfile
│   │   └── payment-service/
│   │       ├── app.py                  # Port 8003: Downstream leaf service
│   │       └── Dockerfile
│   └── k8s-manifests/                  # Kubernetes YAML deployments & observability configs
│       ├── namespace.yaml
│       ├── microservices.yaml
│       ├── prometheus.yaml
│       └── jaeger.yaml
│
├── control-plane/                      # PLANE 2: Autonomous MAPE-K Engine
│   ├── config.py                       # Thresholds, scrape intervals, cooldowns, ports
│   ├── main_loop.py                    # Master MAPE-K orchestrator loop (polls every 5s)
│   ├── monitor/
│   │   ├── prometheus_collector.py     # Scrapes metrics & computes [CPU, MEM, RPS, Err%, p50, p99]
│   │   └── jaeger_topology.py          # Queries traces & builds NetworkX DiGraph G=(V,E)
│   ├── analyzer/
│   │   ├── anomaly_detector.py         # Isolation Forest + temporal slope derivatives
│   │   └── rca_engine.py               # Algorithm 1: Anomaly-Weighted Downstream PageRank
│   ├── planner/
│   │   ├── policy_engine.py            # Maps (RootCause, FaultSignature) -> HealingAction + Cooldown Lock
│   │   └── log_agent.py                # Reads container logs (LLM/MCP + deterministic regex fallback)
│   ├── executor/
│   │   └── k8s_actuator.py             # Executes K8s API patches + Local/Docker fallback
│   └── knowledge_base/
│       └── store.py                    # SQLite store for telemetry history, incidents, and MTTR logs
│
├── chaos-experiments/                  # PLANE 3: Research Evaluation & Paper Plots
│   ├── locustfile.py                   # Realistic user traffic generator
│   ├── chaos_injector.py               # CLI/API utility to trigger deterministic faults
│   ├── benchmark_runner.py             # Automated 3-way comparison (No Heal vs Reactive vs MAPE-K)
│   ├── plot_generator.py               # Generates 300-DPI IEEE research figures from CSV results
│   └── results/                        # Output CSVs and generated PNG/PDF charts
│
└── dashboard/                          # Live Visualization UI for Project Demo & Viva
    └── app.py                          # Streamlit real-time MAPE-K monitor & interactive chaos console
```

---

## Part 4: Sequential Implementation Plan (Feature-by-Feature Specs)

### PHASE 0: Existing Codebase Audit & Alignment
**Goal:** Inspect the workspace before writing new files.
1. Scan the existing directory tree, microservice source files, `requirements.txt` / `package.json`, `Dockerfile`s, and Kubernetes/Docker configurations.
2. Evaluate the existing code against the 5 core readiness pillars:
   - **Topology:** Are there multiple services communicating in a chain so cascading failures and Root Cause Analysis (RCA) can be demonstrated?
   - **Telemetry:** Are Prometheus metrics (including $p95/p99$ latency histograms) and distributed tracing hooks present?
   - **Gray Failure Readiness:** Does `/health` return `200 OK` during latency/memory degradation so we can contrast proactive healing against naive health checks?
   - **Deterministic Chaos Hooks:** Can we programmatically trigger memory leaks, latency spikes, CPU stress, and error spikes?
   - **Control Plane Compatibility:** Can the MAPE-K Python engine monitor and actuate the services?
3. Preserve all working user code and upgrade/extend it to meet the Phase 1 specifications below.

---

### PHASE 1: Target Microservice Mesh & Observability Hooks (`target-cluster/`)
**Goal:** Build or upgrade a 4-service microservice chain with unified telemetry and deterministic fault-injection endpoints.

#### 1.1 Service Call Topology
Implement 4 FastAPI microservices communicating via async `httpx`:
- `api-gateway` (Port `8000`) $\rightarrow$ calls `auth-service` (`http://localhost:8001/verify`) AND `order-service` (`http://localhost:8002/orders`).
- `order-service` (Port `8002`) $\rightarrow$ calls `payment-service` (`http://localhost:8003/charge`).
- Primary business endpoint: `POST /api/v1/checkout` on `api-gateway`.

#### 1.2 Shared Telemetry & Chaos Middleware (`target-cluster/common/telemetry_and_chaos.py`)
Attach a reusable router/middleware to **every** microservice that exposes:
1. **`GET /health` (Naive Liveness Probe):**
   - Returns `{"status": "healthy", "service": SERVICE_NAME, "pid": os.getpid()}` with `HTTP 200` as long as the process is alive—even when latency or memory faults are active (unless in `hard_crash` mode).
2. **`GET /metrics` & `GET /telemetry/snapshot`:**
   - Exposes Prometheus metrics (`/metrics`) AND a fast JSON telemetry summary (`/telemetry/snapshot`) reporting current `cpu_pct`, `mem_mb`, `rps`, `error_rate`, `latency_p50_ms`, `latency_p99_ms`, `active_faults`, and `recent_logs` (last 50 structured log entries) so the Control Plane works both with Prometheus and in standalone local mode.
3. **Deterministic Chaos Injection Endpoints:**
   - `POST /debug/fault/latency` — Body: `{"delay_ms": 1200, "jitter_ms": 150, "enabled": true}`. Injects `await asyncio.sleep()` into business routes while keeping `/health` fast (`< 5ms`).
   - `POST /debug/fault/memory-leak` — Body: `{"rate_mb_per_sec": 4.0, "enabled": true}`. Gradually allocates memory in a background task and degrades response time proportionally as memory climbs.
   - `POST /debug/fault/cpu-burn` — Body: `{"utilization_target": 0.85, "enabled": true}`. Spikes CPU load on worker threads.
   - `POST /debug/fault/error-spike` — Body: `{"failure_rate": 0.60, "http_code": 500, "exception_type": "DatabaseConnectionPoolExhaustedError", "enabled": true}`. Raises realistic exceptions logged with full tracebacks.
   - `POST /debug/fault/reset` — Clears all active synthetic faults, drains leaked memory buffers, resets worker pools, and logs `[REMEDIATION] Service state restored to healthy`.

---

### PHASE 2: The Monitor & Knowledge Base (`control-plane/monitor` & `knowledge_base`)
**Goal:** Poll telemetry and topology every $\Delta t = 5\text{ seconds}$ and persist structured history in SQLite.

#### 2.1 Feature Vector Construction (`prometheus_collector.py`)
For each microservice $s_i \in S$ at timestamp $t$, collect the 6-dimensional telemetry vector:
$$X_t(s_i) = \left[ \text{CPU}_{\%}, \text{MEM}_{\text{MB}}, \text{RPS}, \text{ErrRate}_{\%}, L_{p50}, L_{p99} \right]$$
- Support dual scraping: query Prometheus PromQL (`histogram_quantile(0.99, ...)`), with automatic fallback to the service's `/telemetry/snapshot` endpoint so metrics collection never fails in local environments.

#### 2.2 Dynamic Service Dependency Graph (`jaeger_topology.py`)
- Query Jaeger (`GET /api/dependencies`) or construct the directed call graph $G = (V, E)$ in `NetworkX` from trace parent-child headers:
  $$E = \{(\text{api-gateway} \rightarrow \text{auth-service}), (\text{api-gateway} \rightarrow \text{order-service}), (\text{order-service} \rightarrow \text{payment-service})\}$$

#### 2.3 SQLite Knowledge Base (`store.py`)
Create `knowledge_base.db` with 2 tables:
- `telemetry_history`: `(id, timestamp, service_name, cpu_pct, mem_mb, rps, error_rate, latency_p50, latency_p99, mem_slope_mb_s, anomaly_score, is_anomalous)`
- `remediation_incidents`: `(incident_id, timestamp_detected, timestamp_healed, root_cause_service, confidence, fault_signature, action_taken, mttd_sec, mttr_sec, status, agent_reasoning)`

---

### PHASE 3: Two-Stage Analyzer — Proactive Anomaly Detection & Graph RCA (`control-plane/analyzer`)
**Goal:** Detect gray failures before crashes occur and mathematically isolate the true root-cause service.

#### 3.1 Stage 1: Unsupervised Anomaly Detector (`anomaly_detector.py`)
1. Maintain a sliding window of $W = 12$ samples per service.
2. Compute the temporal memory derivative (slope) and tail-to-median latency ratio:
   $$\Delta \text{MEM}_t(s_i) = \frac{\text{MEM}_t(s_i) - \text{MEM}_{t-k}(s_i)}{k \cdot \Delta t}, \quad R_{\text{lat}}(s_i) = \frac{L_{p99}(s_i)}{\max(L_{p50}(s_i), 1.0)}$$
3. Fit a per-service `IsolationForest(n_estimators=100, contamination=0.05, random_state=42)` on baseline normal traffic and combine with normalized feature deviations to produce a continuous **Anomaly Score** $A_t(s_i) \in [0, 1]$.
4. Flag $s_i$ as anomalous if $A_t(s_i) \ge \tau_{\text{anom}}$ (where default $\tau_{\text{anom}} = 0.65$).

#### 3.2 Stage 2: Topological Root Cause Localization (`rca_engine.py`)
When a downstream service (`payment-service`) experiences a latency spike, upstream callers (`order-service`, `api-gateway`) also exhibit high $L_{p99}$ and cross $\tau_{\text{anom}}$.
Implement **Algorithm 1: Anomaly-Weighted Downstream PageRank**:
1. Extract anomalous node set $V_{\text{anom}} = \{ s_i \in V \mid A_t(s_i) \ge \tau_{\text{anom}} \}$.
2. Construct induced anomalous subgraph $G_{\text{anom}} = (V_{\text{anom}}, E_{\text{anom}})$.
3. For each directed dependency edge $(u \rightarrow v) \in E_{\text{anom}}$ (where $u$ calls $v$), compute edge transition weight:
   $$w(u \rightarrow v) = A_t(v) \cdot \left(1 + \max(0, \rho(L_{p99}(u), L_{p99}(v)))\right)$$
   Add a small self-loop weight $w_{\text{sink}}(v \rightarrow v) = A_t(v)$ on leaf/sink nodes in $G_{\text{anom}}$ that have no anomalous downstream dependencies so probability mass accumulates at the deepest failing service.
4. Compute Personalized PageRank vector $\mathbf{r} = \text{PageRank}(G_{\text{anom}}, \alpha=0.85, \text{personalization}=A_t)$.
5. Select root cause service:
   $$s_{\text{root}} = \arg\max_{s_i \in V_{\text{anom}}} \mathbf{r}(s_i)$$

---

### PHASE 4: Intelligent Planner, Log Agent & Actuator (`control-plane/planner` & `executor`)
**Goal:** Map the isolated root cause to the optimal remediation action with cooldown protection and log verification.

#### 4.1 Remediation Policy Matrix (`policy_engine.py`)
Inspect the telemetry vector $X_t(s_{\text{root}})$ and classify into one of four fault signatures:

| Fault Signature | Condition on $s_{\text{root}}$ | Selected Action | Execution Behavior |
| :--- | :--- | :--- | :--- |
| `MEMORY_CREEP_LEAK` | $\Delta \text{MEM} > 1.5\text{ MB/s}$ OR $\text{MEM}_{\text{MB}} > 250\text{ MB}$ | `GRACEFUL_ROLLING_RESTART` | Spins up fresh replica / drains leaked memory buffer without dropping active requests. |
| `TRAFFIC_OVERLOAD` | $\text{RPS} > 1.8 \times \text{RPS}_{\text{base}}$ AND $\text{CPU}_{\%} > 70\%$ AND $\text{ErrRate} < 10\%$ | `PROACTIVE_HORIZONTAL_SCALE` | Scales deployment replicas `current + 2` (up to `MAX_REPLICAS = 5`). |
| `LATENCY_GRAY_FAILURE` | $L_{p99} > 500\text{ms}$ AND $\text{CPU}_{\%} < 60\%$ AND `/health == 200 OK` | `CIRCUIT_BREAK_AND_RESET` | Resets stuck downstream worker/connection pool and applies timeout circuit breaker. |
| `ERROR_SPIKE_CRASH` | $\text{ErrRate}_{\%} > 15\%$ OR HTTP 5xx burst | `POD_RESTART_OR_ROLLBACK` | Parses stack trace in logs and restarts pod / rolls back faulty config. |

#### 4.2 Anti-Flapping Cooldown Lock
- Query `knowledge_base.db` for the most recent remediation on $s_{\text{root}}$. If $t_{\text{now}} - t_{\text{last\_heal}} < T_{\text{cool}}$ (`45 seconds`), suppress execution and log `[PLAN] Action suppressed by cooldown lock`.

#### 4.3 Log Diagnostic Agent (`log_agent.py`)
- Fetch recent logs from $s_{\text{root}}$.
- If `GEMINI_API_KEY` or `OPENAI_API_KEY` is present in the environment, invoke the LLM/MCP diagnostic tool to summarize the exception and confirm the remediation plan.
- If no API key is set, automatically run the built-in deterministic regex log analyzer (`DatabaseConnectionPoolExhaustedError`, `MemoryLeakWarning`, `UpstreamTimeoutError`) so the pipeline works 100% offline.

#### 4.4 Dual-Mode Actuator (`k8s_actuator.py`)
- If running inside or connected to Kubernetes (`EXECUTION_MODE=k8s`), execute native `kubernetes.client.AppsV1Api` calls (`patch_namespaced_deployment_scale` and rolling restart annotations).
- Simultaneously (or when `EXECUTION_MODE=local`), invoke the target service's remediation/reset actuator endpoint so local benchmark experiments accurately reflect real-time recovery dynamics.

---

### PHASE 5: Automated Chaos Benchmark & Research Paper Plot Generator (`chaos-experiments/`)
**Goal:** Automatically generate empirical CSV data and 300-DPI IEEE research paper charts.

#### 5.1 Three-Way Comparative Benchmark (`benchmark_runner.py`)
Run each of the 4 fault scenarios (`cascading_latency`, `memory_leak`, `error_spike`, `traffic_overload`) across 3 modes:
1. **`no_healing`:** Fault remains active; measures baseline degradation.
2. **`reactive_k8s` (Baseline):** Simulates standard Kubernetes probes + static HPA (only reacts after `OOMKilled` crash at memory limit or sustained CPU $>85\%$; completely blind to gray latency failures where `/health` returns `200 OK`).
3. **`proactive_mapek` (Proposed System):** Full Isolation Forest + PageRank RCA + Proactive Planner.

#### 5.2 Output Metrics & High-Resolution Figures (`plot_generator.py`)
1. Save raw time-series data to `chaos-experiments/results/timeseries_log.csv` and summary metrics to `chaos-experiments/results/experiment_summary.csv` (`scenario`, `mode`, `mttd_sec`, `mttr_sec`, `dropped_requests`, `success_rate_pct`, `rca_top1_accuracy`).
2. Generate 4 publication-ready charts in `chaos-experiments/results/figures/`:
   - `fig1_mttr_mttd_comparison.png`: Grouped bar chart of **MTTD** and **MTTR (seconds)** across all 4 fault scenarios (Reactive Baseline vs. Proposed MAPE-K).
   - `fig2_gray_failure_latency_timeline.png`: Continuous time-series plot ($t=0\text{s} \dots 120\text{s}$) of $p99$ latency during a cascading gray failure across all 3 modes with vertical annotations for *Fault Injected*, *Anomaly Detected*, and *Service Recovered*.
   - `fig3_rca_localization_accuracy.png`: Comparison of Root Cause Localization accuracy (%) between Naive Threshold Alerting (which blames all upstream services) and Proposed Anomaly-Weighted PageRank RCA.
   - `fig4_request_success_rate.png`: Request Success Rate (%) and dropped request reduction during memory creep and error spike faults.

---

### PHASE 6: Live Demo & Viva Dashboard (`dashboard/app.py`)
**Goal:** Build an interactive Streamlit dashboard for live project demonstration.
- **Top Metrics Row:** System Status badge, Active Root Cause Alert, Mean Time To Detect (MTTD), Mean Time To Recover (MTTR).
- **Interactive Chaos Sidebar:** One-click buttons to inject faults live into any microservice (`Inject Payment Latency 1200ms`, `Inject Order Memory Leak`, `Inject Payment 500 Error Spike`, `Reset All Services`).
- **Live Topology Graph View:** Visualizes `api-gateway -> order-service -> payment-service` and `api-gateway -> auth-service` with live node coloring (Green = Healthy, Orange = Cascading Symptom, Red = Isolated Root Cause).
- **Real-Time Telemetry & Audit Table:** Live line charts of $L_{p99}$, Memory (MB), and Anomaly Score $A_t(s_i)$, plus the live `remediation_incidents` table showing the Log Agent's diagnostic reasoning.

---

## Part 5: Copy-Paste Prompt to Audit Your Existing Microservice

If you want your AI coding agent to audit your existing microservice files first, send it this prompt:

```text
Read README.md carefully. First, perform PHASE 0 (Existing Codebase Audit):
1. Inspect all files currently in my repository.
2. Score my existing microservice against the 5 pillars in Phase 0 (Topology, Telemetry, Gray Failure Readiness, Chaos Hooks, Control Plane Compatibility) using a Markdown table (✅ Ready, ⚠️ Partial, ❌ Missing).
3. Immediately upgrade my existing code and build out Phase 1 through Phase 6 step-by-step according to the exact specifications in README.md. Ensure every file contains complete, runnable code with zero TODO placeholders.
```

---

## Part 6: Research Paper Blueprint (IEEE / Springer Structure)

When writing your research paper after running `benchmark_runner.py` and `plot_generator.py`, structure your manuscript into these 6 standard sections:

### 1. Title Ideas
- *"An Autonomous MAPE-K Framework for Proactive Gray Failure Detection and Topological Root Cause Remediation in Cloud-Native Microservices"*
- *"Proactive Self-Healing in Distributed Microservices Using Unsupervised Anomaly Detection and Personalized PageRank Root Cause Localization"*

### 2. Section-by-Section Paper Writing Guide

| Section | Content to Include | Figures / Tables to Insert |
| :--- | :--- | :--- |
| **I. Abstract & Introduction** | Contrast hard crashes vs. gray failures. Highlight why Kubernetes liveness probes and static HPA fail during cascading latency spikes. State your 3 core contributions: (1) Multi-signal anomaly detection, (2) Graph PageRank RCA, (3) Closed-loop remediation. | Bullet list of contributions |
| **II. Related Work** | Review 12–15 papers on (a) Reactive container orchestration, (b) Time-series anomaly detection in microservices, and (c) Trace-based root cause analysis. Point out that most prior works stop at *detection* without closed-loop *remediation*. | **Table I:** Comparison of Existing Works vs. Proposed System across 5 features |
| **III. Proposed System Architecture & Methodology** | Explain the 4 stages of your MAPE-K loop. Include the formal equation for the 6D telemetry vector $X_t(s_i)$, the Isolation Forest anomaly score $A_t(s_i)$, and the Anomaly-Weighted PageRank equation $w(u \rightarrow v)$. | **System Architecture Diagram** + **Algorithm 1 Pseudocode** (below) |
| **IV. Experimental Setup** | Describe the 4-microservice testbed (`api-gateway`, `auth`, `order`, `payment`), Prometheus/Jaeger telemetry interval ($\Delta t = 5\text{s}$), cooldown timer ($T_{\text{cool}} = 45\text{s}$), and the 4 chaos scenarios injected. | **Table II:** Microservice Testbed & Hyperparameter Configuration |
| **V. Results & Discussion** | Present the quantitative improvements in **MTTD**, **MTTR**, **RCA Top-1 Accuracy**, and **Request Success Rate (%)** comparing No Healing, Reactive K8s Baseline, and Proposed MAPE-K. | **Figures 1, 2, 3, and 4** generated by `plot_generator.py` + **Table III:** Quantitative Summary |
| **VI. Conclusion & Future Work** | Summarize MTTR reduction (%) and gray failure recovery capability. Mention future integration with eBPF kernel-level telemetry and Reinforcement Learning policy optimization. | — |

### 3. Formal Algorithm 1 Block for Section III of Your Paper

Include this exact algorithm in your paper's Methodology section:

```text
Algorithm 1: Proactive Anomaly-Driven Root Cause Localization & Autonomous Remediation
--------------------------------------------------------------------------------------
Input:  Service Dependency Graph G = (V, E), Poll Interval Δt,
        Anomaly Threshold τ_anom, Cooldown Window T_cool
Output: Executed Remediation Action a* on Root Cause Service s_root

1:  while cluster is running do
2:      V_anom ← ∅
3:      for each service s_i ∈ V do
4:          X_t(s_i) ← [CPU_%, MEM_MB, RPS, ErrRate_%, L_p50, L_p99] from Monitor
5:          ΔMEM_t(s_i) ← (MEM_t(s_i) - MEM_{t-W}(s_i)) / (W · Δt)
6:          A_t(s_i) ← IsolationForestScore(X_t(s_i), ΔMEM_t(s_i))
7:          if A_t(s_i) ≥ τ_anom then
8:              V_anom ← V_anom ∪ {s_i}
9:          end if
10:     end for
11:     if V_anom ≠ ∅ then
12:         G_anom ← InducedSubgraph(G, V_anom)
13:         for each directed call edge (u → v) ∈ E(G_anom) do
14:             w(u → v) ← A_t(v) · (1 + max(0, Corr(L_p99(u), L_p99(v))))
15:         end for
16:         r ← PersonalizedPageRank(G_anom, α = 0.85, p = A_t, weights = w)
17:         s_root ← argmax_{s_i ∈ V_anom} r(s_i)
18:         if (t_now - LastHealTime(s_root)) > T_cool then
19:             fault_type ← ClassifySignature(X_t(s_root), ΔMEM_t(s_root))
20:             log_context ← LogDiagnosticAgent(s_root, tail = 30)
21:             a* ← PolicyMatrix(fault_type, log_context)
22:             ExecuteRemediation(s_root, a*)
23:             RecordIncident(s_root, fault_type, a*, MTTD, MTTR)
24:         end if
25:     end if
26:     sleep(Δt)
27: end while
```