#!/usr/bin/env python3
# /opt/canonical/agents/worker/worker_agent.py

import time
import socket
import psutil
import subprocess
import logging
import os
import threading
import requests

from flask import Flask, request, Response, jsonify

# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------
logging.basicConfig(
    filename="/tmp/worker_agent.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("agent")

log.info("=== Worker Agent Starting (Hostname + IP Failover Enabled) ===")

app = Flask(__name__)

# ---------------------------------------------------------
# Config
# ---------------------------------------------------------
OLLAMA_URL = "http://localhost:11434"

CONTROL_PLANE_HOST = "192.168.50.60"
BACKEND_URL = f"http://{CONTROL_PLANE_HOST}:8000"
CONTROL_PLANE_HEARTBEAT_URL = f"{BACKEND_URL}/heartbeat"

AGENT_NAME = socket.gethostname()
AGENT_PORT = 9000

# Multi-role support
AGENT_ROLES = ["worker", "inference", "ml", "gpu"]

# ---------------------------------------------------------
# Job registry
# ---------------------------------------------------------
jobs = {}

# ---------------------------------------------------------
# GPU / NVML
# ---------------------------------------------------------
def try_nvml_init():
    try:
        import pynvml
        pynvml.nvmlInit()
        log.info("[agent] NVML initialized")
        return pynvml
    except Exception as e:
        log.warning(f"[agent] NVML unavailable: {e}")
        return None


pynvml = try_nvml_init()


def get_gpu_metrics():
    if not pynvml:
        return {"gpus": []}

    try:
        gpu_count = pynvml.nvmlDeviceGetCount()
        gpus = []

        for idx in range(gpu_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(idx)

            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000
            name = pynvml.nvmlDeviceGetName(handle)

            gpus.append(
                {
                    "index": idx,
                    "name": name,
                    "util": util.gpu,
                    "mem_total": round(mem.total / (1024**2), 1),
                    "mem_used": round(mem.used / (1024**2), 1),
                    "mem_pct": round((mem.used / mem.total) * 100, 1),
                    "temp": temp,
                    "watts": power,
                }
            )

        return {"gpus": gpus}

    except Exception as e:
        log.error(f"[agent] GPU metrics failed: {e}")
        return {"gpus": []}


# ---------------------------------------------------------
# Network metrics
# ---------------------------------------------------------
_last_rx = None
_last_tx = None


def get_network_metrics():
    global _last_rx, _last_tx

    try:
        counters = psutil.net_io_counters()
        rx = counters.bytes_recv
        tx = counters.bytes_sent

        if _last_rx is None:
            _last_rx, _last_tx = rx, tx
            return {"net_rx_kbps": 0, "net_tx_kbps": 0}

        rx_kbps = (rx - _last_rx) / 1024
        tx_kbps = (tx - _last_tx) / 1024

        _last_rx, _last_tx = rx, tx

        return {
            "net_rx_kbps": round(rx_kbps, 1),
            "net_tx_kbps": round(tx_kbps, 1),
        }

    except Exception as e:
        log.error(f"[agent] Network metrics failed: {e}")
        return {"net_rx_kbps": None, "net_tx_kbps": None}


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def get_all_ips():
    ips = []
    for iface, addrs in psutil.net_if_addrs().items():
        for a in addrs:
            if a.family == socket.AF_INET:
                ips.append(a.address)
    return ips


def get_model_list():
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2).json()
        return [m["name"] for m in resp.get("models", [])]
    except Exception as e:
        log.warning(f"[agent] Failed to get model list: {e}")
        return []


# ---------------------------------------------------------
# Heartbeat loop
# ---------------------------------------------------------
def heartbeat_loop():
    log.info("[agent] Heartbeat loop started")

    while True:
        try:
            gpu = get_gpu_metrics()
            net = get_network_metrics()

            primary_ip = get_local_ip()
            all_ips = get_all_ips()

            payload = {
                "name": AGENT_NAME,
                "hostname": AGENT_NAME,
                "role": AGENT_ROLES,
                "agent_port": AGENT_PORT,
                "ip": primary_ip,
                "primary_ip": primary_ip,
                "ips": all_ips,
                "hardware": {"ip": primary_ip},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "busy": any(j.get("status") == "running" for j in jobs.values()),
                "task": None,
                "cpu": round(psutil.cpu_percent(interval=0.5), 1),
                "ram": round(psutil.virtual_memory().percent, 1),
                "models": get_model_list(),
                "gpus": gpu.get("gpus", []),
                **net,
            }

            log.debug(f"[agent] Heartbeat payload: {payload}")
            resp = requests.post(CONTROL_PLANE_HEARTBEAT_URL, json=payload, timeout=5)
            log.info(f"[agent] Heartbeat sent: {resp.status_code}")

        except Exception as e:
            log.exception(f"[agent] Heartbeat error: {e}")

        time.sleep(5)


# ---------------------------------------------------------
# Job runners
# ---------------------------------------------------------
def run_llm_job(job_id, model, prompt):
    log.info(f"[agent] Running LLM job {job_id} model={model}")
    jobs[job_id]["status"] = "running"
    jobs[job_id]["started_at"] = time.time()

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=600,
        )
        resp.raise_for_status()
        data = resp.json()

        jobs[job_id]["result"] = data
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["finished_at"] = time.time()
        log.info(f"[agent] Completed LLM job {job_id}")

    except Exception as e:
        log.exception(f"[agent] LLM job {job_id} failed: {e}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["finished_at"] = time.time()


def run_memory_summarize_job(job_id, model, job_input):
    """
    Multi-user aware summarization job.
    job_input contains:
      - prompt: summarizer prompt
      - user_id: which user's memory to update
    """
    jobs[job_id]["status"] = "running"
    jobs[job_id]["started_at"] = time.time()

    prompt = job_input.get("prompt", "")
    user_id = job_input.get("user_id", "b")

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=600,
        )
        resp.raise_for_status()
        data = resp.json()

        content = data.get("message", {}).get("content", "")

        ingest = requests.post(
            f"{BACKEND_URL}/api/memory/ingest",
            json={"text": content, "user_id": user_id},
            timeout=10,
        )
        ingest.raise_for_status()

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["finished_at"] = time.time()
        log.info(f"[agent] Completed memory summarize job {job_id} for user {user_id}")

    except Exception as e:
        log.exception(f"[agent] Memory summarize job {job_id} failed: {e}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["finished_at"] = time.time()


def run_compiler_job(job_id, job_input):
    jobs[job_id]["status"] = "running"
    jobs[job_id]["started_at"] = time.time()

    try:
        # Control plane exposes /api/compile/run
        resp = requests.post(
            f"{BACKEND_URL}/api/compile/run",
            json=job_input,
            timeout=600,
        )
        resp.raise_for_status()
        data = resp.json()

        jobs[job_id]["result"] = data
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["finished_at"] = time.time()
        log.info(f"[agent] Completed compiler job {job_id}")

    except Exception as e:
        log.exception(f"[agent] Compiler job {job_id} failed: {e}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["finished_at"] = time.time()


# ---------------------------------------------------------
# Job creation / status / streaming
# ---------------------------------------------------------
@app.route("/agent/jobs", methods=["POST"])
def create_job():
    data = request.get_json(force=True) or {}
    job_id = data.get("id")
    job_type = data.get("type")
    model = data.get("model", "")
    job_input = data.get("input") or {}

    if not job_id or not job_type:
        return jsonify({"error": "id and type required"}), 400

    if job_type not in ("code_assist", "llm_chat", "memory_summarize", "compiler"):
        return jsonify({"error": f"unsupported job type '{job_type}'"}), 400

    # Validate model for LLM jobs
    if job_type in ("code_assist", "llm_chat", "memory_summarize"):
        try:
            log.info(f"[agent] Validating model '{model}' for job {job_id}")
            available = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2).json()
            model_names = [m["name"] for m in available.get("models", [])]
            if model not in model_names:
                return jsonify({"error": f"model '{model}' not available on worker"}), 400
        except Exception as e:
            log.warning(f"[agent] Model validation failed for {job_id}: {e}")

    prompt = job_input.get("prompt", "")

    jobs[job_id] = {
        "status": "queued",
        "type": job_type,
        "model": model,
        "input": job_input,
        "created_at": time.time(),
        "started_at": None,
        "finished_at": None,
        "error": None,
    }

    # Thread dispatch
    if job_type == "memory_summarize":
        t = threading.Thread(
            target=run_memory_summarize_job,
            args=(job_id, model, job_input),
            daemon=True,
        )
    elif job_type in ("code_assist", "llm_chat"):
        t = threading.Thread(
            target=run_llm_job,
            args=(job_id, model, prompt),
            daemon=True,
        )
    elif job_type == "compiler":
        t = threading.Thread(
            target=run_compiler_job,
            args=(job_id, job_input),
            daemon=True,
        )

    log.info(f"[agent] Starting thread for job {job_id}")
    t.start()
    return jsonify({"status": "accepted"}), 202


@app.route("/agent/jobs/<job_id>", methods=["GET"])
def job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404

    return jsonify(
        {
            "id": job_id,
            "status": job["status"],
            "type": job["type"],
            "model": job["model"],
            "created_at": job.get("created_at"),
            "started_at": job.get("started_at"),
            "finished_at": job.get("finished_at"),
            "error": job.get("error"),
        }
    )


@app.route("/agent/jobs/<job_id>/stream", methods=["GET"])
def job_stream(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404

    if job["type"] in ("memory_summarize", "compiler"):
        return jsonify({"error": "streaming not supported"}), 400

    job_input = job.get("input") or {}
    prompt = job_input.get("prompt", "")
    model = job["model"]

    def event_stream():
        try:
            with requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": True,
                },
                stream=True,
            ) as resp:
                for line in resp.iter_lines():
                    if not line:
                        continue
                    try:
                        decoded = line.decode("utf-8")
                    except Exception:
                        continue
                    yield f"event: token\ndata: {decoded}\n\n"

        except Exception as e:
            log.exception(f"[agent] Streaming error for job {job_id}: {e}")
        finally:
            yield "event: done\ndata: {}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


# ---------------------------------------------------------
# Model management
# ---------------------------------------------------------
@app.route("/agent/models/pull", methods=["POST"])
def pull_model():
    data = request.get_json(force=True) or {}
    model = data.get("model")

    if not model:
        return jsonify({"error": "model required"}), 400

    try:
        proc = subprocess.run(
            ["ollama", "pull", model],
            capture_output=True,
            text=True,
            check=True,
        )
        return jsonify({"status": "ok", "output": proc.stdout}), 200

    except subprocess.CalledProcessError as e:
        return jsonify({"error": "pull failed", "details": e.stderr}), 500


@app.route("/agent/models/list", methods=["GET"])
def list_models():
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return jsonify(resp.json()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------
if __name__ == "__main__":
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=AGENT_PORT)