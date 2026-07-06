// ui/js/status.js
// Clean, modern worker-card rendering for the Control Plane

import { apiGetStatus } from "./api.js";

// DOM references
const statusIndicator = document.getElementById("status-indicator");
const statusDetails = document.getElementById("status-details");
const machineTable = document.getElementById("machine-table");
const heartbeatPane = document.getElementById("heartbeat-pane");
const gpuClusterSummary = document.getElementById("gpu-cluster-summary");
const machineSelect = document.getElementById("machine-select");

// ---------------------------------------------------------
// Helpers
// ---------------------------------------------------------
function setIndicator(aliveCount, total) {
  statusIndicator.classList.remove("status-unknown", "status-dead", "status-alive");

  if (aliveCount > 0) {
    statusIndicator.classList.add("status-alive");
    statusIndicator.querySelector(".status-label").textContent = "Online";
  } else {
    statusIndicator.classList.add("status-dead");
    statusIndicator.querySelector(".status-label").textContent = "Offline";
  }

  statusDetails.textContent = `${aliveCount} of ${total} machines online`;
}

function gpuBlock(machine) {
  if (!machine.gpu_name) {
    return `
      <div class="gpu-block gpu-none">
        <strong>No GPU</strong>
      </div>
    `;
  }

  return `
    <div class="gpu-block">
      <div><strong>${machine.gpu_name}</strong></div>
      <div>Util: ${machine.gpu_util ?? 0}%</div>
      <div>Mem: ${machine.gpu_mem ?? 0}%</div>
      <div>Temp: ${machine.gpu_temp ?? 0}°C</div>
    </div>
  `;
}

function machineCard(machine) {
  return `
    <div class="machine-card ${machine.alive ? "alive" : "dead"}">
      <div class="machine-header">
        <span class="machine-name">${machine.name}</span>
        <span class="machine-role">${machine.role || "unknown"}</span>
      </div>

      <div class="machine-stats">
        <div>CPU: ${machine.cpu ?? 0}%</div>
        <div>RAM: ${machine.ram ?? 0}%</div>
        <div>Busy: ${machine.busy ? "Yes" : "No"}</div>
      </div>

      ${gpuBlock(machine)}

      <div class="machine-footer">
        <span>IP: ${machine.primary_ip}</span>
        <span>Last seen: ${Math.floor(Date.now() / 1000 - machine.last_seen)}s ago</span>
      </div>
    </div>
  `;
}

function renderGpuClusterSummary(machines) {
  let ok = 0, warn = 0, hot = 0;

  machines.forEach((m) => {
    if (!m.gpu_name) return;

    const temp = m.gpu_temp ?? 0;
    const util = m.gpu_util ?? 0;
    const mem = m.gpu_mem ?? 0;

    if (temp > 75 || util > 90 || mem > 85) hot++;
    else if (temp > 60 || util > 50 || mem > 60) warn++;
    else ok++;
  });

  gpuClusterSummary.innerHTML = `
    <div class="gpu-summary-bar">
      GPU Health:
      <span class="gpu-ok-count">${ok} OK</span> •
      <span class="gpu-warn-count">${warn} WARN</span> •
      <span class="gpu-hot-count">${hot} HOT</span>
    </div>
  `;
}

function renderHeartbeatPane(machines) {
  heartbeatPane.innerHTML = machines
    .map(
      (m) => `
      <div class="heartbeat-card ${m.alive ? "alive" : "dead"}">
        <strong>${m.name}</strong>
        <div>${m.primary_ip}</div>
        <div>${Math.floor(Date.now() / 1000 - m.last_seen)}s ago</div>
      </div>
    `
    )
    .join("");
}

function populateMachineDropdown(machines) {
  machineSelect.innerHTML = "";

  const allOpt = document.createElement("option");
  allOpt.value = "ALL";
  allOpt.textContent = "All Machines";
  machineSelect.appendChild(allOpt);

  machines.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m.name;
    opt.textContent = `${m.name} (${(m.role || "unknown")})`;
    machineSelect.appendChild(opt);
  });
}

// ---------------------------------------------------------
// Main render function
// ---------------------------------------------------------
async function renderStatus() {
  try {
    const data = await apiGetStatus();
    const machines = data.machines || [];

    const aliveCount = machines.filter((m) => m.alive).length;

    setIndicator(aliveCount, machines.length);
    populateMachineDropdown(machines);
    renderGpuClusterSummary(machines);
    renderHeartbeatPane(machines);

    machineTable.innerHTML = machines.map(machineCard).join("");
  } catch (err) {
    console.error("Failed to render status:", err);
    statusDetails.textContent = "Error loading status.";
  }
}

// ---------------------------------------------------------
// Auto-refresh
// ---------------------------------------------------------
setInterval(renderStatus, 3000);
window.addEventListener("DOMContentLoaded", renderStatus);

export { renderStatus };