# backend/drift_engine.py
"""
Drift detection engine.

Compares the latest compiled canonical state with the live heartbeat
registry and produces:

- drift report
- patch plan

Both are saved under ./data/drift_reports/.
"""

import os
import json
import time
import logging
from typing import Dict, Any, List, Optional

from .state_loader import load_latest_state
from .jobs_core import get_heartbeat_registry

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DRIFT_DIR = os.path.join(DATA_DIR, "drift_reports")


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _ensure_dirs():
    os.makedirs(DRIFT_DIR, exist_ok=True)


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H-%M-%S", time.localtime())


def _write_json(path: str, data: Any):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp, path)


# ------------------------------------------------------------
# Drift computation
# ------------------------------------------------------------

def _compare_machine(canonical: Dict[str, Any], live: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare a single machine's canonical vs live heartbeat data.
    Returns a dict describing differences.
    """
    drift = {}

    # Compare IPs (multi-NIC / failover aware)
    c_ips = canonical.get("ips", [])
    l_ips = live.get("ips", [])
    if c_ips != l_ips:
        drift["ips"] = {"canonical": c_ips, "live": l_ips}

    # Compare roles
    c_roles = canonical.get("role", [])
    l_roles = live.get("role", [])
    if c_roles != l_roles:
        drift["role"] = {"canonical": c_roles, "live": l_roles}

    # Compare RAM
    c_ram = canonical.get("ram_mb")
    l_ram = live.get("ram_mb")
    if c_ram != l_ram:
        drift["ram_mb"] = {"canonical": c_ram, "live": l_ram}

    # Compare GPUs
    c_gpus = canonical.get("gpus", [])
    l_gpus = live.get("gpus", [])
    if c_gpus != l_gpus:
        drift["gpus"] = {"canonical": c_gpus, "live": l_gpus}

    # Compare storage
    c_storage = canonical.get("storage", {})
    l_storage = live.get("storage", {})
    if c_storage != l_storage:
        drift["storage"] = {"canonical": c_storage, "live": l_storage}

    # Compare metadata
    c_meta = canonical.get("metadata", {})
    l_meta = live.get("metadata", {})
    if c_meta != l_meta:
        drift["metadata"] = {"canonical": c_meta, "live": l_meta}

    return drift


def compute_drift() -> Dict[str, Any]:
    """
    Compute drift between canonical state and live heartbeat registry.
    Returns:
        {
            "timestamp": "...",
            "missing": [...],
            "extra": [...],
            "machines": {
                "<name>": { ... drift ... }
            }
        }
    """
    logger.info("[drift] loading latest compiled canonical state")
    canonical = load_latest_state()
    if canonical is None:
        return {"error": "no canonical state found"}

    logger.info("[drift] loading heartbeat registry")
    live = get_heartbeat_registry()

    canonical_machines = {m["name"]: m for m in canonical.get("machines", [])}
    live_machines = live or {}

    drift_report = {
        "timestamp": _timestamp(),
        "missing": [],
        "extra": [],
        "machines": {}
    }

    # Machines missing from heartbeat
    for name in canonical_machines:
        if name not in live_machines:
            drift_report["missing"].append(name)

    # Machines in heartbeat but not canonical
    for name in live_machines:
        if name not in canonical_machines:
            drift_report["extra"].append(name)

    # Compare machines that exist in both
    for name in canonical_machines:
        if name in live_machines:
            diff = _compare_machine(canonical_machines[name], live_machines[name])
            if diff:
                drift_report["machines"][name] = diff

    return drift_report


# ------------------------------------------------------------
# Patch plan generation
# ------------------------------------------------------------

def generate_patch_plan(drift: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert drift report into a patch plan.
    This is intentionally simple for now.
    """
    plan = {
        "timestamp": drift.get("timestamp"),
        "actions": []
    }

    # Missing machines
    for name in drift.get("missing", []):
        plan["actions"].append({
            "action": "machine_missing",
            "target": name,
            "details": "Machine not reporting heartbeat"
        })

    # Extra machines
    for name in drift.get("extra", []):
        plan["actions"].append({
            "action": "machine_unknown",
            "target": name,
            "details": "Machine not in canonical state"
        })

    # Field-level drift
    for name, diff in drift.get("machines", {}).items():
        for field, values in diff.items():
            plan["actions"].append({
                "action": "field_mismatch",
                "target": name,
                "field": field,
                "canonical": values["canonical"],
                "live": values["live"]
            })

    return plan


# ------------------------------------------------------------
# Persistence
# ------------------------------------------------------------

def save_drift_report(drift: Dict[str, Any]) -> str:
    _ensure_dirs()
    ts = drift.get("timestamp") or _timestamp()
    filename = f"{ts}_drift.json"
    path = os.path.join(DRIFT_DIR, filename)
    _write_json(path, drift)
    return filename


def save_patch_plan(plan: Dict[str, Any]) -> str:
    _ensure_dirs()
    ts = plan.get("timestamp") or _timestamp()
    filename = f"{ts}_patch_plan.json"
    path = os.path.join(DRIFT_DIR, filename)
    _write_json(path, plan)
    return filename


# ------------------------------------------------------------
# Main entry point for drift_check job
# ------------------------------------------------------------

def run_drift_check(description: Optional[str] = None) -> Dict[str, Any]:
    """
    Compute drift, generate patch plan, save both, return summary.
    """
    logger.info("[drift] computing drift")
    drift = compute_drift()
    if "error" in drift:
        return drift

    logger.info("[drift] generating patch plan")
    plan = generate_patch_plan(drift)

    logger.info("[drift] saving drift report + patch plan")
    drift_file = save_drift_report(drift)
    plan_file = save_patch_plan(plan)

    return {
        "drift_report": drift_file,
        "patch_plan": plan_file,
        "summary": {
            "missing": drift.get("missing", []),
            "extra": drift.get("extra", []),
            "changed": list(drift.get("machines", {}).keys())
        }
    }
