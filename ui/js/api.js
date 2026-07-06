// ui/js/api.js
// Centralized API wrapper for Control Plane + Code Assistant + Memory Debug Panel

// ------------------------------
// Generic Helpers
// ------------------------------
export async function getJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`GET ${url} failed: ${resp.status}`);
  }
  return await resp.json();
}

export async function postJSON(url, data) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    throw new Error(`POST ${url} failed: ${resp.status}`);
  }
  return await resp.json();
}

export async function apiGetModelsLive() {
  const r = await fetch("/api/models/live");
  return await r.json();
}

export async function apiMemoryCreateUser(userId) {
  return postJSON("/api/memory/user/create", { user_id: userId });
}
// ------------------------------
// JOBS
// ------------------------------
export async function createJob(type, model, input) {
  const payload = { type, model, input };
  const resp = await postJSON("/api/jobs", payload);
  return { id: resp.id || resp.job_id };
}

export function streamJob(jobId, onToken, onDone, onError) {
  const stream = new EventSource(`/api/jobs/${jobId}/stream`);

  stream.addEventListener("token", (e) => {
    try {
      const data = JSON.parse(e.data);
      onToken(data);
    } catch (err) {
      console.warn("Stream parse error", err);
    }
  });

  stream.addEventListener("done", () => {
    stream.close();
    onDone();
  });

  stream.onerror = (err) => {
    stream.close();
    onError(err);
  };

  return stream;
}

export async function apiGetJob(jobId) {
  return getJSON(`/api/jobs/${jobId}`);
}

// ------------------------------
// MEMORY (Standard)
// ------------------------------
export async function apiAddEvent(evt) {
  return postJSON("/api/memory/events", evt);
}

export async function apiGetFacts(userId) {
  const data = await getJSON(`/api/memory/facts/${userId}`);
  return {
    user_id: data.user_id || userId,
    facts: Array.isArray(data.facts) ? data.facts : [],
  };
}

export async function apiSummarizeFacts(userId) {
  return postJSON("/api/memory/summarize", { user_id: userId });
}

// ------------------------------
// MEMORY DEBUG PANEL (New)
// ------------------------------
export async function apiMemoryListUsers() {
  const dump = await getJSON("/api/memory/dump");
  return Object.keys(dump.facts || {});
}

export async function apiMemoryGetEvents(userId) {
  return getJSON(`/api/memory/events?user_id=${userId}`);
}

export async function apiMemoryGetMeta(userId) {
  return getJSON(`/api/memory/meta?user_id=${userId}`);
}

export async function apiMemoryGetSettings() {
  return getJSON("/api/memory/settings");
}

export async function apiMemorySummarize(userId, force = false) {
  const url = force
    ? `/api/memory/summarize?force=true`
    : `/api/memory/summarize`;
  return postJSON(url, { user_id: userId });
}

export async function apiMemoryGetLastPrompt(userId) {
  return getJSON(`/api/memory/debug/prompt?user_id=${userId}`);
}

export async function apiMemoryGetLastOutput(userId) {
  return getJSON(`/api/memory/debug/last_output?user_id=${userId}`);
}

export async function apiMemoryDump() {
  return getJSON("/api/memory/dump");
}

export async function apiMemoryDeleteFact(userId, index) {
  return fetch(`/api/memory/facts/${userId}/${index}`, { method: "DELETE" });
}

export async function apiMemoryEditFact(userId, index, newText) {
  return postJSON(`/api/memory/facts/${userId}/${index}/edit`, {
    fact: newText,
  });
}

// ------------------------------
// MODELS
// ------------------------------
export async function apiListModels() {
  return getJSON("/api/models");
}

export async function apiRefreshModels() {
  return getJSON("/api/models/refresh");
}

// ------------------------------
// CANONICAL STATE
// ------------------------------
export async function apiGetCanonical() {
  return getJSON("/canonical");
}

export async function apiGetDriftDiff() {
  return getJSON("/canonical/diff");
}

// ------------------------------
// VM INVENTORY
// ------------------------------
export async function apiGetVmInventory() {
  return getJSON("/api/vm/inventory");
}

// ------------------------------
// STORAGE MAP
// ------------------------------
export async function apiGetStorageMap() {
  return getJSON("/api/storage/map");
}

// ------------------------------
// COMPILER
// ------------------------------
export async function apiRunCompile() {
  return postJSON("/api/compiler/run", {});
}

export async function apiGetCompileHistory() {
  return getJSON("/api/compiler/history");
}

// ------------------------------
// STATUS
// ------------------------------
export async function apiGetStatus() {
  return getJSON("/api/status");
}
