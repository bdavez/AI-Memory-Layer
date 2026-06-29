import { apiGetStatus } from "./api.js";
import { getStatusClass, getStatusLabel } from "../statusColors.js";

// ---------------------------------------------------------
// Reset UI
// ---------------------------------------------------------
export function setStatusUnknown() {
  const indicator = document.getElementById("status-indicator");
  const details = document.getElementById("status-details");
  const table = document.getElementById("machine-table");
  const dropdown = document.getElementById("machine-select");

  if (indicator) {
    indicator.className = "status-indicator status-unknown";
    const label = indicator.querySelector(".status-label");
    if (label) label.textContent = "Unknown";
  }

  if (details) details.textContent = "Waiting for status…";
  if (table) table.innerHTML = "";
  if (dropdown) dropdown.innerHTML = "";
}

// ---------------------------------------------------------
// Machine filter state
// ---------------------------------------------------------
// ---------------------------------------------------------
// Machine filter state
// ---------------------------------------------------------
let machineFilterState = {
  selectedMachine: "ALL",
  showAliveOnly: false,
  showGpuOnly: false,
  showBusyOnly: false,
  searchQuery: "",
  focusMode: false,
};

function normalizeRoleForSearch(role) {
  if (Array.isArray(role)) {
    return role.join(", ").toLowerCase();
  }
  return (role || "").toLowerCase();
}

function hasGpu(m) {
  return Array.isArray(m.gpus) && m.gpus.length > 0;
}

function getFilteredMachines(machines) {
  return machines.filter((m) => {
    if (
      machineFilterState.selectedMachine !== "ALL" &&
      m.name !== machineFilterState.selectedMachine
    ) {
      return false;
    }
    if (machineFilterState.showAliveOnly && !m.alive) {
      return false;
    }
    if (machineFilterState.showGpuOnly && !hasGpu(m)) {
      return false;
    }
    if (machineFilterState.showBusyOnly && m.status !== "busy") {
      return false;
    }
    if (machineFilterState.searchQuery) {
      const q = machineFilterState.searchQuery.toLowerCase();
      const name = (m.name || "").toLowerCase();
      const roleStr = normalizeRoleForSearch(m.role);
      if (!name.includes(q) && !roleStr.includes(q)) {
        return false;
      }
    }
    return true;
  });
}
// ---------------------------------------------------------
// Dropdown
// ---------------------------------------------------------
function roleToLabel(role) {
  if (Array.isArray(role)) return role.join(", ");
  return role || "unknown";
}

function populateMachineDropdown(machines) {
  const dropdown = document.getElementById("machine-select");
  if (!dropdown) return;

  const previous = dropdown.value || "ALL";
  dropdown.innerHTML = "";

  const allOpt = document.createElement("option");
  allOpt.value = "ALL";
  allOpt.textContent = "All Machines";
  dropdown.appendChild(allOpt);

  machines.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m.name;
    opt.textContent = `${m.name} (${roleToLabel(m.role)})`;
    dropdown.appendChild(opt);
  });

  if (previous && Array.from(dropdown.options).some((o) => o.value === previous)) {
    dropdown.value = previous;
  } else {
    dropdown.value = "ALL";
  }
  machineFilterState.selectedMachine = dropdown.value;
}

// Node Summary
function renderGpuClusterSummary(machines) {
  let ok = 0;
  let warn = 0;
  let hot = 0;

  machines.forEach((m) => {
    if (!Array.isArray(m.gpus)) return;

    m.gpus.forEach((g) => {
      const temp = g.temp ?? null;
      const util = g.util ?? null;
      const mem = g.mem_pct ?? null;

      let state = "ok";

      if (
        (temp != null && temp > 75) ||
        (util != null && util > 90) ||
        (mem != null && mem > 85)
      ) {
        state = "hot";
      } else if (
        (temp != null && temp > 60) ||
        (util != null && util > 50) ||
        (mem != null && mem > 60)
      ) {
        state = "warn";
      }

      if (state === "ok") ok++;
      if (state === "warn") warn++;
      if (state === "hot") hot++;
    });
  });

  const el = document.getElementById("gpu-cluster-summary");
  if (!el) return;

  el.innerHTML = `
    <div class="gpu-summary-bar">
      GPU Health:
      <span class="gpu-ok-count">${ok} OK</span> •
      <span class="gpu-warn-count">${warn} WARN</span> •
      <span class="gpu-hot-count">${hot} HOT</span>
    </div>
  `;
}

