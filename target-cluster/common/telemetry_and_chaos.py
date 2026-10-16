"""
Shared Telemetry & Chaos Middleware for Autonomous Self-Healing Microservices.
Implements:
1. GET /health (Naive liveness probe returning HTTP 200 even under gray failures)
2. GET /metrics (Prometheus scrape endpoint) & GET /telemetry/snapshot (JSON telemetry snapshot)
3. POST /debug/fault/* (Deterministic chaos injection for latency, memory leak, CPU burn, error spike, and reset)
4. Structured log ring buffer (last 50 log records)
5. Request tracing (X-Request-ID propagation)
"""

import asyncio
from collections import deque
from datetime import datetime, timezone
import gc
import logging
import math
import os
import random
import threading
import time
import traceback
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CollectorRegistry, Counter, Histogram, Gauge, generate_latest
import psutil
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Ring Buffer Log Handler
# -----------------------------------------------------------------------------

class RingBufferLogHandler(logging.Handler):
    """Stores the last N structured log entries in memory."""

    def __init__(self, service_name: str, max_records: int = 50):
        super().__init__()
        self.service_name = service_name
        self.buffer: deque = deque(maxlen=max_records)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord):
        try:
            timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
            exc_text = None
            if record.exc_info:
                exc_text = "".join(traceback.format_exception(*record.exc_info))

            request_id = getattr(record, "request_id", None)
            entry = {
                "timestamp": timestamp,
                "level": record.levelname,
                "service": self.service_name,
                "logger": record.name,
                "message": record.getMessage(),
                "request_id": request_id,
                "exception": exc_text,
            }
            with self._lock:
                self.buffer.append(entry)
        except Exception:
            self.handleError(record)

    def get_recent_logs(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.buffer)


# -----------------------------------------------------------------------------
# Chaos State Manager
# -----------------------------------------------------------------------------

class LatencyFaultConfig(BaseModel):
    delay_ms: float = Field(default=1200.0, description="Injected delay in milliseconds")
    jitter_ms: float = Field(default=150.0, description="Random jitter in milliseconds")
    enabled: bool = Field(default=True, description="Enable or disable latency fault")


class MemoryLeakFaultConfig(BaseModel):
    rate_mb_per_sec: float = Field(default=4.0, description="Rate of memory growth in MB/sec")
    enabled: bool = Field(default=True, description="Enable or disable memory leak")


class CpuBurnFaultConfig(BaseModel):
    utilization_target: float = Field(default=0.85, description="Target CPU utilization between 0.1 and 1.0")
    enabled: bool = Field(default=True, description="Enable or disable CPU burn")


class ErrorSpikeFaultConfig(BaseModel):
    failure_rate: float = Field(default=0.60, description="Fraction of requests that fail (0.0 to 1.0)")
    http_code: int = Field(default=500, description="HTTP status code returned on error")
    exception_type: str = Field(default="DatabaseConnectionPoolExhaustedError", description="Name of simulated exception")
    enabled: bool = Field(default=True, description="Enable or disable error spike")


