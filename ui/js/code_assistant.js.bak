// ui/js/code_assistant.js
// Code Assistant UI logic: wires prompt -> /api/jobs -> SSE stream

import { createJob, streamJob, apiAddEvent, apiGetFacts } from "./api.js";

// UI elements
const refreshBtn = document.getElementById("ca-refresh-models");
const promptEl = document.getElementById("ca-prompt");
const modelEl = document.getElementById("ca-model");
const modeEl = document.getElementById("ca-mode");   // NEW for Phase 2
const runBtn = document.getElementById("ca-run");
const clearBtn = document.getElementById("ca-clear");
const outputEl = document.getElementById("ca-output");
const statusEl = document.getElementById("ca-status");

let currentStream = null;

// ---------------------------------------------------------
// Helpers
// ---------------------------------------------------------

function setStatus(text) {
  statusEl.textContent = text;
}

function appendOutput(text) {
  outputEl.textContent += text;
  outputEl.scrollTop = outputEl.scrollHeight;
}

function resetOutput() {
  outputEl.textContent = "";
}

// ---------------------------------------------------------
// Model Dropdown Loader
// ---------------------------------------------------------

async function loadModelDropdown() {
  try {
    const resp = await fetch("/api/models");
    const data = await resp.json();

    modelEl.innerHTML = "";

    for (const model of data.models) {
      const opt = document.createElement("option");
      opt.value = model;
      opt.textContent = model;
      modelEl.appendChild(opt);
    }

    console.log("Model dropdown updated:", data.models);
  } catch (e) {
    console.error("Failed to load model dropdown", e);
    setStatus("Failed to load model list.");
  }
}

// ---------------------------------------------------------
// System Prompt Builder (Phase 2)
// ---------------------------------------------------------

function buildSystemPrompt({ userId, facts, mode, userPrompt }) {
  const memoryContext = facts.map((f) => `- ${f.fact}`).join("\n");

  if (mode === "diff") {
    return `
You are a code diff assistant. You generate minimal, clean patches.
Durable facts:
${memoryContext || "(none yet)"}

User diff request:
${userPrompt}
`;
  }

  // Standard mode
  return `
You are the code assistant for user ${userId}.

Durable facts:
${memoryContext || "(none yet)"}

User prompt:
${userPrompt}
`;
}

// ---------------------------------------------------------
// Refresh Models Button
// ---------------------------------------------------------

refreshBtn.addEventListener("click", async () => {
  setStatus("Refreshing model list...");

  try {
    const resp = await fetch("/api/models/refresh");
    const data = await resp.json();
    console.log("Model refresh result:", data);

    await loadModelDropdown();
    setStatus("Model list updated.");
  } catch (e) {
    console.error("Model refresh failed", e);
    setStatus("Failed to refresh model list.");
  }
});

// ---------------------------------------------------------
// RUN Button
// ---------------------------------------------------------

runBtn.addEventListener("click", async () => {
  const prompt = promptEl.value.trim();
  const model = modelEl.value;
  const mode = modeEl.value || "standard";

  if (!prompt) {
    setStatus("Please enter a prompt first.");
    return;
  }

  // Log user prompt into memory
  await apiAddEvent({
    user_id: "b",
    session_id: "code-assistant",
    role: "user",
    content: prompt,
  });

  if (currentStream) {
    currentStream.close();
    currentStream = null;
  }

  resetOutput();
  setStatus(`Creating job on control plane with model ${model}...`);

  try {
    const userId = "b";
    const facts = await apiGetFacts(userId);

    const enrichedPrompt = buildSystemPrompt({
      userId,
      facts: facts.facts,
      mode,
      userPrompt: prompt,
    });

    const job = await createJob("code_assist", model, {
      prompt: enrichedPrompt,
    });

    setStatus(`Job ${job.id} running on cluster. Streaming output...`);

    currentStream = streamJob(
      job.id,
      (token) => {
        const chunk = token?.message?.content ?? "";
        if (chunk) {
          appendOutput(chunk);

          apiAddEvent({
            user_id: "b",
            session_id: "code-assistant",
            role: "assistant",
            content: chunk,
          });
        }
      },
      () => {
        setStatus(`Job completed.`);
        currentStream = null;
      },
      (err) => {
        console.error("Stream error", err);
        setStatus("Stream error. Check worker and control plane logs.");
        currentStream = null;
      }
    );
  } catch (e) {
    console.error(e);
    setStatus(`Error creating job: ${e.message}`);
  }
});

// ---------------------------------------------------------
// CLEAR Button
// ---------------------------------------------------------

clearBtn.addEventListener("click", () => {
  promptEl.value = "";
  resetOutput();
  setStatus("Cleared. Ready.");

  if (currentStream) {
    currentStream.close();
    currentStream = null;
  }
});

// ---------------------------------------------------------
// On Page Load
// ---------------------------------------------------------

window.addEventListener("DOMContentLoaded", async () => {
  await loadModelDropdown();
});
