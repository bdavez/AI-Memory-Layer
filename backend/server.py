# backend/server.py

import os
import time
import socket
import platform
import psutil
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

CONTROL_PLANE_VERSION = "1.0.4"
# ---------------------------------------------------------
# Create Flask App FIRST
# ---------------------------------------------------------
app = Flask(__name__)
app.config["PROPAGATE_EXCEPTIONS"] = True
app.config["TRAP_HTTP_EXCEPTIONS"] = True
CORS(app)

# ---------------------------------------------------------
# Import Blueprints
# ---------------------------------------------------------
from .api_jobs import bp as jobs_bp
from .api_memory import bp as memory_bp
from .api_models import bp as models_bp
from .api_state import bp as state_api_bp
from .api_assistant import bp as assistant_bp
app.register_blueprint(state_api_bp)
# Register blueprints
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

heartbeat_registry = {}

from .jobs_core import register_heartbeat_provider
register_heartbeat_provider(lambda: heartbeat_registry)


def update_heartbeat(data):
    """Normalize and store heartbeat data from worker agents (hostname + IP failover + multi-NIC)."""
    if not isinstance(data, dict):
        return

    # -------------------------------
    # 1. Determine machine identity
    # -------------------------------
    hostname = (
        data.get("hostname")
        or data.get("name")
        or data.get("node")
        or None
    )
    if not hostname:
        return

    # -------------------------------
    # 2. Normalize IPs (multi-NIC + failover)
    # -------------------------------
    # Worker may send:
    #   ip="x.x.x.x"
    #   primary_ip="x.x.x.x"
    #   ips=["x.x.x.x", "y.y.y.y"]
    ip = data.get("ip")
    ips = data.get("ips") or ([] if ip is None else [ip])

    primary_ip = (
        data.get("primary_ip")
        or (ips[0] if ips else None)
        or ip
    )

    # -------------------------------
    # 3. Normalize role + timestamp
    # -------------------------------
    role = data.get("role") or "unknown"
    ts = data.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%S")

    # -------------------------------
    # 4. GPU schema translation
    # -------------------------------
    if "gpus" in data and data["gpus"]:
        gpu = data["gpus"][0]
        data.setdefault("gpu_name", gpu.get("name"))
        data.setdefault("gpu_util", gpu.get("util"))
        data.setdefault("gpu_temp", gpu.get("temp"))
        data.setdefault("gpu_mem", gpu.get("mem_pct"))
        data.setdefault("gpu_mem_used", gpu.get("mem_used"))
        data.setdefault("gpu_mem_total", gpu.get("mem_total"))

    # -------------------------------
    # 5. Store normalized heartbeat
    # -------------------------------
    heartbeat_registry[hostname] = {
        "name": hostname,
        "hostname": hostname,

        # Multi-NIC support
        "ips": ips,
        "primary_ip": primary_ip,

        # Legacy compatibility
        "hardware": {
            "ip": primary_ip
        },

        # Mark worker as alive (required by jobs_core)
        "alive": True,

        # Core metrics
        "role": role,
        "heartbeat": ts,
        "last_seen": time.time(),
        "latency_ms": data.get("latency_ms"),
        "busy": data.get("busy", False),
        "task": data.get("task"),
        "cpu": data.get("cpu"),
        "ram": data.get("ram"),

        # GPU metrics
        "gpu_util": data.get("gpu_util"),
        "gpu_mem": data.get("gpu_mem"),
        "gpu_mem_used": data.get("gpu_mem_used"),
        "gpu_mem_total": data.get("gpu_mem_total"),
        "gpu_temp": data.get("gpu_temp"),
        "gpu_name": data.get("gpu_name"),
        "gpus": data.get("gpus"),

        # Network metrics
        "net_rx_kbps": data.get("net_rx_kbps"),
        "net_tx_kbps": data.get("net_tx_kbps"),

        # Worker capabilities
        "agent_port": data.get("agent_port", 9000),
        "models": data.get("models", []),
    }

    print(f"[heartbeat] updated: {hostname}")
    print(f"[heartbeat] registry now has: {list(heartbeat_registry.keys())}")

def classify_machine_status(info):
    """Return (status, reason)."""
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
    """Return list of machines that have reported heartbeat."""
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

            # GPU metrics
            "gpu_util": info.get("gpu_util"),
            "gpu_mem": info.get("gpu_mem"),
            "gpu_temp": info.get("gpu_temp"),
            "gpu_name": info.get("gpu_name"),
            "gpu_mem_total": info.get("gpu_mem_total"),
            "gpu_mem_used": info.get("gpu_mem_used"),
            "gpus": info.get("gpus"),
            # Network metrics
            "net_rx_kbps": info.get("net_rx_kbps"),
            "net_tx_kbps": info.get("net_tx_kbps"),

            # Hardware inventory
            "hardware": info.get("hardware"),

            # 🔥 REQUIRED FOR JOB ROUTING
            "models": info.get("models", []),

        })

    return machines


