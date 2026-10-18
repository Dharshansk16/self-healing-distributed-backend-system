# Autonomous Self-Healing Distributed System (MAPE-K Architecture)

### Master Project Specification, AI Coding Agent Blueprint & Research Paper Guide (v2.0 — Mathematically Verified)

> **AGENT INSTRUCTION MANUAL & SYSTEM SPECIFICATION**
> **Role:** You are an expert Distributed Systems & Machine Learning Engineer.
> **Directive:** Use this document as the single source of truth to audit, extend, and build this repository into a research-grade, autonomous self-healing distributed system. Implement features strictly **Phase by Phase** (Phases 0 through 6). Before writing code for any phase, inspect the existing repository to reuse or adapt any microservices, Dockerfiles, or Kubernetes manifests already present.

---

## Part 1: Problem Statement & Research Novelty

### 1.1 Why Standard Orchestrators Fail (The Real-World Problem)

While container orchestrators like Kubernetes handle basic **hard failures** (e.g., restarting a crashed container when a process exits or fails a liveness probe), modern cloud-native microservice architectures suffer from **gray failures** and **cascading outages** that reactive orchestrators cannot solve:

1. **Gray Failures (Silent Degradation):** A service does not crash, so its `/health` endpoint continues returning `HTTP 200 OK`. However, a gradual memory leak, thread pool exhaustion, or downstream lock causes its $p99$ tail latency to spike from `40ms` to `3,500ms`. Standard auto-healers take zero action while user requests time out.
2. **Cascading Alerts & Root Cause Blindness:** When a downstream service (`payment-service`) degrades, upstream callers (`order-service` and `api-gateway`) also experience high latency and error spikes. Naive rule-based auto-healers restart healthy upstream pods instead of isolating the actual downstream root cause.
3. **Static Threshold Blindness:** Reactive rules (e.g., CPU exceeding 80%) act too late during sudden traffic surges or fail to detect multi-metric anomalies where CPU is low (`30%`) but tail latency is critically high.

### 1.2 Core Research Contribution

This project implements an autonomous, out-of-cluster **MAPE-K (Monitor, Analyze, Plan, Execute + Knowledge Base)** Control Plane in Python that:

- **Monitors** multi-signal observability data (Prometheus metrics + OpenTelemetry/Jaeger distributed traces + container logs).
- **Analyzes** system health via a **Two-Stage Engine**:
- _Stage 1 (Freeze-Protected Proactive Anomaly Detection):_ Unsupervised Machine Learning (**Isolation Forest** trained on 7D telemetry vectors including temporal slope derivatives + sigmoid polarity calibration + soft disjunctive heuristic fusion) to catch memory creep and latency anomalies _before_ `OOMKilled` crashes occur, protected against baseline model poisoning.
- _Stage 2 (Topological Root Cause Localization):_ Dynamic **5-Service Branching Dependency Graph + Gated Correlation Anomaly-Weighted PageRank with Competing Self-Loops** (`NetworkX`) to mathematically distinguish between internal node failures and downstream cascading propagation without row-normalization bias or sink black-hole traps.

- **Plans** optimal recovery actions using a **Priority-Ordered Policy Decision Matrix + Log Diagnostic Agent (LLM/MCP with deterministic regex fallback)** protected by anti-flapping cooldown locks.
- **Executes** targeted remediation (`Graceful Rolling Restart`, `Proactive Horizontal Scale-Out`, `Circuit Breaking / State Reset`, `Deployment Rollback`) via the **Kubernetes Python SDK** (with a realistic local virtual-replica and warmup-delay actuator fallback).
- **Validates** empirical performance using an automated **Chaos Engineering & Ablation Benchmark** that outputs publication-ready graphs comparing **No Healing**, **Reactive Baseline (Standard K8s)**, **Ablation (MAPE-K without Graph RCA)**, and **Proposed Proactive MAPE-K**.

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
|   [ API Gateway :8000 ] ------> [ Auth Svc :8001 ]                                |
|             |                                                                     |
|             +-----------------> [ Order Svc :8002 ] ---> [ Payment Svc :8003 ]    |
|                                          |                                        |
|                                          +-------------> [ Inventory Svc :8004 ]  |
|                                                                |                  |
|                                      +-------------------------+                  |
|                                      | (Metrics, Logs, OTel Traces)               |
+--------------------------------------|--------------------------------------------+
                                       v
