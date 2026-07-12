# backend/server.py

import os
import time
import socket
import platform
import psutil
import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

CONTROL_PLANE_VERSION = "1.0.4"

# ---------------------------------------------------------
# Create Flask App FIRST
# ---------------------------------------------------------
app = Flask(__name__)
app.config["PROPAGATE_EXCEPTIONS"] = True
app.config["TRAP_HTTP_EXCEPTIONS"] = True

# Allow UI at raynor.local:8000 to call backend at 192.168.50.202:8000
CORS(app, resources={r"/*": {"origins": "*"}})

# ---------------------------------------------------------
# Import Blueprints
# ---------------------------------------------------------
from .api_jobs import bp as jobs_bp
from .api_memory import bp as memory_bp
from .api_models import bp as models_bp
from .api_state import bp as state_api_bp
from .api_assistant import bp as assistant_bp
from .api_models_live import bp as models_live_bp

app.register_blueprint(models_live_bp)
app.register_blueprint(state_api_bp)
app.register_blueprint(jobs_bp)
app.register_blueprint(memory_bp)
app.register_blueprint(models_bp)
app.register_blueprint(assistant_bp)

# ---------------------------------------------------------
# Compiler + Drift Engine Imports
# ---------------------------------------------------------
from .compiler_interface import run_compiler, load_canonical_state, CompilerError
from .canonical_model import load_canonical_state as load_canonical_model

# ---------------------------------------------------------
# Heartbeat Registry
# ---------------------------------------------------------
HEARTBEAT_TIMEOUT_SEC = 30
HEARTBEAT_STALE_SEC = 10

from .state import heartbeat_registry
from .jobs_core import register_heartbeat_provider
register_heartbeat_provider(lambda: heartbeat_registry)

# ---------------------------------------------------------
# ANSI LOG PROXY (🔥 FIXES YOUR UI)
# ---------------------------------------------------------
WORKER_IP = "192.168.50.67"
WORKER_PORT = 9000

@app.get("/ansi-log")
def proxy_ansi_log():
    """Proxy ANSI log from worker agent to avoid CORS issues."""
    try:
        url = f"http://{WORKER_IP}:{WORKER_PORT}/ansi-log"
        r = requests.get(url, timeout=2)
        return jsonify(r.json()), 200
    except Exception as e:
        return jsonify({"error": f"Failed to reach worker: {e}"}), 500

# ---------------------------------------------------------
# Heartbeat Update
# ---------------------------------------------------------
def update_heartbeat(data):
    if not isinstance(data, dict):
        return

    hostname = (
        data.get("hostname")
        or data.get("name")
        or data.get("node")
        or None
    )
    if not hostname:
        return

    ip = data.get("ip")
    ips = data.get("ips") or ([] if ip is None else [ip])
    primary_ip = (
        data.get("primary_ip")
        or (ips[0] if ips else None)
        or ip
    )

    role = data.get("role") or "unknown"
    ts = data.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%S")

    if "gpus" in data and data["gpus"]:
        gpu = data["gpus"][0]
        data.setdefault("gpu_name", gpu.get("name"))
        data.setdefault("gpu_util", gpu.get("util"))
        data.setdefault("gpu_temp", gpu.get("temp"))
        data.setdefault("gpu_mem", gpu.get("mem_pct"))
        data.setdefault("gpu_mem_used", gpu.get("mem_used"))
        data.setdefault("gpu_mem_total", gpu.get("mem_total"))

    heartbeat_registry[hostname] = {
        "name": hostname,
        "hostname": hostname,
        "ips": ips,
        "primary_ip": primary_ip,
        "hardware": {"ip": primary_ip},
        "alive": True,
        "role": role,
        "heartbeat": ts,
        "last_seen": time.time(),
        "latency_ms": data.get("latency_ms"),
        "busy": data.get("busy", False),
        "task": data.get("task"),
        "cpu": data.get("cpu"),
        "ram": data.get("ram"),
        "gpu_util": data.get("gpu_util"),
        "gpu_mem": data.get("gpu_mem"),
        "gpu_mem_used": data.get("gpu_mem_used"),
        "gpu_mem_total": data.get("gpu_mem_total"),
        "gpu_temp": data.get("gpu_temp"),
        "gpu_name": data.get("gpu_name"),
        "gpus": data.get("gpus"),
        "net_rx_kbps": data.get("net_rx_kbps"),
        "net_tx_kbps": data.get("net_tx_kbps"),
        "agent_port": data.get("agent_port", 9000),
        "models": data.get("models", []),
    }

    print(f"[heartbeat] updated: {hostname}")
    print(f"[heartbeat] registry now has: {list(heartbeat_registry.keys())}")

