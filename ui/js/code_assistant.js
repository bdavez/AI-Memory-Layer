// ui/js/code_assistant.js
// Multi-user Code Assistant with model selection, diff mode, and neon UI.

import { getJSON, postJSON } from "./api.js";
import { apiGetModelsLive } from "./api.js";

// ---------------------------------------------------------
// DOM Helpers
// ---------------------------------------------------------
const $ = (id) => document.getElementById(id);

function setStatus(msg) {
  $("ca-status").textContent = msg;
}

function setOutput(text) {
  $("ca-output").textContent = text;
}

// ---------------------------------------------------------
// Load Users (shared with Memory Debug Panel)
// ---------------------------------------------------------
async function loadUsers() {
  const dump = await getJSON("/api/memory/dump");
  const users = Object.keys(dump.facts || {});
  const sel = $("ca-user");

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
// Run Code Assistant
// ---------------------------------------------------------
async function runAssistant() {
  console.log("runAssistant() called");
  const userId = $("ca-user").value;
  const model = $("ca-model").value;
  const mode = $("ca-mode").value;
  const prompt = $("ca-prompt").value.trim();

  console.log("model =", model);
  console.log("prompt =", prompt);



  if (!prompt) {
    setStatus("Prompt is empty.");
    return;
  }

  setStatus("Running…");
  setOutput("");

  const params = new URLSearchParams({
    model,
    prompt,
    user_id: userId,
    mode
  });

  const url = `/api/jobs/assistant/run?model=${model}&prompt=${encodeURIComponent(prompt)}`;
  console.log("EventSource URL =", url);

  const evtSource = new EventSource(`/api/jobs/assistant/run?model=${model}&prompt=${encodeURIComponent(prompt)}`);

  evtSource.onmessage = (e) => {
    console.log("SSE message:", e.data);
    $("ca-output").textContent += e.data + "\n";
  };

  evtSource.addEventListener("done", () => {
     console.log("SSE done event");
    setStatus("Done.");
    evtSource.close();
  });

  evtSource.onerror = () => {
     console.error("SSE error:", err);
    setStatus("Error.");
    evtSource.close();
  };
}


// ---------------------------------------------------------
// Clear Output
// ---------------------------------------------------------
function clearOutput() {
  $("ca-output").textContent = "";
  $("ca-prompt").value = "";
  setStatus("Cleared.");
}
// ---------------------------------------------------------
// Refresh Model Dropdown
// ---------------------------------------------------------
async function refreshModelDropdown() {
  const data = await apiGetModelsLive();

  // For now, pick uno
  const models = data["uno"] || [];

  const select = document.getElementById("ca-model");
  select.innerHTML = "";

  models.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m;
    opt.textContent = m;
    select.appendChild(opt);
  });

  document.getElementById("ca-status").textContent =
    `Loaded ${models.length} model(s) from uno.`;
}

document.getElementById("ca-refresh-models")
  .addEventListener("click", refreshModelDropdown);

window.addEventListener("DOMContentLoaded", refreshModelDropdown);


// ---------------------------------------------------------
// Init
// ---------------------------------------------------------
async function init() {
  setStatus("Loading…");

  // Load users
  const firstUser = await loadUsers();
  if (firstUser) $("ca-user").value = firstUser;

  // Wire buttons
  $("ca-run").onclick = runAssistant;
  $("ca-clear").onclick = clearOutput;

  setStatus("Ready.");
}

window.addEventListener("DOMContentLoaded", init);

