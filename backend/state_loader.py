# backend/state_loader.py
"""
Canonical state versioning and loading.

This module manages versioned canonical state files under ./data/state_versions/.

- Each version is stored as a JSON file:
    data/state_versions/2026-01-27T17-05-00_initial-import.json

- A pointer file tracks the latest version:
    data/state_versions/latest.json  -> { "version": "<filename>" }

Roadmap note:
    In a later phase, we can switch filenames to include a hash:
    2026-01-27T17-05-00_4f9c2a.json
"""

import os
import json
import time
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATE_VERSIONS_DIR = os.path.join(DATA_DIR, "state_versions")
LATEST_POINTER_PATH = os.path.join(STATE_VERSIONS_DIR, "latest.json")


def _ensure_dirs():
    os.makedirs(STATE_VERSIONS_DIR, exist_ok=True)


def _timestamp() -> str:
    # ISO-like, but filesystem-friendly
    return time.strftime("%Y-%m-%dT%H-%M-%S", time.localtime())


def _sanitize_description(desc: str) -> str:
    """
    Turn a free-form description into a safe filename fragment.
    """
    desc = desc.strip().lower().replace(" ", "-")
    out = []
    for ch in desc:
        if ch.isalnum() or ch in ("-", "_"):
            out.append(ch)
    return "".join(out) or "state"


def _version_filename(ts: str, description: Optional[str] = None) -> str:
    """
    Build a filename like:
        2026-01-27T17-05-00_initial-import.json
    """
    if description:
        frag = _sanitize_description(description)
        return f"{ts}_{frag}.json"
    return f"{ts}.json"


def _write_json(path: str, data: Any):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp, path)


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_state_versions() -> List[Dict[str, Any]]:
    """
    Return a list of available state versions, newest first.

    Each entry:
        {
            "filename": "2026-01-27T17-05-00_initial-import.json",
            "timestamp": "2026-01-27T17-05-00",
            "description": "initial-import",
            "path": "/full/path/to/file"
        }
    """
    _ensure_dirs()
    versions = []
    for name in os.listdir(STATE_VERSIONS_DIR):
        if not name.endswith(".json"):
            continue
        if name == "latest.json":
            continue
        ts = name
        desc = None
        if "_" in name:
            ts, rest = name.split("_", 1)
            desc = rest.rsplit(".json", 1)[0]
        else:
            ts = name.rsplit(".json", 1)[0]
        versions.append(
            {
                "filename": name,
                "timestamp": ts,
                "description": desc,
                "path": os.path.join(STATE_VERSIONS_DIR, name),
            }
        )

    # newest first by filename (timestamp prefix)
    versions.sort(key=lambda v: v["filename"], reverse=True)
    return versions


def _set_latest_pointer(filename: str):
    _ensure_dirs()
    data = {"version": filename}
    _write_json(LATEST_POINTER_PATH, data)


def _get_latest_pointer() -> Optional[str]:
    if not os.path.exists(LATEST_POINTER_PATH):
        return None
    try:
        data = _read_json(LATEST_POINTER_PATH)
        return data.get("version")
    except Exception as e:
        logger.exception(f"[state_loader] failed to read latest pointer: {e}")
        return None


def get_state_version(filename: str) -> Optional[Dict[str, Any]]:
    """
    Load a specific version by filename.
    """
    _ensure_dirs()
    path = os.path.join(STATE_VERSIONS_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        return _read_json(path)
    except Exception as e:
        logger.exception(f"[state_loader] failed to load state version {filename}: {e}")
        return None


def load_latest_state() -> Optional[Dict[str, Any]]:
    """
    Load the latest canonical state, if any.

    Resolution order:
        1. latest.json pointer
        2. newest file in state_versions dir
    """
    _ensure_dirs()

    # 1) Try pointer
    latest = _get_latest_pointer()
    if latest:
        state = get_state_version(latest)
        if state is not None:
            return state

    # 2) Fallback: newest file
    versions = list_state_versions()
    if not versions:
        return None

    for v in versions:
        state = get_state_version(v["filename"])
        if state is not None:
            # also refresh pointer
            _set_latest_pointer(v["filename"])
            return state

    return None


def save_new_state_version(state: Dict[str, Any], description: Optional[str] = None) -> str:
    """
    Save a new canonical state version and update latest pointer.

    Returns the filename of the new version.
    """
    _ensure_dirs()
    ts = _timestamp()
    filename = _version_filename(ts, description)
    path = os.path.join(STATE_VERSIONS_DIR, filename)

    logger.info(f"[state_loader] saving new state version: {filename}")
    _write_json(path, state)
    _set_latest_pointer(filename)
    return filename
