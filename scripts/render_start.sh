#!/bin/sh
# Render start command for the public DEMO hub: fresh DEMO data on every start, so the DEMO dates are current and
# nothing typed by visitors survives a restart.
set -e
python -m hub.seed --reset
exec uvicorn hub.main:app --host 0.0.0.0 --port "${PORT:-10000}"
