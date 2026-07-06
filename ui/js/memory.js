// ui/js/memory.js

export async function loadMemoryFacts(userId = "b") {
  const resp = await fetch(`/api/memory/facts?user_id=${userId}`);
  const data = await resp.json();
  return data.facts || [];
}

export async function refreshMemoryUI() {
  const container = document.getElementById("memory-facts-container");
  container.innerHTML = "<p>Loading...</p>";

  const facts = await loadMemoryFacts("b");

  if (!facts.length) {
    container.innerHTML = "<p>No stored memory facts.</p>";
    return;
  }

  const html = facts
    .map(
      (f, i) => `
      <div class="memory-fact">
        <span>${f.fact}</span>
        <button class="delete-fact" data-index="${i}">Delete</button>
      </div>
    `
    )
    .join("");

  container.innerHTML = html;

  // Wire delete buttons
  document.querySelectorAll(".delete-fact").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const index = btn.dataset.index;
      await fetch(`/api/memory/facts/b/${index}`, { method: "DELETE" });
      refreshMemoryUI();
    });
  });
}

export async function summarizeMemoryNow() {
  await fetch("/api/memory/summarize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: "b" }),
  });

  // Give backend a moment to ingest
  setTimeout(refreshMemoryUI, 1500);
}

export function wireMemoryButtons() {
  document
    .getElementById("memory-refresh")
    .addEventListener("click", refreshMemoryUI);

  document
    .getElementById("memory-summarize")
    .addEventListener("click", summarizeMemoryNow);

  document
    .getElementById("memory-clear")
    .addEventListener("click", async () => {
      // Clear all facts for user b
      const facts = await loadMemoryFacts("b");
      for (let i = 0; i < facts.length; i++) {
        await fetch(`/api/memory/facts/b/${i}`, { method: "DELETE" });
      }
      refreshMemoryUI();
    });
}