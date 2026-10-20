# System Architecture: Autonomous Self-Healing Distributed Backend System

This document provides the high-level and detailed architecture of the Autonomous Self-Healing Microservices Mesh.

An interactive hand-drawn diagram file is provided in this repository at:
**[`docs/architecture.excalidraw`](./architecture.excalidraw)**

You can view and edit it by:
1. Dragging and dropping [`architecture.excalidraw`](./architecture.excalidraw) into [excalidraw.com](https://excalidraw.com).
2. Opening it directly in VS Code / Cursor using the **Excalidraw extension**.

---

## 1. Complete System Architecture Diagram

```mermaid
flowchart TD
    subgraph ManagedCluster["Target Cluster (Kubernetes Managed System)"]
        direction TB
        Client["Client / External Traffic"] -->|REST /checkout| GW["API Gateway\n(Port 8000)"]
        
        GW -->|1. /verify| Auth["Auth Service\n(Port 8001)"]
        GW -->|2. /orders| Order["Order Service\n(Port 8002)"]
        
        Order -->|Branch A: /charge| Payment["Payment Service\n(Port 8003)"]
        Order -->|Branch B: /reserve| Inventory["Inventory Service\n(Port 8004)"]
        
        subgraph SharedAgent["Mesh Observability & Chaos Agent"]
            Sidecar["• Prometheus /metrics\n• Telemetry /snapshot\n• Chaos /debug/fault/*\n• Health Probe (Gray Failure)"]
        end
        
        Prom["Prometheus Telemetry Server\n(Scrapes /metrics every 2s)"]
    end

    GW -.-> Prom
    Auth -.-> Prom
    Order -.-> Prom
    Payment -.-> Prom
    Inventory -.-> Prom

    subgraph MAPE["Autonomous Self-Healing Controller (MAPE-K Closed Loop)"]
        direction LR
        
        subgraph M["Monitor (M)"]
            M1["PromQL Metric Puller\nDual-Window Moving Stats\n(W_fast=30s, W_slow=300s)\n7D Feature Vector x_i"]
        end
        
        subgraph A["Analyze (A)"]
            A1["Soft Disjunctive Anomaly Fusion\nS_i = 1 - Π (1 - c_k · σ(z_ik))\nGated PageRank RCA\np = (1-d)v + d M^T p\nInvert Cascading Gray Failures"]
        end
        
        subgraph P["Plan (P)"]
            P1["Priority Policy Matrix\n4-Level Progressive Escalation\nL1: Pool Recycle | L2: Rate Shed\nL3: Circuit Break | L4: K8s Restart\nAnti-Flapping Cooldown (120s)"]
        end
        
        subgraph E["Execute (E)"]
            E1["Kubernetes API Actuator\n(Rolling Pod Restart / Replica Scale)\nEnvoy / Service Mesh Routes\nIn-Process Chaos Reset (/reset)"]
        end
        
        subgraph K["Shared Knowledge Base (K)"]
            K1["• Dynamic Call Graph Adjacency Matrix W\n• Historical Anomaly Signatures & Posteriors\n• MTTR & Safety Invariants"]
        end
        
        M1 -->|7D Telemetry Vector| A1
        A1 -->|Root-Cause Node| P1
        P1 -->|Remediation Action| E1
        
        K1 <-.-> M1
        K1 <-.-> A1
        K1 <-.-> P1
        K1 <-.-> E1
    end

    Prom ==>|PromQL Metric Stream| M1
    E1 ==>|Kubernetes / In-Process Actuation| ManagedCluster

    classDef mesh fill:#e7f5ff,stroke:#1971c2,stroke-width:2px;
    classDef leaf fill:#e3fafc,stroke:#0c8599,stroke-width:2px;
    classDef prom fill:#ffe3e3,stroke:#e03131,stroke-width:2px;
    classDef monitor fill:#f3f0ff,stroke:#7950f2,stroke-width:2px;
    classDef analyze fill:#fff4e6,stroke:#fd7e14,stroke-width:2px;
    classDef plan fill:#fff9db,stroke:#fab005,stroke-width:2px;
    classDef execute fill:#ebfbee,stroke:#40c057,stroke-width:2px;
    classDef kb fill:#f1f3f5,stroke:#495057,stroke-width:2px;

    class GW,Auth,Order mesh;
    class Payment,Inventory leaf;
    class Prom prom;
    class M1 monitor;
    class A1 analyze;
    class P1 plan;
    class E1 execute;
    class K1 kb;
```

---

## 2. Key Architectural Layers

### A. Target Cluster (5-Microservice Branching DAG)
- **`api-gateway` (Port 8000)**: Ingress orchestrator that validates requests and initiates downstream calls.
- **`auth-service` (Port 8001)**: High-throughput authentication verification.
- **`order-service` (Port 8002)**: Multi-branch business logic coordinator.
- **`payment-service` (Port 8003)**: Financial capture leaf node (Branch A).
- **`inventory-service` (Port 8004)**: Stock reservation leaf node (Branch B).

### B. Observability & Chaos Injection
Every service incorporates uniform telemetry and fault injection:
- `/metrics`: Prometheus exposition of p50, p95, p99 latencies, request counts, errors, and in-flight concurrency.
- `/telemetry/snapshot`: Real-time JSON telemetry diagnostics.
- `/debug/fault/*`: In-process fault injection (latency, CPU burn, memory leaks, thread starvation, error spikes).
- `/health`: Naive Kubernetes liveness probe (used to demonstrate gray failure blind spots).

### C. MAPE-K Closed-Loop Controller
1. **Monitor (M)**: Ingests 7D telemetry vector $\vec{x}_i \in \mathbb{R}^7$ across sliding windows ($W_{\text{fast}}=30\text{s}$, $W_{\text{slow}}=300\text{s}$).
2. **Analyze (A)**: Fuses dimensional anomalies using soft disjunctive fusion ($S_i$) and isolates root causes via Gated Correlation PageRank ($\mathbf{p} = (1-d)\mathbf{v} + d\mathbf{M}^T\mathbf{p}$).
3. **Plan (P)**: Evaluates a 4-level progressive escalation matrix with an anti-flapping cooldown timer ($120\text{s}$).
4. **Execute (E)**: Actuates remediation through the Kubernetes API and dynamic service mesh traffic controls.
5. **Knowledge Base (K)**: Persists mesh topology, fault history, and safety policies.
