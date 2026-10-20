#!/usr/bin/env python3
"""
Single-Command Local Cluster Launcher for Autonomous Self-Healing System.
Spawns all 5 microservices as local background processes:
- API Gateway:       http://localhost:8000
- Auth Service:      http://localhost:8001
- Order Service:     http://localhost:8002
- Payment Service:   http://localhost:8003
- Inventory Service: http://localhost:8004

Usage:
  python run_local_cluster.py start      # Starts cluster in background and validates health
  python run_local_cluster.py status     # Checks health status of all 5 microservices
  python run_local_cluster.py stop       # Stops all running microservices
  python run_local_cluster.py run        # Runs in foreground with graceful Ctrl+C shutdown
"""

import json
import os
import signal
import subprocess
import sys
import time
from typing import Dict
import urllib.request
import urllib.error

PID_FILE = ".cluster_pids.json"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SERVICES = [
    {
        "name": "auth-service",
        "port": 8001,
        "path": os.path.join(BASE_DIR, "target-cluster", "services", "auth-service", "app.py"),
        "env": {"PORT": "8001"},
    },
    {
        "name": "inventory-service",
        "port": 8004,
        "path": os.path.join(BASE_DIR, "target-cluster", "services", "inventory-service", "app.py"),
        "env": {"PORT": "8004"},
    },
    {
        "name": "payment-service",
        "port": 8003,
        "path": os.path.join(BASE_DIR, "target-cluster", "services", "payment-service", "app.py"),
        "env": {"PORT": "8003"},
    },
    {
        "name": "order-service",
        "port": 8002,
        "path": os.path.join(BASE_DIR, "target-cluster", "services", "order-service", "app.py"),
        "env": {
            "PORT": "8002",
            "PAYMENT_SERVICE_URL": "http://localhost:8003",
            "INVENTORY_SERVICE_URL": "http://localhost:8004",
        },
    },
    {
        "name": "api-gateway",
        "port": 8000,
        "path": os.path.join(BASE_DIR, "target-cluster", "services", "api-gateway", "app.py"),
        "env": {
            "PORT": "8000",
            "AUTH_SERVICE_URL": "http://localhost:8001",
            "ORDER_SERVICE_URL": "http://localhost:8002",
        },
    },
]


def check_health(port: int, timeout: float = 1.0) -> bool:
    try:
        url = f"http://localhost:{port}/health"
        req = urllib.request.Request(url, headers={"User-Agent": "ClusterRunner"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_service(svc: Dict) -> subprocess.Popen:
    env = os.environ.copy()
    env.update(svc.get("env", {}))
    # Add target-cluster and project root to PYTHONPATH
    pythonpath = env.get("PYTHONPATH", "")
    target_cluster_dir = os.path.join(BASE_DIR, "target-cluster")
    env["PYTHONPATH"] = f"{BASE_DIR}:{target_cluster_dir}:{pythonpath}"

    cmd = [sys.executable, svc["path"]]
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
    )
    return proc


def cmd_start(foreground: bool = False):
    print("=" * 60)
    print("🚀 Starting Self-Healing Microservice Mesh locally...")
    print("=" * 60)

    # Stop any existing processes
    cmd_stop(silent=True)

    processes: Dict[str, subprocess.Popen] = {}
    pids: Dict[str, int] = {}

    for svc in SERVICES:
        print(f"  -> Launching {svc['name']:<18} on port {svc['port']}...")
        proc = start_service(svc)
        processes[svc["name"]] = proc
        pids[svc["name"]] = proc.pid

    # Save PIDs
    with open(PID_FILE, "w") as f:
        json.dump(pids, f)

    # Wait for all services to become healthy
    print("\n⏳ Waiting for health checks to pass...")
    max_wait = 15
    start_time = time.time()
    all_ready = False

    while (time.time() - start_time) < max_wait:
        all_ready = all(check_health(s["port"]) for s in SERVICES)
        if all_ready:
            break
        time.sleep(0.5)

    if all_ready:
        print("\n✅ All 5 microservices are healthy and running!")
        print("-" * 60)
        print("  • API Gateway:       http://localhost:8000/api/v1/checkout")
        print("  • Auth Service:      http://localhost:8001/health")
        print("  • Order Service:     http://localhost:8002/health")
        print("  • Payment Service:   http://localhost:8003/health")
        print("  • Inventory Service: http://localhost:8004/health")
        print("-" * 60)
    else:
        print("\n⚠️ Warning: Some services did not respond in time:")
        for s in SERVICES:
            healthy = check_health(s["port"])
            status = "HEALTHY (200 OK)" if healthy else "FAILED"
            print(f"  • {s['name']:<18} port {s['port']}: {status}")

    if foreground:
        print("\nPress Ctrl+C to terminate all services.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down cluster...")
            cmd_stop()


def cmd_stop(silent: bool = False):
    if not silent:
        print("🛑 Stopping all microservice processes...")

    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                pids = json.load(f)
            for name, pid in pids.items():
                try:
                    if hasattr(os, "killpg"):
                        os.killpg(os.getpgid(pid), signal.SIGTERM)
                    else:
                        os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass
            os.remove(PID_FILE)
        except Exception:
            pass

    # Safety fallback: terminate any processes listening on ports 8000..8003
    for s in SERVICES:
        port = s["port"]
        try:
            out = subprocess.check_output(["lsof", "-t", f"-i:{port}"], text=True).strip()
            for pid_str in out.split():
                if pid_str.isdigit():
                    os.kill(int(pid_str), signal.SIGKILL)
        except Exception:
            pass

    if not silent:
        print("✅ Cluster stopped successfully.")


def cmd_status():
    print("=" * 60)
    print("🔍 Microservices Cluster Health & Status")
    print("=" * 60)
    all_healthy = True
    for s in SERVICES:
        healthy = check_health(s["port"])
        status = "🟢 HEALTHY (HTTP 200)" if healthy else "🔴 DOWN / UNREACHABLE"
        if not healthy:
            all_healthy = False
        print(f"  • {s['name']:<18} (Port {s['port']}): {status}")
    print("=" * 60)
    if all_healthy:
        print("✅ Mesh is fully operational.")
    else:
        print("⚠️ Mesh has degraded or stopped services.")


def main():
    if len(sys.argv) < 2 or sys.argv[1] == "run":
        cmd_start(foreground=True)
    elif sys.argv[1] == "start":
        cmd_start(foreground=False)
    elif sys.argv[1] == "stop":
        cmd_stop()
    elif sys.argv[1] == "status":
        cmd_status()
    else:
        print("Usage: python run_local_cluster.py [start|stop|status|run]")
        sys.exit(1)


if __name__ == "__main__":
    main()
