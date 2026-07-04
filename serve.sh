#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8090}"
HOST="${HOST:-127.0.0.1}"
python3 -c "import aiohttp" 2>/dev/null || python3 -m pip install -q -r requirements.txt
echo "Nexa → http://${HOST}:${PORT}"
echo "Deploy online: ./deploy-render.sh → https://nexa.onrender.com"
echo "Press Ctrl+C to stop."
export PORT HOST
exec python3 server.py
