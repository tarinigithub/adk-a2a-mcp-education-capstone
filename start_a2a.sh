#!/usr/bin/env bash
# Start the capstone's A2A servers only (no UI), for use by other agents such as the voice agent:
#   insights agent -> http://localhost:8001   root agent -> http://localhost:8002
set -euo pipefail
cd "$(dirname "$0")"

[ -f data/schools.db ] || .venv/bin/python data/build_db.py

.venv/bin/python -W ignore -m uvicorn education_agent.a2a_server:app --app-dir agents --port 8001 &
INSIGHTS_PID=$!
trap 'kill $INSIGHTS_PID 2>/dev/null' EXIT

.venv/bin/python -W ignore -m uvicorn education_agent.root_a2a_server:app --app-dir agents --port 8002
