import yaml
import json
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
INV_DIR = BASE / "docs" / "inventory"
OUT_DIR = BASE / "compiler" / "output"

def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def main():
    spec = load_yaml(BASE / "compiler" / "spec.yaml")
    machines = load_yaml(INV_DIR / "machines.yaml")
    storage = load_yaml(INV_DIR / "storage.yaml")
    network = load_yaml(INV_DIR / "network.yaml")
    services = load_yaml(INV_DIR / "services.yaml")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Simple machine->role mapping (first pass, canonical for now)
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

    # 1) Ansible inventory
    ansible_lines = []
    ansible_lines.append("[all]")
    for m_key, hw in machines.items():
        hostname = spec["hostnames"].get(m_key, m_key)
        ip = spec["ips"].get(m_key, "")
        role = machine_roles.get(m_key, "unknown")
        gpus = hw.get("gpus", 0)
        ansible_lines.append(
            f"{hostname} ansible_host={ip} role={role} gpus={gpus}"
        )

    ansible_lines.append("")
    for role in sorted(set(machine_roles.values())):
        ansible_lines.append(f"[{role}]")
        for m_key, r in machine_roles.items():
            if r == role:
                hostname = spec["hostnames"].get(m_key, m_key)
                ansible_lines.append(hostname)
        ansible_lines.append("")

    (OUT_DIR / "ansible_inventory.ini").write_text("\n".join(ansible_lines))

    # 2) Terraform-style vars
    tf_vars = {
        "machines": {},
        "network": network,
        "storage": storage,
        "services": services,
    }
    for m_key, hw in machines.items():
        tf_vars["machines"][m_key] = {
            "hostname": spec["hostnames"].get(m_key, m_key),
            "ip": spec["ips"].get(m_key, ""),
            "role": machine_roles.get(m_key, "unknown"),
            "cpu_cores": hw.get("cpu_cores", 0),
            "ram_gb": hw.get("ram_gb", 0),
            "gpus": hw.get("gpus", 0),
            "nvme_count": hw.get("nvme_count", 0),
            "arm": hw.get("arm", False),
            "has_ext_sr": hw.get("has_ext_sr", False),
        }

    (OUT_DIR / "terraform_vars.json").write_text(
        json.dumps(tf_vars, indent=2, sort_keys=True)
    )

    # 3) VM placement rules (from vm_rules in spec)
    vm_rules = spec.get("vm_rules", {})
    vm_placement = {}
    for m_key, rules in vm_rules.items():
        vm_placement[m_key] = {
            "hostname": spec["hostnames"].get(m_key, m_key),
            "required_vms": rules.get("required", []),
        }

    (OUT_DIR / "vm_placement.json").write_text(
        json.dumps(vm_placement, indent=2, sort_keys=True)
    )

    # 4) Hardware summary (Markdown)
    lines = []
    lines.append("# Hardware Summary")
    lines.append("")
    for m_key, hw in machines.items():
        hostname = spec["hostnames"].get(m_key, m_key)
        ip = spec["ips"].get(m_key, "")
        role = machine_roles.get(m_key, "unknown")
        lines.append(f"## {hostname} ({m_key})")
        lines.append(f"- IP: {ip}")
        lines.append(f"- Role: {role}")
        lines.append(f"- CPU cores: {hw.get('cpu_cores', 0)}")
        lines.append(f"- RAM: {hw.get('ram_gb', 0)} GB")
        lines.append(f"- GPUs: {hw.get('gpus', 0)}")
        if "gpu_models" in hw:
            for model, vram in zip(hw.get("gpu_models", []), hw.get("gpu_vram_gb", [])):
                lines.append(f"  - {model} ({vram} GB)")
        lines.append(f"- NVMe count: {hw.get('nvme_count', 0)}")
        lines.append(f"- EXT SR: {hw.get('has_ext_sr', False)}")
        lines.append(f"- ARM: {hw.get('arm', False)}")
        lines.append("")

    (OUT_DIR / "hardware_summary.md").write_text("\n".join(lines))

    print("Compiler outputs written to compiler/output/")
    # Also render static dashboard
    try:
        from . import dashboard_static  # type: ignore
    except ImportError:
        import importlib
        dashboard_static = importlib.import_module("compiler.dashboard_static")
    dashboard_static.main()


if __name__ == "__main__":
    main()
