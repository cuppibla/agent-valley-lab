#!/usr/bin/env bash
# Boot the valley: the agent (8100) + the app (3200). Ctrl+C stops both.
# Ports are overridable:  AGENT_PORT=8101 APP_PORT=3201 bash valley.sh
set -euo pipefail
cd "$(dirname "$0")"

AGENT_PORT="${AGENT_PORT:-8100}"
APP_PORT="${APP_PORT:-3200}"

if [ ! -f .env ]; then
  echo "No .env yet. Run:  cp .env.example .env"
  exit 1
fi
if ! .venv/bin/python -c "import forge,sys; sys.exit(0 if forge.MODE else 1)" 2>/dev/null; then
  echo "Not configured yet. Either point gcloud at a project (Vertex, the default):"
  echo "    gcloud config set project YOUR_PROJECT_ID"
  echo "or put an API key in .env — see .env.example."
  exit 1
fi

# The app is a separate process — point it at the agent this script is starting.
echo "VALLEY_AGENT_URL=http://127.0.0.1:${AGENT_PORT}" > site/.env.local

[ -d site/node_modules ] || (cd site && npm install)

cleanup() { kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

.venv/bin/uvicorn forge.agent.service:app --port "$AGENT_PORT" --log-level warning &
(cd site && npm run dev -- --port "$APP_PORT") &

echo
echo "  agent  → http://127.0.0.1:${AGENT_PORT}"
echo "  valley → http://localhost:${APP_PORT}"
echo
wait
