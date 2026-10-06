#!/bin/bash
# Job B entry point (Layer 3, no_agent): dedup + format + emit matches for
# cron delivery (stdout -> Telegram adapter, split on "---" into messages).
export PYTHONPATH="/usr/local/lib64/python3.9/site-packages:/usr/local/lib/python3.9/site-packages:/home/opc/.local/lib/python3.9/site-packages:$PYTHONPATH"
export HOME="/home/opc"

cd "$(dirname "$0")"

/usr/bin/python3 send_formatter.py