class ChaosManager:
    """Manages active synthetic faults and execution state."""

    def __init__(self, service_name: str, logger: logging.Logger):
        self.service_name = service_name
        self.logger = logger
        self.lock = threading.Lock()

        # Fault configurations
        self.latency = {"enabled": False, "delay_ms": 1200.0, "jitter_ms": 150.0}
        self.memory_leak = {"enabled": False, "rate_mb_per_sec": 4.0}
        self.cpu_burn = {"enabled": False, "utilization_target": 0.85}
        self.error_spike = {
            "enabled": False,
            "failure_rate": 0.60,
            "http_code": 500,
            "exception_type": "DatabaseConnectionPoolExhaustedError",
        }
        self.hard_crash = False

        # Memory buffer and CPU worker
        self.leak_buffer: List[bytearray] = []
        self._leak_task: Optional[asyncio.Task] = None
        self._cpu_thread: Optional[threading.Thread] = None
        self._stop_cpu_event = threading.Event()

    def set_latency(self, config: LatencyFaultConfig):
        with self.lock:
            self.latency["enabled"] = config.enabled
            self.latency["delay_ms"] = float(config.delay_ms)
            self.latency["jitter_ms"] = float(config.jitter_ms)
        self.logger.warning(
            f"[CHAOS] Latency fault set: enabled={config.enabled}, delay={config.delay_ms}ms, jitter={config.jitter_ms}ms"
        )

    def set_memory_leak(self, config: MemoryLeakFaultConfig, loop: Optional[asyncio.AbstractEventLoop] = None):
        with self.lock:
            self.memory_leak["enabled"] = config.enabled
            self.memory_leak["rate_mb_per_sec"] = float(config.rate_mb_per_sec)

        if config.enabled:
            self.logger.warning(f"[CHAOS] Memory leak fault enabled at {config.rate_mb_per_sec} MB/s")
            self._ensure_leak_task_running(loop)
        else:
            self.logger.info("[CHAOS] Memory leak fault disabled")

    def _ensure_leak_task_running(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        if self._leak_task is None or self._leak_task.done():
            try:
                active_loop = loop or asyncio.get_running_loop()
                self._leak_task = active_loop.create_task(self._memory_leak_loop())
            except RuntimeError:
                pass

    async def _memory_leak_loop(self):
        """Asynchronously allocates memory chunks every 0.5 seconds while enabled."""
        chunk_interval = 0.5
        while True:
            with self.lock:
                enabled = self.memory_leak["enabled"]
                rate = self.memory_leak["rate_mb_per_sec"]

            if not enabled:
                break

            # Allocate rate * interval MB
            mb_to_allocate = rate * chunk_interval
            bytes_to_allocate = int(mb_to_allocate * 1024 * 1024)
            if bytes_to_allocate > 0:
                with self.lock:
                    self.leak_buffer.append(bytearray(bytes_to_allocate))

            await asyncio.sleep(chunk_interval)

    def set_cpu_burn(self, config: CpuBurnFaultConfig):
        with self.lock:
            self.cpu_burn["enabled"] = config.enabled
            self.cpu_burn["utilization_target"] = max(0.1, min(1.0, float(config.utilization_target)))

        if config.enabled:
            self.logger.warning(f"[CHAOS] CPU burn fault enabled at target {config.utilization_target * 100:.0f}%")
            self._ensure_cpu_worker_running()
        else:
            self._stop_cpu_event.set()
            self.logger.info("[CHAOS] CPU burn fault disabled")

    def _ensure_cpu_worker_running(self):
        if self._cpu_thread is None or not self._cpu_thread.is_alive():
            self._stop_cpu_event.clear()
            self._cpu_thread = threading.Thread(target=self._cpu_burn_worker, daemon=True)
            self._cpu_thread.start()

    def _cpu_burn_worker(self):
        """Runs a controlled busy-loop in a background thread to burn CPU cycles."""
        interval = 0.05
        while not self._stop_cpu_event.is_set():
            with self.lock:
                enabled = self.cpu_burn["enabled"]
                target = self.cpu_burn["utilization_target"]

            if not enabled:
                time.sleep(0.1)
                continue

            work_duration = interval * target
            sleep_duration = interval * (1.0 - target)

            start = time.perf_counter()
            while (time.perf_counter() - start) < work_duration:
                # Math calculation to keep CPU core busy
                _ = math.sqrt(random.random() * 1000000.0)

            if sleep_duration > 0.001:
                time.sleep(sleep_duration)

    def set_error_spike(self, config: ErrorSpikeFaultConfig):
        with self.lock:
            self.error_spike["enabled"] = config.enabled
            self.error_spike["failure_rate"] = float(config.failure_rate)
            self.error_spike["http_code"] = int(config.http_code)
            self.error_spike["exception_type"] = config.exception_type
        self.logger.warning(
            f"[CHAOS] Error spike fault set: enabled={config.enabled}, rate={config.failure_rate*100:.0f}%, "
            f"code={config.http_code}, type={config.exception_type}"
        )

    def reset_all(self):
        with self.lock:
            self.latency["enabled"] = False
            self.memory_leak["enabled"] = False
            self.cpu_burn["enabled"] = False
            self.error_spike["enabled"] = False
            self.hard_crash = False
            self.leak_buffer.clear()

        self._stop_cpu_event.set()
        if self._leak_task and not self._leak_task.done():
            self._leak_task.cancel()

        gc.collect()
        self.logger.info(f"[REMEDIATION] Service state restored to healthy for {self.service_name}")

    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "service": self.service_name,
                "latency": dict(self.latency),
                "memory_leak": dict(self.memory_leak),
                "cpu_burn": dict(self.cpu_burn),
                "error_spike": dict(self.error_spike),
                "hard_crash": self.hard_crash,
                "leak_buffer_chunks": len(self.leak_buffer),
            }


