# workerV2.py — safe heartbeat demo (no real GPU, no real backend)

import time
import socket
import requests

BACKEND_BASE_URL = "http://127.0.0.1:8000"  # safe local placeholder
HEARTBEAT_INTERVAL = 5  # seconds
PUBLIC_RELEASE = True


def get_gpu_stats():
    # Safe mock GPU stats
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


def get_system_stats():
    return {
        "hostname": socket.gethostname(),
        "cpu": 0.0,
        "ram": 0.0,
        "gpus": get_gpu_stats(),
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
            "busy": False,
            "task": None,
        }

        if PUBLIC_RELEASE:
            # In public mode, just print instead of sending
            print(f"[heartbeat mock] {payload}")
            return

        try:
            r = self.session.post(f"{BACKEND_BASE_URL}/heartbeat", json=payload, timeout=5)
            r.raise_for_status()
            print(f"[heartbeat] sent for {self.hostname}")
        except Exception as e:
            print(f"[heartbeat] failed: {e}")

    def loop(self):
        print(f"[workerV2] starting heartbeat loop as {self.hostname} (public_release={PUBLIC_RELEASE})")

        while True:
            self.send_heartbeat()
            time.sleep(HEARTBEAT_INTERVAL)


def main():
    agent = WorkerAgent()
    agent.loop()


if __name__ == "__main__":
    main()
