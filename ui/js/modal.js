import { renderJsonToElement } from "./jsonviewer.js";

export function openJsonModal(title, data, filename = null) {
  const container = document.getElementById("modal-container").classList.add("hidden");
  const titleEl = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");
  const close = document.getElementById("modal-close");
  const closeFooter = document.getElementById("modal-close-footer");
  const download = document.getElementById("modal-download");

  if (!container || !titleEl || !body) return;

  titleEl.textContent = title;
  renderJsonToElement(body, data);

  let url = null;
  if (filename) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    url = URL.createObjectURL(blob);
    download.onclick = () => {
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
    };
  } else {
    download.onclick = null;
  }

  const closeFn = () => {
    container.classList.add("hidden");
    if (url) URL.revokeObjectURL(url);
    download.onclick = null;
  };

  close.onclick = closeFn;
  closeFooter.onclick = closeFn;

  container.classList.remove("hidden");
}
