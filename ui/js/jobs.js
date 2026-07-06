// ui/js/jobs.js
// Phase 3 UI: Jobs Pane with durations, icons, sorting, logs

import { openJsonModal } from "./modal.js";

async function fetchJSON(url, options = {}) {
  const resp = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`HTTP ${resp.status}: ${text}`);
  }
  return resp.json();
}

// ---------------------------------------------------------
// Helpers
// ---------------------------------------------------------
function formatDuration(ms) {
  if (!ms || ms < 0) return "—";
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const rem = sec % 60;
  return `${min}m ${rem}s`;
}

function jobIcon(type) {
  const map = {
    "code_assist": "💻",
    "llm": "🧠",
    "compiler_run": "🛠️",
    "drift_analysis": "📉",
    "summarize": "📝",
    "vision": "👁️",
    "diffusion": "🎨",
  };
  return map[type] || "📦";
}

function machineBadge(name) {
  if (!name) return "—";
  return `<span class="machine-badge">${name}</span>`;
}

// ---------------------------------------------------------
// Job Actions
// ---------------------------------------------------------
async function cancelJob(jobId) {
  return fetchJSON(`/api/jobs/${jobId}/cancel`, { method: "POST" });
}

async function retryJob(jobId) {
  return fetchJSON(`/api/jobs/${jobId}/retry`, { method: "POST" });
}

// ---------------------------------------------------------
// Log Viewer
// ---------------------------------------------------------
async function loadJobLogs(jobId) {
  try {
    const logs = await fetchJSON(`/api/jobs/${jobId}/logs`);
    const modalData = logs?.logs || [];
    openJsonModal(`Logs for Job ${jobId}`, modalData, `job-${jobId}-logs.json`);
  } catch (err) {
    console.error("Failed to load logs:", err);
    openJsonModal(`Logs for Job ${jobId}`, { error: err.message });
  }
}

// ---------------------------------------------------------
// Job Detail Drawer
// ---------------------------------------------------------
function renderJobDetails(job) {
  const detail = document.getElementById("job-detail-pane");
  if (!detail) return;

  const duration = job.started_at && job.finished_at
    ? formatDuration(job.finished_at - job.started_at)
    : "—";

  detail.innerHTML = `
    <div class="status-section">
      <div class="status-section-header">Job Details</div>
      <div class="job-detail-meta">
        <div><strong>ID:</strong> ${job.id}</div>
        <div><strong>Type:</strong> ${jobIcon(job.type)} ${job.type}</div>
        <div><strong>Status:</strong> ${job.status}</div>
        <div><strong>Machine:</strong> ${machineBadge(job.assigned_machine)}</div>
        <div><strong>Duration:</strong> ${duration}</div>
      </div>

      <button class="job-log-button" data-id="${job.id}">View Logs</button>

      <pre class="json-viewer">${JSON.stringify(job, null, 2)}</pre>
    </div>
  `;

  detail.querySelector(".job-log-button").addEventListener("click", () => {
    loadJobLogs(job.id);
  });
}

// ---------------------------------------------------------
// Job Table Renderer
// ---------------------------------------------------------
function renderJobTable(list, title) {
  if (!list || list.length === 0) {
    return `
      <div class="status-section">
        <div class="status-section-header">${title}</div>
        <div class="empty">No jobs.</div>
      </div>
    `;
  }

  const rows = list
    .map((j) => {
      const duration = j.started_at && j.finished_at
        ? formatDuration(j.finished_at - j.started_at)
        : "—";

      return `
        <tr>
          <td>${j.id}</td>
          <td>${jobIcon(j.type)} ${j.type}</td>
          <td><span class="job-status job-${j.status}">${j.status}</span></td>
          <td>${machineBadge(j.assigned_machine)}</td>
          <td>${duration}</td>
          <td>
            <button class="job-view" data-id="${j.id}">View</button>
            ${
              j.status === "running"
                ? `<button class="job-cancel" data-id="${j.id}">Cancel</button>`
                : ""
            }
            ${
              j.status === "failed" || j.status === "cancelled"
                ? `<button class="job-retry" data-id="${j.id}">Retry</button>`
                : ""
            }
          </td>
        </tr>
      `;
    })
    .join("");

  return `
    <div class="status-section">
      <div class="status-section-header">${title}</div>
      <table class="data-table sortable">
        <thead>
          <tr>
            <th data-sort="id">ID</th>
            <th data-sort="type">Type</th>
            <th data-sort="status">Status</th>
            <th data-sort="machine">Machine</th>
            <th data-sort="duration">Duration</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

// ---------------------------------------------------------
// Sorting
// ---------------------------------------------------------
function applySorting() {
  document.querySelectorAll(".sortable th[data-sort]").forEach((th) => {
    th.addEventListener("click", () => {
      const table = th.closest("table");
      const tbody = table.querySelector("tbody");
      const rows = Array.from(tbody.querySelectorAll("tr"));
      const key = th.getAttribute("data-sort");

      const idx = Array.from(th.parentNode.children).indexOf(th);

      rows.sort((a, b) => {
        const A = a.children[idx].innerText;
        const B = b.children[idx].innerText;
        return A.localeCompare(B, undefined, { numeric: true });
      });

      tbody.innerHTML = "";
      rows.forEach((r) => tbody.appendChild(r));
    });
  });
}

// ---------------------------------------------------------
// Load Jobs
// ---------------------------------------------------------
async function loadJobs() {
  const pane = document.getElementById("jobs-content");
  if (!pane) return;

  try {
    const [pending, running, completed, failed] = await Promise.all([
      fetchJSON("/api/jobs/pending"),
      fetchJSON("/api/jobs/running"),
      fetchJSON("/api/jobs/completed"),
      fetchJSON("/api/jobs/failed"),
    ]);

    pane.innerHTML = `
      ${renderJobTable(pending, "Pending")}
      ${renderJobTable(running, "Running")}
      ${renderJobTable(completed, "Completed")}
      ${renderJobTable(failed, "Failed")}
    `;

    applySorting();

    // Wire job detail buttons
    pane.querySelectorAll(".job-view").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        const job = await fetchJSON(`/api/jobs/${id}`);
        renderJobDetails(job);
      });
    });

    // Wire cancel buttons
    pane.querySelectorAll(".job-cancel").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        await cancelJob(id);
        loadJobs();
      });
    });

    // Wire retry buttons
    pane.querySelectorAll(".job-retry").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        await retryJob(id);
        loadJobs();
      });
    });

  } catch (err) {
    console.error("Failed to load jobs:", err);
    pane.innerHTML = `<div class="error">Failed to load jobs.</div>`;
  }
}

// ---------------------------------------------------------
// Public entrypoint
// ---------------------------------------------------------
export function showJobsPane() {
  const pane = document.getElementById("jobs-pane");
  if (!pane) return;

  pane.style.display = "block";

  if (!document.getElementById("job-detail-pane")) {
    const detail = document.createElement("div");
    detail.id = "job-detail-pane";
    detail.style.marginTop = "12px";
    pane.appendChild(detail);
  }

  loadJobs();

  if (!window.__jobsAutoRefresh) {
    window.__jobsAutoRefresh = setInterval(loadJobs, 5000);
  }
}