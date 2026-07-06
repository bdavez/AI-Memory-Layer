# backend/api_memory.py

import time
import importlib

from flask import Blueprint, request, jsonify

from .memory_store import memory_store
from .memory_settings import load_settings, save_settings
from . import memory_summarizer

bp = Blueprint("memory", __name__, url_prefix="/api/memory")


# ---------------------------------------------------------
# Add Event (auto summarization: debounced + batched)
# ---------------------------------------------------------
@bp.route("/events", methods=["POST"])
def add_event():
    try:
        data = request.get_json(force=True) or {}

        user_id = data.get("user_id")
        session_id = data.get("session_id")
        role = data.get("role")
        content = data.get("content")
        metadata = data.get("metadata") or {}

        if not user_id or not session_id or not role or content is None:
            return jsonify({"error": "user_id, session_id, role, content required"}), 400

        evt = memory_store.add_event(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata,
        )

        # Auto summarization (debounced + batched)
        importlib.reload(memory_summarizer)
        memory_summarizer.run_memory_summarizer(user_id, force=False)

        return jsonify(evt), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------
# GET: Raw Events (multi-user)
# ---------------------------------------------------------
@bp.route("/events", methods=["GET"])
def list_events():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    events = memory_store.get_recent_events(user_id, limit=999999)
    return jsonify({"events": events}), 200


# ---------------------------------------------------------
# Facts
# ---------------------------------------------------------
@bp.route("/facts", methods=["GET"])
def list_facts():
    """
    If user_id is provided, return only that user's facts.
    Otherwise return all facts.
    """
    user_id = request.args.get("user_id")

    if user_id:
        return jsonify({"facts": memory_store.get_facts(user_id)}), 200

    return jsonify({"facts": memory_store.list_facts()}), 200


@bp.route("/facts/<user_id>/<int:index>", methods=["DELETE"])
def delete_fact(user_id, index):
    memory_store.delete_fact(user_id, index)
    return jsonify({"status": "ok"}), 200


@bp.route("/facts/<user_id>/<int:index>/edit", methods=["POST"])
def edit_fact(user_id, index):
    data = request.get_json(force=True) or {}
    new_text = data.get("fact")

    if not new_text:
        return jsonify({"error": "fact text required"}), 400

    facts = memory_store.get_facts(user_id)
    if index < 0 or index >= len(facts):
        return jsonify({"error": "index out of range"}), 400

    facts[index]["fact"] = new_text.strip()
    memory_store._save()

    return jsonify({"status": "ok"}), 200


@bp.route("/facts/<user_id>", methods=["GET"])
def get_facts_for_user(user_id):
    try:
        facts = memory_store.get_facts(user_id)
        return jsonify({"user_id": user_id, "facts": facts}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------
# Settings
# ---------------------------------------------------------
@bp.route("/settings", methods=["GET"])
def get_memory_settings():
    return jsonify(load_settings()), 200


@bp.route("/settings", methods=["POST"])
def update_memory_settings():
    data = request.get_json(force=True) or {}
    settings = load_settings()

    for key in [
        "debounce_seconds",
        "min_events_for_summary",
        "max_events_per_user",
        "max_facts_per_user",
        "enable_auto_summarize",
        "enable_manual_summarize",
        "domain_keywords",
        "summarizer_model",
    ]:
        if key in data:
            settings[key] = data[key]

    save_settings(settings)
    return jsonify(settings), 200


# ---------------------------------------------------------
# Manual Summarizer Trigger
# ---------------------------------------------------------
@bp.route("/summarize", methods=["POST"])
def summarize_memory():
    data = request.get_json(force=True) or {}
    user_id = data.get("user_id")
    force = request.args.get("force", "false").lower() == "true"

    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    importlib.reload(memory_summarizer)

    job = memory_summarizer.run_memory_summarizer(user_id, force=force)

    if job is None:
        return jsonify({"error": "no events to summarize"}), 400

    return jsonify({"job_id": job["id"]}), 202


# ---------------------------------------------------------
# Worker Callback: Ingest Summarizer Output
# ---------------------------------------------------------
@bp.route("/ingest", methods=["POST"])
def ingest_summary():
    data = request.get_json(force=True) or {}
    raw_text = data.get("text")

    if raw_text is None:
        return jsonify({"error": "text required"}), 400

    user_id = data.get("user_id", "b")

    importlib.reload(memory_summarizer)
    facts = memory_summarizer.ingest_summarizer_output(raw_text)

    for f in facts:
        memory_store.add_fact(user_id, f)

    memory_store.update_meta(
        user_id,
        last_summary_ts=time.time(),
        last_event_index=len(memory_store.get_recent_events(user_id, limit=999999)),
        last_output=raw_text,
    )

    return jsonify({"added_facts": facts}), 201


# ---------------------------------------------------------
# Debug: Last Summarizer Prompt
# ---------------------------------------------------------
@bp.route("/debug/prompt", methods=["GET"])
def debug_last_prompt():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    meta = memory_store.get_meta(user_id)
    return jsonify({"user_id": user_id, "prompt": meta.get("last_prompt", "(none)")}), 200


# ---------------------------------------------------------
# Debug: Last Summarizer Output
# ---------------------------------------------------------
@bp.route("/debug/last_output", methods=["GET"])
def debug_last_output():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    meta = memory_store.get_meta(user_id)
    return jsonify({"user_id": user_id, "output": meta.get("last_output", "(none)")}), 200


# ---------------------------------------------------------
# Dump full memory.json
# ---------------------------------------------------------
@bp.route("/dump", methods=["GET"])
def dump_memory():
    try:
        data = {
            "events": memory_store._events,
            "facts": memory_store._facts,
            "meta": memory_store._meta,
        }
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------
# Create Memory User
# ---------------------------------------------------------
@bp.route("/user/create", methods=["POST"])
def create_user():
    data = request.get_json(force=True) or {}
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    # Initialize empty meta + facts
    memory_store.get_meta(user_id)
    memory_store._facts.setdefault(user_id, [])
    memory_store._save()

    return jsonify({"status": "ok", "user_id": user_id}), 201