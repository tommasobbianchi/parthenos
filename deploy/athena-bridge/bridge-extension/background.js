// Athena Bridge — background service worker.
// Debounces content-script messages and forwards presence to the Athena receiver.
// Receiver endpoints (tried in order): nativedev via Tailscale, then localhost.

const RECEIVERS = [
  "http://100.112.35.102:8008/llm-context",
  "http://127.0.0.1:8008/llm-context",
];
let activeReceiver = "http://100.112.35.102:8008/llm-context"; // preferred
let lastSend = 0;
const MIN_INTERVAL_MS = 15_000;

function relay(payload) {
  const now = Date.now();
  if (now - lastSend < MIN_INTERVAL_MS) {
    lastSend = now;
    return;
  }
  lastSend = now;
  fetch(activeReceiver, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then(() => {
    if (activeReceiver !== RECEIVERS[0]) activeReceiver = RECEIVERS[0];
  }).catch(() => {
    // fall back to loopback (same-machine receiver)
    activeReceiver = RECEIVERS[1];
  });
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "athena-presence") {
    relay(msg.payload);
    sendResponse({ ok: true });
  }
  return false;
});
