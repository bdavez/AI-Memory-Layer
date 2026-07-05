
# CANONICAL_LOADER_PATCHED
from .compiler_interface import load_canonical_state as _load_canonical_state

class CanonicalError(Exception):
    pass


# CANONICAL_NORMALIZATION_PATCHED
def normalize_canonical(data):
    machines = data.get("machines", [])
    if isinstance(machines, list):
        data["machines_by_name"] = {m["name"]: m for m in machines}
    elif isinstance(machines, dict):
        data["machines_by_name"] = machines
    data['canonical_version'] = data.get('version', 'unknown')
    return data


def load_canonical_state():
    data = _load_canonical_state()
    validate_canonical_state(data)
    data = normalize_canonical(data)
    return data


def validate_canonical_state(data):
    if "version" not in data:
        raise CanonicalError("Canonical state missing 'version'")
    if "machines" not in data:
        raise CanonicalError("Canonical state missing 'machines'")

    if not isinstance(data["machines"], list):
        raise CanonicalError("'machines' must be a list")

    for m in data["machines"]:
        for field in ["name", "role", "ip"]:
            if field not in m:
                raise CanonicalError(f"Machine missing required field: {field}")
