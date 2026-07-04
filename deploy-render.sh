#!/usr/bin/env bash
# One-click Render setup for Nexa
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

REPO="https://github.com/riangandhi10-cyber/nexa"
URL="https://nexa.onrender.com"

echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  Deploy Nexa to Render"
echo "══════════════════════════════════════════════════════════════"
echo ""
echo "  Repo:  $REPO"
echo "  Live:  $URL"
echo ""
echo "  1. Render opens → connect repo 'nexa'"
echo "  2. Click Apply (render.yaml is already in the repo)"
echo "  3. Add OPENAI_API_KEY in Environment (paste from your .env)"
echo "  4. Wait ~2 min for deploy"
echo ""

open "https://dashboard.render.com/select-repo?type=blueprint" 2>/dev/null || true

echo "After deploy, run: ./deploy-now.sh"
echo ""
