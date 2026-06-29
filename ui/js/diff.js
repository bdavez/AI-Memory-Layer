import { renderJsonToElement } from "./jsonviewer.js";

export function showCanonicalDiff(diffData) {
  const modal = document.getElementById("canonical-diff-modal");
  const pre = document.getElementById("canonical-diff-json");
  const btnClose = document.getElementById("btn-close-canonical-diff");
  const btnCloseFooter = document.getElementById("btn-close-canonical-diff-footer");
  const btnDownload = document.getElementById("btn-download-canonical-diff");

  if (!modal || !pre) return;

  renderJsonToElement(pre, diffData);

  let url = null;
  if (btnDownload) {
    const blob = new Blob([JSON.stringify(diffData, null, 2)], { type: "application/json" });
    url = URL.createObjectURL(blob);
    btnDownload.onclick = () => {
      const a = document.createElement("a");
      a.href = url;
      a.download = "canonical-diff.json";
      a.click();
    };
  }

  const closeFn = () => {
    modal.classList.add("hidden");
    if (btnDownload) btnDownload.onclick = null;
    if (url) URL.revokeObjectURL(url);
  };

  btnClose.onclick = closeFn;
  btnCloseFooter.onclick = closeFn;

  modal.classList.remove("hidden");
}
