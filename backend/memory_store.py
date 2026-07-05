# backend/memory_store.py

import json
import os
import time
from threading import Lock

from .memory_settings import load_settings

# ---------------------------------------------------------
# Utility filters (A–F support)
# ---------------------------------------------------------

def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _is_greeting(text: str) -> bool:
    t = _normalize(text)
    greetings = ["hi", "hii", "hiii", "hello", "hey", "yo", "sup"]
    return any(t.startswith(g) for g in greetings)


def _is_low_quality(text: str) -> bool:
    t = _normalize(text)

    # Too short
    if len(t) < 10:
        return True

    # Greetings / filler
    if _is_greeting(t):
        return True

    # Obvious junk
    junk = [
        "i am an ai model",
        "as an ai model",
        "i cannot remember past interactions",
        "i am not able to",
        "i'm sorry but this question",
        "this question doesn't seem",
    ]
    if any(j in t for j in junk):
        return True

    return False


def _is_domain_relevant(text: str, settings) -> bool:
    t = _normalize(text)
    keywords = settings.get("domain_keywords", [])
    if not keywords:
        return True
    return any(k in t for k in keywords)


# ---------------------------------------------------------
# Memory Store
# ---------------------------------------------------------

class MemoryStore:
    """
    Persistent memory store for:
      - raw events
      - distilled facts
      - summarizer metadata
    """

    def __init__(self, path):
        self.path = path
        self._lock = Lock()
        self._loaded = False

        self._events = []          # list of dicts
        self._facts = {}           # { user_id: [ {"fact": "..."} ] }
        self._meta = {}            # { user_id: { ... } }

    # ---------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------

    def _ensure_loaded(self):
        if self._loaded:
            return

        if not os.path.exists(self.path):
            self._events = []
            self._facts = {}
            self._meta = {}
            self._save()
            self._loaded = True
            return

        with open(self.path, "r") as f:
            data = json.load(f)

        self._events = data.get("events", [])
        self._facts = data.get("facts", {})
        self._meta = data.get("meta", {})

        # Migrate legacy formats
        if isinstance(self._facts, list):
            self._facts = {"global": self._facts}

        if not isinstance(self._meta, dict):
            self._meta = {}

        self._loaded = True

    def _save(self):
        with self._lock:
            with open(self.path, "w") as f:
                json.dump(
                    {
                        "events": self._events,
                        "facts": self._facts,
                        "meta": self._meta,
                    },
                    f,
                    indent=2,
                )

    # ---------------------------------------------------------
    # Meta helpers (debounce + batching + debug fields)
    # ---------------------------------------------------------

    def get_meta(self, user_id):
        if user_id not in self._meta:
            self._meta[user_id] = {
                "created": time.time(),
                "updated": time.time(),
                "summary": "",
                "summary_ts": 0,
                "tokens": 0,
            }
            self._save()
        return self._meta[user_id]

    def update_meta(self, user_id, **kwargs):
        self._ensure_loaded()
        meta = self.get_meta(user_id)
        meta.update(kwargs)
        self._save()

    # ---------------------------------------------------------
    # Events (short-lived)
    # ---------------------------------------------------------

    def add_event(self, user_id, session_id, role, content, metadata=None):
        """
        Add a raw event. Summarization is NOT triggered here.
        memory_summarizer.py handles debounce + batching.
        """
        self._ensure_loaded()

        evt = {
            "ts": time.time(),
            "user_id": user_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "metadata": metadata or {},
        }

        self._events.append(evt)

        # Trim global event list
        if len(self._events) > 5000:
            self._events = self._events[-5000:]

        self._save()
        return evt

    def get_recent_events(self, user_id, limit=200):
        self._ensure_loaded()
        events = [e for e in self._events if e["user_id"] == user_id]
        return events[-limit:]

    def get_events_since(self, user_id, index):
        self._ensure_loaded()
        events = [e for e in self._events if e["user_id"] == user_id]
        return events[index:]

    # ---------------------------------------------------------
    # Durable Facts (per-user)
    # ---------------------------------------------------------

    def add_fact(self, user_id, fact_text):
        """
        Store a distilled fact for a specific user.
        Applies:
          - quality filtering
          - domain filtering
          - deduplication
          - max fact limit
        """
        self._ensure_loaded()
        settings = load_settings()

        norm = _normalize(fact_text)

        # Quality filter
        if _is_low_quality(norm):
            return False

        # Domain filter
        if not _is_domain_relevant(norm, settings):
            return False

        # Dedup
        self._facts.setdefault(user_id, [])
        existing_norm = {_normalize(f["fact"]) for f in self._facts[user_id]}
        if norm in existing_norm:
            return False

        # Add fact
        self._facts[user_id].append({"fact": fact_text})

        # Trim
        max_facts = settings.get("max_facts_per_user", 200)
        if len(self._facts[user_id]) > max_facts:
            self._facts[user_id] = self._facts[user_id][-max_facts:]

        self._save()
        return True

    def get_facts(self, user_id):
        self._ensure_loaded()
        return self._facts.get(user_id, [])

    def delete_fact(self, user_id, index):
        self._ensure_loaded()
        if user_id in self._facts and 0 <= index < len(self._facts[user_id]):
            self._facts[user_id].pop(index)
            self._save()

    def list_facts(self):
        self._ensure_loaded()
        return self._facts


# Global instance
memory_store = MemoryStore(
    os.path.join(os.path.dirname(__file__), "..", "data", "memory.json")
)
