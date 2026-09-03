# Self-Healing Distributed Systems

This repository contains the microservice foundation for a self-healing distributed-systems project. The current implementation models an order workflow whose request flow, service failures, and compensating actions can be observed through structured logs. It is deliberately small and runnable so that log analysis, root-cause analysis, agentic RAG, and automated remediation can be layered on top without coupling those concerns to business services.

## Implemented architecture

```text
Client
  |
  v
order-service :8000
  | reserves stock                         | charges payment
  v                                        v
inventory-service :8001               payment-service :8002
```

`order-service` orchestrates a synchronous three-step workflow:

1. Reserve the requested quantity in `inventory-service`.
2. Charge the request through `payment-service`.
3. Return a confirmed order only after both operations succeed.

If payment is declined or unreachable after stock has been reserved, the order service calls the inventory release endpoint. This is a small, explicit compensating-transaction (saga) flow that produces useful failure signals for the later self-healing pipeline.

## Services

| Service | Port | Responsibility |
| --- | --- | --- |
| Order service | 8000 | Validates orders, coordinates inventory and payment, and compensates failed payment flows. |
| Inventory service | 8001 | Exposes stock levels and creates/releases inventory reservations. Seed stock: product `1` = 100, `2` = 50, `3` = 0. |
| Payment service | 8002 | Provides a deterministic payment stub. Any token except `decline` is captured; `decline` returns a payment failure. |

All APIs are versioned under `/api/v1`. Every service provides `GET /api/v1/health` for orchestration health checks.

## API reference

| Service | Method and path | Purpose |
| --- | --- | --- |
| Order | `POST /orders` | Reserve stock, capture payment, and create a confirmed order. |
| Order | `GET /health` | Service liveness endpoint. |
| Inventory | `GET /inventory/{product_id}` | Return currently available stock for a product. |
| Inventory | `POST /inventory/reservations` | Atomically reserve stock; returns `409` when unavailable. |
| Inventory | `DELETE /inventory/reservations/{reservation_id}` | Release a prior reservation. |
| Payment | `POST /payments` | Capture a deterministic mock payment. |
| Payment | `GET /health` | Service liveness endpoint. |

Prefix every path in the table with `/api/v1`. The order failure-simulation paths are intentionally omitted because they are disabled unless explicitly enabled for isolated development.

## Observability and resilience hooks

- Services emit JSON logs with timestamp, level, service, logger, message, and `request_id` fields.
- A caller-supplied `X-Request-ID` is propagated from the order service to downstream calls and returned in the response. This makes one distributed transaction traceable across service logs.
- The order service applies a configurable downstream timeout (`REQUEST_TIMEOUT_SECONDS`, default `3`). It reports unavailable dependencies as `503` and unexpected downstream rejections as `502`.
- Failure simulation endpoints remain available in order service but are disabled by default. Set `FAILURE_SIMULATION_ENABLED=true` only in an isolated development environment before using `/api/v1/simulate/*`.

The service state is intentionally in memory and the payment implementation is a stub. Persistence, asynchronous messaging, authentication, and the log-analysis/RAG/remediation components are not yet implemented.

## Run locally with Docker Compose

```bash
docker compose up --build
```

The services become available at `http://localhost:8000`, `http://localhost:8001`, and `http://localhost:8002`. Compose waits for inventory and payment health checks before starting the order service.

Stop the stack with:

```bash
docker compose down
```

## Exercise the order flow

Create a successful order:

```bash
curl -i -X POST http://localhost:8000/api/v1/orders \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: demo-order-001' \
  -d '{"product_id": 1, "quantity": 2, "amount": 49.99, "payment_token": "approved"}'
```

The response is `201 Created` with the generated `order_id`, `reservation_id`, and `payment_id`. Inspect the logs for `demo-order-001` to follow the same transaction through all three services.

Exercise payment failure and inventory compensation:

```bash
curl -i -X POST http://localhost:8000/api/v1/orders \
  -H 'Content-Type: application/json' \
  -d '{"product_id": 1, "quantity": 2, "amount": 49.99, "payment_token": "decline"}'
```

This returns `402 Payment Required`; the prior inventory reservation is released. Requesting more stock than is available returns `409 Conflict`.

Check inventory directly:

```bash
curl http://localhost:8001/api/v1/inventory/1
```

## Configuration

Order service configuration can be set through environment variables. The local `services/order-service/.env` targets ports on the host; Compose overrides those URLs with service DNS names.

For a local non-container run, create `services/order-service/.env` from [`services/order-service/.env.example`](services/order-service/.env.example).

| Variable | Default | Purpose |
| --- | --- | --- |
| `INVENTORY_SERVICE_URL` | `http://localhost:8001` | Inventory base URL. |
| `PAYMENT_SERVICE_URL` | `http://localhost:8002` | Payment base URL. |
| `REQUEST_TIMEOUT_SECONDS` | `3.0` | Timeout for each downstream HTTP request. |
| `FAILURE_SIMULATION_ENABLED` | `false` | Enables destructive development-only simulation routes. |