+-----------------------------------------------------------------------------------+
|                  AUTONOMOUS SELF-HEALING CONTROL PLANE (MAPE-K)                   |
|                                                                                   |
|  +------------------+   +-----------------------+   +--------------------------+  |
|  |   1. MONITOR     |   |      2. ANALYZE       |   |         3. PLAN          |  |
|  |                  |   |                       |   |                          |  |
|  | - Prometheus     |-->| - Stage A: Frozen IF  |-->| - Priority Policy Matrix |  |
|  |   Scraper (5s)   |   |   + Sigmoid + Slopes  |   | - Log Diagnostic Agent   |  |
|  | - Jaeger Trace   |   | - Stage B: Self-Loop  |   |   (LLM/MCP + Regex)      |  |
|  |   Topology Sync  |   |   Weighted PageRank   |   | - Cooldown Safety Lock   |  |
|  +------------------+   +-----------------------+   +-------------+------------+  |
|                                ^                                  |               |
|                                | (Reads/Writes State)             v               |
|                         +------+----------------+   +-------------+------------+  |
|                         |    KNOWLEDGE BASE     |   |        4. EXECUTE        |  |
|                         |                       |   |                          |  |
|                         | - SQLite Incident DB  |   | - Kubernetes Python SDK  |  |
|                         | - Dependency Graph G  |<--| - Virtual Replica &      |  |
|                         | - Cooldown Timestamps |   |   Warmup Local Actuator  |  |
|                         +-----------------------+   +-------------+------------+  |
+-------------------------------------------------------------------|---------------+
                                                                    |
                                         (3. Autonomous Healing API Call)
                                                                    v
                                                     [ Back to Target Plane ]

```

### 2.2 Recommended Tech Stack (Optimized for Single Laptop Execution)

| Layer                    | Tool / Library                                                    | Purpose                                                                                                          |
| ------------------------ | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| **Container & Cluster**  | **k3d** (K3s in Docker) / **Docker Compose**                      | Runs the entire multi-service cluster locally using less than $2\text{GB}$ RAM.                                  |
| **Target Microservices** | **Python 3.11+**, **FastAPI**, `uvicorn`, `httpx`                 | High-performance async services with built-in telemetry & chaos hooks.                                           |
| **Metrics Monitoring**   | **Prometheus** + `prometheus_client`                              | Collects request rates, error rates, memory usage, and $p95/p99$ latency histograms.                             |
| **Distributed Tracing**  | **OpenTelemetry** + **Jaeger All-in-One**                         | Captures inter-service branching call graphs automatically.                                                      |
| **Anomaly & RCA Engine** | `scikit-learn` (`IsolationForest`), `networkx`, `numpy`, `pandas` | Performs unsupervised anomaly scoring and graph PageRank root cause isolation in less than $50\text{ms}$ on CPU. |
| **Log Diagnostic Agent** | `langchain` / `mcp` + Regex Fallback                              | Inspects container stack traces to confirm fault signatures.                                                     |
| **Remediation Executor** | Official `kubernetes` Python SDK + Local Actuator API             | Executes rolling restarts, horizontal scaling, and circuit-breaking resets.                                      |
| **Chaos & Benchmarking** | **Locust** + Custom Chaos Controller + `matplotlib`/`seaborn`     | Generates synthetic load, injects gray failures, computes MTTD/MTTR, and plots IEEE paper charts.                |
| **Live Demo UI**         | **Streamlit** (`dashboard/app.py`)                                | Real-time visualization of the dependency graph, anomaly scores, and healing audit trail.                        |

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
├── target-cluster/                     # PLANE 1: The Victim Microservice Mesh (5-Service Branching DAG)
│   ├── common/
│   │   └── telemetry_and_chaos.py      # Shared middleware: 10s sliding window, virtual replicas, chaos hooks
│   ├── services/
│   │   ├── api-gateway/
│   │   │   ├── app.py                  # Port 8000: Calls auth-service & order-service
│   │   │   └── Dockerfile
│   │   ├── auth-service/
│   │   │   ├── app.py                  # Port 8001: Validates tokens (Tier 1 branch)
│   │   │   └── Dockerfile
│   │   ├── order-service/
│   │   │   ├── app.py                  # Port 8002: Calls payment-service & inventory-service
│   │   │   └── Dockerfile
│   │   ├── payment-service/
│   │   │   ├── app.py                  # Port 8003: Downstream leaf service A
│   │   │   └── Dockerfile
│   │   └── inventory-service/
│   │       ├── app.py                  # Port 8004: Downstream leaf service B
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
│   │   ├── anomaly_detector.py         # Baseline-frozen Isolation Forest + Sigmoid calibration + slopes
│   │   └── rca_engine.py               # Algorithm 1: Self-Loop Competing Anomaly-Weighted PageRank
│   ├── planner/
│   │   ├── policy_engine.py            # Priority-ordered Policy Matrix + Anti-Flapping Cooldown Lock
│   │   └── log_agent.py                # Reads container logs (LLM/MCP + deterministic regex fallback)
│   ├── executor/
│   │   └── k8s_actuator.py             # Executes K8s API patches + Local Virtual-Replica Actuator
│   └── knowledge_base/
│       └── store.py                    # SQLite store for telemetry history, incidents, and MTTR logs
│
├── chaos-experiments/                  # PLANE 3: Research Evaluation & Paper Plots
│   ├── locustfile.py                   # Realistic user traffic generator
│   ├── chaos_injector.py               # CLI/API utility to trigger deterministic faults
│   ├── benchmark_runner.py             # Automated 4-way comparison (including RCA ablation study)
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

1. Scan the existing directory tree, microservice source files, `requirements.txt` / `pyproject.toml`, `Dockerfile`s, and Kubernetes/Docker configurations.
2. Evaluate the existing code against the 5 core readiness pillars:

- **Topology:** Are there multiple services communicating in a branching chain so cascading failures and Root Cause Analysis (RCA) can be demonstrated?
- **Telemetry:** Are Prometheus metrics (including $p95/p99$ latency histograms) and distributed tracing hooks present?
- **Gray Failure Readiness:** Does `/health` return `200 OK` during latency/memory degradation so we can contrast proactive healing against naive health checks?
- **Deterministic Chaos Hooks:** Can we programmatically trigger memory leaks, latency spikes, CPU stress, and error spikes without starving the `/health` or `/telemetry/snapshot` endpoints?
- **Control Plane Compatibility:** Can the MAPE-K Python engine monitor and actuate the services?

3. Preserve all working user code and upgrade/extend it to meet the Phase 1 specifications below.

---

### PHASE 1: Target Microservice Mesh & Observability Hooks (`target-cluster/`)

**Goal:** Build or upgrade a 5-service branching microservice DAG with unified telemetry, time-decayed sliding latency windows, and non-blocking fault-injection endpoints.

#### 1.1 Branching Service Call Topology

Implement 5 FastAPI microservices communicating via async `httpx` (with a `4.0s` client timeout):

- `api-gateway` (Port `8000`) $\rightarrow$ calls `auth-service` (`http://localhost:8001/verify`) AND `order-service` (`http://localhost:8002/orders`).
- `order-service` (Port `8002`) $\rightarrow$ calls `payment-service` (`http://localhost:8003/charge`) AND `inventory-service` (`http://localhost:8004/reserve`) concurrently or sequentially.
- Primary business endpoint: `POST /api/v1/checkout` on `api-gateway`.

