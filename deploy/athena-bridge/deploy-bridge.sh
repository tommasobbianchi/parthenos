#!/usr/bin/env bash
# Deploy the Athena Bridge extension to a target host over Tailscale ssh.
#
# Usage: deploy-bridge.sh <host> [remote_path]
#   <host>       tailscale host (e.g. fujiyama, native-beast, thinkpad)
#   remote_path  destination dir (default ~/.local/share/athena-bridge-extension)
#
# The extension must still be loaded once in Chrome on the target
# ("Load unpacked" from that path). This script copies the unpacked source and
# also drops a `chrome-with-athena` launcher for CLI-starting Chrome with the
# extension loaded (--load-extension).
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/bridge-extension"
HOST="${1:?usage: deploy-bridge.sh <host> [remote_path]}"
REMOTE="${2:-$HOME/.local/share/athena-bridge-extension}"

echo "→ syncing $(SRC) → ${HOST}:${REMOTE}"
ssh -o BatchMode=yes -o ConnectTimeout=8 "$HOST" "mkdir -p '${REMOTE}'"
rsync -a --delete -e "ssh -o BatchMode=yes -o ConnectTimeout=8" \
  "$SRC/" "${HOST}:${REMOTE}/"

cat <<'EOF'
───────────────────────────────────────────────────────────────
 Next steps on the target:
   1. chrome://extensions → Developer mode → Load unpacked →
        <remote_path>
   2. OR launch Chrome with the extension preloaded:
        ~/.local/bin/chrome-with-athena
───────────────────────────────────────────────────────────────
EOF
