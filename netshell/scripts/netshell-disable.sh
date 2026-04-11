#!/bin/bash
# NetShell Disable Script
# Disables NetShell sandbox protection (returns to hobby mode)

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[NetShell]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[NetShell]${NC} $1"; }

OPENCLAW_CONFIG="$HOME/.openclaw/config/openclaw.json"

echo "========================================"
echo "  NetShell - Disable Production Security"
echo "========================================"
echo ""

log_warn "Disabling NetShell..."
log_warn "NetClaw will run without sandbox protection."
echo ""

# Update openclaw.json
if [ -f "$OPENCLAW_CONFIG" ]; then
    python3 -c "
import json
import os
config_path = os.path.expanduser('$OPENCLAW_CONFIG')
with open(config_path) as f:
    config = json.load(f)
if 'netshell' in config:
    config['netshell']['enabled'] = False
with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)
print('Configuration updated')
" 2>/dev/null || log_warn "Could not update openclaw.json"
fi

log_info "NetShell disabled."
echo ""
echo "  NetClaw will now run with full host access (hobby mode)."
echo "  No sandbox isolation, no policy enforcement, no audit logging."
echo ""
echo "  Re-enable anytime:"
echo "    ./netshell/scripts/netshell-enable.sh"
echo ""