# -----------------------------------------------------------------------------
# Sliding Window Rolling Telemetry Metrics
# -----------------------------------------------------------------------------

class RequestWindowSample:
    __slots__ = ("timestamp", "duration_ms", "is_error")

    def __init__(self, timestamp: float, duration_ms: float, is_error: bool):
        self.timestamp = timestamp
        self.duration_ms = duration_ms
        self.is_error = is_error


class RollingMetrics:
    """Computes real-time RPS, Error Rate, p50, and p99 latency over a sliding window."""

    def __init__(self, window_sec: float = 10.0):
        self.window_sec = window_sec
        self.samples: deque = deque()
        self.lock = threading.Lock()

    def record(self, duration_ms: float, is_error: bool):
        now = time.time()
        with self.lock:
            self.samples.append(RequestWindowSample(now, duration_ms, is_error))
            self._trim(now)

    def _trim(self, now: float):
        cutoff = now - self.window_sec
        while self.samples and self.samples[0].timestamp < cutoff:
            self.samples.popleft()

    def get_summary(self) -> Dict[str, float]:
        now = time.time()
        with self.lock:
            self._trim(now)
            count = len(self.samples)
            if count == 0:
                return {
                    "rps": 0.0,
                    "error_rate": 0.0,
                    "latency_p50_ms": 0.0,
                    "latency_p99_ms": 0.0,
                }

            error_count = sum(1 for s in self.samples if s.is_error)
            rps = round(count / self.window_sec, 2)
            error_rate = round((error_count / count) * 100.0, 2)

            durations = sorted(s.duration_ms for s in self.samples)
            p50_idx = int(0.50 * (count - 1))
            p99_idx = int(0.99 * (count - 1))

            latency_p50_ms = round(durations[p50_idx], 2)
            latency_p99_ms = round(durations[p99_idx], 2)

            return {
                "rps": rps,
                "error_rate": error_rate,
                "latency_p50_ms": latency_p50_ms,
                "latency_p99_ms": latency_p99_ms,
            }


# -----------------------------------------------------------------------------
# Service Telemetry & Chaos Setup Helper
# -----------------------------------------------------------------------------