#### 1.2 Shared Telemetry, Virtual Scaling & Chaos Middleware (`target-cluster/common/telemetry_and_chaos.py`)

Attach a reusable router/middleware to **every** microservice that implements the following exact mechanics:

1. **`GET /health` (Naive Liveness Probe):**

- Bypass all fault injection middleware so `/health` always responds in less than `5ms` with `{"status": "healthy", "service": SERVICE_NAME, "pid": os.getpid(), "replicas": virtual_replicas}` and `HTTP 200`—even when latency, CPU, or memory faults are active.

2. **Time-Decayed Sliding Window Telemetry (`GET /metrics` & `GET /telemetry/snapshot`):**

- Maintain a timestamped ring buffer (`collections.deque`) storing `(timestamp, latency_ms, is_error)` for requests strictly within the **last 10.0 seconds**.
- **Why 10 seconds:** Cumulative or 60-second windows retain stale high-latency samples long after remediation, causing false repeat triggers when the cooldown lock expires.
- Expose `/telemetry/snapshot` returning: `cpu_pct`, `mem_mb`, `rps`, `error_rate`, `latency_p50_ms`, `latency_p99_ms`, `virtual_replicas`, `active_faults`, and `recent_logs` (last 50 structured log lines).

3. **Non-Blocking Deterministic Chaos Injection Endpoints:**

- `POST /debug/fault/latency` — Body: `{"delay_ms": 1200, "jitter_ms": 150, "enabled": true}`. Injects `await asyncio.sleep()` into business routes while keeping `/health` and `/telemetry/snapshot` fast.
- `POST /debug/fault/memory-leak` — Body: `{"rate_mb_per_sec": 4.0, "enabled": true}`. Gradually increments resident memory buffer in a background async task and adds proportional GC-pause latency penalty (`+1.5ms` per leaked MB) as memory climbs. Also logs `[WARN] MemoryLeakWarning: Resident heap buffer expanding rapidly`.
- `POST /debug/fault/cpu-burn` — Body: `{"utilization_target": 0.85, "enabled": true}`. **GIL-Safe Implementation:** Uses a duty-cycled background thread (`0.015s` math burst followed by `time.sleep(0.01)`) combined with deterministic CPU metric modeling scaled inversely by `virtual_replicas` ($\text{CPU}_{\text{eff}} = \text{CPU}_{\text{target}} / R$). This prevents Python's GIL from starving the FastAPI `asyncio` event loop.
- `POST /debug/fault/error-spike` — Body: `{"failure_rate": 0.60, "http_code": 500, "exception_type": "DatabaseConnectionPoolExhaustedError", "enabled": true}`. Raises realistic exceptions logged with full stack tracebacks.

4. **Realistic Local Remediation Actuators (`POST /debug/remediate` & `POST /debug/fault/reset`):**

- `POST /debug/remediate` — Body: `{"action": "GRACEFUL_ROLLING_RESTART" | "PROACTIVE_HORIZONTAL_SCALE" | "CIRCUIT_BREAK_AND_RESET" | "POD_RESTART_OR_ROLLBACK", "target_replicas": 3}`.
- Instead of an instant `0ms` magic reset, simulate a realistic **Actuation Warmup Ramp (`4.0 seconds`)** where fault intensity decays linearly to zero over 4 seconds, `virtual_replicas` updates to `target_replicas` (scaling down effective CPU and overload queueing latency by $1/R$), and the 10-second latency sliding window is flushed upon completion.
- `POST /debug/fault/reset` — Hard resets all faults, sets `virtual_replicas = 1`, clears memory buffers, and flushes telemetry deques prior to starting a new benchmark run.

