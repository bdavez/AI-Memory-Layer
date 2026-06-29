#!/usr/bin/env python3
# /opt/canonical/agents/worker/worker_agent.py

import time
import socket
import psutil
import subprocess
import glob
import logging
import os
import threading

import requests
from flask import Flask, request, Response, jsonify

# === Logging ===
logging.basicConfig(
    filename="/tmp/worker_agent.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logging.error("WORKER STARTED — top of file executed")
logging.info("=== Worker Agent Starting (Role-Aware + GPU + Network) ===")
logging.info(f"PATH={os.environ.get('PATH')}")
logging.info(f"LD_LIBRARY_PATH={os.environ.get('LD_LIBRARY_PATH')}")

app = Flask(__name__)

jobs = {}  # job_id -> job dict

# ---------------------------------------------------------
# Config
# ---------------------------------------------------------

OLLAMA_URL = "http://localhost:11434"

CONTROL_PLANE_HOST = "192.168.50.60"
BACKEND_URL = f"http://{CONTROL_PLANE_HOST}:8000"
CONTROL_PLANE_HEARTBEAT_URL = f"{BACKEND_URL}/heartbeat"

AGENT_NAME = "192.168.50.10"
AGENT_ROLES = ["worker", "inference", "ml", "gpu"]
AGENT_PORT = 9000

# ---------------------------------------------------------
# GPU / NVML setup
# ---------------------------------------------------------

def try_nvml_init():
    print("TRY_NVML_INIT CALLED")
    try:
        import pynvml
        logging.error("NVML: pynvml imported successfully")
    except Exception as e:
        logging.error(f"NVML: failed to import pynvml: {e}")
        return None

    try:
        pynvml.nvmlInit()
        logging.error("NVML: NVML initialized successfully")
        return pynvml
    except Exception as e:
        logging.error(f"NVML: NVML init failed: {e}")
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

            gpus.append({
                "index": idx,
                "name": name,
                "util": util.gpu,
                "mem_total": round(mem.total / (1024**2), 1),
                "mem_used": round(mem.used / (1024**2), 1),
                "mem_pct": round((mem.used / mem.total) * 100, 1),
                "temp": temp,
                "watts": power,
            })

        return {"gpus": gpus}

    except Exception as e:
        logging.error(f"Multi-GPU metrics failed: {e}")
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
        logging.error(f"Network metrics failed: {e}")
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

def get_model_list():
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2).json()
        return [m["name"] for m in resp.get("models", [])]
    except Exception as e:
        logging.warning(f"Failed to get model list: {e}")
        return []

# ---------------------------------------------------------
# Heartbeat loop
# ---------------------------------------------------------

def heartbeat_loop():
    logging.info("Heartbeat loop starting...")

    while True:
        try:
            gpu = get_gpu_metrics()
            net = get_network_metrics()

            payload = {
                "name": AGENT_NAME,
                "role": AGENT_ROLES if len(AGENT_ROLES) > 1 else AGENT_ROLES[0],
                "agent_port": AGENT_PORT,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "busy": any(j.get("status") == "running" for j in jobs.values()),
                "task": None,
                "cpu": round(psutil.cpu_percent(interval=0.5), 1),
                "ram": round(psutil.virtual_memory().percent, 1),
                "cpu_temp": None,
                "cpu_watts": None,
                "hardware": {"ip": get_local_ip()},
                "models": get_model_list(),
                "gpus": gpu.get("gpus", []),
                **net,
            }

            logging.debug(f"Sending heartbeat: {payload}")
            response = requests.post(
                CONTROL_PLANE_HEARTBEAT_URL, json=payload, timeout=5
            )
            logging.info(f"Heartbeat sent: {response.status_code}")

        except Exception as e:
            logging.exception(f"Unhandled error in heartbeat loop: {e}")

        time.sleep(5)

# ---------------------------------------------------------
# LLM job runners
# ---------------------------------------------------------

