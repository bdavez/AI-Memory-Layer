# workerV5.py — safe mock with IP + agent port

import time
import socket
import requests

BACKEND_BASE_URL = "http://127.0.0.1:8000"
HEARTBEAT_INTERVAL = 5
PUBLIC_RELEASE = True


def get_primary_ip():
    # Safe mock IP for public release
    return "127.0.0.1"


def get_gpu_stats():
    return [
        {
            "name": "mock-gpu-0",
            "util": 0,
            "temp": 30,
            "mem_used": 0,
            "mem_total": 8192,
            "mem_pct": 0.0,
        }
    ]


def get_ollama_models():
    return ["mock-model-1", "mock-model-2"]


def get_system_stats():
    return {
        "hostname": socket.gethostname(),
        "cpu": 0.0,
        "ram": 0.0,
        "gpus": get_gpu_stats(),
        "models": get_ollama_models(),
    }


class WorkerAgent:
    def __init__(self):
        self.session = requests.Session()
        self.hostname = socket.gethostname()
        self.primary_ip = get_primary_ip()

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
            "primary_ip": self.primary_ip,
            "agent_port": 9000,
        }

        if PUBLIC_RELEASE:
            print(f"[heartbeatV5 mock] {self.hostname} | ip={self.primary_ip} cpu={stats['cpu']} ram={stats['ram']} models={stats['models']}")
            return

        try:
            r = self.session.post(f"{BACKEND_BASE_URL}/heartbeat", json=payload, timeout=5)
            r.raise_for_status()
            print(f"[heartbeat] {self.hostname} | ip={self.primary_ip} cpu={stats['cpu']} ram={stats['ram']} models={stats['models']}")
        except Exception as e:
            print(f"[heartbeat] failed: {e}")

    def loop(self):
        print(f"[workerV5] running as {self.hostname} (ip={self.primary_ip}, public_release={PUBLIC_RELEASE})")
        while True:
            self.send_heartbeat()
            time.sleep(HEARTBEAT_INTERVAL)


def main():
    WorkerAgent().loop()


if __name__ == "__main__":
    main()
