from flask import Blueprint, jsonify
from .state import heartbeat_registry

bp = Blueprint("models_live", __name__, url_prefix="/api/models")

@bp.get("/live")
def api_models_live():
    out = {}
    for name, info in heartbeat_registry.items():
        out[name] = info.get("models", [])
    return jsonify(out), 200
