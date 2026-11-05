// Athena Bridge — popup.

document.getElementById("autocontext").addEventListener("change", async (e) => {
  await chrome.storage.local.set({ autocontext: e.target.checked });
});

document.getElementById("inject").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) return;
  // fetch the live Athena context block; then inject into the page's composer
  try {
    const resp = await fetch("http://100.112.35.102:8008/llm-context/block")
      .catch(() => fetch("http://127.0.0.1:8008/llm-context/block"));
    if (!resp.ok) return;
    const { block } = await resp.json();
    await chrome.tabs.sendMessage(tab.id, { type: "athena-inject", text: block });
  } catch (_) { /* receiver down */ }
});

chrome.storage.local.get("autocontext", ({ autocontext }) => {
  document.getElementById("autocontext").checked = !!autocontext;
});
