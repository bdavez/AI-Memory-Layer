export function renderJsonToElement(el, data) {
  if (!el) return;
  el.textContent = "";
  const pre = document.createElement("pre");
  pre.className = "json-viewer";
  pre.textContent = JSON.stringify(data, null, 2);
  el.appendChild(pre);
}