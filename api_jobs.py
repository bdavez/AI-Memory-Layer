# backend/jobs_core.py

import time
import uuid
import logging
from typing import Callable, Dict, Any, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# Heartbeat provider registration
# ---------------------------------------------------------

_heartbeat_provider: Optional[Callable[[], Dict[str, Dict[str, Any]]]] = None


def register_heartbeat_provider(fn: Callable[[], Dict[str, Dict[str, Any]]]):
    """
    Called from server.py to give us access to the live heartbeat_registry.
    """
    global _heartbeat_provider
    _heartbeat_provider = fn
    logger.info("[jobs_core] heartbeat provider registered")


def get_heartbeat_registry() -> Dict[str, Dict[str, Any]]:
    """
    Backwards-compatible accessor used by api_models.py.
    Returns the live heartbeat registry dict (or {} if not set).
    """
    if not _heartbeat_provider:
        return {}
    return _heartbeat_provider() or {}


# ---------------------------------------------------------
# Job registry (control plane view)
# ---------------------------------------------------------

JOBS: Dict[str, Dict[str, Any]] = {}

JOB_TTL_SECONDS = 1800  # 30 minutes


def _new_job_id() -> str:
    return f"job_{uuid.uuid4().hex[:8]}"


def _get_machines() -> Dict[str, Dict[str, Any]]:
    registry = get_heartbeat_registry()
    if isinstance(registry, list):
        return {m["name"]: m for m in registry}
    return registry


def _machine_supports_model(machine: Dict[str, Any], model: str) -> bool:
    models = machine.get("models") or []
    if not model:
        return True
    return model in models


def _machine_has_role(machine: Dict[str, Any], role: str) -> bool:
    r = machine.get("role")
    if isinstance(r, list):
        return role in r
    return r == role


def _select_worker_for_job(job_type: str, model: str) -> Optional[Dict[str, Any]]:
    """
    Routing policy:

    - code_assist / llm_chat / memory_summarize:
        prefer GPU nodes (role includes 'gpu' or 'ml')
    - compiler and other non-LLM jobs:
        prefer CPU-only worker nodes (no 'gpu' role)
    """
    machines = _get_machines()
    if not machines:
        return None

    candidates = []

    for name, info in machines.items():
        if not info.get("alive"):
            continue
        if not _machine_supports_model(info, model):
            # For compiler jobs, model may be empty; skip only if explicitly mismatched
            if job_type not in ("compiler", "drift_check", "state_compile", "vm_inventory", "storage_map"):
                continue

        roles = info.get("role")
        roles = roles if isinstance(roles, list) else [roles] if roles else []

        is_gpu_node = any(r in ("gpu", "ml") for r in roles)
        is_cpu_node = not is_gpu_node

        score = 0
        if job_type in ("code_assist", "llm_chat", "memory_summarize"):
            if is_gpu_node:
                score += 10
        elif job_type in ("compiler", "drift_check", "state_compile", "vm_inventory", "storage_map"):
            if is_cpu_node:
                score += 10

        if not info.get("busy"):
            score += 2

        # mild preference for 192.168.50.201 for compiler-like jobs
        hw_ip = (info.get("hardware") or {}).get("ip")
        if job_type in ("compiler", "drift_check", "state_compile", "vm_inventory", "storage_map"):
            if hw_ip == "192.168.50.201":
                score += 3

        if score > 0:
            candidates.append((score, info))

    if not candidates:
        return None

    # sort by score desc, then by name for deterministic tie-breaking
    candidates.sort(key=lambda x: (x[0], x[1].get("name", "")), reverse=True)
    return candidates[0][1]


def _init_job_dict(
    job_id: str,
    job_type: str,
    model: str,
    job_input: Dict[str, Any],
    machine_name: str,
    created_at: float,
) -> Dict[str, Any]:
    return {
        "id": job_id,
        "type": job_type,
        "model": model,
        "input": job_input,
        "assigned_machine": machine_name,
        "created_at": created_at,
        "started_at": None,
        "finished_at": None,
        "status": "pending",
        "error": None,
        "progress": 0.0,
        "retry_count": 0,
    }


