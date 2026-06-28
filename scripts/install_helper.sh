#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/home/$USER/freefire_shop_helper}"
SERVICE_NAME="${SERVICE_NAME:-freefire-helper}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi

sudo apt update
sudo apt install -y python3-venv python3-full python3-pip chromium-browser xvfb ca-certificates

mkdir -p "$APP_DIR"
rsync -a --exclude .git --exclude .venv --exclude config.env ./ "$APP_DIR"/
cd "$APP_DIR"

if [ ! -f config.env ]; then
  cp config.env.example config.env
  api_key="$(openssl rand -hex 32)"
  sed -i "s/^HELPER_API_KEY=.*/HELPER_API_KEY=$api_key/" config.env
  if command -v chromium >/dev/null 2>&1; then
    sed -i "s#^CHROMIUM_PATH=.*#CHROMIUM_PATH=$(command -v chromium)#" config.env
  elif command -v chromium-browser >/dev/null 2>&1; then
    sed -i "s#^CHROMIUM_PATH=.*#CHROMIUM_PATH=$(command -v chromium-browser)#" config.env
  fi
  echo "Created $APP_DIR/config.env with a new HELPER_API_KEY."
fi

$PYTHON_BIN -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

sudo tee "/etc/systemd/system/$SERVICE_NAME.service" >/dev/null <<EOF
[Unit]
Description=FreeFire Shop Helper API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/config.env
ExecStart=$APP_DIR/.venv/bin/python -m uvicorn api_server:app --host 0.0.0.0 --port 8088
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "Installed $SERVICE_NAME."
echo "Check: systemctl status $SERVICE_NAME --no-pager"
echo "Local health test: curl -H \"X-API-Key: $(grep '^HELPER_API_KEY=' config.env | cut -d= -f2)\" http://127.0.0.1:8088/health"
