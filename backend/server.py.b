# backend/server.py

import os
import time
import socket
import platform
import psutil
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# ---------------------------------------------------------
# Create Flask App FIRST
# ---------------------------------------------------------
app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------
# Import Blueprints
# ---------------------------------------------------------
from .api_jobs import bp as jobs_bp
from .api_memory import bp as memory_bp
from .api_models import bp as models_bp

# Register blueprints
app.register_blueprint(jobs_bp)
app.register_blueprint(memory_bp)
app.register_blueprint(models_bp)

# ---------------------------------------------------------
# Compiler + Drift Engine Imports
# ---------------------------------------------------------
from .compiler_interface import run_compiler, load_canonical_state, CompilerError
from .drift_engine import compare_machines
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
    """Normalize and store heartbeat data from worker agents."""
    if not isinstance(data, dict):
        return

    name = (
        data.get("name")
        or data.get("node")
        or data.get("hostname")
        or None
    )
    if not name:
        return

    role = data.get("role") or "unknown"
    ts = data.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%S")

    heartbeat_registry[name] = {
        "name": name,
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

        # CPU metrics
        "cpu_temp": data.get("cpu_temp"),

        # Network metrics
        "net_rx_kbps": data.get("net_rx_kbps"),
        "net_tx_kbps": data.get("net_tx_kbps"),

        # Hardware info
        "hardware": data.get("hardware"),
        "agent_port": data.get("agent_port", 9000),
        "models": data.get("models", []),
    }

    print(f"[heartbeat] updated: {name}")
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

            # Network metrics
            "net_rx_kbps": info.get("net_rx_kbps"),
            "net_tx_kbps": info.get("net_tx_kbps"),

            # Hardware inventory
            "hardware": info.get("hardware"),
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
@app.route("/status", methods=["GET"])
def status_route():
    try:
        cpu = psutil.cpu_count()
        ram_mb = int(psutil.virtual_memory().total / (1024 * 1024))

        disk_info = {}
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disk_info[part.mountpoint] = {
                    "total_gb": round(usage.total / (1024**3), 1),
                    "used_gb": round(usage.used / (1024**3), 1),
                }
            except Exception:
                pass

        system_metrics = {
            "cpu": cpu,
            "ram_mb": ram_mb,
            "disk": disk_info,
            "hostname": socket.gethostname(),
            "os": platform.platform(),
            "load_avg": psutil.getloadavg(),
            "uptime_sec": int(time.time() - psutil.boot_time()),
        }

        machines = get_machine_list()
        overall_status = "OK" if any(m["alive"] for m in machines) else "UNKNOWN"

        return jsonify({
            "overall_status": overall_status,
            "machines": machines,
            "vm_inventory": VM_NODES,
            "system": system_metrics
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
        return jsonify({"success": False, "error": str(e)}), 500


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
@app.route("/drift-diff", methods=["GET"])
def get_drift_diff():
    canonical = load_canonical_model()
    live = get_vm_inventory().get("vms", [])
    diff = compare_machines(canonical["machines"], live)
    return jsonify({
        "timestamp": int(time.time()),
        "drift": diff
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
