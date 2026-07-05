from flask import Blueprint, jsonify
import requests
from .jobs_core import get_heartbeat_registry

bp = Blueprint("models", __name__, url_prefix="/api/models")


def _has_ml_role(info):
    """Return True if worker role includes 'ml'."""
    role = info.get("role")

    if isinstance(role, str):
        return role.lower() == "ml"

    if isinstance(role, list):
        return any(r.lower() == "ml" for r in role)

    return False


@bp.route("", methods=["GET"])
def list_all_models():
    """Return a flattened list of all models from ML-capable workers."""
    registry = get_heartbeat_registry()

    models = set()

    for info in registry.values():
        if not _has_ml_role(info):
            continue

        for m in info.get("models", []):
            models.add(m)

    return jsonify({"models": sorted(models)})


@bp.route("/refresh", methods=["GET"])
def refresh_models():
    """
    Refresh model lists ONLY from workers with ML role.
    Skip workers that do not support model refresh.
    """
    registry = get_heartbeat_registry()
    updated = {}

    for name, info in registry.items():

        # Skip non-ML workers entirely
        if not _has_ml_role(info):
            updated[name] = info.get("models", [])
            continue

        ip = info.get("hardware", {}).get("ip") or info.get("ip") or name
        port = info.get("agent_port", 9000)

        try:
            resp = requests.get(
                f"http://{ip}:{port}/agent/models/list",
                timeout=3
            )
            resp.raise_for_status()

            models = resp.json().get("models", [])
            info["models"] = [m["name"] for m in models]
            updated[name] = info["models"]

        except Exception:
            updated[name] = info.get("models", [])

    return jsonify({"updated": updated})
