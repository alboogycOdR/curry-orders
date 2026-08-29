#!/usr/bin/env bash
# Republish the Brandon's Kitchen static prototype to Clawsrv.
# Not part of the production stack (§17/§17.5) — a separate, isolated
# container on its own port, purely for showing the design to Brandon.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/design/prototype/index.html"
HOST="clawusr@100.78.70.2"
REMOTE_PATH="/home/clawusr/brandons-kitchen-prototype/index.html"

echo "Uploading $SRC ..."
scp "$SRC" "$HOST:$REMOTE_PATH"

echo "Done. No restart needed — Caddy serves the file straight off disk."
echo "Live at: http://204.168.249.99:8104/"
