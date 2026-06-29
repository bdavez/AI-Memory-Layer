// ui/js/memory.js
// Memory Pane logic for durable facts + settings + manual summarize

import { apiGetFacts } from "./api.js";

export async function renderMemoryPane() {
  const container = document.getElementById("memory-pane");
  if (!container) return;

  const userId = "b";

  try {
    // Load settings
    const settingsResp = await fetch("/api/memory/settings");
    const settings = await settingsResp.json();

    // Load facts
    const facts = await apiGetFacts(userId);

    container.innerHTML = `
      <div class="status-section">
        <div class="status-section-header">Memory</div>

        <div class="memory-toggle">
          <label>
            <input type="checkbox" id="memory-auto-toggle" ${
              settings.auto_summarize ? "checked" : ""
            }>
            Automatic Summarization
          </label>
        </div>

        <div class="memory-subheader">Durable Facts</div>
        <div class="memory-facts">
          ${
            facts.facts.length === 0
              ? `<div class="empty">No stored facts yet.</div>`
              : facts.facts
                  .map(
                    (f, i) => `
              <div class="memory-fact">
                <div class="memory-fact-text">${f.fact}</div>
                <button class="memory-delete" data-index="${i}">delete</button>
              </div>
            `
                  )
                  .join("")
          }
        </div>

        <div class="memory-actions">
          <button id="memory-summarize" class="op-button">Summarize to Facts</button>
        </div>
      </div>
    `;

    // Wire auto toggle
    const autoToggle = document.getElementById("memory-auto-toggle");
    if (autoToggle) {
      autoToggle.addEventListener("change", async (e) => {
        await fetch("/api/memory/settings", {
          method: "POST",
          body: JSON.stringify({ auto_summarize: e.target.checked }),
          headers: { "Content-Type": "application/json" },
        });
      });
    }

    // Wire delete buttons
    container.querySelectorAll(".memory-delete").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const idx = btn.getAttribute("data-index");
        await fetch(`/api/memory/facts/${idx}`, {
          method: "DELETE",
        });
        renderMemoryPane();
      });
    });

    // Wire manual summarize button
    const summarizeBtn = document.getElementById("memory-summarize");
    if (summarizeBtn) {
      summarizeBtn.addEventListener("click", async () => {
        const resp = await fetch("/api/memory/summarize", {
          method: "POST",
          body: JSON.stringify({ user_id: userId }),
          headers: { "Content-Type": "application/json" },
        });

        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          alert(`Summarize failed: ${err.error || resp.statusText}`);
          return;
        }

        const data = await resp.json();
        alert(`Summarizer job started: ${data.job_id}`);
      });
    }
  } catch (err) {
    console.error("Failed to render memory pane:", err);
    container.innerHTML = `<div class="error">Failed to load memory.</div>`;
  }
}
