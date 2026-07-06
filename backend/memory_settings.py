# backend/memory_settings.py

import json
import os

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "memory_settings.json")

# Default settings for A–F
DEFAULT_SETTINGS = {
    "debounce_seconds": 60,
    "min_events_for_summary": 10,
    "max_events_per_user": 500,
    "max_facts_per_user": 200,
    "enable_auto_summarize": True,
    "enable_manual_summarize": True,
    "domain_keywords": [
        "code",
        "coding",
        "programming",
        "python",
        "javascript",
        "gpu",
        "server",
        "cluster",
        "datacenter",
        "vm",
        "storage",
        "job",
        "compile",
        "deployment",
        "backend",
        "frontend"
    ],
}


def load_settings():
    """
    Load settings from disk, merging with defaults.
    """
    if not os.path.exists(SETTINGS_PATH):
        return DEFAULT_SETTINGS.copy()

    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return DEFAULT_SETTINGS.copy()

    merged = DEFAULT_SETTINGS.copy()
    merged.update(data)
    return merged


def save_settings(settings):
    """
    Save settings to disk.
    """
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)