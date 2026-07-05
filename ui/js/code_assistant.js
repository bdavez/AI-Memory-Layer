// ui/js/code_assistant.js
// Multi-user Code Assistant with model selection, diff mode, and neon UI.

import { getJSON, postJSON } from "./api.js";

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
// Load Models
// ---------------------------------------------------------
async function loadModels() {
  const res = await getJSON("/api/models");

  // Accept both { models: [...] } and [...]
  const models = Array.isArray(res) ? res : res.models;

  if (!Array.isArray(models)) {
    console.error("Invalid /api/models response:", res);
    setStatus("Model list unavailable.");
    return;
  }

  const sel = $("ca-model");
  sel.innerHTML = "";

  models.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m;
    opt.textContent = m;
    sel.appendChild(opt);
  });
}
// ---------------------------------------------------------
// Run Code Assistant
// ---------------------------------------------------------
async function runAssistant() {
  const userId = $("ca-user").value;
  const model = $("ca-model").value;
  const mode = $("ca-mode").value;
  const prompt = $("ca-prompt").value.trim();

  if (!prompt) {
    setStatus("Prompt is empty.");
    return;
  }

  setStatus("Running…");

  try {
    const result = await postJSON("/api/assistant/run", {
      user_id: userId,
      model,
      mode,
      prompt,
    });

    setOutput(result.output || "(no output)");
    setStatus("Done.");
  } catch (err) {
    console.error("Assistant error:", err);
    setOutput("Error running assistant.");
    setStatus("Error.");
  }
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
// Init
// ---------------------------------------------------------
async function init() {
  setStatus("Loading…");

  // Load users
  const firstUser = await loadUsers();
  if (firstUser) $("ca-user").value = firstUser;

  // Load models
  await loadModels();

  // Wire buttons
  $("ca-run").onclick = runAssistant;
  $("ca-clear").onclick = clearOutput;
  $("ca-refresh-models").onclick = loadModels;

  setStatus("Ready.");
}

window.addEventListener("DOMContentLoaded", init);
