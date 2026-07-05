# backend/api_assistant.py

from flask import Blueprint, request, jsonify
from .memory_store import memory_store
import requests

bp = Blueprint("assistant", __name__, url_prefix="/api/assistant")

def run_model(model, prompt, mode="standard"):
    """
    Universal Ollama model runner.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }

    # Diff mode support (optional)
    if mode == "diff":
        payload["options"] = {"temperature": 0.0}

    r = requests.post("http://localhost:11434/api/generate", json=payload)
    r.raise_for_status()
    data = r.json()

    return data.get("response", "")

@bp.route("/run", methods=["POST"])
def assistant_run():
    data = request.get_json(force=True)

    user_id = data.get("user_id")
    model = data.get("model")
    mode = data.get("mode", "standard")
    prompt = data.get("prompt")

    if not user_id or not prompt or not model:
        return jsonify({"error": "Missing required fields"}), 400

    # Ensure metadata exists
    memory_store.get_meta(user_id)

    # Log event
    memory_store.add_event(
        user_id=user_id,
        role="user",
        content=prompt,
        session_id="code-assistant"
    )

    # Run model
    result = run_model(model=model, prompt=prompt, mode=mode)

    # Log assistant output
    memory_store.add_event(
        user_id=user_id,
        role="assistant",
        content=result,
        session_id="code-assistant"
    )

    return jsonify({"output": result})
