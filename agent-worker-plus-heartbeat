import time
import socket
import psutil
import subprocess
import glob
import logging
import requests

# === Logging ===
logging.basicConfig(
    filename="/tmp/worker_agent.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# === GPU Setup ===
try:
    import pynvml
    pynvml.nvmlInit()
except Exception as e:
    logging.warning(f"GPU init failed: {e}")
    pynvml = None

# === Config ===
CONTROL_PLANE_URL = "http://192.168.50.60:8000/heartbeat"
AGENT_NAME = "vm-ml-node-01"
AGENT_ROLE = "ml"
AGENT_PORT = 9000

# === Helpers ===
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

def get_cpu_temp():
    try:
        for zone in range(10):
            path = f"/sys/class/thermal/thermal_zone{zone}/temp"
            try:
                with open(path) as f:
                    temp = int(f.read().strip()) / 1000
                    if 10 < temp < 120:
                        return round(temp)
            except FileNotFoundError:
                continue
    except Exception:
        pass
    return None

def get_net_usage():
    try:
        net_io = psutil.net_io_counters(pernic=True)
        rx = tx = 0
        for iface, stats in net_io.items():
            if iface != "lo":
                rx += stats.bytes_recv
                tx += stats.bytes_sent
        return rx / 1024, tx / 1024
    except Exception:
        return None, None

def get_link_speed():
    try:
        for iface in glob.glob("/sys/class/net/*"):
            if "lo" in iface:
                continue
            try:
                with open(f"{iface}/speed") as f:
                    speed = int(f.read().strip())
                    if speed > 0:
                        return speed
            except Exception:
                continue
    except Exception:
        pass
    return None

def get_gpu_metrics():
    if not pynvml:
        return {}
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000
        name = pynvml.nvmlDeviceGetName(handle).decode()
        return {
            "gpu_util": util.gpu,
            "gpu_mem_total": round(mem.total / (1024**2), 1),
            "gpu_mem_used": round(mem.used / (1024**2), 1),
            "gpu_mem": round((mem.used / mem.total) * 100, 1),
            "gpu_temp": temp,
            "gpu_watts": power,
            "gpu_name": name
        }
    except Exception as e:
        logging.warning(f"GPU metrics failed: {e}")
        return {}

# === Main Loop ===
if __name__ == "__main__":
    while True:
        try:
            rx_kb, tx_kb = get_net_usage()
            gpu = get_gpu_metrics()

            payload = {
                "name": AGENT_NAME,
                "role": AGENT_ROLE,
                "agent_port": AGENT_PORT,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "busy": False,
                "task": None,
                "cpu": round(psutil.cpu_percent(interval=0.5), 1),
                "ram": round(psutil.virtual_memory().percent, 1),
                "cpu_temp": get_cpu_temp(),
                "cpu_watts": None,
                "net_rx_kbps": round(rx_kb, 1) if rx_kb else None,
                "net_tx_kbps": round(tx_kb, 1) if tx_kb else None,
                "link_speed_mbps": get_link_speed(),
                "hardware": {
                    "ip": get_local_ip()
                },
                **gpu
            }

            response = requests.post(CONTROL_PLANE_URL, json=payload, timeout=5)
            logging.info(f"Heartbeat sent: {response.status_code}")
        except Exception as e:
            logging.exception(f"Unhandled error in heartbeat loop: {e}")

        time.sleep(5)