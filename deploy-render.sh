#!/usr/bin/env bash
# Deploy Nexa to Render — permanent URL: https://nexa.onrender.com
set -euo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$PATH"
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

REPO="https://github.com/riangandhi10-cyber/nexa"
URL="https://nexa.onrender.com"

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  Deploy Nexa to Render"
echo "══════════════════════════════════════════════════════════════"
echo ""
echo "  Repo:  $REPO  (public)"
echo "  Live:  $URL"
echo ""
echo "  Easiest: ./deploy-for-me.sh  (logs into Render + opens Blueprint)"
echo ""
echo "  Manual steps:"
echo "  1. Render → New + → Blueprint (or Web Service)"
echo "  2. Connect repo: nexa"
echo "  3. If nexa is missing → Configure GitHub → grant access to nexa"
echo "  4. Apply → add OPENAI_API_KEY → Deploy"
echo ""
echo "  See DEPLOY-STEPS.txt for full manual Web Service setup."
echo ""

open "https://dashboard.render.com/select-repo?type=blueprint" 2>/dev/null || true

echo "After deploy, run: ./deploy-now.sh"
echo ""