def setup_telemetry_and_chaos(app: FastAPI, service_name: str) -> ChaosManager:
    """
    Attaches the Prometheus metrics, JSON telemetry snapshot, structured log
    ring buffer, naive /health probe, and /debug/fault/* chaos endpoints to the FastAPI app.
    """
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.INFO)

    # Attach ring buffer handler
    log_handler = RingBufferLogHandler(service_name=service_name, max_records=50)
    formatter = logging.Formatter('{"time":"%(asctime)s", "level":"%(levelname)s", "service":"%(name)s", "message":"%(message)s"}')
    log_handler.setFormatter(formatter)
    logger.addHandler(log_handler)

    # Attach root logger handler so all module logs are captured
    root_logger = logging.getLogger()
    if not any(isinstance(h, RingBufferLogHandler) for h in root_logger.handlers):
        root_logger.addHandler(log_handler)

    chaos_manager = ChaosManager(service_name=service_name, logger=logger)
    rolling_metrics = RollingMetrics(window_sec=10.0)

    # Prometheus Registry & Metrics
    registry = CollectorRegistry()
    http_requests_total = Counter(
        "http_requests_total",
        "Total HTTP requests handled by the service",
        ["method", "endpoint", "status"],
        registry=registry,
    )
    http_request_duration_seconds = Histogram(
        "http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "endpoint"],
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        registry=registry,
    )
    cpu_gauge = Gauge("process_cpu_percent", "Process CPU utilization percent", registry=registry)
    mem_gauge = Gauge("process_memory_rss_mb", "Process resident memory in MB", registry=registry)

    # Initialize psutil Process
    process = psutil.Process(os.getpid())
    process.cpu_percent(interval=None)

    # -------------------------------------------------------------------------
    # HTTP Middleware for Telemetry, Tracing, and Fault Injection
    # -------------------------------------------------------------------------
    @app.middleware("http")
    async def telemetry_and_chaos_middleware(request: Request, call_next):
        # 1. Tracing context propagation
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = request.headers.get("x-request-id") or f"req-{int(time.time()*1000)}-{random.randint(1000, 9999)}"
        request.state.request_id = request_id

        path = request.url.path

        # Hard crash check
        if chaos_manager.hard_crash and not path.startswith("/debug/fault"):
            os._exit(1)

        # Naive /health, /metrics, /telemetry, /debug paths bypass chaos delays & errors
        is_control_plane_path = (
            path == "/health"
            or path.endswith("/health")
            or path.startswith("/metrics")
            or path.startswith("/telemetry")
            or path.startswith("/debug/fault")
            or path == "/favicon.ico"
        )

        # Injected faults for business routes
        if not is_control_plane_path:
            # Error spike fault
            with chaos_manager.lock:
                err_cfg = dict(chaos_manager.error_spike)
            if err_cfg["enabled"] and random.random() < err_cfg["failure_rate"]:
                logger.error(
                    f"Simulated fault: {err_cfg['exception_type']}: Database connection pool exhausted",
                    extra={"request_id": request_id},
                )
                rolling_metrics.record(duration_ms=10.0, is_error=True)
                http_requests_total.labels(method=request.method, endpoint=path, status=str(err_cfg["http_code"])).inc()
                response = JSONResponse(
                    status_code=err_cfg["http_code"],
                    content={
                        "error": err_cfg["exception_type"],
                        "detail": f"Simulated gray failure: {err_cfg['exception_type']}",
                        "service": service_name,
                    },
                )
                response.headers["X-Request-ID"] = request_id
                return response

            # Latency fault
            with chaos_manager.lock:
                lat_cfg = dict(chaos_manager.latency)
            if lat_cfg["enabled"]:
                jitter = random.uniform(-lat_cfg["jitter_ms"], lat_cfg["jitter_ms"])
                delay_sec = max(0.0, (lat_cfg["delay_ms"] + jitter) / 1000.0)
                await asyncio.sleep(delay_sec)

        # Execute business route
        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            rolling_metrics.record(duration_ms=duration_ms, is_error=True)
            http_requests_total.labels(method=request.method, endpoint=path, status="500").inc()
            logger.exception(f"Unhandled exception in {service_name}: {exc}", extra={"request_id": request_id})
            err_response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
            err_response.headers["X-Request-ID"] = request_id
            return err_response

        duration_sec = time.perf_counter() - start_time
        duration_ms = duration_sec * 1000.0
        is_error = status_code >= 500

        # Record metrics
        http_requests_total.labels(method=request.method, endpoint=path, status=str(status_code)).inc()
        http_request_duration_seconds.labels(method=request.method, endpoint=path).observe(duration_sec)
        rolling_metrics.record(duration_ms=duration_ms, is_error=is_error)

        response.headers["X-Request-ID"] = request_id
        return response

    # -------------------------------------------------------------------------
    # Endpoints Router
    # -------------------------------------------------------------------------
    router = APIRouter()

    @router.get("/health", tags=["Observability"])
    @router.get("/api/v1/health", tags=["Observability"])
    def naive_health_probe():
        """
        Naive liveness probe.
        Returns HTTP 200 OK as long as the process is alive, even when latency
        or memory faults are active. Standard orchestrators rely on this and fail
        to detect gray failures!
        """
        return {
            "status": "healthy",
            "service": service_name,
            "pid": os.getpid(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @router.get("/metrics", response_class=PlainTextResponse, tags=["Observability"])
    def prometheus_metrics():
        """Exposes standard Prometheus scrape metrics."""
        try:
            cpu_val = process.cpu_percent(interval=None)
            mem_val = process.memory_info().rss / (1024 * 1024)
            cpu_gauge.set(cpu_val)
            mem_gauge.set(mem_val)
        except Exception:
            pass
        return PlainTextResponse(generate_latest(registry).decode("utf-8"), media_type="text/plain")

    @router.get("/telemetry/snapshot", tags=["Observability"])
    def telemetry_snapshot():
        """
        Fast JSON telemetry snapshot reporting CPU, memory, RPS, error rate,
        p50/p99 latency, active faults, and recent structured logs.
        """
        try:
            cpu_pct = round(process.cpu_percent(interval=None), 2)
            mem_mb = round(process.memory_info().rss / (1024 * 1024), 2)
        except Exception:
            cpu_pct = 0.0
            mem_mb = 0.0

        summary = rolling_metrics.get_summary()
        return {
            "service": service_name,
            "timestamp": time.time(),
            "cpu_pct": cpu_pct,
            "mem_mb": mem_mb,
            "rps": summary["rps"],
            "error_rate": summary["error_rate"],
            "latency_p50_ms": summary["latency_p50_ms"],
            "latency_p99_ms": summary["latency_p99_ms"],
            "active_faults": chaos_manager.get_status(),
            "recent_logs": log_handler.get_recent_logs(),
        }

    # -------------------------------------------------------------------------
    # Deterministic Chaos Endpoints
    # -------------------------------------------------------------------------
    @router.post("/debug/fault/latency", tags=["Chaos Engineering"])
    def inject_latency_fault(config: LatencyFaultConfig):
        chaos_manager.set_latency(config)
        return {"status": "applied", "fault": "latency", "config": chaos_manager.latency}

    @router.post("/debug/fault/memory-leak", tags=["Chaos Engineering"])
    def inject_memory_leak_fault(config: MemoryLeakFaultConfig):
        chaos_manager.set_memory_leak(config)
        return {"status": "applied", "fault": "memory_leak", "config": chaos_manager.memory_leak}

    @router.post("/debug/fault/cpu-burn", tags=["Chaos Engineering"])
    def inject_cpu_burn_fault(config: CpuBurnFaultConfig):
        chaos_manager.set_cpu_burn(config)
        return {"status": "applied", "fault": "cpu_burn", "config": chaos_manager.cpu_burn}

    @router.post("/debug/fault/error-spike", tags=["Chaos Engineering"])
    def inject_error_spike_fault(config: ErrorSpikeFaultConfig):
        chaos_manager.set_error_spike(config)
        return {"status": "applied", "fault": "error_spike", "config": chaos_manager.error_spike}

    @router.post("/debug/fault/hard-crash", tags=["Chaos Engineering"])
    def inject_hard_crash():
        chaos_manager.hard_crash = True
        logger.critical(f"[CHAOS] Hard crash triggered for {service_name}")
        os._exit(1)

    @router.post("/debug/fault/reset", tags=["Chaos Engineering"])
    def reset_chaos_faults():
        chaos_manager.reset_all()
        return {"status": "reset_complete", "service": service_name}

    @router.get("/debug/fault/status", tags=["Chaos Engineering"])
    def get_chaos_status():
        return chaos_manager.get_status()

    app.include_router(router)
    return chaos_manager
