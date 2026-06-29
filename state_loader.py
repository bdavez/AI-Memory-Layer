from typing import Any, Dict
import socket
import requests

from .compiler_interface import load_canonical_state, CompilerError
from .config import (
    HEARTBEAT_PORT,
    HEARTBEAT_PATH,
    HEARTBEAT_HTTP_TIMEOUT,
    HEARTBEAT_TCP_TIMEOUT,
    HEARTBEAT_TCP_FALLBACK_PORT,
)


def _check_http_heartbeat(ip: str) -> bool:
    """Primary liveness check: HTTP heartbeat on the configured port/path."""
    url = f"http://{ip}:{HEARTBEAT_PORT}{HEARTBEAT_PATH}"
    try:
        r = requests.get(url, timeout=HEARTBEAT_HTTP_TIMEOUT)
        if r.status_code == 200:
            try:
                data = r.json()
            except Exception:
                return True
            return bool(data.get("alive", True))
    except Exception:
        pass
    return False


def _check_tcp_fallback(ip: str, port: int = HEARTBEAT_TCP_FALLBACK_PORT) -> bool:
    """Fallback liveness check: simple TCP connect (e.g., SSH on port 22)."""
    try:
        with socket.create_connection((ip, port), timeout=HEARTBEAT_TCP_TIMEOUT):
            return True
    except Exception:
        return False


def _evaluate_machine_liveness(machine: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate liveness for a single machine using HTTP heartbeat, then TCP fallback."""
    ip = machine.get("ip") or machine.get("address")
    if not ip:
        return {"alive": False, "method": "none", "reason": "no ip"}

    if _check_http_heartbeat(ip):
        return {"alive": True, "method": "http"}

    if _check_tcp_fallback(ip):
        return {"alive": True, "method": "tcp"}

    return {"alive": False, "method": "failed"}


def get_status() -> Dict[str, Any]:
    """Returns a status object derived from canonical state plus live liveness checks."""
    try:
        state = load_canonical_state()
    except CompilerError as e:
        return {
            "ok": False,
            "drift": None,
            "message": str(e),
            "machines": {},
        }

    machines = state.get("machines", {})
    live_info: Dict[str, Any] = {}

    for name, m in machines.items():
        live_info[name] = _evaluate_machine_liveness(m)

    drift_flag = state.get("drift", False)
    message = state.get("message", "Canonical state loaded.")

    return {
        "ok": not bool(drift_flag),
        "drift": bool(drift_flag),
        "message": message,
        "machines": live_info,
    }