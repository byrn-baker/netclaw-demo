#!/usr/bin/env bash
# Configure and start Vector on a NetClaw demo VM for token metrics export.
# Called from demo-start.sh on boot.
#
# Prerequisites: Vector is pre-installed in the VM template.
#
# What it does:
#   1. Deploys the token-metrics Vector config from the repo
#   2. Ensures the OpenClaw log directory exists
#   3. Restarts the Vector service
#
# Metrics are pushed via remote-write to Prometheus at your-obs-host:9090

set -euo pipefail

LOG_FILE="/var/log/demo-setup.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [vector] $1" | tee -a "$LOG_FILE"; }

NETCLAW_DIR="/home/ubuntu/netclaw"
[ -d "$NETCLAW_DIR" ] || NETCLAW_DIR="/home/ubuntu/netclaw-demo"

VECTOR_CONFIG="$NETCLAW_DIR/observability/vector.yaml"

# --- Verify Vector is installed (should be in template) ---
if ! command -v vector &>/dev/null; then
  log "ERROR: Vector not found — it should be pre-installed in the VM template"
  exit 1
fi
log "Vector present: $(vector --version 2>&1 | head -1)"

# --- Deploy config ---
if [ -f "$VECTOR_CONFIG" ]; then
  cp "$VECTOR_CONFIG" /etc/vector/vector.yaml
  log "Deployed Vector config from $VECTOR_CONFIG"
else
  log "ERROR: Vector config not found at $VECTOR_CONFIG"
  exit 1
fi

# --- Ensure OpenClaw log directory exists (Vector needs it at start) ---
mkdir -p /tmp/openclaw
chown ubuntu:ubuntu /tmp/openclaw

# --- Ensure data directory exists ---
mkdir -p /var/lib/vector
chown vector:vector /var/lib/vector 2>/dev/null || true

# --- Restart Vector with new config ---
systemctl enable vector 2>/dev/null || true
systemctl restart vector

if systemctl is-active --quiet vector; then
  log "Vector is running and pushing token metrics"
else
  log "WARNING: Vector failed to start. Check: journalctl -u vector"
fi
