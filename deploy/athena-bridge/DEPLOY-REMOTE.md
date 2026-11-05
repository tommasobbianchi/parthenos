# Deploying the Athena Bridge to other machines

The receiver stays on **nativedev** (single canonical writer). Each target only
runs the Chrome extension, which talks to the receiver over Tailscale
(`http://100.112.35.102:8008/llm-context`).

## Targets & status

| Target | Type | Status (2026-11-05) | Notes |
|---|---|---|---|
| fujiyama (100.85.88.58) | Linux (GNOME/Wayland) | offline 4h, SSH unreachable | deploy via `deploy-bridge.sh fujiyama` |
| native-beast (100.115.135.14) | Linux (Ubuntu dev) | offline 1d | same |
| thinkpad t14s (100.97.139.3) | Linux | offline 1d | same |
| thinkpad-sls-win (100.66.218.116) | Windows | offline 2h | same script works via tailscale ssh (Windows OpenSSH) |
| pixel-9a (100.120.88.98) | Android | on tailnet, no adb | **Chrome for Android has no extension support** → use Kiwi Browser (see below) |

## Deploy a Linux/Windows target

```bash
~/projects/athena/modules/llm-context/deploy-bridge.sh <host>
# then, on the target: chrome://extensions → Dev mode → Load unpacked →
#   ~/.local/share/athena-bridge-extension
# or launch chrome with it preloaded:
#   chrome-with-athena
```

## Android (pixel9a) — Kiwi Browser

Chrome for Android does not support extensions. Workaround:

1. Install **Kiwi Browser** (Play/APK) — Chromium-based, supports MV3.
2. Copy the `bridge-extension` folder to the phone (e.g. via
   Tailscale + `adb push` when USB debugging is on, or a file-share).
3. In Kiwi: `kiwi://extensions` → Developer mode → Load unpacked → select the
   folder.

Receiver URL is already the Tailscale one; Android needs no `127.0.0.1` (it
must reach `100.112.35.102:8008`).

## Notes

- The receiver listens on `0.0.0.0:8008` (Tailscale + loopback). Keep nativedev
  on the tailnet; expose only over Tailscale.
- When hosts are online, run the deploy script per host; reload the extension if
  it was already loaded (source changed).
