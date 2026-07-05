import { wireButtons } from "./buttons.js";
import { renderStatus } from "./status.js";

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
