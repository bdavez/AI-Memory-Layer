# backend/jobs_core.py

import time
import uuid
import threading
import requests

# Global in-memory job registry
_jobs = {}
_jobs_lock = threading.Lock()

# Heartbeat providers (server.py registers one)
_heartbeat_providers = []


# ---------------------------------------------------------
# Heartbeat registry plumbing
# ---------------------------------------------------------
def register_heartbeat_provider(func):
    """
    server.py calls this with a lambda that returns heartbeat_registry.
    """
    if callable(func):
        _heartbeat_providers.append(func)
    return func


def get_heartbeat_registry():
    """
    Aggregate heartbeat data from all registered providers.
    api_models.py expects this to exist.
    """
    registry = {}
    for provider in _heartbeat_providers:
        try:
            data = provider()
            if isinstance(data, dict):
                registry.update(data)
        except Exception:
            continue
    return registry


# ---------------------------------------------------------
# Job creation / registry
# ---------------------------------------------------------
def create_job(job_type, model, job_input):
    """
    Create a job entry in the control-plane registry.
    """
    job_id = str(uuid.uuid4())

    job = {
        "id": job_id,
        "type": job_type,
        "model": model,
        "input": job_input or {},
        "status": "created",
        "created_at": time.time(),
        "assigned_machine": None,
        "started_at": None,
        "completed_at": None,
        "error": None,
        "result": None,
        "retry_count": 0,
        "progress": 0,
    }

    with _jobs_lock:
        _jobs[job_id] = job

    return job


def get_job(job_id):
    with _jobs_lock:
        return _jobs.get(job_id)


def list_jobs():
    with _jobs_lock:
        return list(_jobs.values())


def update_job_status(job_id, **kwargs):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        job.update(kwargs)
        return job


def complete_job(job_id, result=None, error=None):
    now = time.time()

    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return None

        if error:
            job["status"] = "error"
            job["error"] = error
        else:
            job["status"] = "completed"
            job["result"] = result

        job["completed_at"] = now
        return job


# ---------------------------------------------------------
# Worker selection
# ---------------------------------------------------------
def _select_worker_for_job(job_type, model):
    """
    Select a worker machine capable of running the job.
    Uses heartbeat registry from server.py via providers.
    """
    registry = get_heartbeat_registry()
    if not registry:
        return None

    candidates = []

    for name, info in registry.items():
        alive = info.get("alive", True)
        busy = info.get("busy", False)

        if not alive or busy:
            continue

        roles = info.get("role") or []
        if isinstance(roles, str):
            roles = [roles]

        # For LLM-style jobs, prefer workers that actually have the model.
        if job_type in ("code_assist", "llm_chat", "memory_summarize"):
            models = info.get("models", [])
            if model and models and model not in models:
                continue

        # You can tighten this further by role if you want (e.g. require "ml").
        candidates.append(info)

    if not candidates:
        return None

    # Simple heuristic: pick least busy by CPU, then RAM
    candidates.sort(
        key=lambda m: (
            m.get("cpu") if m.get("cpu") is not None else 100.0,
            m.get("ram") if m.get("ram") is not None else 100.0,
        )
    )
    return candidates[0]


def _get_worker_url(job):
    """
    Return base URL for the worker assigned to this job.
    api_jobs.py expects this to exist.
    """
    registry = get_heartbeat_registry()
    name = job.get("assigned_machine")
    if not name:
        return None

    info = registry.get(name)
    if not info:
        return None

    ip = info.get("primary_ip") or info.get("hardware", {}).get("ip")
    port = info.get("agent_port", 9000)
    if not ip:
        return None

    return f"http://{ip}:{port}"


# ---------------------------------------------------------
# Grouped job views (for api_jobs.py)
# ---------------------------------------------------------
def list_jobs_grouped():
    """
    Return jobs grouped by status:
    {
        "pending": {id: job},
        "running": {id: job},
        "completed": {id: job},
        "failed": {id: job}
    }
    """
    groups = {
        "pending": {},
        "running": {},
        "completed": {},
        "failed": {},
    }

    with _jobs_lock:
        for job_id, job in _jobs.items():
            status = job.get("status")

            if status in ("created", "queued", "dispatched"):
                groups["pending"][job_id] = job
            elif status == "running":
                groups["running"][job_id] = job
            elif status == "completed":
                groups["completed"][job_id] = job
            elif status in ("error", "failed"):
                groups["failed"][job_id] = job
            else:
                groups["pending"][job_id] = job

    return groups


# ---------------------------------------------------------
# Cancel / retry
# ---------------------------------------------------------
def cancel_job(job_id):
    job = get_job(job_id)
    if not job:
        return None

    if job["status"] in ("completed", "error", "failed"):
        return job

    job["status"] = "error"
    job["error"] = "Cancelled by user"
    job["completed_at"] = time.time()

    return job


def retry_job(job_id):
    job = get_job(job_id)
    if not job:
        return None

    job["retry_count"] = job.get("retry_count", 0) + 1
    job["status"] = "created"
    job["error"] = None
    job["result"] = None
    job["started_at"] = None
    job["completed_at"] = None

    return job


# ---------------------------------------------------------
# Refresh job status (poll worker)
# ---------------------------------------------------------
def refresh_job_status(job_id):
    job = get_job(job_id)
    if not job:
        return None

    base = _get_worker_url(job)
    if not base:
        return job

    try:
        url = f"{base}/agent/jobs/{job_id}"
        resp = requests.get(url, timeout=3)
        resp.raise_for_status()
        data = resp.json()

        # Map worker fields back into our job
        update_job_status(
            job_id,
            status=data.get("status", job.get("status")),
            started_at=data.get("started_at", job.get("started_at")),
            completed_at=data.get("finished_at", job.get("completed_at")),
            error=data.get("error", job.get("error")),
        )
        return get_job(job_id)

    except Exception:
        return job


def refresh_all_jobs():
    for job_id in list(_jobs.keys()):
        refresh_job_status(job_id)