// ---------------------------------------------------------
// Machine table
// ---------------------------------------------------------

function renderMachineTable(machines) {
  const table = document.getElementById("machine-table");
  if (!table) return;

  if (!machines.length) {
    table.innerHTML = "<div class='empty'>No machines reporting</div>";
    return;
  }
 renderGpuClusterSummary(machines);
  const rows = machines
    .map((m) => {
      const alive = m.alive ? "alive" : "dead";

      // -----------------------------------------
      // Phase 2.2 — Machine-level GPU alert logic
      // -----------------------------------------
      let gpuAlert = false;

      if (Array.isArray(m.gpus)) {
        gpuAlert = m.gpus.some((g) => {
          const hot =
            (g.temp != null && g.temp > 75) ||
            (g.util != null && g.util > 90) ||
            (g.mem_pct != null && g.mem_pct > 85);

          const warn =
            (g.temp != null && g.temp > 60) ||
            (g.util != null && g.util > 50) ||
            (g.mem_pct != null && g.mem_pct > 60);

          return hot || warn;
        });
      }

      return `
      <tr class="machine-row ${alive}">
        <td>${m.name}</td>
        <td>${roleToLabel(m.role)}</td>
        <td>${m.heartbeat}</td>
        <td class="hb-${alive}">${alive.toUpperCase()}</td>
        <td class="gpu-alert-cell">${gpuAlert ? "🔥" : ""}</td>
      </tr>

      ${
        Array.isArray(m.gpus) && m.gpus.length > 0
          ? `
            <tr class="machine-gpu-row">
              <td colspan="5">
                ${renderGpuBlocks(m)}
              </td>
            </tr>
          `
          : ""
      }
    `;
    })
    .join("");

  table.innerHTML = `
    <table class="machine-table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Role</th>
          <th>Last Heartbeat</th>
          <th>Status</th>
          <th>GPU</th>   <!-- NEW COLUMN -->
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}
// ---------------------------------------------------------
// Apply status
// ---------------------------------------------------------
function setStatusFromData(data) {
  const indicator = document.getElementById("status-indicator");
  const details = document.getElementById("status-details");

  if (!data) {
    setStatusUnknown();
    return;
  }

  if (indicator) {
    const status = data.overall_status || "unknown";
    indicator.className = `status-indicator status-${status.toLowerCase()}`;
    const label = indicator.querySelector(".status-label");
    if (label) label.textContent = status;
  }

  if (details) details.textContent = data.message || "Status updated.";

  const machines = data.machines || [];
  populateMachineDropdown(machines);
  initializeMachineFilters(data);
  renderMachineTable(machines);
}

// ---------------------------------------------------------
// Machine filter initialization
// ---------------------------------------------------------
function initializeMachineFilters(statusData) {
  if (window.__machineFiltersInitialized) return;
  window.__machineFiltersInitialized = true;

  const dropdown = document.getElementById("machine-select");
  const searchInput = document.getElementById("machine-search");
  const aliveToggle = document.getElementById("filter-alive");
  const gpuToggle = document.getElementById("filter-gpu");
  const busyToggle = document.getElementById("filter-busy");
  const focusToggle = document.getElementById("filter-focus");

  function reRender() {
    const data = window.__lastStatusData || statusData;
    renderHeartbeatPane(data);
  }

  if (dropdown) {
    dropdown.addEventListener("change", () => {
      machineFilterState.selectedMachine = dropdown.value;
      reRender();
    });
  }

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      machineFilterState.searchQuery = searchInput.value.trim();
      reRender();
    });
  }

  if (aliveToggle) {
    aliveToggle.addEventListener("change", () => {
      machineFilterState.showAliveOnly = aliveToggle.checked;
      reRender();
    });
  }

  if (gpuToggle) {
    gpuToggle.addEventListener("change", () => {
      machineFilterState.showGpuOnly = gpuToggle.checked;
      reRender();
    });
  }

  if (busyToggle) {
    busyToggle.addEventListener("change", () => {
      machineFilterState.showBusyOnly = busyToggle.checked;
      reRender();
    });
  }

  if (focusToggle) {
    focusToggle.addEventListener("change", () => {
      machineFilterState.focusMode = focusToggle.checked;
      reRender();
    });
  }
}

// ---------------------------------------------------------
// Sparkline helpers
// ---------------------------------------------------------
const sparkHistoryCluster = {
  cpu: [],
  ram: [],
};

const sparkHistoryNodes = {};

function smoothSeries(values, windowSize = 3) {
  if (values.length <= 2 || windowSize <= 1) return values.slice();
  const out = [];
  for (let i = 0; i < values.length; i++) {
    const start = Math.max(0, i - windowSize + 1);
    const slice = values.slice(start, i + 1);
    const avg = slice.reduce((a, b) => a + b, 0) / slice.length;
    out.push(avg);
  }
  return out;
}

function drawSparklineSegmented(canvasId, values, thresholds) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;

  ctx.clearRect(0, 0, w, h);
  if (!values || values.length < 2) return;

  const max = 100;
  const min = 0;

  const segments = [];
  for (let i = 0; i < values.length - 1; i++) {
    const v1 = values[i];
    const v2 = values[i + 1];
    const x1 = (i / (values.length - 1)) * w;
    const x2 = ((i + 1) / (values.length - 1)) * w;
    const y1 = h - ((v1 - min) / (max - min)) * h;
    const y2 = h - ((v2 - min) / (max - min)) * h;

    let color = thresholds.okColor;
    if (v1 >= thresholds.crit) color = thresholds.critColor;
    else if (v1 >= thresholds.warn) color = thresholds.warnColor;

    segments.push({ x1, y1, x2, y2, color });
  }

  ctx.lineWidth = 2;
  segments.forEach((seg) => {
    ctx.strokeStyle = seg.color;
    ctx.beginPath();
    ctx.moveTo(seg.x1, seg.y1);
    ctx.lineTo(seg.x2, seg.y2);
    ctx.stroke();
  });
}

// ---------------------------------------------------------
// Refresh loop
// ---------------------------------------------------------
export async function refreshStatus() {
  return refreshStatusImpl();
}

async function refreshStatusImpl() {
  try {
    const data = await apiGetStatus();
    window.__lastStatusData = data;

    setStatusFromData(data);

    const machines = data.machines || [];

    renderHeartbeatPane(data);
    renderTaskActivityPane(data);

    const cpuValues = machines.map((m) => m.cpu).filter((v) => v != null);
    const ramValues = machines.map((m) => m.ram).filter((v) => v != null);

    if (cpuValues.length) {
      const avgCpu = Math.round(
        cpuValues.reduce((a, b) => a + b, 0) / cpuValues.length
      );
      sparkHistoryCluster.cpu.push(avgCpu);
      if (sparkHistoryCluster.cpu.length > 60) sparkHistoryCluster.cpu.shift();
    }

    if (ramValues.length) {
      const avgRam = Math.round(
        ramValues.reduce((a, b) => a + b, 0) / ramValues.length
      );
      sparkHistoryCluster.ram.push(avgRam);
      if (sparkHistoryCluster.ram.length > 60) sparkHistoryCluster.ram.shift();
    }

machines.forEach((m) => {
  if (!sparkHistoryNodes[m.name]) {
    sparkHistoryNodes[m.name] = {
      cpu: [],
      ram: [],
      gpu: [],
      gpu_mem: [],
      net_rx: [],
      net_tx: [],
    };
  }

  if (m.cpu != null) {
    sparkHistoryNodes[m.name].cpu.push(m.cpu);
    if (sparkHistoryNodes[m.name].cpu.length > 60)
      sparkHistoryNodes[m.name].cpu.shift();
  }

  if (m.ram != null) {
    sparkHistoryNodes[m.name].ram.push(m.ram);
    if (sparkHistoryNodes[m.name].ram.length > 60)
      sparkHistoryNodes[m.name].ram.shift();
  }

  // Multi-GPU: aggregate GPU util/mem_pct per node
  if (Array.isArray(m.gpus) && m.gpus.length > 0) {
    const utilValues = m.gpus
      .map((g) => g.util)
      .filter((v) => v != null);
    const memPctValues = m.gpus
      .map((g) => g.mem_pct)
      .filter((v) => v != null);

    if (utilValues.length) {
      const avgUtil = Math.round(
        utilValues.reduce((a, b) => a + b, 0) / utilValues.length
      );
      sparkHistoryNodes[m.name].gpu.push(avgUtil);
      if (sparkHistoryNodes[m.name].gpu.length > 60)
        sparkHistoryNodes[m.name].gpu.shift();
    }

    if (memPctValues.length) {
      const avgMemPct = Math.round(
        memPctValues.reduce((a, b) => a + b, 0) / memPctValues.length
      );
      sparkHistoryNodes[m.name].gpu_mem.push(avgMemPct);
      if (sparkHistoryNodes[m.name].gpu_mem.length > 60)
        sparkHistoryNodes[m.name].gpu_mem.shift();
    }
  }

  if (m.net_rx_kbps != null) {
    sparkHistoryNodes[m.name].net_rx.push(m.net_rx_kbps);
    if (sparkHistoryNodes[m.name].net_rx.length > 60)
      sparkHistoryNodes[m.name].net_rx.shift();
  }

  if (m.net_tx_kbps != null) {
    sparkHistoryNodes[m.name].net_tx.push(m.net_tx_kbps);
    if (sparkHistoryNodes[m.name].net_tx.length > 60)
      sparkHistoryNodes[m.name].net_tx.shift();
  }
});


    renderClusterSummary(data.machines);
    renderClusterTrendPane(data.machines);

    drawSparklineSegmented(
      "cluster-cpu-spark",
      smoothSeries(sparkHistoryCluster.cpu, 2),
      {
        ok: 0,
        warn: 70,
        crit: 90,
        okColor: "#00e676",
        warnColor: "#ffca28",
        critColor: "#ff5252",
      }
    );
    drawSparklineSegmented(
      "cluster-ram-spark",
      smoothSeries(sparkHistoryCluster.ram, 2),
      {
        ok: 0,
        warn: 70,
        crit: 90,
        okColor: "#40c4ff",
        warnColor: "#ffca28",
        critColor: "#ff5252",
      }
    );

    machines.forEach((m) => {
      const hist = sparkHistoryNodes[m.name];
      if (!hist) return;
      const safeName = m.name.replace(/[^a-zA-Z0-9_-]/g, "_");

      drawSparklineSegmented(
        `node-cpu-spark-${safeName}`,
        smoothSeries(hist.cpu, 2),
        {
          ok: 0,
          warn: 70,
          crit: 90,
          okColor: "#00e676",
          warnColor: "#ffca28",
          critColor: "#ff5252",
        }
      );

      drawSparklineSegmented(
        `node-ram-spark-${safeName}`,
        smoothSeries(hist.ram, 2),
        {
          ok: 0,
          warn: 70,
          crit: 90,
          okColor: "#40c4ff",
          warnColor: "#ffca28",
          critColor: "#ff5252",
        }
      );

      if (hist.gpu && hist.gpu.length > 1) {
        drawSparklineSegmented(
          `node-gpu-spark-${safeName}`,
          smoothSeries(hist.gpu, 2),
          {
            ok: 0,
            warn: 70,
            crit: 90,
            okColor: "#00bcd4",
            warnColor: "#ffca28",
            critColor: "#ff5252",
          }
        );
      }

      if (hist.gpu_mem && hist.gpu_mem.length > 1) {
        drawSparklineSegmented(
          `node-gpu-mem-spark-${safeName}`,
          smoothSeries(hist.gpu_mem, 2),
          {
            ok: 0,
            warn: 70,
            crit: 90,
            okColor: "#7e57c2",
            warnColor: "#ffca28",
            critColor: "#ff5252",
          }
        );
      }

      if (hist.net_rx && hist.net_rx.length > 1) {
        drawSparklineSegmented(
          `node-net-rx-spark-${safeName}`,
          smoothSeries(hist.net_rx, 2),
          {
            ok: 0,
            warn: 5000,
            crit: 20000,
            okColor: "#4caf50",
            warnColor: "#ffca28",
            critColor: "#ff5252",
          }
        );
      }

      if (hist.net_tx && hist.net_tx.length > 1) {
        drawSparklineSegmented(
          `node-net-tx-spark-${safeName}`,
          smoothSeries(hist.net_tx, 2),
          {
            ok: 0,
            warn: 5000,
            crit: 20000,
            okColor: "#8bc34a",
            warnColor: "#ffca28",
            critColor: "#ff5252",
          }
        );
      }
    });
  } catch (err) {
    console.error("Failed to refresh status:", err);
    setStatusUnknown();
  }
}

// ========================================================
// Heartbeat Pane Renderer
// ========================================================
function groupByRole(machines) {
  const groups = {};
  machines.forEach((m) => {
    const roleLabel = roleToLabel(m.role);
    if (!groups[roleLabel]) groups[roleLabel] = [];
    groups[roleLabel].push(m);
  });
  return groups;
}

export function renderHeartbeatPane(statusData) {
  const allMachines = statusData.machines || [];
  const machines = getFilteredMachines(allMachines);
  const groups = groupByRole(machines);

  const container = document.getElementById("heartbeat-pane");
  if (!container) return;

  container.innerHTML = `
    <div class="status-section">
      <div class="status-section-header">Cluster Heartbeat</div>
      <div class="status-section-body">
        ${
          Object.keys(groups).length === 0
            ? `<div class="hb-empty">No machines reporting heartbeat.</div>`
            : Object.entries(groups)
                .map(
                  ([role, nodes]) => `
                <div class="hb-group">
                  <div class="hb-group-title">${role}</div>
                  <div class="hb-group-grid">
                    ${nodes.map((node) => renderHeartbeatCard(node)).join("")}
                  </div>
                </div>
              `
                )
                .join("")
        }
      </div>
    </div>
  `;
}

function renderGpuSummary(node) {
  if (!Array.isArray(node.gpus) || node.gpus.length === 0) {
    return `<div class="hb-gpu-none">No GPUs</div>`;
  }

  const lines = node.gpus.map((g) => {
    const name = g.name || `GPU${g.index}`;
    const util = g.util != null ? `${g.util}%` : "—";
    const mem = g.mem_pct != null ? `${g.mem_pct}%` : "—";
    const temp = g.temp != null ? `${g.temp}°C` : "—";
    return `<div class="hb-gpu-line">GPU${g.index}: ${name} — ${util} • ${mem} • ${temp}</div>`;
  });

  return `<div class="hb-gpu-list">${lines.join("")}</div>`;
}

function renderResourceBar(value, key, label, isAlert = false) {
  if (value == null) {
    return `
      <div class="hb-resource hb-${key}">
        <span class="hb-resource-label">${label}</span>
        <span class="hb-resource-value">—</span>
      </div>
    `;
  }

  const pct = Math.max(0, Math.min(100, value));
  const barClass = isAlert ? "hb-bar-alert" : "hb-bar-normal";

  return `
    <div class="hb-resource hb-${key}">
      <span class="hb-resource-label">${label}</span>
      <div class="hb-resource-bar">
        <div class="hb-resource-bar-fill ${barClass}" style="width: ${pct}%;"></div>
      </div>
      <span class="hb-resource-value">${pct}%</span>
    </div>
  `;
}

function renderGpuBlocks(node) {
  if (!Array.isArray(node.gpus) || node.gpus.length === 0) {
    return `<div class="hb-gpu-none">No GPUs</div>`;
  }

  const blocks = node.gpus.map((g) => {
    const index = g.index != null ? g.index : "?";
    const name = g.name || `GPU${index}`;
    const utilVal = g.util != null ? g.util : null;
    const memPctVal = g.mem_pct != null ? g.mem_pct : null;
    const tempVal = g.temp != null ? g.temp : null;
    const wattsVal = g.watts != null ? g.watts : null;

    // -------------------------------
    // Phase 2: GPU health classification
    // -------------------------------
    let healthClass = "gpu-ok";

    // Temperature thresholds
    if (tempVal != null) {
      if (tempVal > 75) healthClass = "gpu-hot";
      else if (tempVal > 60) healthClass = "gpu-warn";
    }

    // Utilization thresholds
    if (utilVal != null) {
      if (utilVal > 90) healthClass = "gpu-hot";
      else if (utilVal > 50 && healthClass !== "gpu-hot") healthClass = "gpu-warn";
    }

    // Memory usage thresholds
    if (memPctVal != null) {
      if (memPctVal > 85) healthClass = "gpu-hot";
      else if (memPctVal > 60 && healthClass !== "gpu-hot") healthClass = "gpu-warn";
    }

    // Power thresholds (simple heuristic)
    if (wattsVal != null) {
      if (wattsVal > 200) healthClass = "gpu-hot";
      else if (wattsVal > 150 && healthClass !== "gpu-hot") healthClass = "gpu-warn";
    }

    // -------------------------------
    // Formatting for display
    // -------------------------------
    const util = utilVal != null ? `${utilVal}%` : "—";
    const memPct = memPctVal != null ? `${memPctVal}%` : "—";

    let memDetail = "";
    if (g.mem_used_gb != null && g.mem_total_gb != null) {
      memDetail = ` (${g.mem_used_gb.toFixed(1)} / ${g.mem_total_gb.toFixed(1)} GB)`;
    }

    const temp = tempVal != null ? `${tempVal}°c` : "—";
    const watts = wattsVal != null ? `${wattsVal} w` : "—";

    return `
      <div class="hb-gpu-block ${healthClass}">
        <div class="hb-gpu-title">GPU${index} — ${name}</div>
        <div class="hb-gpu-field">util: ${util}</div>
        <div class="hb-gpu-field">mem: ${memPct}${memDetail}</div>
        <div class="hb-gpu-field">temp: ${temp}</div>
        <div class="hb-gpu-field">power: ${watts}</div>
      </div>
    `;
  });

  return `<div class="hb-gpu-blocks">${blocks.join("")}</div>`;
}

function renderHeartbeatCard(node) {
  const statusClass = getStatusClass(node.status);
  const statusLabel = getStatusLabel(node.status);

  const lastSeen = node.last_seen
    ? new Date(node.last_seen * 1000).toLocaleTimeString()
    : "—";

  const heartbeat = node.heartbeat || "—";
  const latency =
    node.latency_ms != null ? `${node.latency_ms} ms` : "—";

  const safeName = node.name.replace(/[^a-zA-Z0-9_-]/g, "_");

  // Network usage text helpers
  const linkMbps = node.link_speed_mbps;
  const rxKbps = node.net_rx_kbps;
  const txKbps = node.net_tx_kbps;

  const rxMbps = rxKbps != null ? (rxKbps / 1000).toFixed(1) : null;
  const txMbps = txKbps != null ? (txKbps / 1000).toFixed(1) : null;

  const rxPct =
    rxKbps != null && linkMbps
      ? Math.round((rxKbps / (linkMbps * 1000)) * 100)
      : null;

  const txPct =
    txKbps != null && linkMbps
      ? Math.round((txKbps / (linkMbps * 1000)) * 100)
      : null;

  const linkText = linkMbps ? `${linkMbps} mbps` : "—";

  // ---- alerting thresholds ----
  const cpuAlert = node.cpu != null && node.cpu >= 90;
  const ramAlert = node.ram != null && node.ram >= 90;

  let gpuAlert = false;
  if (Array.isArray(node.gpus) && node.gpus.length > 0) {
    const maxUtil = Math.max(
      ...node.gpus
        .map((g) => g.util)
        .filter((v) => v != null && !isNaN(v)),
      0
    );
    gpuAlert = maxUtil >= 90;
  }

  const netAlert =
    (rxPct != null && rxPct >= 80) ||
    (txPct != null && txPct >= 80);
  const latencyAlert =
    node.latency_ms != null && node.latency_ms >= 200;

  const cardAlert =
    cpuAlert || ramAlert || gpuAlert || netAlert || latencyAlert;

  const cardAlertClass = cardAlert ? " hb-card-alert" : "";

  // thermal/io/power presence checks (safe if missing)
  const hasGpuTemp =
    Array.isArray(node.gpus) &&
    node.gpus.some((g) => g.temp != null);
  const hasCpuTemp = node.cpu_temp != null;
  const hasThermal = hasGpuTemp || hasCpuTemp;

  const hasIo =
    node.disk_read_kbps != null ||
    node.disk_write_kbps != null ||
    node.disk_busy_pct != null;

  const hasPower =
    node.cpu_watts != null ||
    (Array.isArray(node.gpus) &&
      node.gpus.some((g) => g.watts != null));

  return `
    <div class="hb-card${cardAlertClass}">
      <div class="hb-card-header">
        <span class="hb-name">${node.name}</span>
        <span class="${statusClass}">${statusLabel}</span>
      </div>

      <div class="hb-card-meta">
        <span class="hb-meta-item">Last HB: ${heartbeat}</span>
        <span class="hb-meta-item">Seen: ${lastSeen}</span>
        <span class="hb-meta-item${
          latencyAlert ? " hb-meta-alert" : ""
        }">Latency: ${latency}</span>
        <span class="hb-meta-item">Role: ${roleToLabel(
          node.role
        )}</span>
      </div>

      <div class="hb-card-resources">

        <!-- System -->
        <div class="hb-subsection-title">system</div>
        ${renderResourceBar(node.cpu, "cpu", "⚙️", cpuAlert)}
        ${renderResourceBar(node.ram, "ram", "🧠", ramAlert)}

        <!-- GPU -->
        <div class="hb-subsection-title">gpu</div>
        ${renderGpuBlocks(node)}

        <!-- Network -->
        <div class="hb-subsection-title">network</div>
        ${
          node.net_rx_kbps != null && node.link_speed_mbps != null
            ? renderResourceBar(
                Math.round(
                  (node.net_rx_kbps / (node.link_speed_mbps * 1000)) * 100
                ),
                "net-rx",
                "⬇️",
                netAlert
              )
            : ""
        }
        ${
          node.net_tx_kbps != null && node.link_speed_mbps != null
            ? renderResourceBar(
                Math.round(
                  (node.net_tx_kbps / (node.link_speed_mbps * 1000)) * 100
                ),
                "net-tx",
                "⬆️",
                netAlert
              )
            : ""
        }

        ${
          rxMbps != null || txMbps != null || linkMbps != null
            ? `
              <div class="hb-network-text">
                <div>rx: ${
                  rxMbps != null
                    ? `${rxMbps} mbps${
                        rxPct != null ? ` (${rxPct}% )` : ""
                      }`
                    : "—"
                }</div>
                <div>tx: ${
                  txMbps != null
                    ? `${txMbps} mbps${
                        txPct != null ? ` (${txPct}% )` : ""
                      }`
                    : "—"
                }</div>
                <div>link: ${linkText}</div>
              </div>
            `
            : ""
        }

        ${
          hasThermal
            ? `
              <div class="hb-subsection-title">thermal</div>
              <div class="hb-thermal-grid">
                ${
                  hasCpuTemp
                    ? `<div class="hb-thermal-item">
                         <span class="hb-thermal-label">cpu temp</span>
                         <span class="hb-thermal-value">${node.cpu_temp}°c</span>
                       </div>`
                    : ""
                }
                ${
                  hasGpuTemp
                    ? `<div class="hb-thermal-item">
                         <span class="hb-thermal-label">gpu temp</span>
                         <span class="hb-thermal-value">mixed</span>
                       </div>`
                    : ""
                }
              </div>
            `
            : ""
        }

        ${
          hasIo
            ? `
              <div class="hb-subsection-title">io</div>
              <div class="hb-io-grid">
                ${
                  node.disk_read_kbps != null
                    ? `<div class="hb-io-item">
                         <span class="hb-io-label">read</span>
                         <span class="hb-io-value">${(
                           node.disk_read_kbps / 1000
                         ).toFixed(1)} mb/s</span>
                       </div>`
                    : ""
                }
                ${
                  node.disk_write_kbps != null
                    ? `<div class="hb-io-item">
                         <span class="hb-io-label">write</span>
                         <span class="hb-io-value">${(
                           node.disk_write_kbps / 1000
                         ).toFixed(1)} mb/s</span>
                       </div>`
                    : ""
                }
                ${
                  node.disk_busy_pct != null
                    ? `<div class="hb-io-item">
                         <span class="hb-io-label">busy</span>
                         <span class="hb-io-value">${node.disk_busy_pct}%</span>
                       </div>`
                    : ""
                }
              </div>
            `
            : ""
        }

        ${
          hasPower
            ? `
              <div class="hb-subsection-title">power</div>
              <div class="hb-power-grid">
                ${
                  node.cpu_watts != null
                    ? `<div class="hb-power-item">
                         <span class="hb-power-label">cpu</span>
                         <span class="hb-power-value">${node.cpu_watts} w</span>
                       </div>`
                    : ""
                }
                ${
                  Array.isArray(node.gpus) &&
                  node.gpus.some((g) => g.watts != null)
                    ? `<div class="hb-power-item">
                         <span class="hb-power-label">gpu</span>
                         <span class="hb-power-value">mixed</span>
                       </div>`
                    : ""
                }
              </div>
            `
            : ""
        }

      </div>

      <div class="hb-card-reason">
        ${node.status_reason || ""}
      </div>

      <div class="hb-subsection-title">signals</div>
      <div class="hb-signals-grid">

        <div class="sparkline-row">
          <div class="sparkline-label">cpu</div>
          <canvas class="node-cpu-spark hb-spark-hover"
                  id="node-cpu-spark-${safeName}"
                  data-node="${safeName}"
                  data-metric="cpu"
                  width="140" height="26"></canvas>
        </div>

        <div class="sparkline-row">
          <div class="sparkline-label">ram</div>
          <canvas class="node-ram-spark hb-spark-hover"
                  id="node-ram-spark-${safeName}"
                  data-node="${safeName}"
                  data-metric="ram"
                  width="140" height="26"></canvas>
        </div>

        <div class="sparkline-row">
          <div class="sparkline-label">gpu</div>
          <canvas class="node-gpu-spark hb-spark-hover"
                  id="node-gpu-spark-${safeName}"
                  data-node="${safeName}"
                  data-metric="gpu"
                  width="140" height="26"></canvas>
        </div>

        <div class="sparkline-row">
          <div class="sparkline-label">gpu mem</div>
          <canvas class="node-gpu-mem-spark hb-spark-hover"
                  id="node-gpu-mem-spark-${safeName}"
                  data-node="${safeName}"
                  data-metric="gpu-mem"
                  width="140" height="26"></canvas>
        </div>

        <div class="sparkline-row">
          <div class="sparkline-label">net rx</div>
          <canvas class="node-net-rx-spark hb-spark-hover"
                  id="node-net-rx-spark-${safeName}"
                  data-node="${safeName}"
                  data-metric="net-rx"
                  width="140" height="26"></canvas>
        </div>

        <div class="sparkline-row">
          <div class="sparkline-label">net tx</div>
          <canvas class="node-net-tx-spark hb-spark-hover"
                  id="node-net-tx-spark-${safeName}"
                  data-node="${safeName}"
                  data-metric="net-tx"
                  width="140" height="26"></canvas>
        </div>

      </div>
    </div>
  `;
}
// ---------------------------------------------------------
// Stubs for other panes (assumed existing in your codebase)
// ---------------------------------------------------------
function renderTaskActivityPane(_data) {
  // existing implementation in your project
}

  // existing implementation in your project
function renderClusterSummary(machines) {
  const el = document.getElementById("cluster-summary-pane");
  if (!el) return;

  let totalCpu = 0;
  let totalRam = 0;
  let totalGpuUtil = 0;
  let gpuCount = 0;

  let alive = 0;
  let dead = 0;
  let gpuNodes = 0;
  let busyNodes = 0;

  machines.forEach((m) => {
    if (m.alive) alive++;
    else dead++;

    if (m.busy) busyNodes++;

    if (m.cpu != null) totalCpu += m.cpu;
    if (m.ram != null) totalRam += m.ram;

    if (Array.isArray(m.gpus)) {
      gpuNodes++;
      m.gpus.forEach((g) => {
        if (g.util != null) {
          totalGpuUtil += g.util;
          gpuCount++;
        }
      });
    }
  });

  const avgCpu = (totalCpu / machines.length).toFixed(1);
  const avgRam = (totalRam / machines.length).toFixed(1);
  const avgGpu = gpuCount > 0 ? (totalGpuUtil / gpuCount).toFixed(1) : "—";

  el.innerHTML = `
    <div class="cluster-summary-card">
      <div class="cluster-summary-title">Cluster Summary</div>

      <div class="cluster-summary-row">
        <span>Avg CPU:</span> <span>${avgCpu}%</span>
      </div>

      <div class="cluster-summary-row">
        <span>Avg RAM:</span> <span>${avgRam}%</span>
      </div>

      <div class="cluster-summary-row">
        <span>Avg GPU Util:</span> <span>${avgGpu}%</span>
      </div>

      <div class="cluster-summary-row">
        <span>Alive Machines:</span> <span>${alive}</span>
      </div>

      <div class="cluster-summary-row">
        <span>GPU Nodes:</span> <span>${gpuNodes}</span>
      </div>

      <div class="cluster-summary-row">
        <span>Busy Nodes:</span> <span>${busyNodes}</span>
      </div>
    </div>
  `;
}


function renderClusterTrendPane(_data) {
  // existing implementation in your project
}