# ---------------------------------------------------------
# Canonical VM Inventory
# ---------------------------------------------------------
VM_NODES = [
    {
        "name": "control-plane",
        "ip": "192.168.50.60",
        "role": "control-plane",
        "cpu": 2,
        "ram_mb": 4096
    },
    {
        "name": "vm-ml-node-01",
        "ip": "192.168.50.201",
        "role": "ml-inference-node",
        "cpu": 2,
        "ram_mb": 4096
    }
]


def get_vm_inventory():
    return {"vms": VM_NODES}


# ---------------------------------------------------------
# Compile History
# ---------------------------------------------------------
COMPILE_HISTORY = []


@app.route("/compile-history", methods=["GET"])
def compile_history_route():
    return jsonify(COMPILE_HISTORY), 200


# ---------------------------------------------------------
# Registry Endpoint
# ---------------------------------------------------------
@app.route("/registry", methods=["GET"])
def registry():
    return jsonify(heartbeat_registry), 200


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
        # Use the global heartbeat_registry directly
        global heartbeat_registry

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

# ------------------------------
# Compiler + Drift Endpoints
# ------------------------------

@app.route("/api/drift", methods=["GET"])
def drift_route():
    """Return canonical vs live drift information."""
    try:
        canonical_state = load_canonical_state()
    except CompilerError as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "type": "compiler_error"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to load canonical state: {e}",
            "type": "internal_error"
        }), 500

    live_machines = get_machine_list()
    from .drift_engine import compare_canonical_vs_live
    drift = compare_canonical_vs_live(canonical_state, live_machines)

    return jsonify({
        "success": True,
        "canonical_version": canonical_state.get("canonical_version"),
        "drift": drift,
    })


@app.route("/api/compile/run", methods=["POST"])
def compile_run_route():
    """Run compiler as a synchronous job-like operation."""
    try:
        result = run_compiler_job()
        return jsonify(result), 200 if result.get("success") else 500
    except CompilerError as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "type": "compiler_error"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Unexpected error: {e}",
            "type": "internal_error"
        }), 500
# ---------------------------------------------------------
# Compile Endpoint
# ---------------------------------------------------------
@app.route("/compile", methods=["POST"])
def compile_route():
    try:
        result = run_compiler()

        from datetime import datetime
        COMPILE_HISTORY.append({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "success": bool(result.get("success", True)),
            "message": result.get("message", "")
        })

        return jsonify(result), 200

    except CompilerError as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "type": "compiler_error"
        }), 500

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "type": "internal_error"
        }), 500

# ---------------------------------------------------------
# Canonical State Endpoint
# ---------------------------------------------------------
@app.route("/canonical", methods=["GET"])
def canonical():
    try:
        state = load_canonical_state()
        return jsonify(state), 200
    except CompilerError as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------
# VM Inventory Endpoint
# ---------------------------------------------------------
@app.route("/vm-inventory", methods=["GET"])
def vm_inventory():
    return jsonify(get_vm_inventory()), 200


# ---------------------------------------------------------
# Storage Map Endpoint
# ---------------------------------------------------------
@app.route("/storage-map", methods=["GET"])
def storage_map():
    data = {
        "machines": {
            "A": {
                "drives": [
                    {"name": "nvme0", "size_tb": 2, "type": "NVMe", "roles": ["OS", "scratch"]},
                    {"name": "nvme1", "size_tb": 2, "type": "NVMe", "roles": ["VM storage"]},
                ]
            },
            "B": {
                "drives": [
                    {"name": "nvme0", "size_tb": 1, "type": "NVMe", "roles": ["OS", "misc"]},
                ]
            },
            "C": {
                "drives": [
                    {"name": "nvme0", "size_tb": 2, "type": "NVMe", "roles": ["OS", "VM host"]},
                ]
            },
            "D": {
                "drives": [
                    {"name": "ssd0", "size_tb": 1, "type": "SATA", "roles": ["ARM link", "logs"]},
                ]
            },
        }
    }
    return jsonify(data), 200


# ---------------------------------------------------------
# Drift Diff Endpoint
# ---------------------------------------------------------
from .drift_engine import compute_drift

@app.route("/drift-diff", methods=["GET"])
def get_drift_diff():
    drift = compute_drift()
    return jsonify({
        "timestamp": int(time.time()),
        "drift": drift
    }), 200

# ---------------------------------------------------------
# Health Check
# ---------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


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
# Entrypoint
# ---------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
