import { wireButtons } from "./buttons.js";
import { renderStatus } from "./status.js";
import { apiGetModelsLive } from "./api.js";

async function loadModels() {
  const data = await apiGetModelsLive();

  // pick uno for now
  const models = data["uno"] || [];

  const container = document.getElementById("model-list");
  container.innerHTML = models.map(m => `<div class="model-item">${m}</div>`).join("");
}

window.addEventListener("DOMContentLoaded", loadModels);


document.addEventListener("DOMContentLoaded", async () => {
  wireButtons();
  try {
    await renderStatus();
  } catch (err) {
    console.error("Initial status refresh failed:", err);
  }
});

// Refresh every 5 seconds
setInterval(renderStatus, 5000);