def create_job(job_type: str, model: str, job_input: Dict[str, Any]) -> Dict[str, Any]:
    # ---------------------------------------------------------
    # Local job types that run on the control plane
    # ---------------------------------------------------------
    if job_type == "state_compile":
        from .compiler_engine import compile_state

        result = compile_state(job_input.get("description"))
        job_id = _new_job_id()
        now = time.time()

        job = _init_job_dict(
            job_id,
            job_type,
            model,
            job_input,
            "control-plane",
            now,
        )

        job["status"] = "completed"
        job["finished_at"] = time.time()
        job["result"] = result

        JOBS[job_id] = job
        return job

    if job_type == "drift_check":
        from .drift_engine import run_drift_check

        result = run_drift_check(job_input.get("description"))
        job_id = _new_job_id()
        now = time.time()

        job = _init_job_dict(
            job_id,
            job_type,
            model,
            job_input,
            "control-plane",
            now,
        )

        job["status"] = "completed"
        job["finished_at"] = time.time()
        job["result"] = result

        JOBS[job_id] = job
        return job
    worker = _select_worker_for_job(job_type, model)
    if not worker:
        raise RuntimeError(f"No available worker for job_type='{job_type}' model='{model}'")

    job_id = _new_job_id()
    machine_name = worker["name"]
    agent_port = worker.get("agent_port", 9000)
    ip = worker.get("hardware", {}).get("ip") or machine_name

    payload = {
        "id": job_id,
        "type": job_type,
        "model": model,
        "input": job_input,
    }

    url = f"http://{ip}:{agent_port}/agent/jobs"
    logger.info(f"[jobs_core] creating job {job_id} ({job_type}) on {machine_name} via {url}")

    now = time.time()
    job = _init_job_dict(job_id, job_type, model, job_input, machine_name, now)

    resp = requests.post(url, json=payload, timeout=30)
    if resp.status_code >= 300:
        job["status"] = "failed"
        job["finished_at"] = time.time()
        job["error"] = f"Worker rejected job: {resp.status_code} {resp.text}"
        JOBS[job_id] = job
        raise RuntimeError(job["error"])

    # optimistic: worker accepted the job
    job["status"] = "running"
    job["started_at"] = time.time()
    JOBS[job_id] = job
    return job


def _get_worker_url(job: Dict[str, Any]) -> str:
    machines = _get_machines()
    name = job["assigned_machine"]
    info = machines.get(name) or {}
    ip = info.get("hardware", {}).get("ip") or name
    port = info.get("agent_port", 9000)
    return f"http://{ip}:{port}"


def refresh_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    job = JOBS.get(job_id)
    if not job:
        return None

    try:
        base = _get_worker_url(job)
        resp = requests.get(f"{base}/agent/jobs/{job_id}", timeout=10)
        if resp.status_code == 404:
            job["status"] = "unknown"
            job["error"] = "worker reports job not found"
            if job.get("finished_at") is None:
                job["finished_at"] = time.time()
            return job

        resp.raise_for_status()
        data = resp.json()

        # update lifecycle fields
        job["status"] = data.get("status", job.get("status"))
        job["started_at"] = data.get("started_at", job.get("started_at"))
        job["finished_at"] = data.get("finished_at", job.get("finished_at"))
        job["error"] = data.get("error", job.get("error"))
        if "progress" in data:
            job["progress"] = data.get("progress")

        # if worker reports completed/failed but no finished_at, set it
        if job["status"] in ("completed", "failed", "cancelled", "unknown") and job.get("finished_at") is None:
            job["finished_at"] = time.time()

    except Exception as e:
        logger.exception(f"[jobs_core] failed to refresh job {job_id}: {e}")
        job["error"] = str(e)

    return job


def refresh_all_jobs() -> Dict[str, Dict[str, Any]]:
    """
    Refresh all jobs from workers and perform TTL-based cleanup.
    Returns the updated JOBS dict.
    """
    for jid in list(JOBS.keys()):
        refresh_job_status(jid)
    _cleanup_jobs()
    return JOBS


def _cleanup_jobs():
    """
    Remove completed/failed jobs older than JOB_TTL_SECONDS.
    """
    now = time.time()
    to_delete = []
    for jid, job in JOBS.items():
        st = job.get("status")
        if st not in ("completed", "failed"):
            continue
        finished = job.get("finished_at")
        if not finished:
            continue
        if now - finished > JOB_TTL_SECONDS:
            to_delete.append(jid)

    for jid in to_delete:
        logger.info(f"[jobs_core] cleaning up job {jid} (TTL expired)")
        JOBS.pop(jid, None)


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    job = JOBS.get(job_id)
    if not job:
        return None
    return refresh_job_status(job_id)


def list_jobs_by_status(status: str) -> Dict[str, Dict[str, Any]]:
    out = {}
    for jid, job in JOBS.items():
        refresh_job_status(jid)
        if job.get("status") == status:
            out[jid] = job
    return out


def list_jobs_grouped() -> Dict[str, Dict[str, Dict[str, Any]]]:
    groups = {
        "pending": {},
        "running": {},
        "completed": {},
        "failed": {},
        "unknown": {},
        "cancelled": {},
    }
    for jid in list(JOBS.keys()):
        job = refresh_job_status(jid)
        if not job:
            continue
        st = job.get("status")
        if st in groups:
            groups[st][jid] = job
    _cleanup_jobs()
    return groups


def cancel_job(job_id: str) -> Dict[str, Any]:
    # Placeholder: worker doesn't yet support cancel; just mark locally
    job = JOBS.get(job_id)
    if not job:
        raise RuntimeError("job not found")
    job["status"] = "cancelled"
    job["finished_at"] = time.time()
    return job


def retry_job(job_id: str) -> Dict[str, Any]:
    job = JOBS.get(job_id)
    if not job:
        raise RuntimeError("job not found")

    job["retry_count"] = job.get("retry_count", 0) + 1
    new_job = create_job(job["type"], job["model"], job["input"])
    return new_job