def run_llm_job(job_id, model, prompt):
    jobs[job_id]["status"] = "running"
    jobs[job_id]["started_at"] = time.time()

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
            },
            stream=True,
        )

        for _ in resp.iter_lines():
            pass

        jobs[job_id]["status"] = "completed"

    except Exception as e:
        logging.exception(f"LLM job {job_id} failed: {e}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)

def run_memory_summarize_job(job_id, model, prompt):
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

        message = data.get("message", {})
        content = message.get("content", "")

        ingest_resp = requests.post(
            f"{BACKEND_URL}/api/memory/ingest",
            json={"text": content},
            timeout=10,
        )
        ingest_resp.raise_for_status()

        jobs[job_id]["status"] = "completed"

    except Exception as e:
        logging.exception(f"Memory summarize job {job_id} failed: {e}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)

# ---------------------------------------------------------
# Job creation / status / streaming
# ---------------------------------------------------------

@app.route("/agent/jobs", methods=["POST"])
def create_job():
    data = request.get_json(force=True)
    job_id = data["id"]
    job_type = data["type"]
    model = data["model"]
    job_input = data["input"]

    if job_type not in ("code_assist", "llm_chat", "memory_summarize"):
        return jsonify({"error": "unsupported job type"}), 400

    try:
        available = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2).json()
        model_names = [m["name"] for m in available.get("models", [])]
        if model not in model_names:
            return jsonify({"error": f"model '{model}' not available on worker"}), 400
    except Exception as e:
        logging.warning(f"Model validation failed: {e}")

    prompt = job_input.get("prompt")
    if not prompt:
        messages = job_input.get("messages", [])
        if messages and isinstance(messages, list):
            prompt = messages[-1].get("content", "")
        else:
            prompt = ""

    jobs[job_id] = {
        "status": "queued",
        "type": job_type,
        "model": model,
        "input": job_input,
        "created_at": time.time(),
    }

    if job_type == "memory_summarize":
        t = threading.Thread(
            target=run_memory_summarize_job, args=(job_id, model, prompt), daemon=True
        )
    else:
        t = threading.Thread(
            target=run_llm_job, args=(job_id, model, prompt), daemon=True
        )

    t.start()

    return jsonify({"status": "accepted"}), 202

@app.route("/agent/jobs/<job_id>", methods=["GET"])
def job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404

    return jsonify(
        {
            "status": job["status"],
            "type": job["type"],
            "model": job["model"],
            "created_at": job.get("created_at"),
            "started_at": job.get("started_at"),
            "error": job.get("error"),
        }
    )

@app.route("/agent/jobs/<job_id>/stream", methods=["GET"])
def job_stream(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404

    if job["type"] == "memory_summarize":
        return jsonify({"error": "streaming not supported"}), 400

    prompt = job["input"].get("prompt")
    if not prompt:
        messages = job["input"].get("messages", [])
        if messages and isinstance(messages, list):
            prompt = messages[-1].get("content", "")
        else:
            prompt = ""

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

        except GeneratorExit:
            return
        except Exception as e:
            logging.exception(f"Streaming error for job {job_id}: {e}")
            return
        finally:
            try:
                yield "event: done\ndata: {}\n\n"
            except GeneratorExit:
                pass

    return Response(event_stream(), mimetype="text/event-stream")

# ---------------------------------------------------------
# Model management
# ---------------------------------------------------------

@app.route("/agent/models/pull", methods=["POST"])
def pull_model():
    data = request.get_json(force=True)
    model = data.get("model")

    if not model:
        return jsonify({"error": "model is required"}), 400

    try:
        proc = subprocess.run(
            ["ollama", "pull", model],
            capture_output=True,
            text=True,
            check=True,
        )
        logging.info(f"Pulled model {model}: {proc.stdout}")
        return jsonify({"status": "ok", "output": proc.stdout}), 200

    except subprocess.CalledProcessError as e:
        logging.error(f"Pull failed for model {model}: {e.stderr}")
        return jsonify({"error": "pull failed", "details": e.stderr}), 500

@app.route("/agent/models/list", methods=["GET"])
def list_models():
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return jsonify(resp.json()), 200
    except Exception as e:
        logging.error(f"Model list failed: {e}")
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

if __name__ == "__main__":
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=AGENT_PORT)
