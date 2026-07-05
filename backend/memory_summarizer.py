# backend/memory_summarizer.py

import json
import time
import importlib

from .memory_settings import load_settings


# ---------------------------------------------------------
# Dynamic import to avoid circular dependency with memory_store
# ---------------------------------------------------------
def _get_memory_store():
    """
    Dynamically import and return memory_store to avoid circular imports.
    """
    from . import memory_store as ms
    importlib.reload(ms)
    return ms.memory_store


# ---------------------------------------------------------
# Prompt Builder
# ---------------------------------------------------------
def build_summarizer_prompt(events):
    """
    Build a clean transcript from NEW events only.
    """
    lines = []
    for e in events:
        role = e.get("role")
        content = (e.get("content") or "").strip()
        if content:
            lines.append(f"{role.upper()}: {content}")

    transcript = "\n".join(lines)

    return f"""
You are a memory distillation system.

Your job is to read the following conversation transcript and extract
long-term, stable facts about the user. These should be things that will
still matter in future interactions.

Rules:
- Only output facts about the USER.
- Ignore assistant messages unless they reveal user preferences or stable traits.
- Output facts as a JSON list of strings.
- Do NOT include commentary or explanation.

Transcript:
{transcript}

Output JSON list of facts:
"""


# ---------------------------------------------------------
# Debounce + Batch Logic
# ---------------------------------------------------------
def _should_summarize(user_id, settings, store):
    """
    Decide whether we should auto-summarize for this user right now.
    Respects debounce + min event thresholds + enable_auto_summarize.
    """
    if not settings.get("enable_auto_summarize", True):
        return False

    meta = store.get_meta(user_id)
    now = time.time()

    # Debounce
    debounce = settings.get("debounce_seconds", 60)
    if now - meta.get("last_summary_ts", 0) < debounce:
        return False

    # Batch threshold
    last_idx = meta.get("last_event_index", 0)
    new_events = store.get_events_since(user_id, last_idx)
    min_events = settings.get("min_events_for_summary", 10)

    if len(new_events) < min_events:
        return False

    return True


# ---------------------------------------------------------
# Summarizer Job Dispatcher
# ---------------------------------------------------------
def run_memory_summarizer(user_id, force=False, model=None):
    """
    Main entrypoint for summarization.

    - force=True bypasses debounce + batch checks (manual summarize)
    - user_id is always threaded through to the worker so ingest is per-user
    """
    store = _get_memory_store()
    settings = load_settings()

    # Model selection (settings override)
    if model is None:
        model = settings.get("summarizer_model", "deepseek-coder:33b")

    # Determine which events to summarize
    meta = store.get_meta(user_id)
    last_idx = meta.get("last_event_index", 0)
    new_events = store.get_events_since(user_id, last_idx)

    if not new_events:
        return None

    # Auto mode: check debounce + batch + enable_auto_summarize
    if not force:
        if not _should_summarize(user_id, settings, store):
            return None

    # Build prompt from NEW events only
    prompt = build_summarizer_prompt(new_events)

    # Store last prompt for debug panel
    store.update_meta(user_id, last_prompt=prompt)

    # Import job system
    from . import jobs_core
    import requests

    # Create job object in central registry
    job = jobs_core.create_job(
        job_type="memory_summarize",
        model=model,
        payload={
            "user_id": user_id,
            "prompt": prompt,
        },
    )

    # Select worker
    machine = jobs_core._select_worker_for_job("memory_summarize", model)
    if not machine:
        jobs_core.update_job_status(
            job["id"],
            status="error",
            error="No available worker",
        )
        return job

    machine_ip = machine.get("primary_ip") or machine.get("hardware", {}).get("ip")
    agent_port = machine.get("agent_port", 9000)
    base_url = f"http://{machine_ip}:{agent_port}"

    # Payload expected by worker_agent /agent/jobs
    worker_payload = {
        "id": job["id"],
        "type": "memory_summarize",
        "model": model,
        "input": {
            "user_id": user_id,
            "prompt": prompt,
        },
    }

    # Dispatch job to worker
    try:
        url = f"{base_url}/agent/jobs"
        resp = requests.post(url, json=worker_payload, timeout=5)
        resp.raise_for_status()

        jobs_core.update_job_status(
            job["id"],
            status="queued",
            assigned_machine=machine.get("name"),
            started_at=time.time(),
        )

    except Exception as e:
        jobs_core.update_job_status(
            job["id"],
            status="error",
            error=str(e),
        )

    return jobs_core.get_job(job["id"])


# ---------------------------------------------------------
# Summarizer Output Parser
# ---------------------------------------------------------
def ingest_summarizer_output(raw_text):
    """
    Robust parser for summarizer output.
    Accepts:
      - JSON list of strings
      - JSON object with "facts" key
      - Bullet lists (-, *, •)
      - Numbered lists (1., 2.)
      - Newline-separated facts
      - Plain sentences
      - Mixed formats
    Returns:
      A clean list of fact strings.
    """
    import json
    import re

    if not raw_text or not isinstance(raw_text, str):
        return []

    text = raw_text.strip()

    # 1. Strict JSON
    try:
        data = json.loads(text)

        if isinstance(data, dict) and "facts" in data and isinstance(data["facts"], list):
            return [str(x).strip() for x in data["facts"] if isinstance(x, str)]

        if isinstance(data, list):
            return [str(x).strip() for x in data if isinstance(x, str)]

    except Exception:
        pass

    # 2. Bullet points
    bullet_pattern = r"^[\-\*\•]\s+(.*)$"
    bullets = []
    for line in text.splitlines():
        m = re.match(bullet_pattern, line.strip())
        if m:
            bullets.append(m.group(1).strip())
    if bullets:
        return bullets

    # 3. Numbered lists
    numbered_pattern = r"^\d+[\.\)]\s+(.*)$"
    numbered = []
    for line in text.splitlines():
        m = re.match(numbered_pattern, line.strip())
        if m:
            numbered.append(m.group(1).strip())
    if numbered:
        return numbered

    # 4. Sentence split
    sentences = re.split(r"[\.!?]\s+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 3]
    if sentences:
        return sentences

    # 5. Fallback
    return [text]
