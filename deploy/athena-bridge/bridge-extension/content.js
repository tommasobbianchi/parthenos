// Athena Bridge — content script.
// Structural metadata only: domain, conversation title (header heuristics), and
// window/tab visibility. Never reads message content, keystrokes, or clipboard.

(() => {
  const SITES = {
    "claude.ai": { titleSel: "h1", fallback: "Claude" },
    "gemini.google.com": { titleSel: "div[aria-label*='Conversation'], h1", fallback: "Gemini" },
    "chatgpt.com": { titleSel: "h1[data-testid='conversation-title'], h1", fallback: "ChatGPT" },
  };

  const host = location.hostname.replace(/^www\./, "");
  const site = SITES[host] || null;
  if (!site) return;

  function getTitle() {
    try {
      const el = document.querySelector(site.titleSel);
      if (el && el.textContent.trim()) return el.textContent.trim().slice(0, 120);
    } catch (_) { /* ignore */ }
    return null;
  }

  function send(reason) {
    const payload = {
      client: host.startsWith("gemini") ? "gemini" : (host.startsWith("chatgpt") ? "chatgpt" : "claude-web"),
      domain: host,
      conv_title: getTitle(),
      window_active: document.visibilityState === "visible",
      tab_count: null,
      reason,
    };
    try {
      fetch("http://127.0.0.1:8008/llm-context", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }).catch(() => { /* offline — retry on next signal */ });
    } catch (_) { /* ignore */ }
  }

  // heartbeat + visibility/title changes
  send("init");
  const iv = setInterval(() => send("heartbeat"), 60_000);
  document.addEventListener("visibilitychange", () => send("visibility"));

  // title changes (conversation switches)
  new MutationObserver(() => send("title")).observe(document.body, {
    subtree: true, childList: true, characterData: false,
  });
  // stop when page unloads
  window.addEventListener("beforeunload", () => clearInterval(iv));

  // Expose an injector for the popup (opt-in context block).
  window.__ATHENA_BRIDGE__ = {
    inject(text) {
      const candidates = [
        'textarea[contenteditable="true"]',
        "textarea",
        'div[contenteditable="true"]',
        '[role="textbox"]',
      ];
      for (const sel of candidates) {
        const el = document.querySelector(sel);
        if (!el) continue;
        if (el.tagName === "TEXTAREA") {
          el.value = el.value ? el.value + "\n\n" + text : text;
          el.dispatchEvent(new Event("input", { bubbles: true }));
          el.focus();
          return true;
        }
        // contenteditable/role textbox
        el.focus();
        document.execCommand("insertText", false, (el.innerText ? "\n\n" : "") + text);
        return true;
      }
      return false;
    },
  };
})();
