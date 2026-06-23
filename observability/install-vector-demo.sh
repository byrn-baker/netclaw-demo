#!/usr/bin/env bash
# Install and configure Vector on a NetClaw demo VM for token metrics export.
# Called from demo-start.sh or cloud-init runcmd.
#
# What it does:
#   1. Installs Vector (if not already present)
#   2. Deploys the token-metrics Vector config
#   3. Enables and starts the Vector service
#
# Metrics are pushed via remote-write to Prometheus at your-obs-host:9090

set -euo pipefail

LOG_FILE="/var/log/demo-setup.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [vector] $1" | tee -a "$LOG_FILE"; }

NETCLAW_DIR="/home/ubuntu/netclaw"
[ -d "$NETCLAW_DIR" ] || NETCLAW_DIR="/home/ubuntu/netclaw-demo"

VECTOR_CONFIG="$NETCLAW_DIR/observability/vector.yaml"

# --- Install Vector if not present ---
if ! command -v vector &>/dev/null; then
  log "Installing Vector..."
  export DEBIAN_FRONTEND=noninteractive

  # Add Vector repo
  if [ ! -f /etc/apt/sources.list.d/vector.list ]; then
    curl -fsSL https://apt.vector.dev/gpg | gpg --dearmor -o /usr/share/keyrings/vector-archive-keyring.gpg 2>/dev/null
    echo "deb [signed-by=/usr/share/keyrings/vector-archive-keyring.gpg] https://apt.vector.dev/ stable main" > /etc/apt/sources.list.d/vector.list
    apt-get update -y -qq
  fi

  apt-get install -y vector -qq
  log "Vector installed: $(vector --version)"
else
  log "Vector already installed: $(vector --version)"
fi

# --- Deploy config ---
if [ -f "$VECTOR_CONFIG" ]; then
  cp "$VECTOR_CONFIG" /etc/vector/vector.yaml
  log "Deployed Vector config from $VECTOR_CONFIG"
else
  log "ERROR: Vector config not found at $VECTOR_CONFIG"
  exit 1
fi

# --- Create data directory ---
mkdir -p /var/lib/vector
chown vector:vector /var/lib/vector 2>/dev/null || true

# --- Ensure OpenClaw log directory exists (Vector needs it at start) ---
mkdir -p /tmp/openclaw
chown ubuntu:ubuntu /tmp/openclaw

# --- Validate config ---
if vector validate /etc/vector/vector.yaml 2>/dev/null; then
  log "Vector config validated OK"
else
  log "WARNING: Vector config validation failed, starting anyway"
fi

# --- Enable and start ---
systemctl enable vector
systemctl restart vector

if systemctl is-active --quiet vector; then
  log "Vector is running and pushing token metrics"
else
  log "WARNING: Vector failed to start. Check: journalctl -u vector"
fi
