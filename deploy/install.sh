#!/usr/bin/env bash
# Run on the VPS from the extracted card-api-deploy folder:  sudo bash deploy/install.sh
# Safe to re-run (acts as an update). Never touches nginx, firewall, or other databases.
set -euo pipefail

PORT=5005
APP_ROOT=/opt/card-api
HERE="$(cd "$(dirname "$0")/.." && pwd)"

[ "$(id -u)" -eq 0 ] || { echo "Run with sudo"; exit 1; }

# 1) Port check (skip if our own service already owns it, i.e. an update)
if ! systemctl is-active --quiet card-api; then
  if ss -H -ltn "sport = :$PORT" | grep -q .; then
    echo "ERROR: port $PORT is already in use by:"; ss -ltnp "sport = :$PORT"
    echo "Pick another port: edit --port in deploy/card-api.service and PORT in this script."
    exit 1
  fi
fi
echo "[ok] port $PORT is free (or owned by card-api)"

# 2) Python venv support
command -v python3 >/dev/null || { echo "python3 missing"; exit 1; }
python3 -m venv --help >/dev/null 2>&1 || apt-get install -y python3-venv

# 3) Dedicated user + folders
id cardapi >/dev/null 2>&1 || useradd --system --home "$APP_ROOT" --shell /usr/sbin/nologin cardapi
mkdir -p "$APP_ROOT/app"

# 4) App code (database is NOT here, so updates never overwrite data)
cp "$HERE"/app/main.py "$HERE"/app/schema.sql "$HERE"/app/requirements.txt "$APP_ROOT/app/"

# 5) Isolated virtualenv
[ -d "$APP_ROOT/venv" ] || python3 -m venv "$APP_ROOT/venv"
"$APP_ROOT/venv/bin/pip" install --quiet --upgrade pip
"$APP_ROOT/venv/bin/pip" install --quiet -r "$APP_ROOT/app/requirements.txt"
chown -R root:root "$APP_ROOT"

# 6) Env file (keep existing one if present) + systemd unit
[ -f /etc/card-api.env ] || install -m 640 -o root -g cardapi "$HERE/deploy/card-api.env" /etc/card-api.env
install -m 644 "$HERE/deploy/card-api.service" /etc/systemd/system/card-api.service

# 7) Start now + on boot
systemctl daemon-reload
systemctl enable card-api >/dev/null
systemctl restart card-api
sleep 2
systemctl --no-pager --lines=5 status card-api || true

echo "--- local test ---"
curl -fsS http://127.0.0.1:$PORT/api/card/summary && echo
echo "Done. API: http://72.61.146.237:5005  (open firewall for 5005, see guide)"
