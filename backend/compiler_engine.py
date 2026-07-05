# backend/compiler_engine.py
"""
Compiler engine for canonical state.

Takes the latest canonical state, normalizes it, validates structure,
and writes a new compiled version using state_loader.

This is the foundation for drift detection and patch planning.
"""

import logging
from typing import Dict, Any, Optional

from .state_loader import (
    load_latest_state,
    save_new_state_version,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _normalize_machine(machine: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a single machine entry.
    Ensures consistent keys and default values.
    """
    return {
        "name": machine.get("name"),
        "ip": machine.get("ip"),
        "role": machine.get("role", []),
        "cpu": machine.get("cpu"),
        "ram_mb": machine.get("ram_mb"),
        "gpus": machine.get("gpus", []),
        "storage": machine.get("storage", {}),
        "metadata": machine.get("metadata", {}),
    }


def _normalize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize the entire canonical state.
    """
    machines = state.get("machines", [])
    normalized = {
        "version": state.get("version"),
        "description": state.get("description"),
        "machines": [_normalize_machine(m) for m in machines],
        "network": state.get("network", {}),
        "storage_plan": state.get("storage_plan", {}),
        "vm_inventory": state.get("vm_inventory", []),
        "metadata": state.get("metadata", {}),
    }
    return normalized


def _validate_state(state: Dict[str, Any]) -> Optional[str]:
    """
    Basic validation. Returns None if OK, or an error string.
    """
    if "machines" not in state:
        return "missing 'machines' list"

    for m in state["machines"]:
        if "name" not in m:
            return "machine missing 'name'"
        if "ip" not in m:
            return f"machine '{m.get('name')}' missing 'ip'"

    return None


# ------------------------------------------------------------
# Main compile function
# ------------------------------------------------------------

def compile_state(description: Optional[str] = None) -> Dict[str, Any]:
    """
    Load latest canonical state, normalize it, validate it,
    and save a new compiled version.

    Returns:
        {
            "compiled_version": "<filename>",
            "summary": {...}
        }
    """
    logger.info("[compiler] loading latest canonical state")
    state = load_latest_state()
    if state is None:
        return {"error": "no canonical state found"}

    logger.info("[compiler] normalizing state")
    normalized = _normalize_state(state)

    logger.info("[compiler] validating state")
    err = _validate_state(normalized)
    if err:
        logger.error(f"[compiler] validation failed: {err}")
        return {"error": f"validation failed: {err}"}

    logger.info("[compiler] saving compiled version")
    filename = save_new_state_version(normalized, description)

    summary = {
        "machines": len(normalized.get("machines", [])),
        "vm_inventory": len(normalized.get("vm_inventory", [])),
        "network_keys": list(normalized.get("network", {}).keys()),
    }

    return {
        "compiled_version": filename,
        "summary": summary,
    }
