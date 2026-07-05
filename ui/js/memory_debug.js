// ui/js/memory_debug.js
// Multi-user Memory Debug Panel
// Operator-grade introspection for events, facts, metadata, summarizer state, and memory dump.

import {
  getJSON,
  postJSON,
} from "./api.js";

// ---------------------------------------------------------
// DOM Helpers
// ---------------------------------------------------------
function $(id) {
  return document.getElementById(id);
}

function setJSON(el, data) {
  el.textContent = JSON.stringify(data, null, 2);
}

function collapseSection(section) {
  section.classList.toggle("open");
}

// ---------------------------------------------------------
// API Endpoints (Memory Debug Extensions)
// ---------------------------------------------------------

async function apiListUsers() {
  const dump = await getJSON("/api/memory/dump");
  return Object.keys(dump.facts || {});
}

async function apiCreateUser(userId) {
  return postJSON("/api/memory/user/create", { user_id: userId });
}

async function apiGetFacts(userId) {
  return getJSON(`/api/memory/facts/${userId}`);
}

async function apiGetEvents(userId) {
  return getJSON(`/api/memory/events?user_id=${userId}`);
}

async function apiGetMeta(userId) {
  return getJSON(`/api/memory/meta?user_id=${userId}`);
}

async function apiGetSettings() {
  return getJSON(`/api/memory/settings`);
}

async function apiSummarize(userId, force = false) {
  return postJSON(`/api/memory/summarize${force ? "?force=true" : ""}`, {
    user_id: userId,
  });
}

async function apiGetLastPrompt(userId) {
  return getJSON(`/api/memory/debug/prompt?user_id=${userId}`);
}

async function apiGetLastOutput(userId) {
  return getJSON(`/api/memory/debug/last_output?user_id=${userId}`);
}

async function apiGetDump() {
  return getJSON(`/api/memory/dump`);
}

async function apiDeleteFact(userId, index) {
  return fetch(`/api/memory/facts/${userId}/${index}`, { method: "DELETE" });
}

async function apiUpdateFact(userId, index, newText) {
  return postJSON(`/api/memory/facts/${userId}/${index}/edit`, {
    fact: newText,
  });
}

// ---------------------------------------------------------
// Rendering: User Selector
// ---------------------------------------------------------
async function loadUserDropdown() {
  const users = await apiListUsers();
  const sel = $("md-user");

  sel.innerHTML = "";
  users.forEach((u) => {
    const opt = document.createElement("option");
    opt.value = u;
    opt.textContent = u;
    sel.appendChild(opt);
  });

  return users[0] || null;
}

// ---------------------------------------------------------
// Rendering: Facts
// ---------------------------------------------------------
async function renderFacts(userId) {
  const container = $("md-facts-list");
  container.innerHTML = "Loading…";

  const data = await apiGetFacts(userId);
  const facts = data.facts || [];

  if (!facts.length) {
    container.innerHTML = "<p>No facts stored.</p>";
    return;
  }

  container.innerHTML = "";

  facts.forEach((f, i) => {
    const row = document.createElement("div");
    row.className = "md-fact";

    const text = document.createElement("input");
    text.className = "md-fact-edit";
    text.value = f.fact;

    const del = document.createElement("button");
    del.className = "md-delete";
    del.textContent = "Delete";

    del.onclick = async () => {
      await apiDeleteFact(userId, i);
      renderFacts(userId);
    };

    text.onchange = async () => {
      await apiUpdateFact(userId, i, text.value.trim());
      renderFacts(userId);
    };

    row.appendChild(text);
    row.appendChild(del);
    container.appendChild(row);
  });
}

// ---------------------------------------------------------
// Rendering: Events
// ---------------------------------------------------------
async function renderEvents(userId) {
  const container = $("md-events-list");
  container.innerHTML = "Loading…";

  const data = await apiGetEvents(userId);
  const events = data.events || [];

  if (!events.length) {
    container.innerHTML = "<p>No events recorded.</p>";
    return;
  }

  const html = events
    .map(
      (e) => `
      <div class="md-fact">
        <div>
          <strong>${e.role}</strong> — ${new Date(e.ts * 1000).toLocaleString()}<br>
          <em>${e.session_id}</em><br>
          ${e.content}
        </div>
      </div>
    `
    )
    .join("");

  container.innerHTML = html;
}

// ---------------------------------------------------------
// Rendering: Metadata
// ---------------------------------------------------------
async function renderMeta(userId) {
  const el = $("md-meta-json");
  el.textContent = "Loading…";

  const meta = await apiGetMeta(userId);
  setJSON(el, meta);
}

// ---------------------------------------------------------
// Rendering: Settings
// ---------------------------------------------------------
async function renderSettings() {
  const el = $("md-settings-json");
  el.textContent = "Loading…";

  const settings = await apiGetSettings();
  setJSON(el, settings);
}

// ---------------------------------------------------------
// Rendering: Memory Dump
// ---------------------------------------------------------
async function renderDump() {
  const el = $("md-dump-json");
  el.textContent = "Loading…";

  const dump = await apiGetDump();
  setJSON(el, dump);
}

// ---------------------------------------------------------
// Summarizer Tools
// ---------------------------------------------------------
async function handleSummarize(userId, force = false) {
  await apiSummarize(userId, force);

  setTimeout(() => {
    renderFacts(userId);
    renderMeta(userId);
  }, 1500);
}

async function showLastPrompt(userId) {
  const out = $("md-summarizer-output");
  out.style.display = "block";
  out.textContent = "Loading…";

  const data = await apiGetLastPrompt(userId);
  setJSON(out, data);
}

async function showLastOutput(userId) {
  const out = $("md-summarizer-output");
  out.style.display = "block";
  out.textContent = "Loading…";

  const data = await apiGetLastOutput(userId);
  setJSON(out, data);
}

// ---------------------------------------------------------
// Section Collapsing
// ---------------------------------------------------------
function wireSectionToggles() {
  document.querySelectorAll(".md-section").forEach((sec) => {
    const header = sec.querySelector(".md-section-header");
    header.addEventListener("click", () => collapseSection(sec));
  });
}

// ---------------------------------------------------------
// Main Initialization
// ---------------------------------------------------------
async function init() {
  wireSectionToggles();

  const firstUser = await loadUserDropdown();
  const sel = $("md-user");

// define loadAll FIRST
async function loadAll() {
  const userId = sel.value;
  renderFacts(userId);
  renderEvents(userId);
  renderMeta(userId);
  renderSettings();
  renderDump();
}



  // NEW USER CREATION
  $("md-create-user").onclick = async () => {
    const name = prompt("Enter new user ID:");
    if (!name) return;

    await apiCreateUser(name);
    await loadUserDropdown();
    sel.value = name;
    loadAll();
  };

  if (!firstUser) {
    alert("No users found in memory.json");
    return;
  }

  sel.value = firstUser;

  window.loadAll = async () => {
    const userId = sel.value;
    renderFacts(userId);
    renderEvents(userId);
    renderMeta(userId);
    renderSettings();
    renderDump();
  };

  sel.onchange = loadAll;

  $("md-summarize").onclick = () => handleSummarize(sel.value, false);
  $("md-summarize-force").onclick = () => handleSummarize(sel.value, true);
  $("md-show-prompt").onclick = () => showLastPrompt(sel.value);
  $("md-show-output").onclick = () => showLastOutput(sel.value);
  $("md-load-dump").onclick = renderDump;

  $("md-export-dump").onclick = async () => {
    const dump = await apiGetDump();
    const blob = new Blob([JSON.stringify(dump, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "memory.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  loadAll();
}

window.addEventListener("DOMContentLoaded", init);
