#!/usr/bin/env bash
# Cafetal: one command to start the co-op hub (it also serves the phone app at /app/).
#   ./run.sh              (PORT=8000 by default; PORT=9000 ./run.sh to change)
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8000}"
PY="${PYTHON:-python3}"

if [ ! -x .venv/bin/python ]; then
  echo "Creating virtual environment in .venv ..."
  "$PY" -m venv .venv
fi
# Install/upgrade dependencies only when requirements.txt changed (works offline after the first run).
STAMP=.venv/.requirements.sha
WANT=$(.venv/bin/python -c "import hashlib;print(hashlib.sha256(open('requirements.txt','rb').read()).hexdigest())")
if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$WANT" ]; then
  echo "Installing hub dependencies ..."
  .venv/bin/pip install -q --disable-pip-version-check -r requirements.txt
  echo "$WANT" > "$STAMP"
fi

# Load the DEMO data the first time (when the database file does not exist yet).
.venv/bin/python -m hub.seed --if-missing

LAN_IP=$(.venv/bin/python - <<'PYEOF' 2>/dev/null || true
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(("10.255.255.255", 1))   # no packet is sent; this only picks the LAN interface
    print(s.getsockname()[0])
except OSError:
    pass
PYEOF
)
echo
echo "  Cafetal hub         http://localhost:${PORT}/"
[ -n "$LAN_IP" ] && echo "  On the co-op LAN    http://${LAN_IP}:${PORT}/"
echo "  Phone app           http://localhost:${PORT}/app/"
echo "  SMS simulator       http://localhost:${PORT}/hub/simulador.html   (SIMULATED gateway, DEMO data)"
echo
echo "  Phone tip: service workers (offline mode) need localhost or HTTPS. With the phone on USB:"
echo "    adb reverse tcp:${PORT} tcp:${PORT}   then open http://localhost:${PORT}/app/ on the phone."
echo "  Reset the DEMO data: button on the hub home page, or .venv/bin/python -m hub.seed --reset"
echo
exec .venv/bin/uvicorn hub.main:app --host 0.0.0.0 --port "$PORT"
