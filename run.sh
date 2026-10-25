#!/usr/bin/env bash
# Start the insights agent (A2A server, port 8001) and the ADK web UI (port 8000).
set -euo pipefail
cd "$(dirname "$0")"

[ -f data/schools.db ] || .venv/bin/python data/build_db.py

.venv/bin/python -W ignore -m uvicorn education_agent.a2a_server:app --app-dir agents --port 8001 &
A2A_PID=$!
trap 'kill $A2A_PID 2>/dev/null' EXIT

until curl -sf http://localhost:8001/.well-known/agent-card.json >/dev/null; do sleep 1; done
echo "Insights agent (A2A) ready: http://localhost:8001/.well-known/agent-card.json"

.venv/bin/adk web agents --port 8000
