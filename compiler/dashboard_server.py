import yaml
import json
from pathlib import Path
from flask import Flask, jsonify, send_from_directory

BASE = Path(__file__).resolve().parent.parent
INV_DIR = BASE / "docs" / "inventory"
OUT_DIR = BASE / "compiler" / "output"

app = Flask(__name__)

def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def load_json(path):
    with open(path, "r") as f:
        return json.load(f)

@app.route("/")
def index():
    # Serve the static dashboard
    return send_from_directory(OUT_DIR, "dashboard.html")

@app.route("/output/<path:filename>")
def output_file(filename):
    return send_from_directory(OUT_DIR, filename)

@app.route("/api/machines")
def api_machines():
    machines = load_yaml(INV_DIR / "machines.yaml")
    spec = load_yaml(BASE / "compiler" / "spec.yaml")
    return jsonify({"machines": machines, "hostnames": spec.get("hostnames", {}), "ips": spec.get("ips", {})})

@app.route("/api/storage")
def api_storage():
    storage = load_yaml(INV_DIR / "storage.yaml")
    return jsonify(storage)

@app.route("/api/network")
def api_network():
    network = load_yaml(INV_DIR / "network.yaml")
    return jsonify(network)

@app.route("/api/services")
def api_services():
    services = load_yaml(INV_DIR / "services.yaml")
    return jsonify(services)

@app.route("/api/vm_placement")
def api_vm_placement():
    path = OUT_DIR / "vm_placement.json"
    if path.exists():
        return jsonify(load_json(path))
    return jsonify({})

@app.route("/api/drift")
def api_drift():
    drift_path = BASE / "compiler" / "drift_report.txt"
    if drift_path.exists():
        return jsonify({"drift": drift_path.read_text().splitlines()})
    return jsonify({"drift": []})

if __name__ == "__main__":
    # Expect dashboard.html to already exist (via compile or dashboard_static)
    app.run(host="0.0.0.0", port=8080, debug=False)
