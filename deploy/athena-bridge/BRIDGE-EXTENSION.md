# Athena Bridge — Chrome extension (web-AI presence + optional context inject)

Reports **structural** presence of web-AI sessions (claude.ai, gemini.google.com,
chatgpt.com) to Athena. It never reads message content, keystrokes, or clipboard —
only domain, conversation title (header heuristics), and window/tab visibility.

## Components

| Part | Role |
|---|---|
| `bridge-extension/` | Chrome MV3 extension (content script + service worker + popup) |
| `browser_receiver.py` | loopback HTTP server `:8008` (systemd `athena-browser-receiver.service`) |
| `data/browser-events.ndjson` | append-only presence events (same conventions as `capture.py`) |

## Install

1. **Receiver** (already provisioned on nativedev):
   `systemctl --user enable --now athena-browser-receiver.service`
   → `http://127.0.0.1:8008/llm-context`.

2. **Extension** (in Chrome):
   - `chrome://extensions` → enable *Developer mode* → *Load unpacked*
   - select `bridge-extension/` from this module.
   - Grant the localhost receiver if prompted; the manifest limits
     `host_permissions` to `http://127.0.0.1:8008/*` and content scripts to the
     three AI sites.

## Behavior

- Content script sends `init`, then heartbeat every 60 s, plus on
  `visibilitychange` and conversation-title (DOM) changes.
- Service worker debounces to ≥15 s intervals before POSTing to the receiver.
- The popup can fetch `/llm-context/block` (live Athena context) and inject it
  into the focused composer (`__ATHENA_BRIDGE__.inject`) — **opt-in**, manual.

## Privacy boundary

Metadata only. No keystrokes, no clipboard, no message text, no full page
content. This matches Athena's rule: *already-flowing structural state only*.
