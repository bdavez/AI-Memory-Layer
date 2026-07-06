import time
import uuid
import hashlib
import socket
import requests
import psutil

BACKEND_BASE_URL = "http://192.168.50.202:8000"
API_BASE = f"{BACKEND_BASE_URL}/api"

HEARTBEAT_INTERVAL = 5  # seconds
JOB_POLL_INTERVAL = 3   # seconds


def generate_node_id():
    mac = uuid.getnode()  # integer MAC
    mac_bytes = mac.to_bytes(6, byteorder="big")
    node_hash = hashlib.sha256(mac_bytes).hexdigest()[:8]
    return f"node-{node_hash}"


def get_system_stats():
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "memory_percent": psutil.virtual_memory().percent,
        "hostname": socket.gethostname(),
    }


class WorkerAgent:
    def __init__(self):
        self.node_id = generate_node_id()
        self.session = requests.Session()

    def register(self):
        payload = {
            "node_id": self.node_id,
            "capabilities": {
                "cpu_cores": psutil.cpu_count(),
                "memory_total_mb": int(psutil.virtual_memory().total / (1024 * 1024)),
            },
        }
        try:
            r = self.session.post(f"{API_BASE}/state/register", json=payload, timeout=5)
            r.raise_for_status()
            print(f"[worker] registered as {self.node_id}")
        except Exception as e:
            print(f"[worker] register failed: {e}")

    def send_heartbeat(self):
        stats = get_system_stats()
        payload = {
            "node_id": self.node_id,
            "status": "online",
            "metrics": stats,
        }
        try:
            r = self.session.post(f"{API_BASE}/state/heartbeat", json=payload, timeout=5)
            r.raise_for_status()
        except Exception as e:
            print(f"[worker] heartbeat failed: {e}")

    def fetch_next_job(self):
        try:
            r = self.session.get(
                f"{API_BASE}/jobs/next",
                params={"node_id": self.node_id},
                timeout=5,
            )
            if r.status_code == 204:
                return None
            r.raise_for_status()
            job = r.json()
            return job
        except Exception as e:
            print(f"[worker] job fetch failed: {e}")
            return None

    def report_job_update(self, job_id, status, result=None, error=None):
        payload = {
            "node_id": self.node_id,
            "job_id": job_id,
            "status": status,
            "result": result,
            "error": error,
        }
        try:
            r = self.session.post(f"{API_BASE}/jobs/update", json=payload, timeout=5)
            r.raise_for_status()
        except Exception as e:
            print(f"[worker] job update failed: {e}")

    def run_job(self, job):
        job_id = job.get("id")
        job_type = job.get("type")
        job_payload = job.get("payload", {})

        print(f"[worker] running job {job_id} type={job_type}")

        try:
            # Placeholder: integrate with compiler / memory / drift as you wire it up
            # For now, just echo payload back.
            result = {
                "echo": job_payload,
                "node_id": self.node_id,
            }
            self.report_job_update(job_id, "finished", result=result)
            print(f"[worker] job {job_id} finished")
        except Exception as e:
            self.report_job_update(job_id, "failed", error=str(e))
            print(f"[worker] job {job_id} failed: {e}")

    def loop(self):
        self.register()
        last_heartbeat = 0

        while True:
            now = time.time()

            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                self.send_heartbeat()
                last_heartbeat = now

            job = self.fetch_next_job()
            if job:
                self.run_job(job)
            else:
                time.sleep(JOB_POLL_INTERVAL)


def main():
    agent = WorkerAgent()
    agent.loop()


if __name__ == "__main__":
    main()
