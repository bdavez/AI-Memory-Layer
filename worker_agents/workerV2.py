import time
import socket
import subprocess
import requests
import psutil

BACKEND_BASE_URL = "http://192.168.50.202:8000"
HEARTBEAT_INTERVAL = 5  # seconds


def get_gpu_stats():
    """
    Returns a list of GPU metric dicts using nvidia-smi.
    Works perfectly with VM passthrough GPUs.
    """
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total",
            "--format=csv,noheader,nounits"
        ]
        output = subprocess.check_output(cmd).decode("utf-8").strip()

        gpus = []
        for line in output.splitlines():
            name, util, temp, mem_used, mem_total = [x.strip() for x in line.split(",")]

            gpus.append({
                "name": name,
                "util": int(util),
                "temp": int(temp),
                "mem_used": int(mem_used),
                "mem_total": int(mem_total),
                "mem_pct": round((int(mem_used) / int(mem_total)) * 100, 2)
            })

        return gpus

    except Exception:
        return []


def get_system_stats():
    return {
        "hostname": socket.gethostname(),
        "cpu": psutil.cpu_percent(interval=0.5),
        "ram": psutil.virtual_memory().percent,
        "gpus": get_gpu_stats()
    }


class WorkerAgent:
    def __init__(self):
        self.session = requests.Session()
        self.hostname = socket.gethostname()

    def send_heartbeat(self):
        stats = get_system_stats()

        payload = {
            "name": stats["hostname"],     # REQUIRED by backend
            "role": "worker",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "cpu": stats["cpu"],
            "ram": stats["ram"],
            "gpus": stats["gpus"],
            "busy": False,
            "task": None,
        }

        try:
            r = self.session.post(f"{BACKEND_BASE_URL}/heartbeat", json=payload, timeout=5)
            r.raise_for_status()
            print(f"[heartbeat] sent for {self.hostname}")
        except Exception as e:
            print(f"[heartbeat] failed: {e}")

    def loop(self):
        print(f"[worker] starting heartbeat loop as {self.hostname}")

        while True:
            self.send_heartbeat()
            time.sleep(HEARTBEAT_INTERVAL)


def main():
    agent = WorkerAgent()
    agent.loop()


if __name__ == "__main__":
    main()