---

### PHASE 2: The Monitor & Knowledge Base (`control-plane/monitor` & `knowledge_base`)

**Goal:** Poll telemetry and topology every $\Delta t = 5\text{ seconds}$ and persist structured history in SQLite.

#### 2.1 Feature Vector Construction (`prometheus_collector.py`)

For each microservice $s_i \in S$ at timestamp $t$, collect the 7-dimensional telemetry vector (incorporating temporal memory slope directly so machine learning detects memory creep before static limits are reached):

$$X_t(s_i) = \left[ \text{CPU}_{\%}, \text{MEM}_{\text{MB}}, \text{RPS}, \text{ErrRate}_{\%}, L_{p50}, L_{p99}, \Delta \text{MEM}_t \right]$$

- Support dual scraping: query Prometheus PromQL (`histogram_quantile(0.99, ...)`), with automatic fallback to the service's `/telemetry/snapshot` endpoint so metrics collection never fails in local environments.

#### 2.2 Dynamic Service Dependency Graph (`jaeger_topology.py`)

- Query Jaeger (`GET /api/dependencies`) or construct the directed branching call graph $G = (V, E)$ in `NetworkX` from trace parent-child headers:

$$E = \{(\text{api-gateway} \rightarrow \text{auth-service}), (\text{api-gateway} \rightarrow \text{order-service}), (\text{order-service} \rightarrow \text{payment-service}), (\text{order-service} \rightarrow \text{inventory-service})\}$$

#### 2.3 SQLite Knowledge Base (`store.py`)

Create `knowledge_base.db` with 2 tables:

- `telemetry_history`: `(id, timestamp, service_name, cpu_pct, mem_mb, rps, error_rate, latency_p50, latency_p99, mem_slope_mb_s, anomaly_score, is_anomalous)`
- `remediation_incidents`: `(incident_id, timestamp_detected, timestamp_healed, root_cause_service, rca_pagerank_score, fault_signature, action_taken, mttd_sec, mttr_sec, status, agent_reasoning)`

---

### PHASE 3: Two-Stage Analyzer — Proactive Anomaly Detection & Graph RCA (`control-plane/analyzer`)

**Goal:** Detect gray failures before crashes occur and mathematically isolate the true root-cause service without sliding-window poisoning, row-normalization bias, or sink black-hole traps.

#### 3.1 Stage 1: Freeze-Protected Unsupervised Anomaly Detector (`anomaly_detector.py`)

1. **Sliding Window for Derivatives Only:** Maintain a rolling deque of $W = 12$ samples ($60\text{s}$) per service to compute temporal derivatives and tail latency ratios:

$$\Delta \text{MEM}_t(s_i) = \frac{\text{MEM}_t(s_i) - \text{MEM}_{t-k}(s_i)}{k \cdot \Delta t}, \quad k = \min\left(\text{len}(\text{history}), W\right), \; k \ge 1$$

$$\text{TailRatio}_{\text{lat}}(s_i) = \frac{L_{p99}(s_i)}{\max(L_{p50}(s_i), 1.0)}$$

2. **Baseline-Frozen Isolation Forest on 7D Telemetry (Anti-Poisoning):**

- Fit a per-service `StandardScaler` and `IsolationForest(n_estimators=100, contamination=0.05, random_state=42)` on an initial clean baseline buffer of $N_{\text{base}} = 30\text{ to }60$ healthy 7D samples $[ \text{CPU}, \text{MEM}, \text{RPS}, \text{ErrRate}, L_{p50}, L_{p99}, \Delta \text{MEM} ]$ (seeded with synthetic healthy baseline distributions on startup so detection works immediately at $t=0$).
- **Freeze Rule:** Never update or re-fit the `IsolationForest` on anomalous samples where $A_t(s_i) \ge \tau_{\text{anom}}$. This guarantees that prolonged outages in `no_healing` or slow `memory_leak` tests never poison the normal baseline distribution.

3. **Sigmoid Polarity Calibration & Soft Disjunctive Score Fusion:**

- Because `scikit-learn`'s `decision_function(x)` returns negative values for outliers and positive values for inliers, invert and calibrate the raw decision value $d_t(s_i)$ using a scaled sigmoid:

$$S_{\text{IF}}(s_i) = \frac{1}{1 + \exp\left(5.0 \cdot d_t(s_i)\right)}$$

- Compute the bounded domain-heuristic severity score $H_t(s_i) \in [0, 1]$ (calibrated against policy thresholds with guaranteed non-negative bounding):

$$H_t(s_i) = \text{clip}\left(\max\left(0.0, \; \frac{L_{p99} - 120}{600}, \; \frac{\Delta\text{MEM}_t}{1.5}, \; \frac{\text{MEM}_{\text{MB}} - 160}{150}, \; \frac{\text{ErrRate}_{\%}}{20.0}, \; \frac{\text{CPU}_{\%} - 65}{30}\right), \; 0.0, \; 1.0\right)$$

- Combine ML and domain heuristics using **Soft Disjunctive Fusion (Noisy-OR Evidence Combination)**:

