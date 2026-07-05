import yaml
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
INV_DIR = BASE / "docs" / "inventory"

def load_yaml(path):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def load_roles(path):
    sections = {}
    current = None
    with open(path, 'r') as f:
        for line in f:
            if line.startswith("## "):
                current = line.strip().replace("## ", "")
                sections[current] = []
            elif current:
                sections[current].append(line.rstrip())
    return sections

def normalize(key):
    return (
        key.replace("machine", "machine ")
           .replace("Pi4", "Pi4")
           .replace("ARM", "ARM")
    ).lower()

def main():
    spec = load_yaml(BASE / "compiler" / "spec.yaml")
    roles = load_roles(INV_DIR / "roles.md")
    machines = load_yaml(INV_DIR / "machines.yaml")

    errors = []
    drift = []

    # HOSTNAME + IP VALIDATION (identity vs roles.md)
    for key, hostname in spec.get("hostnames", {}).items():
        norm = normalize(key)
        match = [t for t in roles if norm in t.lower()]
        if not match:
            errors.append(f"Missing roles section for {key}")
            continue
        section = roles[match[0]]
        if not any(f"- Hostname: {hostname}" in line for line in section):
            errors.append(f"Hostname mismatch for {key}")

    for key, ip in spec.get("ips", {}).items():
        norm = normalize(key)
        match = [t for t in roles if norm in t.lower()]
        if not match:
            errors.append(f"Missing roles section for {key}")
            continue
        section = roles[match[0]]
        if not any(f"- IP: {ip}" in line for line in section):
            errors.append(f"IP mismatch for {key}")

    # STRICT MACHINE RULES (spec vs machines.yaml)
    rules = spec.get("machine_rules", {})

    for key, req in rules.items():
        hw = machines.get(key, {})

        # CPU
        if "cpu_cores" in req:
            actual = hw.get("cpu_cores", 0)
            if actual < req["cpu_cores"]:
                msg = f"{key} fails cpu_cores requirement (have {actual}, need {req['cpu_cores']})"
                errors.append(msg)
                drift.append(msg)

        # RAM
        if "ram_gb" in req:
            actual = hw.get("ram_gb", 0)
            if actual < req["ram_gb"]:
                msg = f"{key} fails ram_gb requirement (have {actual}, need {req['ram_gb']})"
                errors.append(msg)
                drift.append(msg)

        # GPU count
        if "gpus" in req:
            actual = hw.get("gpus", 0)
            if actual < req["gpus"]:
                msg = f"{key} fails GPU requirement (have {actual}, need {req['gpus']})"
                errors.append(msg)
                drift.append(msg)

        # NVMe count
        if "nvme_count" in req:
            actual = hw.get("nvme_count", 0)
            if actual < req["nvme_count"]:
                msg = f"{key} fails NVMe requirement (have {actual}, need {req['nvme_count']})"
                errors.append(msg)
                drift.append(msg)

        # EXT SR
        if req.get("ext_sr", False):
            if not hw.get("has_ext_sr", False):
                msg = f"{key} requires EXT SR but none found"
                errors.append(msg)
                drift.append(msg)

        # ARM flag
        if req.get("arm", False):
            if not hw.get("arm", False):
                msg = f"{key} must be ARM architecture"
                errors.append(msg)
                drift.append(msg)

    # DRIFT: missing/extra machines vs spec.machines.required
    required = set(spec.get("machines", {}).get("required", []))
    present = set(
        k.replace("machine", "").replace("Pi4", "Pi4").replace("ARM", "ARM")
        for k in machines.keys()
    )

    # Normalize keys like machineA -> A
    def norm_machine_key(k):
        if k.startswith("machine"):
            return k.replace("machine", "")
        return k

    present_norm = set(norm_machine_key(k) for k in machines.keys())
    missing = required - present_norm
    extra = present_norm - required

    for m in sorted(missing):
        msg = f"Machine {m} is required in spec but missing from machines.yaml"
        errors.append(msg)
        drift.append(msg)

    for m in sorted(extra):
        msg = f"Machine {m} exists in machines.yaml but is not required in spec"
        errors.append(msg)
        drift.append(msg)

    # Write drift report
    drift_path = BASE / "compiler" / "drift_report.txt"
    if drift:
        with open(drift_path, "w") as f:
            f.write("DRIFT DETECTED:\n")
            for d in drift:
                f.write(f"- {d}\n")
    else:
        if drift_path.exists():
            drift_path.unlink()

    if errors:
        print("VALIDATION ERRORS:")
        for e in errors:
            print(" -", e)
        if drift:
            print("\nDrift report written to compiler/drift_report.txt")
        sys.exit(1)

    print("Validator checks passed.")
    if not drift:
        print("No drift detected.")

if __name__ == "__main__":
    main()
