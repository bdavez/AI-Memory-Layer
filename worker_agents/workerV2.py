import time
import uuid
import hashlib
import socket
import requests
import psutil
import subprocess

BACKEND_BASE_URL = "http://192.168.50.202:8000"
API_BASE = f"{BACKEND_BASE_URL}/api"

HEARTBEAT_INTERVAL = 5  # seconds
JOB_POLL_INTERVAL = 3   # seconds

def get_gpu_stats():
    """
    Returns a list of GPU metric dicts using nvidia-smi.
    Supports VM passthrough GPUs.
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
        "cpu": psutil.cpu_percent(interval=0.5),
        "ram": psutil.virtual_memory().percent,
        "hostname": socket.gethostname(),
        "gpus": get_gpu_stats()
    }


def send_heartbeat(self):
    stats = get_system_stats()

    payload = {
        "name": stats["hostname"],     # IMPORTANT: backend expects "name", not node_id
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
        print(f"[heartbeat] sent for {stats['hostname']}")
    except Exception as e:
        print(f"[heartbeat] failed: {e}")


def generate_node_id():
    mac = uuid.getnode()  # integer MAC
    mac_bytes = mac.to_bytes(6, byteorder="big")
    node_hash = hashlib.sha256(mac_bytes).hexdigest()[:8]
    return f"node-{node_hash}"

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
