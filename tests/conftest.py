"""Pytest configuration and module loader for target-cluster microservices."""

import importlib.util
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET_CLUSTER_DIR = os.path.join(BASE_DIR, "target-cluster")

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if TARGET_CLUSTER_DIR not in sys.path:
    sys.path.insert(0, TARGET_CLUSTER_DIR)


def load_service_app(service_name: str):
    """Dynamically loads the FastAPI app from a service directory with hyphens."""
    app_path = os.path.join(TARGET_CLUSTER_DIR, "services", service_name, "app.py")
    spec = importlib.util.spec_from_file_location(f"{service_name.replace('-', '_')}_app", app_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load spec from {app_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app
