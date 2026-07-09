# backend/api_memory.py
# Safe Public Release Version — Mock Memory Layer Only

import time
import importlib
from flask import Blueprint, request, jsonify

# ---------------------------------------------------------
# Public Release Mode (no disk writes, no real memory)
# ---------------------------------------------------------
PUBLIC_RELEASE = True

MOCK_MEMORY_DUMP = {
    "events": {},
    "facts": {
        "example-user": [
            {"fact": "Example fact: system running in public release mode."},
            {"fact": "Example fact: no real user data is stored."}
        ]
    },
    "meta": {
        "example-user": {
            "last_prompt": "(none)",
            "last_output": "(none)",
            "last_summary_ts": None
        }
    },
    "settings": {
        "public_release": True,
        "debounce_seconds": 2,
        "min_events_for_summary": 1,
        "max_events_per_user": 50,
        "max_facts_per_user": 50,
        "enable_auto_summarize": False,
        "enable_manual_summarize": False,
        "domain_keywords": [],
        "summarizer_model": "mock"
    }
}

bp = Blueprint("memory", __name__, url_prefix="/api/memory")


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def ensure_user(user_id):
    MOCK_MEMORY_DUMP["facts"].setdefault(user_id, [])
    MOCK_MEMORY_DUMP["events"].setdefault(user_id, [])
    MOCK_MEMORY_DUMP["meta"].setdefault(user_id, {
        "last_prompt": "(none)",
        "last_output": "(none)",
        "last_summary_ts": None
    })


# ---------------------------------------------------------
# Add Event (mock)
# ---------------------------------------------------------
@bp.route("/events", methods=["POST"])
def add_event():
    if not PUBLIC_RELEASE:
        return jsonify({"error": "Public release mode only"}), 400

    data = request.get_json(force=True) or {}

    user_id = data.get("user_id")
    session_id = data.get("session_id")
    role = data.get("role")
    content = data.get("content")

    if not user_id or not session_id or not role or content is None:
        return jsonify({"error": "user_id, session_id, role, content required"}), 400

    ensure_user(user_id)

    evt = {
        "user_id": user_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "ts": time.time()
    }

    MOCK_MEMORY_DUMP["events"][user_id].append(evt)

    return jsonify(evt), 200


# ---------------------------------------------------------
# GET: Raw Events
# ---------------------------------------------------------
@bp.route("/events", methods=["GET"])
def list_events():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    ensure_user(user_id)
    return jsonify({"events": MOCK_MEMORY_DUMP["events"].get(user_id, [])}), 200


# ---------------------------------------------------------
# Facts
# ---------------------------------------------------------
@bp.route("/facts", methods=["GET"])
def list_facts():
    user_id = request.args.get("user_id")

    if user_id:
        ensure_user(user_id)
        return jsonify({"facts": MOCK_MEMORY_DUMP["facts"].get(user_id, [])}), 200

    return jsonify({"facts": MOCK_MEMORY_DUMP["facts"]}), 200


@bp.route("/facts/<user_id>/<int:index>", methods=["DELETE"])
def delete_fact(user_id, index):
    ensure_user(user_id)

    try:
        MOCK_MEMORY_DUMP["facts"][user_id].pop(index)
        return jsonify({"status": "ok"}), 200
    except Exception:
        return jsonify({"error": "index out of range"}), 400


@bp.route("/facts/<user_id>/<int:index>/edit", methods=["POST"])
def edit_fact(user_id, index):
    data = request.get_json(force=True) or {}
    new_text = data.get("fact")

    if not new_text:
        return jsonify({"error": "fact text required"}), 400

    ensure_user(user_id)
    facts = MOCK_MEMORY_DUMP["facts"][user_id]

    if index < 0 or index >= len(facts):
        return jsonify({"error": "index out of range"}), 400

    facts[index]["fact"] = new_text.strip()

    return jsonify({"status": "ok"}), 200


@bp.route("/facts/<user_id>", methods=["GET"])
def get_facts_for_user(user_id):
    ensure_user(user_id)
    return jsonify({"user_id": user_id, "facts": MOCK_MEMORY_DUMP["facts"].get(user_id, [])}), 200


# ---------------------------------------------------------
# Settings (mock)
# ---------------------------------------------------------
@bp.route("/settings", methods=["GET"])
def get_memory_settings():
    return jsonify(MOCK_MEMORY_DUMP["settings"]), 200


@bp.route("/settings", methods=["POST"])
def update_memory_settings():
    data = request.get_json(force=True) or {}

    for key, value in data.items():
        MOCK_MEMORY_DUMP["settings"][key] = value

    return jsonify(MOCK_MEMORY_DUMP["settings"]), 200


# ---------------------------------------------------------
# Summarizer (disabled)
# ---------------------------------------------------------
@bp.route("/summarize", methods=["POST"])
def summarize_memory():
    return jsonify({"error": "Summarizer disabled in public release mode"}), 400


@bp.route("/ingest", methods=["POST"])
def ingest_summary():
    return jsonify({"error": "Summarizer disabled in public release mode"}), 400


# ---------------------------------------------------------
# Debug: Last Summarizer Prompt
# ---------------------------------------------------------
@bp.route("/debug/prompt", methods=["GET"])
def debug_last_prompt():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    ensure_user(user_id)
    return jsonify({"user_id": user_id, "prompt": MOCK_MEMORY_DUMP["meta"][user_id]["last_prompt"]}), 200


# ---------------------------------------------------------
# Debug: Last Summarizer Output
# ---------------------------------------------------------
@bp.route("/debug/last_output", methods=["GET"])
def debug_last_output():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    ensure_user(user_id)
    return jsonify({"user_id": user_id, "output": MOCK_MEMORY_DUMP["meta"][user_id]["last_output"]}), 200


# ---------------------------------------------------------
# Dump full memory.json (mock)
# ---------------------------------------------------------
@bp.route("/dump", methods=["GET"])
def dump_memory():
    return jsonify(MOCK_MEMORY_DUMP), 200


# ---------------------------------------------------------
# Create Memory User
# ---------------------------------------------------------
@bp.route("/user/create", methods=["POST"])
def create_user():
    data = request.get_json(force=True) or {}
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    ensure_user(user_id)

    return jsonify({"status": "ok", "user_id": user_id}), 201
