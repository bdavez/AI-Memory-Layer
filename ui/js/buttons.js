// ui/js/buttons.js

import {
  apiRunCompile,
  apiGetCanonical,
  apiGetVmInventory,
  apiGetStorageMap,
  apiGetCompileHistory,
  apiGetDriftDiff
} from "./api.js";

import { openJsonModal } from "./modal.js";
import { showCanonicalDiff } from "./diff.js";

export function wireButtons() {
  const buttons = document.querySelectorAll(".op-button");
  buttons.forEach(btn => {
    const action = btn.getAttribute("data-action");
    btn.addEventListener("click", () => handleOperatorAction(action));
  });

  document.getElementById("btn-refresh-canonical")
    ?.addEventListener("click", handleRefreshCanonical);

  document.getElementById("btn-download-canonical")
    ?.addEventListener("click", handleDownloadCanonical);

  document.getElementById("btn-compare-canonical-live")
    ?.addEventListener("click", handleCompareCanonicalLive);
}

async function handleOperatorAction(action) {
  try {
    switch (action) {

      case "view-jobs": {
        const { showJobsPane } = await import("./jobs.js");
        showJobsPane();
        break;
      }

      case "view-memory": {
        const { renderMemoryPane } = await import("./memory.js");
        renderMemoryPane();
        break;
      }

      case "open-memory-debug": {
        // NEW: Open standalone Memory Debug Panel
        window.open("memory-debug.html", "_blank");
        break;
      }

      case "run-compile":
        await apiRunCompile();
        await refreshStatus();
        break;

      case "view-canonical": {
        const data = await apiGetCanonical();
        openJsonModal("Canonical State", data, "canonical.json");
        break;
      }

      case "view-diff": {
        const diff = await apiGetDriftDiff();
        showCanonicalDiff(diff);
        break;
      }

      case "view-vm-inventory": {
        const inv = await apiGetVmInventory();
        openJsonModal("VM Inventory", inv, "vm-inventory.json");
        break;
      }

      case "view-storage-map": {
        const sm = await apiGetStorageMap();
        openJsonModal("Storage Map", sm, "storage-map.json");
        break;
      }

      case "view-compile-history": {
        const hist = await apiGetCompileHistory();
        openJsonModal("Compile History", hist, "compile-history.json");
        break;
      }

      case "open-code-assistant": {
        window.open("code-assistant.html", "_blank");
        break;
      }

      default:
        console.warn("Unhandled operator action:", action);
    }
  } catch (err) {
    console.error("Operator action failed:", action, err);
  }
}

async function handleRefreshCanonical() {
  try {
    const data = await apiGetCanonical();
    const ts = data?.last_updated ?? "n/a";
    const el = document.getElementById("canonical-last-updated");
    if (el) el.textContent = `Canonical Last Updated: ${ts}`;
  } catch (err) {
    console.error("Failed to refresh canonical state:", err);
  }
}

async function handleDownloadCanonical() {
  try {
    const data = await apiGetCanonical();
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json"
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "canonical-state.json";
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    console.error("Failed to download canonical state:", err);
  }
}

async function handleCompareCanonicalLive() {
  try {
    const diff = await apiGetDriftDiff();
    showCanonicalDiff(diff);
  } catch (err) {
    console.error("Failed to compare canonical vs live",err);
  }
}