$$A_t(s_i) = \text{clip}\left(1.0 - \left(1.0 - S_{\text{IF}}(s_i)\right) \cdot \left(1.0 - H_t(s_i)\right), \; 0.0, \; 1.0\right)$$

  - _Mathematical Justification:_ Unlike a rigid weighted sum ($0.45 S_{\text{IF}} + 0.55 H_t$) where neither detector could cross $\tau_{\text{anom}} = 0.65$ alone, soft disjunction guarantees that:
    1. If the Isolation Forest detects an unsupervised multi-metric anomaly ($S_{\text{IF}} \ge 0.65$), $A_t(s_i) \ge 0.65$ triggers immediately without requiring heuristic support.
    2. If a deterministic heuristic threshold fires ($H_t \ge 0.65$), $A_t(s_i) \ge 0.65$ triggers immediately.
    3. If both signals exhibit moderate degradation (e.g., $S_{\text{IF}} = 0.55, H_t = 0.55$), the fused score constructively reinforces to $A_t = 1 - (0.45)^2 \approx 0.80$.
    4. For clean baseline traffic ($S_{\text{IF}} \approx 0.32, H_t = 0.0$), $A_t = 0.32 \ll \tau_{\text{anom}}$, preventing false alerts.

4. Flag $s_i$ as anomalous if $A_t(s_i) \ge \tau_{\text{anom}}$ (default $\tau_{\text{anom}} = 0.65$).

#### 3.2 Stage 2: Gated Correlation Anomaly-Weighted PageRank (`rca_engine.py`)

To prevent `networkx.pagerank()` row-normalization from turning downstream leaf nodes into absorbing black holes or leaking probability mass when correlation is zero, implement **Algorithm 1: Gated Correlation Anomaly-Weighted PageRank**:

1. Extract the anomalous node set $V_{\text{anom}} = \{ s_i \in V \mid A_t(s_i) \ge \tau_{\text{anom}} \}$ and construct the induced subgraph $G_{\text{anom}} = (V_{\text{anom}}, E_{\text{anom}})$.
2. For each directed dependency edge $(u \rightarrow v) \in E_{\text{anom}}$ (where upstream caller $u$ calls downstream callee $v$), compute the positive Pearson correlation with a zero-variance flatline guard:

$$\rho^+(u, v) = \begin{cases} \max\left(0.0, \; \text{PearsonCorr}(L_{p99}(u), L_{p99}(v))\right) & \text{if } \sigma(L_{p99}(u)) > 10^{-4} \text{ and } \sigma(L_{p99}(v)) > 10^{-4} \\ \frac{\min(A_t(u), A_t(v))}{\max(A_t(u), A_t(v))} & \text{otherwise (steady-state / flatline fallback)} \end{cases}$$

3. **Assign Forward Propagation Weights (Gated Correlation):**
   Gating by $(\rho^+)^2$ ensures that if downstream latency is uncorrelated ($\rho^+ \approx 0$), no transition weight is assigned to the forward edge, preventing mass from leaking into innocent downstream services:

$$w(u \rightarrow v) = A_t(v) \cdot \left(\rho^+(u, v)\right)^2$$

4. **Assign Competing Self-Loops on Internal Nodes Only:**
   For any node $u \in V_{\text{anom}}$ that has anomalous downstream dependencies ($\mathcal{N}_{\text{out}}^{\text{anom}}(u) \neq \emptyset$), assign a self-loop representing the **internal fault hypothesis**:

$$w(u \rightarrow u) = A_t(u) \cdot \left(1.0 - \max_{v \in \mathcal{N}_{\text{out}}^{\text{anom}}(u)} \rho^+(u, v)\right)$$

   - _Mathematical Effect:_ When downstream $v$ causes $u$'s latency spike ($\rho^+ \approx 1.0$), $w(u \rightarrow u) \rightarrow 0$ and transition mass flows forward to $v$. When $u$ has an internal fault and downstream $v$ is uncorrelated ($\rho^+ \approx 0$), $w(u \rightarrow v) \rightarrow 0$ and $w(u \rightarrow u) \rightarrow A_t(u)$, retaining $100\%$ of probability mass at $u$.
   - **Leaf/Sink Nodes Handling:** Do NOT add artificial absorbing self-loops $w(u \rightarrow u) = 1.5 A_t(u)$ on sink nodes ($\mathcal{N}_{\text{out}}^{\text{anom}}(u) = \emptyset$). By leaving sinks without outgoing edges in $G_{\text{anom}}$, `networkx.pagerank()` treats them as dangling nodes and redistributes their teleport probability across the personalization vector $\mathbf{p} = \mathbf{A}_t / \sum A_t$, completely eliminating the $5.67\times$ absorbing state trap.

5. Compute Personalized PageRank $\mathbf{r} = \text{PageRank}(G_{\text{anom}}, \alpha=0.85, \text{personalization}=A_t, \text{weight}='weight')$ and isolate the root cause:

$$s_{\text{root}} = \arg\max_{s_i \in V_{\text{anom}}} \mathbf{r}(s_i)$$

---

### PHASE 4: Intelligent Planner, Log Agent & Actuator (`control-plane/planner` & `executor`)

