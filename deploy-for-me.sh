#!/usr/bin/env bash
# One-shot deploy Nexa to Render — needs GitHub + Render login once (browser).
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

URL="https://nexa.onrender.com"
REPO="https://github.com/riangandhi10-cyber/nexa"

echo ""
echo "Nexa → Render deploy"
echo "===================="
echo ""

# 1) GitHub
if ! command -v gh >/dev/null 2>&1; then
  echo "Install GitHub CLI: brew install gh"
  exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "Opening GitHub login in your browser (one-time)…"
  gh auth login --web --git-protocol https
fi

# 2) Push latest
echo "Pushing to GitHub…"
git push -u origin main 2>/dev/null || git push origin main

# 3) Render CLI
if ! command -v render >/dev/null 2>&1; then
  echo "Install Render CLI: brew install render"
  exit 1
fi
if ! render whoami >/dev/null 2>&1; then
  echo "Opening Render login in your browser (one-time)…"
  render login
fi

echo ""
echo "Launching Render Blueprint…"
render blueprint launch 2>/dev/null || true

echo ""
echo "If Blueprint did not auto-start, in the browser:"
echo "  1. New + → Blueprint"
echo "  2. Search for repo: nexa  ($REPO)"
echo "  3. If you don't see it: Configure GitHub → grant access to 'nexa'"
echo "  4. Click Apply → add OPENAI_API_KEY → Deploy"
echo ""
echo "Or use New Web Service (manual):"
echo "  Repo: riangandhi10-cyber/nexa"
echo "  Runtime: Python 3"
echo "  Build:  pip install -r requirements.txt"
echo "  Start:  python server.py"
echo "  Health: /api/health"
echo ""
open "https://dashboard.render.com/select-repo?type=blueprint" 2>/dev/null || true

echo "Waiting for $URL (up to 8 min)…"
for i in $(seq 1 48); do
  if curl -sf --max-time 15 "$URL/api/health" >/dev/null 2>&1; then
    echo ""
    echo "✓ LIVE: $URL"
    echo "$URL" > "$DIR/CURRENT_LINK.txt"
    exit 0
  fi
  sleep 10
done

echo ""
echo "Deploy may still be building — check Render dashboard, then run: ./deploy-now.sh"
exit 0