# ---------------------------------------------------------
# Machine Status Helpers
# ---------------------------------------------------------
def classify_machine_status(info):
    now = time.time()
    last_seen = info.get("last_seen")
    busy = info.get("busy", False)
    latency = info.get("latency_ms")

    if last_seen is None:
        return "unknown", "No heartbeat received"

    age = now - last_seen

    if age > HEARTBEAT_TIMEOUT_SEC:
        return "dead", f"No heartbeat for {int(age)}s"

    if busy:
        return "busy", "Machine is running a task"

    if age > HEARTBEAT_STALE_SEC:
        return "warning", f"Stale heartbeat ({int(age)}s old)"

    if latency is not None and latency > 300:
        return "warning", f"High latency ({latency} ms)"

    return "healthy", "Heartbeat OK"

def get_machine_list():
    machines = []
    for name, info in heartbeat_registry.items():
        status, reason = classify_machine_status(info)
        machines.append({
            "name": info["name"],
            "role": info["role"],
            "heartbeat": info["heartbeat"],
            "alive": status in ("healthy", "busy", "warning"),
            "status": status,
            "status_reason": reason,
            "last_seen": info.get("last_seen"),
            "latency_ms": info.get("latency_ms"),
            "busy": info.get("busy"),
            "task": info.get("task"),
            "cpu": info.get("cpu"),
            "ram": info.get("ram"),
            "gpu_util": info.get("gpu_util"),
            "gpu_mem": info.get("gpu_mem"),
            "gpu_temp": info.get("gpu_temp"),
            "gpu_name": info.get("gpu_name"),
            "gpu_mem_total": info.get("gpu_mem_total"),
            "gpu_mem_used": info.get("gpu_mem_used"),
            "gpus": info.get("gpus"),
            "net_rx_kbps": info.get("net_rx_kbps"),
            "net_tx_kbps": info.get("net_tx_kbps"),
            "hardware": info.get("hardware"),
            "models": info.get("models", []),
        })
    return machines

# ---------------------------------------------------------
# Heartbeat Endpoint
# ---------------------------------------------------------
@app.route("/heartbeat", methods=["GET", "POST"])
def heartbeat():
    if request.method == "POST":
        payload = request.get_json(force=True)
        update_heartbeat(payload)
    else:
        update_heartbeat({
            "name": request.args.get("name"),
            "role": request.args.get("role"),
            "timestamp": request.args.get("timestamp"),
            "latency_ms": request.args.get("latency_ms"),
            "busy": False,
            "task": None,
            "cpu": None,
            "ram": None,
        })

    return jsonify({"status": "ok"})

# ---------------------------------------------------------
# Status Endpoint
# ---------------------------------------------------------
@app.route("/api/status", methods=["GET"])
def api_status():
    try:
        machines = []
        for name, info in heartbeat_registry.items():
            machines.append({
                "name": name,
                "alive": info.get("alive", False),
                "role": info.get("role"),
                "primary_ip": info.get("primary_ip"),
                "cpu": info.get("cpu"),
                "ram": info.get("ram"),
                "busy": info.get("busy"),
                "gpu_name": info.get("gpu_name"),
                "gpu_util": info.get("gpu_util"),
                "gpu_mem": info.get("gpu_mem"),
                "gpu_temp": info.get("gpu_temp"),
                "last_seen": info.get("last_seen"),
            })

        return jsonify({
            "status": "ok",
            "machines": machines,
            "count": len(machines),
        }), 200

    except Exception as e:
        print(f"[api_status] ERROR: {e}")
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------
# UI Serving
# ---------------------------------------------------------
@app.route("/", methods=["GET"])
def serve_ui():
    ui_path = os.path.join(os.path.dirname(__file__), "..", "ui")
    return send_from_directory(ui_path, "index.html")

@app.route("/<path:path>", methods=["GET"])
def serve_static(path):
    ui_path = os.path.join(os.path.dirname(__file__), "..", "ui")
    return send_from_directory(ui_path, path)

# ---------------------------------------------------------
# ansi-log reset
# ---------------------------------------------------------
@app.post("/ansi-log/reset")
def reset_ansi_log():
    import requests
    try:
        url = "http://{WORKER_IP}:{WORKER_PORT}/ansi-log/ansi-log/reset"
        r = requests.post(url, timeout=2)
        return jsonify({"status": "reset"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