**Goal:** Map the isolated root cause to a deterministic, priority-ordered remediation action with cooldown protection and log verification.

#### 4.1 Priority-Ordered Remediation Policy Matrix (`policy_engine.py`)

Because faults often produce overlapping symptoms (e.g., a memory leak also increases $L_{p99}$ latency due to GC pressure), `policy_engine.py` MUST evaluate conditions on $X_t(s_{\text{root}})$ in strict **Priority Order (`1` through `4`)**:

| Priority        | Fault Signature        | Evaluation Condition on $s_{\text{root}}$                                               | Selected Action              | Execution Behavior                                                                                          |
| --------------- | ---------------------- | --------------------------------------------------------------------------------------- | ---------------------------- | ----------------------------------------------------------------------------------------------------------- |
| **1 (Highest)** | `MEMORY_CREEP_LEAK`    | $\Delta \text{MEM}_t \gt 1.5\text{ MB/s}$ OR $\text{MEM}_{\text{MB}} \gt 250\text{ MB}$ | `GRACEFUL_ROLLING_RESTART`   | Spins up fresh replica and drains leaked heap buffer without dropping active requests.                      |
| **2**           | `ERROR_SPIKE_CRASH`    | $\text{ErrRate}_{\%} \gt 15\%$ OR HTTP 5xx exception burst                              | `POD_RESTART_OR_ROLLBACK`    | Parses stack trace in logs and restarts pod / resets broken connection pool.                                |
| **3**           | `TRAFFIC_OVERLOAD`     | $\text{CPU}_{\%} \gt 70\%$ AND $\text{ErrRate}_{\%} \le 15\%$                           | `PROACTIVE_HORIZONTAL_SCALE` | Scales deployment replicas `current + 2` (up to `MAX_REPLICAS = 5`), reducing per-pod CPU & queueing delay. |
| **4 (Default)** | `LATENCY_GRAY_FAILURE` | $L_{p99} \gt 500\text{ms}$ OR Fallback for any unclassified $s_{\text{root}} \in V_{\text{anom}}$ | `CIRCUIT_BREAK_AND_RESET`    | Resets stuck downstream worker/thread lock and flushes stalled request queues.                              |

#### 4.2 Anti-Flapping Cooldown Lock

- Query `knowledge_base.db` for the most recent completed remediation on $s_{\text{root}}$. If $t_{\text{now}} - t_{\text{last\_heal}} \lt T_{\text{cool}}$ (`45 seconds`, where $t_{\text{last\_heal}}$ defaults to $-\infty$ if never healed), suppress execution and log `[PLAN] Action suppressed by cooldown lock`.

#### 4.3 Log Diagnostic Agent (`log_agent.py`)

- Fetch recent logs from $s_{\text{root}}$.
- If `GEMINI_API_KEY` or `OPENAI_API_KEY` is present in the environment, invoke the LLM/MCP diagnostic tool to summarize the exception and confirm the remediation plan.
- If no API key is set, automatically run the built-in deterministic regex log analyzer (`DatabaseConnectionPoolExhaustedError`, `MemoryLeakWarning`, `UpstreamTimeoutError`, `ThreadStarvationWarning`) so the pipeline works 100% offline.

#### 4.4 Dual-Mode Actuator (`k8s_actuator.py`)

- If `EXECUTION_MODE=k8s`, execute native `kubernetes.client.AppsV1Api` calls (`patch_namespaced_deployment_scale` and rolling restart pod template annotations).
- Simultaneously (or when `EXECUTION_MODE=local`), invoke `POST /debug/remediate` on $s_{\text{root}}$ so local benchmarks reflect realistic warmup recovery curves and virtual replica scaling.

---

### PHASE 5: Automated Chaos Benchmark, Ablation Study & Plot Generator (`chaos-experiments/`)

**Goal:** Automatically generate empirical CSV data and 300-DPI IEEE research paper charts, including an ablation study proving the necessity of Graph PageRank RCA.

#### 5.1 Four-Way Comparative & Ablation Benchmark (`benchmark_runner.py`)

Run each of the 4 fault scenarios (`cascading_latency`, `memory_leak`, `error_spike`, `traffic_overload`) across 4 evaluation modes:

1. **`no_healing`:** Fault remains active; measures baseline degradation.
2. **`reactive_k8s` (Orchestrator Baseline):** Simulates standard Kubernetes liveness probes + static HPA (only reacts after `OOMKilled` crash at `512MB` memory limit or sustained CPU exceeding $85\%$; completely blind to gray latency failures where `/health` returns `200 OK`).
3. **`ablation_no_rca` (Isolation Forest Only — No PageRank):** Uses Stage 1 Anomaly Detection but remediates the highest raw anomaly score or first alerting upstream node without Graph PageRank localization (demonstrating why naive ML alerting restarts `api-gateway` during downstream faults).
4. **`proactive_mapek` (Proposed Full System):** Full Freeze-Protected Isolation Forest + Self-Loop Competing PageRank RCA + Priority Policy Matrix.

#### 5.2 Output Metrics & High-Resolution Figures (`plot_generator.py`)

