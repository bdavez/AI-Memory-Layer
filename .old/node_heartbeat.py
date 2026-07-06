#!/usr/bin/env python3
import time
import json
import socket
import psutil
import platform
import subprocess
import requests
from pathlib import Path

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
CONTROL_PLANE_HOST = "192.168.50.60"
CONTROL_PLANE_URL = f"http://{CONTROL_PLANE_HOST}:8000/heartbeat"
ROLE = "worker"
INTERVAL = 5  # seconds

_prev_net = {}

# ---------------------------------------------------------
# Network Interface Detection
# ---------------------------------------------------------
def detect_primary_interface():
    for iface in psutil.net_if_addrs().keys():
        if iface.startswith("lo"):
            continue
        if iface.startswith("cali") or iface.startswith("vxlan"):
            continue
        return iface
    return "eth0"

INTERFACE = detect_primary_interface()

# ---------------------------------------------------------
# Latency Measurement
# ---------------------------------------------------------
def get_latency_ms(host=CONTROL_PLANE_HOST):
    start = time.time()
    try:
        socket.create_connection((host, 8000), timeout=1)
    except Exception:
        return None
    return int((time.time() - start) * 1000)

# ---------------------------------------------------------
# CPU Temperature
# ---------------------------------------------------------
def get_cpu_temp():
    try:
        temps = psutil.sensors_temperatures()
        for key, entries in temps.items():
            for entry in entries:
                if entry.current:
                    return int(entry.current)
    except Exception:
        pass
    return None

# ---------------------------------------------------------
# GPU Metrics
# ---------------------------------------------------------
def get_gpu_stats():
    try:
        out = subprocess.check_output([
            "nvidia-smi",
            "--query-gpu=utilization.gpu,utilization.memory,memory.total,memory.used,temperature.gpu,name",
            "--format=csv,noheader,nounits"
        ], text=True).strip()
    except Exception:
        return None

    if not out:
        return None

    util_gpu, util_mem, mem_total, mem_used, temp, name = [
        x.strip() for x in out.split(",")
    ]

    # Convert to ints
    util_gpu = int(util_gpu)
    util_mem = int(util_mem)
    mem_total = int(mem_total)
    mem_used = int(mem_used)
    temp = int(temp)

    # Percent of memory used
    mem_pct = int((mem_used / mem_total) * 100) if mem_total > 0 else 0

    return {
        "gpu_util": util_gpu,
        "gpu_mem": mem_pct,          # percent for UI bar + sparkline
        "gpu_temp": temp,
        "gpu_name": name,
        "gpu_mem_total": mem_total,  # MB
        "gpu_mem_used": mem_used,    # MB
    }

# ---------------------------------------------------------
# Network Throughput
# ---------------------------------------------------------
def get_net_stats(iface):
    global _prev_net
    now = time.time()

    rx_path = Path(f"/sys/class/net/{iface}/statistics/rx_bytes")
    tx_path = Path(f"/sys/class/net/{iface}/statistics/tx_bytes")

    try:
        rx = int(rx_path.read_text().strip())
        tx = int(tx_path.read_text().strip())
    except Exception:
        return {"net_rx_kbps": None, "net_tx_kbps": None}

    prev = _prev_net.get(iface)
    _prev_net[iface] = (now, rx, tx)

    if prev is None:
        return {"net_rx_kbps": 0, "net_tx_kbps": 0}

    prev_t, prev_rx, prev_tx = prev
    dt = max(now - prev_t, 1e-3)

    rx_kbps = (rx - prev_rx) * 8 / 1000.0 / dt
    tx_kbps = (tx - prev_tx) * 8 / 1000.0 / dt

    return {
        "net_rx_kbps": int(rx_kbps),
        "net_tx_kbps": int(tx_kbps),
    }

# ---------------------------------------------------------
# Hardware Inventory
# ---------------------------------------------------------
def get_lspci_info():
    try:
        out = subprocess.check_output(["lspci"], text=True)
        return out.splitlines()
    except Exception:
        return []

def get_hardware_inventory():
    mem = psutil.virtual_memory()
    disks = []

    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "mount": part.mountpoint,
                "total_gb": round(usage.total / (1024**3), 1)
            })
        except Exception:
            pass

    return {
        "cpu_model": platform.processor(),
        "cpu_cores": psutil.cpu_count(logical=False),
        "cpu_threads": psutil.cpu_count(logical=True),
        "ram_total_gb": round(mem.total / (1024**3)),
        "hostname": socket.gethostname(),
        "disks": disks,
        "net_interfaces": list(psutil.net_if_addrs().keys()),
        "lspci": get_lspci_info(),
    }

# ---------------------------------------------------------
# Heartbeat Sender
# ---------------------------------------------------------
def send_heartbeat():
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    cpu_temp = get_cpu_temp()
    gpu = get_gpu_stats()
    net = get_net_stats(INTERFACE)
    hardware = get_hardware_inventory()
    latency = get_latency_ms()

    payload = {
        "name": hardware["hostname"],
        "role": ROLE,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "latency_ms": latency,
        "busy": False,
        "task": None,
        "cpu": cpu,
        "ram": ram,
        "cpu_temp": cpu_temp,
        "hardware": hardware,
        **net
    }

    if gpu:
        payload.update(gpu)

    try:
        requests.post(CONTROL_PLANE_URL, json=payload, timeout=2)
        print("Heartbeat sent:", json.dumps(payload))
    except Exception as e:
        print("Failed to send heartbeat:", e)

# ---------------------------------------------------------
# Main Loop
# ---------------------------------------------------------
def main():
    print(f"Starting node heartbeat agent on {socket.gethostname()} (iface={INTERFACE})...")
    while True:
        send_heartbeat()
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()