import time
import socket
import subprocess
import requests
import psutil

BACKEND_BASE_URL = "http://192.168.50.202:8000"
HEARTBEAT_INTERVAL = 5


def get_gpu_stats():
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total",
            "--format=csv,noheader,nounits",
        ]
        output = subprocess.check_output(cmd).decode("utf-8").strip()

        gpus = []
        for line in output.splitlines():
            name, util, temp, mem_used, mem_total = [x.strip() for x in line.split(",")]

            mem_used_i = int(mem_used)
            mem_total_i = int(mem_total)
            mem_pct = round((mem_used_i / mem_total_i) * 100, 2) if mem_total_i > 0 else 0.0

            gpus.append({
                "name": name,
                "util": int(util),
                "temp": int(temp),
                "mem_used": mem_used_i,
                "mem_total": mem_total_i,
                "mem_pct": mem_pct,
            })

        return gpus

    except Exception:
        return []


def get_ollama_models():
    try:
        output = subprocess.check_output(["ollama", "list"]).decode("utf-8")
        lines = [l.strip() for l in output.splitlines() if l.strip()]

        models = []
        for line in lines:
            if line.startswith("NAME"):  # skip header
                continue
            models.append(line.split()[0])

        return models

    except Exception:
        return []


def get_system_stats():
    return {
        "hostname": socket.gethostname(),
        "cpu": psutil.cpu_percent(interval=0.5),
        "ram": psutil.virtual_memory().percent,
        "gpus": get_gpu_stats(),
        "models": get_ollama_models(),
    }


class WorkerAgent:
    def __init__(self):
        self.session = requests.Session()
        self.hostname = socket.gethostname()

    def send_heartbeat(self):
        stats = get_system_stats()

        payload = {
            "name": stats["hostname"],
            "role": "worker",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "cpu": stats["cpu"],
            "ram": stats["ram"],
            "gpus": stats["gpus"],
            "models": stats["models"],
            "busy": False,
            "task": None,
        }

        try:
            r = self.session.post(f"{BACKEND_BASE_URL}/heartbeat", json=payload, timeout=5)
            r.raise_for_status()
            print(f"[heartbeat] uno | cpu={stats['cpu']} ram={stats['ram']} gpus={len(stats['gpus'])} models={stats['models']}")
        except Exception as e:
            print(f"[heartbeat] failed: {e}")

    def loop(self):
        print(f"[workerV5] running as {self.hostname}")
        while True:
            self.send_heartbeat()
            time.sleep(HEARTBEAT_INTERVAL)


def main():
    WorkerAgent().loop()


if __name__ == "__main__":
    main()
