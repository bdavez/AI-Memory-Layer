import json
import subprocess
from pathlib import Path
from typing import Any, Dict

from .config import COMPILER_RUN_SCRIPT, CANONICAL_STATE_PATH


class CompilerError(Exception):
    pass


def run_compiler() -> Dict[str, Any]:
    """
    Runs the compiler via run.sh and returns a simple result dict.
    Assumes run.sh prints 'Validator checks passed.' on success.
    """
    if not COMPILER_RUN_SCRIPT.exists():
        raise CompilerError(f"Compiler run script not found at {COMPILER_RUN_SCRIPT}")

    try:
        proc = subprocess.run(
            ["bash", str(COMPILER_RUN_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=COMPILER_RUN_SCRIPT.parent.parent,  # repo root
        )
    except Exception as e:
        raise CompilerError(f"Failed to execute compiler: {e}") from e

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()

    if proc.returncode != 0:
        raise CompilerError(
            f"Compiler exited with code {proc.returncode}. "
            f"stdout: {stdout} stderr: {stderr}"
        )

    return {
        "success": True,
        "stdout": stdout,
        "stderr": stderr,
    }


def load_canonical_state() -> Dict[str, Any]:
    """
    Loads the canonical state JSON written by the compiler.
    """
    if not CANONICAL_STATE_PATH.exists():
        raise CompilerError(f"Canonical state file not found at {CANONICAL_STATE_PATH}")

    try:
        with CANONICAL_STATE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise CompilerError(f"Failed to load canonical state: {e}") from e


# COMPILER_DRIFT_PHASE4
def run_compiler_job():
    """Wrapper to run compiler as a job-friendly call.

    Returns:
        dict with keys:
            - success: bool
            - message: str
            - canonical_version: optional
    """
    result = run_compiler()
    if not isinstance(result, dict):
        result = {"success": bool(result), "message": str(result)}

    try:
        state = load_canonical_state()
        result["canonical_version"] = state.get("canonical_version")
    except Exception:
        pass

    return result

