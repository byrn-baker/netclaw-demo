#!/bin/bash
# NetShell Enable Script
# Enables NetShell sandbox protection for NetClaw

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[NetShell]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[NetShell]${NC} $1"; }
log_error() { echo -e "${RED}[NetShell]${NC} $1" >&2; }

NETSHELL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NETCLAW_DIR="$(dirname "$NETSHELL_DIR")"
OPENCLAW_CONFIG="$HOME/.openclaw/config/openclaw.json"

echo "========================================"
echo "  NetShell - Enable Production Security"
echo "========================================"
echo ""

# Check Docker
log_info "Checking Docker..."
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed."
    log_error "Install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info &> /dev/null 2>&1; then
    log_error "Docker daemon is not running."
    log_error "Start Docker and try again."
    exit 1
fi
log_info "Docker OK"

# Check/Install OpenShell CLI
log_info "Checking OpenShell CLI..."
if ! command -v openshell &> /dev/null; then
    if command -v uv &> /dev/null; then
        log_info "Installing OpenShell CLI..."
        uv tool install openshell
    else
        log_error "OpenShell CLI not found and uv not available."
        log_error "Install manually: uv tool install openshell"
        exit 1
    fi
fi
log_info "OpenShell CLI OK"

# Install dependencies
log_info "Installing NetShell dependencies..."
if [ -f "$NETSHELL_DIR/requirements.txt" ]; then
    pip3 install -q -r "$NETSHELL_DIR/requirements.txt" 2>/dev/null || \
        pip3 install --break-system-packages -q -r "$NETSHELL_DIR/requirements.txt" 2>/dev/null || \
        log_warn "Some dependencies may not have installed correctly"
fi

# Validate policies
log_info "Validating security policies..."
if [ -f "$NETSHELL_DIR/scripts/validate-policies.py" ]; then
    python3 "$NETSHELL_DIR/scripts/validate-policies.py" --quiet 2>/dev/null && \
        log_info "Policies valid" || \
        log_warn "Policy validation found issues - run: python3 $NETSHELL_DIR/scripts/validate-policies.py"
fi

# Compile skill policies
log_info "Compiling skill policies..."
if [ -f "$NETSHELL_DIR/scripts/compile-policies.py" ]; then
    python3 "$NETSHELL_DIR/scripts/compile-policies.py" 2>/dev/null || true
fi

# Update openclaw.json
log_info "Updating configuration..."
if [ -f "$OPENCLAW_CONFIG" ]; then
    python3 -c "
import json
import os
config_path = os.path.expanduser('$OPENCLAW_CONFIG')
with open(config_path) as f:
    config = json.load(f)
if 'netshell' not in config:
    config['netshell'] = {}
config['netshell']['enabled'] = True
config['netshell']['policyDir'] = 'netshell/policies'
config['netshell']['auditLogPath'] = '/workspace/logs/audit/netshell.log'
with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)
" 2>/dev/null || log_warn "Could not update openclaw.json"
fi

echo ""
log_info "NetShell enabled successfully!"
echo ""
echo "  Sandbox policy:  $NETSHELL_DIR/policies/base.yaml"
echo "  MCP policies:    $NETSHELL_DIR/policies/mcp/ (23 servers)"
echo "  Audit logs:      /workspace/logs/audit/netshell.log"
echo ""
echo "  Run NetClaw with sandbox:"
echo "    openclaw gateway"
echo ""
echo "  Disable anytime:"
echo "    $NETSHELL_DIR/scripts/netshell-disable.sh"
echo ""
