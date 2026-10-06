#!/bin/bash
# Stage 1: scrape + dedupe. Output (NDJSON) feeds the cron Agent for matching.
export PYTHONPATH="/usr/local/lib64/python3.9/site-packages:/usr/local/lib/python3.9/site-packages:/home/opc/.local/lib/python3.9/site-packages:$PYTHONPATH"
export HOME="/home/opc"

cd "$(dirname "$0")"

/usr/bin/python3 orchestrator.py "$@" 2>/dev/null
