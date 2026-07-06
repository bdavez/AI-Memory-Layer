# backend/api_state.py
"""
API endpoints for canonical state management, version history,
and triggering compiler/drift/apply jobs.

This is the operator-facing interface for:
- listing state versions
- loading latest or specific versions
- saving new snapshots
- triggering state_compile, drift_check, apply_patch jobs
"""

from flask import Blueprint, request, jsonify
import logging

from .state_loader import (
    list_state_versions,
    load_latest_state,
    get_state_version,
    save_new_state_version,
)

from .jobs_core import create_job

bp = Blueprint("state_api", __name__, url_prefix="/api/state")
logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# GET /api/state/versions
# ------------------------------------------------------------
@bp.get("/versions")
def api_list_versions():
    versions = list_state_versions()
    return jsonify({"versions": versions}), 200


# ------------------------------------------------------------
# GET /api/state/latest
# ------------------------------------------------------------
@bp.get("/latest")
def api_get_latest():
    state = load_latest_state()
    if state is None:
        return jsonify({"error": "no canonical state found"}), 404
    return jsonify({"state": state}), 200


# ------------------------------------------------------------
# GET /api/state/<version>
# ------------------------------------------------------------
@bp.get("/<version>")
def api_get_version(version):
    state = get_state_version(version)
    if state is None:
        return jsonify({"error": f"version '{version}' not found"}), 404
    return jsonify({"state": state}), 200


# ------------------------------------------------------------
# POST /api/state/save
# Body: { "state": {...}, "description": "optional" }
# ------------------------------------------------------------
@bp.post("/save")
def api_save_state():
    payload = request.json or {}
    state = payload.get("state")
    desc = payload.get("description")

    if not isinstance(state, dict):
        return jsonify({"error": "missing or invalid 'state'"}), 400

    filename = save_new_state_version(state, desc)
    return jsonify({"saved_as": filename}), 200


# ------------------------------------------------------------
# POST /api/state/compile
# Body: { "description": "optional" }
# Creates a state_compile job
# ------------------------------------------------------------
@bp.post("/compile")
def api_compile_state():
    payload = request.json or {}
    desc = payload.get("description")

    job = create_job(
        job_type="state_compile",
        model=None,
        job_input={"description": desc},
    )
    return jsonify({"job": job}), 200


# ------------------------------------------------------------
# POST /api/state/drift
# Body: { "description": "optional" }
# Creates a drift_check job
# ------------------------------------------------------------
@bp.post("/drift")
def api_drift_check():
    payload = request.json or {}
    desc = payload.get("description")

    job = create_job(
        job_type="drift_check",
        model=None,
        job_input={"description": desc},
    )
    return jsonify({"job": job}), 200


# ------------------------------------------------------------
# POST /api/state/apply
# Body: { "patch_plan": {...}, "description": "optional" }
# Creates an apply_patch job
# ------------------------------------------------------------
@bp.post("/apply")
def api_apply_patch():
    payload = request.json or {}
    patch_plan = payload.get("patch_plan")
    desc = payload.get("description")

    if not isinstance(patch_plan, dict):
        return jsonify({"error": "missing or invalid 'patch_plan'"}), 400

    job = create_job(
        job_type="apply_patch",
        model=None,
        input_data={"patch_plan": patch_plan, "description": desc},
    )
    return jsonify({"job": job}), 200