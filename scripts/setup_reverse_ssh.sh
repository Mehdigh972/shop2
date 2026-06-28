#!/usr/bin/env bash
set -euo pipefail

REMOTE_USER="${REMOTE_USER:-root}"
REMOTE_HOST="${REMOTE_HOST:-38.54.84.173}"
REMOTE_PORT="${REMOTE_PORT:-22}"
REVERSE_PORT="${REVERSE_PORT:-2222}"
SERVICE_NAME="${SERVICE_NAME:-freefire-reverse-ssh}"
KEY_PATH="${KEY_PATH:-$HOME/.ssh/freefire_helper_reverse_ed25519}"

mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

sudo apt update
sudo apt install -y openssh-client autossh

if [ ! -f "$KEY_PATH" ]; then
  ssh-keygen -t ed25519 -N "" -f "$KEY_PATH" -C "freefire-helper-reverse-ssh@$(hostname)"
fi

cat > "$HOME/.ssh/config.freefire-helper" <<EOF
Host freefire-helper-remote
  HostName $REMOTE_HOST
  User $REMOTE_USER
  Port $REMOTE_PORT
  IdentityFile $KEY_PATH
  ServerAliveInterval 30
  ServerAliveCountMax 3
  ExitOnForwardFailure yes
  StrictHostKeyChecking accept-new
EOF
chmod 600 "$HOME/.ssh/config.freefire-helper"

PUBKEY="$(cat "$KEY_PATH.pub")"

cat <<EOF

=== NEXT STEP REQUIRED ===
Add this public key to the remote server ($REMOTE_USER@$REMOTE_HOST):

$PUBKEY

Quick command from your Raspberry Pi terminal:
ssh -p $REMOTE_PORT $REMOTE_USER@$REMOTE_HOST 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && grep -qxF "$PUBKEY" ~/.ssh/authorized_keys 2>/dev/null || echo "$PUBKEY" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'

After that succeeds, run this script again with:
INSTALL_SERVICE=1 $0

Then Codex can connect by SSHing to the server and then:
ssh -p $REVERSE_PORT $USER@127.0.0.1

EOF

if [ "${INSTALL_SERVICE:-0}" != "1" ]; then
  exit 0
fi

ssh -F "$HOME/.ssh/config.freefire-helper" freefire-helper-remote true

sudo tee "/etc/systemd/system/$SERVICE_NAME.service" >/dev/null <<EOF
[Unit]
Description=FreeFire Raspberry Pi reverse SSH tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
Environment=AUTOSSH_GATETIME=0
ExecStart=/usr/bin/autossh -M 0 -N -F $HOME/.ssh/config.freefire-helper -R 127.0.0.1:$REVERSE_PORT:127.0.0.1:22 freefire-helper-remote
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

cat <<EOF
Installed $SERVICE_NAME.
Check status:
  systemctl status $SERVICE_NAME --no-pager

From the remote server, connect back to this Raspberry Pi with:
  ssh -p $REVERSE_PORT $USER@127.0.0.1
EOF
