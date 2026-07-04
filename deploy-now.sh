#!/usr/bin/env bash
# Check if Nexa is live on Render
set -euo pipefail
URL="${NEXA_URL:-https://nexa.onrender.com}"

echo "Checking $URL ..."
if curl -sf "$URL/api/health" | grep -q '"ok"'; then
  echo "✓ Nexa is live: $URL"
  echo "$URL" > "$(dirname "$0")/CURRENT_LINK.txt"
else
  echo "✗ Not live yet. Finish Render deploy, then run this again."
  echo "  Run ./deploy-render.sh if you haven't connected Render yet."
  exit 1
fi
