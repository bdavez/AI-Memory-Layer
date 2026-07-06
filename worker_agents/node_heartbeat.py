import time
import uuid
import hashlib
import socket
import requests
import psutil

BACKEND_BASE_URL = "http://192.168.50.202:8000"
API_BASE = f"{BACKEND_BASE_URL}/api"
HEARTBEAT_INTERVAL = 5


def generate_node_id():
    mac = uuid.getnode()
    mac_bytes = mac.to_bytes(6, byteorder="big")
    node_hash = hashlib.sha256(mac_bytes).hexdigest()[:8]
    return f"node-{node_hash}"


def get_system_stats():
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "memory_percent": psutil.virtual_memory().percent,
        "hostname": socket.gethostname(),
    }


def main():
    node_id = generate_node_id()
    session = requests.Session()

    print(f"[heartbeat] starting for {node_id}")

    while True:
        payload = {
            "node_id": node_id,
            "status": "online",
            "metrics": get_system_stats(),
        }
        try:
            r = session.post(f"{API_BASE}/state/heartbeat", json=payload, timeout=5)
            r.raise_for_status()
        except Exception as e:
            print(f"[heartbeat] failed: {e}")
        time.sleep(HEARTBEAT_INTERVAL)


if __name__ == "__main__":
    main()
