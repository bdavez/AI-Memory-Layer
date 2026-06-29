# backend/jobs_core.py

import time
import uuid

# In-memory job registry
JOBS = {}  # job_id -> job dict

# This will be set by server.py after heartbeat_registry exists
_get_heartbeat_registry = None


def register_heartbeat_provider(func):
    """
    server.py calls this once to provide access to heartbeat_registry
    without creating a circular import.
    """
    global _get_heartbeat_registry
    _get_heartbeat_registry = func


def create_job(job_type, model, job_input):
    """Create a new job and store it in memory."""
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    now = time.time()
    job = {
        "id": job_id,
        "type": job_type,
        "model": model,
        "input": job_input,
        "status": "queued",
        "assigned_machine": None,
        "created_at": now,
        "updated_at": now,
    }
    JOBS[job_id] = job
    return job


def get_job(job_id):
    return JOBS.get(job_id)


def _get_alive_machines():
    """
    Return list of machines that are alive according to heartbeat.
    Each machine dict matches the structure expected by api_jobs.py:
    - host
    - agent_port
    - id
    - status
    - models (optional)
    """
    if _get_heartbeat_registry is None:
        return []

    registry = _get_heartbeat_registry()
    now = time.time()
    alive = []

    for name, info in registry.items():
        last_seen = info.get("last_seen")
        if not last_seen or (now - last_seen) >= 30:
            continue

        # Extract IP/host
        ip = (
            info.get("hardware", {}).get("ip")
            or info.get("ip")
            or name
        )

        # Extract agent port (default 9000)
        agent_port = info.get("agent_port", 9000)

        alive.append({
            "id": name,
            "host": ip,
            "agent_port": agent_port,
            "role": info.get("role", "unknown"),
            "status": "online",
            "models": info.get("models", []),
            "raw": info,
        })

    return alive


def pick_machine_for_job(job):
    """
    Scheduler:
    - Prefer ML inference nodes for memory_summarize jobs
    - Otherwise pick any alive machine
    """
    alive = _get_alive_machines()

    if not alive:
        raise RuntimeError("No alive machines available for job scheduling")

    # Prefer ML nodes for summarization
    if job["type"] == "memory_summarize":
        ml_nodes = [m for m in alive if "ml" in m.get("role", "").lower()]
        if ml_nodes:
            return ml_nodes[0]

    # Fallback: first alive machine
    return alive[0]


def assign_job(job_id, machine):
    job = JOBS[job_id]
    job["assigned_machine"] = machine["id"]
    job["status"] = "assigned"
    job["updated_at"] = time.time()
    return job


def update_job_status(job_id, status):
    job = JOBS.get(job_id)
    if not job:
        return None
    job["status"] = status
    job["updated_at"] = time.time()
    return job