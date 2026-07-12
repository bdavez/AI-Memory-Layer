// ui/js/code_assistant.js
// Multi-user Code Assistant with model selection, diff mode, and neon UI.

import { getJSON, postJSON } from "./api.js";
import { apiGetModelsLive } from "./api.js";

// ---------------------------------------------------------
// Terminal Initialization
// ---------------------------------------------------------
const term = new Terminal({
    convertEol: true,
    cursorBlink: true,
    fontSize: 14,
    theme: {
        background: "#1e1e1e",
        foreground: "#ffffff",
    },
});

// Attach terminal to the HTML container
term.open(document.getElementById("terminal"));

// ---------------------------------------------------------
// DOM Helpers
// ---------------------------------------------------------
const $ = (id) => document.getElementById(id);

const caOutput = $("ca-output");
const outputModeSel = $("output-mode");
const autoClearSel = $("auto-clear");
const preserveTerminalSel = $("preserve-terminal");
const copyBtn = $("copy-output");
const downloadBtn = $("download-output");

function setStatus(msg) {
  $("ca-status").textContent = msg;
}

function setOutput(text) {
  caOutput.textContent = text;
}

// ---------------------------------------------------------
// Refresh ANSI Inspector
// ---------------------------------------------------------
async function refreshAnsiInspector() {
  const res = await fetch("/ansi-log");
  const data = await res.json();

  const out = $("ansi-inspector-output");
  if (!out) return;

  out.innerHTML = "";

  for (const line of data.log) {
    const safe = line.replace(/\x1b\[([0-9;]+)m/g, (match) => {return `<span style="color:#7df9ff;">${match}</span>`;}).replace(/\x1b\[[0-9;?]*[A-Za-z]/g, (match) => {return `<span style="color:#f0f;">${match}</span>`;});

    out.innerHTML += safe + "<br>";
  }
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
//   console.log("runAssistant() called");

  const userId = $("ca-user").value;
  const model = $("ca-model").value;
  const assistantMode = $("ca-mode").value;
  const prompt = $("ca-prompt").value.trim();

//   console.log("model =", model);
//   console.log("prompt =", prompt);

  if (!prompt) {
    setStatus("Prompt is empty.");
    return;
  }

  setStatus("Running…");

  // Auto-clear behavior
  if (autoClearSel.value === "on" && preserveTerminalSel.value === "off") {
    caOutput.textContent = "";
    term.clear();
  } else {
    caOutput.textContent = "";
    // terminal keeps running log
  }

  // Clear instruction box after sending
  $("ca-prompt").value = "";

  const params = new URLSearchParams({
    model,
    prompt,
    user_id: userId,
    mode: assistantMode,
  });

  const url = `/api/jobs/assistant/run?model=${model}&prompt=${encodeURIComponent(prompt)}`;
//   console.log("EventSource URL =", url);

  const evtSource = new EventSource(url);

  evtSource.onmessage = (e) => {
    const chunk = e.data + "\n";
    const outputMode = outputModeSel.value;

    // console.log("SSE message:", chunk);

    if (outputMode === "terminal") {
      term.write(chunk); // RAW ANSI
    } else {
      caOutput.textContent += chunk; // stripped text
      caOutput.scrollTop = caOutput.scrollHeight;
    }
  };

  evtSource.addEventListener("done", () => {
    // console.log("SSE done event");
    setStatus("Done.");
    evtSource.close();
  });

  evtSource.onerror = (e) => {
    // console.error("SSE error:", e);
    setStatus("Error.");
    evtSource.close();
  };
}

// ---------------------------------------------------------
// Clear Output
// ---------------------------------------------------------
function clearOutput() {
  caOutput.textContent = "";
  term.clear();
  $("ca-prompt").value = "";
  setStatus("Cleared.");
}

// ---------------------------------------------------------
// Copy / Download Output
// ---------------------------------------------------------
copyBtn.onclick = () => {
  const mode = outputModeSel.value;
  let text = "";

  if (mode === "chat") {
    text = caOutput.textContent;
  } else {
    for (let i = 0; i < term.buffer.active.length; i++) {
      const line = term.buffer.active.getLine(i);
      if (line) text += line.translateToString(true) + "\n";
    }
  }

  navigator.clipboard.writeText(text);
  setStatus("Copied output.");
};

downloadBtn.onclick = () => {
  const mode = outputModeSel.value;
  let text = "";

  if (mode === "chat") {
    text = caOutput.textContent;
  } else {
    for (let i = 0; i < term.buffer.active.length; i++) {
      const line = term.buffer.active.getLine(i);
      if (line) text += line.translateToString(true) + "\n";
    }
  }

  const blob = new Blob([text], { type: "text/plain" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = "assistant_output.txt";
  a.click();

  URL.revokeObjectURL(url);
  setStatus("Downloaded chat log.");
};

// ---------------------------------------------------------
// Refresh Model Dropdown
// ---------------------------------------------------------
async function refreshModelDropdown() {
  const data = await apiGetModelsLive();

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

  // ANSI inspector refresh
  setInterval(refreshAnsiInspector, 2000);

  // Output mode toggle
  outputModeSel.addEventListener("change", () => {
    const mode = outputModeSel.value;

    if (mode === "chat") {
      caOutput.style.display = "block";
      $("terminal").style.display = "none";

      $("preserve-terminal-wrapper").style.display = "none";
      $("auto-clear-wrapper").style.display = "none";
    } else {
      caOutput.style.display = "none";
      $("terminal").style.display = "block";

      $("preserve-terminal-wrapper").style.display = "block";
      $("auto-clear-wrapper").style.display = "block";
    }
  });

  // Wire buttons
  $("ca-run").onclick = runAssistant;
  $("ca-clear").onclick = clearOutput;

  $("reset-all").onclick = () => {
    caOutput.textContent = "";
    term.clear();
    $("ca-prompt").value = "";
    setStatus("All cleared.");
  };

  $("clear-terminal").onclick = () => {
    term.clear();
    setStatus("Terminal cleared.");
  };

  $("/replay-ansi").onclick = async () => {
    const res = await fetch("/ansi-log");
    const data = await res.json();

    term.clear();

    for (const line of data.log) {
      term.write(line);
    }

    setStatus("Replayed ANSI log.");
  };

  $("reset-ansi-log").onclick = async () => {
    await fetch("/ansi-log/reset", { method: "POST" });
    setStatus("ANSI log reset.");
    refreshAnsiInspector();
  };

  setStatus("Ready.");
}

window.addEventListener("DOMContentLoaded", init);