1. Save raw time-series data to `chaos-experiments/results/timeseries_log.csv` and summary metrics to `chaos-experiments/results/experiment_summary.csv` (`scenario`, `mode`, `mttd_sec`, `mttr_sec`, `dropped_requests`, `success_rate_pct`, `rca_top1_accuracy`, `wasted_upstream_restarts`).
2. Generate 4 publication-ready charts in `chaos-experiments/results/figures/` (`300 DPI`):

- `fig1_mttr_mttd_comparison.png`: Grouped bar chart of **MTTD** and **MTTR (seconds)** across all 4 fault scenarios (Reactive K8s vs. Proposed MAPE-K).
- `fig2_gray_failure_latency_timeline.png`: Continuous time-series plot ($t=0\text{s} \dots 120\text{s}$) of $p99$ latency during a cascading gray failure across `no_healing`, `reactive_k8s`, and `proactive_mapek` with vertical phase annotations (_Fault Injected_, _Proactive Detection_, _Warmup Recovery Complete_).
- `fig3_rca_ablation_accuracy.png`: Ablation comparison of **Top-1 Root Cause Localization Accuracy (%)** and **False Upstream Restarts** comparing Naive Threshold Alerting, Isolation Forest Only (`ablation_no_rca`), and Proposed Self-Loop PageRank RCA (`proactive_mapek`).
- `fig4_request_success_rate.png`: Request Success Rate (%) and dropped request reduction across all 4 scenarios.

---

### PHASE 6: Live Demo & Viva Dashboard (`dashboard/app.py`)

**Goal:** Build an interactive Streamlit dashboard for live project demonstration.

- **Top Metrics Row:** System Status badge, Active Root Cause Alert, Mean Time To Detect (MTTD), Mean Time To Recover (MTTR), Active Virtual Replicas.
- **Interactive Chaos Sidebar:** One-click buttons to inject faults live into any microservice (`Inject Payment Latency 1200ms`, `Inject Inventory Error Spike`, `Inject Order Memory Leak`, `Inject Gateway CPU Overload`, `Reset All Services`).
- **Live 5-Node Branching Topology Graph View:** Visualizes the directed graph (`api-gateway -> auth-service`, `api-gateway -> order-service -> {payment-service, inventory-service}`) with live node coloring (Green = Healthy, Orange = Cascading Upstream Victim, Red = Isolated Root Cause with PageRank score $\mathbf{r}(s_i)$).
- **Real-Time Telemetry & Audit Table:** Live line charts of $L_{p99}$, Memory (MB), and Anomaly Score $A_t(s_i)$, plus the live `remediation_incidents` table showing the Log Agent's diagnostic reasoning.

---

## Part 5: Copy-Paste Prompt to Audit & Build Your Repository

Send this prompt to your AI coding agent to execute the entire specification:

```text
Read README.md carefully. First, perform PHASE 0 (Existing Codebase Audit):
1. Inspect all files currently in my repository.
2. Score my existing codebase against the 5 pillars in Phase 0 (Topology, Telemetry, Gray Failure Readiness, Chaos Hooks, Control Plane Compatibility) using a Markdown table (✅ Ready, ⚠️ Partial, ❌ Missing).
3. Immediately upgrade my existing code and build out Phase 1 through Phase 6 step-by-step according to the exact v2.0 specifications in README.md (including the 5-service branching topology, 10s sliding telemetry window, baseline-frozen Isolation Forest with sigmoid calibration, self-loop competing PageRank RCA, priority-ordered policy matrix, and 4-way ablation benchmark). Ensure every file contains complete, runnable code with zero TODO placeholders.

```

---

## Part 6: Research Paper Blueprint (IEEE / Springer Structure)

When writing your research paper after running `benchmark_runner.py` and `plot_generator.py`, structure your manuscript into these 6 standard sections:

### 1. Title Ideas

- _"An Autonomous MAPE-K Framework for Proactive Gray Failure Detection and Topological Root Cause Remediation in Cloud-Native Microservices"_
- _"Proactive Self-Healing in Distributed Microservices Using Slope-Aware Anomaly Detection and Self-Loop Competing PageRank Localization"_

### 2. Section-by-Section Paper Writing Guide

