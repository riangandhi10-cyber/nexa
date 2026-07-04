#!/usr/bin/env bash
# Deploy Nexa to Render — permanent URL: https://nexa.onrender.com
set -euo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$PATH"
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  Deploy Nexa to Render (free permanent URL)"
echo "══════════════════════════════════════════════════════════════"
echo ""
echo "Your app URL will be:"
echo "  https://nexa.onrender.com"
echo ""
echo "Steps:"
echo "  1) Push this folder to GitHub (repo can be 'files' with root ai-chatbot)"
echo "  2) Open https://dashboard.render.com → New + → Blueprint"
echo "  3) Connect your repo"
echo "  4) Set root directory to: ai-chatbot"
echo "  5) Add environment variable OPENAI_API_KEY (Dashboard → Environment)"
echo "  6) Deploy — wait ~2 min for first build"
echo ""
echo "Optional (Google search + images):"
echo "  GOOGLE_API_KEY and GOOGLE_CSE_ID in Render env vars"
echo ""

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  echo "GitHub CLI is logged in."
  REMOTE="$(git -C "$DIR/.." remote get-url origin 2>/dev/null || true)"
  [[ -n "$REMOTE" ]] && echo "  Parent repo remote: ${REMOTE}"
  echo ""
  echo "Push latest code:"
  echo "  cd $(dirname "$DIR") && git add ai-chatbot && git commit -m 'Deploy Nexa' && git push"
  echo ""
fi

echo "Open Render dashboard now? (y/n)"
read -r OPEN
if [[ "$(echo "$OPEN" | tr '[:upper:]' '[:lower:]')" == "y" ]]; then
  open "https://dashboard.render.com/select-repo?type=blueprint" 2>/dev/null || true
fi

echo ""
echo "After deploy, check:"
echo "  curl https://nexa.onrender.com/api/health"
