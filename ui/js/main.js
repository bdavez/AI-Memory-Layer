import { setStatusUnknown, refreshStatus } from "./status.js";
import { wireButtons } from "./buttons.js";

document.addEventListener("DOMContentLoaded", async () => {
  setStatusUnknown();
  wireButtons();
  try {
    await refreshStatus();
  } catch (err) {
    console.error("Initial status refresh failed:", err);
  }
});

// Refresh every 5 seconds
setInterval(refreshStatus, 5000);