| Section                                             | Content to Include                                                                                                                                                                                                                                                                                                                | Figures / Tables to Insert                                                                        |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| **I. Abstract & Introduction**                      | Contrast hard crashes vs. gray failures. Highlight why Kubernetes liveness probes and static HPA fail during cascading latency spikes. State your 3 core contributions: (1) Freeze-protected multi-signal anomaly detection, (2) Self-loop competing PageRank RCA on branching call graphs, (3) Closed-loop priority remediation. | Bullet list of contributions                                                                      |
| **II. Related Work**                                | Review 12–15 papers on (a) Reactive container orchestration, (b) Unsupervised anomaly detection in microservices, and (c) Trace-based root cause analysis. Point out that prior works either suffer from row-normalization bias on linear call chains or stop at _detection_ without closed-loop _remediation_.                   | **Table I:** Comparison of Existing Works vs. Proposed System across 6 features                   |
| **III. Proposed System Architecture & Methodology** | Explain the 4 stages of your MAPE-K loop. Include the 7D telemetry vector $X_t(s_i)$, the calibrated Isolation Forest + soft disjunctive heuristic fusion score $A_t(s_i)$, and the Gated Correlation PageRank equations $w(u \rightarrow v)$ and $w(u \rightarrow u)$.                                                                          | **System Architecture Diagram** + **Algorithm 1 Pseudocode** (below)                              |
| **IV. Experimental Setup**                          | Describe the 5-microservice branching testbed (`api-gateway`, `auth`, `order`, `payment`, `inventory`), 10-second sliding telemetry window, $\Delta t = 5\text{s}$ control loop, cooldown lock ($T_{\text{cool}} = 45\text{s}$), and the 4 chaos scenarios.                                                                       | **Table II:** Microservice Testbed & Hyperparameter Configuration                                 |
| **V. Results, Ablation Study & Discussion**         | Present the quantitative improvements in **MTTD**, **MTTR**, **RCA Top-1 Accuracy**, and **Request Success Rate (%)** across No Healing, Reactive K8s, Ablation (No Graph RCA), and Proposed MAPE-K.                                                                                                                              | **Figures 1, 2, 3, and 4** generated by `plot_generator.py` + **Table III:** Quantitative Summary |
| **VI. Conclusion & Future Work**                    | Summarize MTTR reduction (%) and gray failure recovery capability. Mention future integration with eBPF kernel-level telemetry and Reinforcement Learning policy optimization.                                                                                                                                                    | —                                                                                                 |

### 3. Formal Algorithm 1 Block for Section III of Your Paper

Include this exact, mathematically verified algorithm in your paper's Methodology section:

```text
Algorithm 1: Proactive Anomaly-Driven Root Cause Localization & Autonomous Remediation
--------------------------------------------------------------------------------------
Input:  Directed Service Dependency Graph G = (V, E), Poll Interval Δt = 5s,
        Baseline Models {M_IF(s_i)}, Anomaly Threshold τ_anom = 0.65, Cooldown T_cool = 45s
Output: Executed Remediation Action a* on Isolated Root Cause Service s_root

1:  while cluster is running do
2:      V_anom ← ∅
3:      for each service s_i ∈ V do
4:          ΔMEM_t(s_i) ← (MEM_t(s_i) - MEM_{t-k}(s_i)) / (k · Δt)   // k = min(|history|, W), k ≥ 1
5:          X_t(s_i) ← [CPU_%, MEM_MB, RPS, ErrRate_%, L_p50, L_p99, ΔMEM_t(s_i)]
6:          d_t(s_i) ← M_IF(s_i).decision_function(X_t(s_i))
7:          S_IF(s_i) ← 1 / (1 + exp(5.0 · d_t(s_i)))              // Sigmoid polarity calibration
8:          H_t(s_i) ← clip(max(0, (L_p99-120)/600, ΔMEM_t/1.5, (MEM-160)/150, Err%/20, (CPU-65)/30), 0, 1)
9:          A_t(s_i) ← clip(1.0 - (1.0 - S_IF(s_i)) · (1.0 - H_t(s_i)), 0, 1) // Soft disjunctive fusion
10:         if A_t(s_i) ≥ τ_anom then
11:             V_anom ← V_anom ∪ {s_i}
12:         else if BaselineBufferNotFull(s_i) then
13:             M_IF(s_i).fit_or_update(X_t(s_i))                  // Freeze rule: never update on anomalous samples
14:         end if
15:     end for
16:     if V_anom ≠ ∅ then
17:         G_anom ← InducedSubgraph(G, V_anom)
18:         for each directed call edge (u → v) ∈ E(G_anom) do
19:             ρ+(u, v) ← SafePearsonCorr(L_p99(u), L_p99(v))       // Fallback to min-ratio if σ < 1e-4
20:             w(u → v) ← A_t(v) · (ρ+(u, v))^2                     // Gated downstream propagation weight
21:         end for
22:         for each node u ∈ V_anom with OutNeighbors(G_anom, u) ≠ ∅ do
23:             ρ_max(u) ← max_{v ∈ OutNeighbors(G_anom, u)} ρ+(u, v)
24:             w(u → u) ← A_t(u) · (1.0 - ρ_max(u))                 // Internal fault competing self-loop
25:         end for                                                  // Leaf sinks remain natural dangling nodes
26:         r ← PersonalizedPageRank(G_anom, α = 0.85, p = A_t, weight = 'weight')
27:         s_root ← argmax_{s_i ∈ V_anom} r(s_i)
28:         if (t_now - LastHealTime(s_root)) > T_cool then          // LastHealTime defaults to -∞
29:             fault_type ← PriorityClassify(X_t(s_root), ΔMEM_t(s_root)) // Order: MEM > ERR > CPU > DEFAULT
30:             log_context ← LogDiagnosticAgent(s_root, tail = 30)
31:             a* ← PolicyMatrix(fault_type, log_context)
32:             ExecuteRemediation(s_root, a*)
33:             RecordIncident(s_root, r(s_root), fault_type, a*, MTTD, MTTR)
34:         end if
35:     end if
36:     sleep(Δt)
37: end while
```
