
import os
from pathlib import Path

# Base project directory (assumes backend/ is at repo root)
BASE_DIR = Path(__file__).resolve().parent.parent

# Path to the compiler run script
COMPILER_RUN_SCRIPT = BASE_DIR / "compiler" / "run.sh"

# Where the compiler writes its canonical state (adjust if needed)
CANONICAL_STATE_PATH = BASE_DIR / "compiler" / "output" / "state.json"

# Heartbeat configuration
HEARTBEAT_PORT = int(os.environ.get("HEARTBEAT_PORT", "5050"))
HEARTBEAT_PATH = os.environ.get("HEARTBEAT_PATH", "/heartbeat")
HEARTBEAT_HTTP_TIMEOUT = float(os.environ.get("HEARTBEAT_HTTP_TIMEOUT", "1.0"))
HEARTBEAT_TCP_TIMEOUT = float(os.environ.get("HEARTBEAT_TCP_TIMEOUT", "1.0"))
HEARTBEAT_TCP_FALLBACK_PORT = int(os.environ.get("HEARTBEAT_TCP_FALLBACK_PORT", "22"))

# Optional: environment override for debug
DEBUG = os.environ.get("DASHBOARD_DEBUG", "0") == "1"