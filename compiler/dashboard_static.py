import yaml
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
INV_DIR = BASE / "docs" / "inventory"
OUT_DIR = BASE / "compiler" / "output"

def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def load_json(path):
    with open(path, "r") as f:
        return json.load(f)

def main():
    spec = load_yaml(BASE / "compiler" / "spec.yaml")
    machines = load_yaml(INV_DIR / "machines.yaml")
    storage = load_yaml(INV_DIR / "storage.yaml")
    network = load_yaml(INV_DIR / "network.yaml")
    services = load_yaml(INV_DIR / "services.yaml")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Optional compiler outputs
    tf_vars_path = OUT_DIR / "terraform_vars.json"
    vm_place_path = OUT_DIR / "vm_placement.json"
    hw_summary_path = OUT_DIR / "hardware_summary.md"
    drift_path = BASE / "compiler" / "drift_report.txt"

    tf_vars = load_json(tf_vars_path) if tf_vars_path.exists() else {}
    vm_placement = load_json(vm_place_path) if vm_place_path.exists() else {}
    hw_summary = hw_summary_path.read_text() if hw_summary_path.exists() else ""
    drift = drift_path.read_text() if drift_path.exists() else ""

    machine_roles = {
        "machineA": "gpu_training",
        "machineB": "gpu_inference",
        "machineC": "xcp_host",
        "machineD": "cpu_compute",
        "machineE": "control_plane",
        "machineF": "backup",
        "machinePi4": "bridge",
        "machineARM": "arm_workload",
    }

    def status_badge(text, kind="ok"):
        colors = {
            "ok": "#00ffcc",
            "warn": "#ffcc00",
            "err": "#ff3366",
            "info": "#66aaff",
        }
        return f'<span class="badge badge-{kind}" style="border-color:{colors.get(kind)};color:{colors.get(kind)};">{text}</span>'

    drift_status = "No drift detected."
    drift_kind = "ok"
    if drift.strip():
        drift_status = "Drift detected — see details below."
        drift_kind = "err"

    html = []
    html.append("<!DOCTYPE html>")
    html.append("<html lang='en'>")
    html.append("<head>")
    html.append("<meta charset='UTF-8' />")
    html.append("<title>Datacenter Control Plane — Cyberpunk</title>")
    html.append("""
<style>
body {
  background: radial-gradient(circle at top, #1a0026 0, #05010a 40%, #020008 100%);
  color: #e0e0ff;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  margin: 0;
  padding: 0;
}
h1, h2, h3 {
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
a {
  color: #66ccff;
  text-decoration: none;
}
a:hover {
  text-shadow: 0 0 8px #66ccff;
}
.page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 16px 64px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.header-title {
  font-size: 1.4rem;
}
.header-sub {
  font-size: 0.8rem;
  color: #9999ff;
}
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.card {
  background: linear-gradient(135deg, rgba(102,0,204,0.35), rgba(0,255,204,0.08));
  border: 1px solid rgba(0,255,204,0.35);
  border-radius: 10px;
  padding: 14px 16px;
  box-shadow: 0 0 18px rgba(0,0,0,0.7);
  backdrop-filter: blur(6px);
}
.card h2 {
  font-size: 0.9rem;
  margin-top: 0;
  margin-bottom: 8px;
}
.card small {
  color: #aaaaee;
}
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.section {
  margin-top: 32px;
}
.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}
.table th, .table td {
  padding: 6px 8px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.table th {
  text-align: left;
  font-weight: 600;
  color: #bbbbff;
}
.table tr:hover {
  background: rgba(255,255,255,0.03);
}
.tag {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
  margin-right: 4px;
  background: rgba(0,0,0,0.4);
  border: 1px solid rgba(255,255,255,0.15);
}
.footer {
  margin-top: 40px;
  font-size: 0.75rem;
  color: #7777aa;
  text-align: center;
}
pre {
  background: rgba(0,0,0,0.5);
  padding: 8px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 0.75rem;
}
</style>
""")
    html.append("</head>")
    html.append("<body>")
    html.append("<div class='page'>")

    # Header
    html.append("<div class='header'>")
    html.append("<div>")
    html.append("<div class='header-title'>Mini AI Datacenter — Cyberpunk Control Plane</div>")
    html.append("<div class='header-sub'>Canonical baseline · YAML‑driven · Drift‑aware · GPU‑topology‑aware</div>")
    html.append("</div>")
    html.append("<div>")
    html.append(status_badge(drift_status, drift_kind))
    html.append("</div>")
    html.append("</div>")

    # Top cards: counts
    html.append("<div class='card-grid'>")
    # Machines
    html.append("<div class='card'>")
    html.append("<h2>Machines</h2>")
    html.append(f"<div><strong>Total:</strong> {len(machines)}</div>")
    roles = set(machine_roles.values())
    html.append(f"<div><strong>Roles:</strong> {', '.join(sorted(roles))}</div>")
    html.append("</div>")

    # GPUs
    total_gpus = sum(hw.get("gpus", 0) for hw in machines.values())
    html.append("<div class='card'>")
    html.append("<h2>GPU Topology</h2>")
    html.append(f"<div><strong>Total GPUs:</strong> {total_gpus}</div>")
    gpu_nodes = [k for k, hw in machines.items() if hw.get("gpus", 0) > 0]
    html.append(f"<div><strong>GPU Nodes:</strong> {', '.join(gpu_nodes) or 'None'}</div>")
    html.append("</div>")

    # Storage
    html.append("<div class='card'>")
    html.append("<h2>Storage</h2>")
    ext_nodes = [k for k, hw in machines.items() if hw.get("has_ext_sr", False)]
    html.append(f"<div><strong>EXT SR:</strong> {', '.join(ext_nodes) or 'None'}</div>")
    html.append("</div>")

    # Outputs
    html.append("<div class='card'>")
    html.append("<h2>Compiler Outputs</h2>")
    html.append("<small>Generated artifacts</small><br/>")
    html.append("<div><a href='ansible_inventory.ini'>ansible_inventory.ini</a></div>")
    html.append("<div><a href='terraform_vars.json'>terraform_vars.json</a></div>")
    html.append("<div><a href='vm_placement.json'>vm_placement.json</a></div>")
    html.append("<div><a href='hardware_summary.md'>hardware_summary.md</a></div>")
    html.append("</div>")

    html.append("</div>")  # card-grid

    # Machines table
    html.append("<div class='section'>")
    html.append("<h2>Hardware Overview</h2>")
    html.append("<table class='table'>")
    html.append("<tr><th>Machine</th><th>Hostname</th><th>IP</th><th>Role</th><th>CPU</th><th>RAM</th><th>GPUs</th><th>NVMe</th><th>EXT SR</th><th>ARM</th></tr>")
    for m_key, hw in machines.items():
        hostname = spec["hostnames"].get(m_key, m_key)
        ip = spec["ips"].get(m_key, "")
        role = machine_roles.get(m_key, "unknown")
        html.append("<tr>")
        html.append(f"<td>{m_key}</td>")
        html.append(f"<td>{hostname}</td>")
        html.append(f"<td>{ip}</td>")
        html.append(f"<td><span class='tag'>{role}</span></td>")
        html.append(f"<td>{hw.get('cpu_cores', 0)}</td>")
        html.append(f"<td>{hw.get('ram_gb', 0)} GB</td>")
        html.append(f"<td>{hw.get('gpus', 0)}</td>")
        html.append(f"<td>{hw.get('nvme_count', 0)}</td>")
        html.append(f"<td>{'Yes' if hw.get('has_ext_sr', False) else 'No'}</td>")
        html.append(f"<td>{'Yes' if hw.get('arm', False) else 'No'}</td>")
        html.append("</tr>")
    html.append("</table>")
    html.append("</div>")

    # GPU details
    html.append("<div class='section'>")
    html.append("<h2>GPU Details</h2>")
    html.append("<table class='table'>")
    html.append("<tr><th>Machine</th><th>Hostname</th><th>GPU Count</th><th>Models</th></tr>")
    for m_key, hw in machines.items():
        if hw.get("gpus", 0) <= 0:
            continue
        hostname = spec["hostnames"].get(m_key, m_key)
        models = hw.get("gpu_models", [])
        vram = hw.get("gpu_vram_gb", [])
        model_strs = []
        for model, v in zip(models, vram):
            model_strs.append(f"{model} ({v} GB)")
        html.append("<tr>")
        html.append(f"<td>{m_key}</td>")
        html.append(f"<td>{hostname}</td>")
        html.append(f"<td>{hw.get('gpus', 0)}</td>")
        html.append(f"<td>{', '.join(model_strs) if model_strs else 'Unknown'}</td>")
        html.append("</tr>")
    html.append("</table>")
    html.append("</div>")

    # VM placement
    if vm_placement:
        html.append("<div class='section'>")
        html.append("<h2>VM Placement</h2>")
        html.append("<table class='table'>")
        html.append("<tr><th>Machine</th><th>Hostname</th><th>Required VMs</th></tr>")
        for m_key, info in vm_placement.items():
            hostname = info.get("hostname", m_key)
            vms = info.get("required_vms", [])
            html.append("<tr>")
            html.append(f"<td>{m_key}</td>")
            html.append(f"<td>{hostname}</td>")
            html.append(f"<td>{', '.join(vms) if vms else 'None'}</td>")
            html.append("</tr>")
        html.append("</table>")
        html.append("</div>")

    # Drift
    html.append("<div class='section'>")
    html.append("<h2>Drift Status</h2>")
    if drift.strip():
        html.append("<pre>")
        html.append(drift.strip())
        html.append("</pre>")
    else:
        html.append("<div>No drift detected.</div>")
    html.append("</div>")

    # Hardware summary (raw)
    if hw_summary.strip():
        html.append("<div class='section'>")
        html.append("<h2>Hardware Summary (Raw)</h2>")
        html.append("<pre>")
        html.append(hw_summary.strip())
        html.append("</pre>")
        html.append("</div>")

    # Footer
    html.append("<div class='footer'>")
    html.append("Mini AI Datacenter · Canonical Baseline · Cyberpunk Control Plane")
    html.append("</div>")

    html.append("</div>")  # page
    html.append("</body></html>")

    (OUT_DIR / "dashboard.html").write_text("\n".join(html))
    print("Static dashboard written to compiler/output/dashboard.html")

if __name__ == "__main__":
    main()
