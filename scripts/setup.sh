#!/usr/bin/env bash
# NetClaw Setup Wizard
# Interactive first-run configuration for brand new users

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

NETCLAW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENCLAW_DIR="$HOME/.openclaw"
OPENCLAW_ENV="$OPENCLAW_DIR/.env"

# ───────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────

prompt() {
    local var="$1" prompt_text="$2" default="${3:-}"
    if [ -n "$default" ]; then
        echo -ne "${CYAN}${prompt_text}${NC} ${DIM}[${default}]${NC}: "
    else
        echo -ne "${CYAN}${prompt_text}${NC}: "
    fi
    read -r input
    eval "$var=\"${input:-$default}\""
}

prompt_secret() {
    local var="$1" prompt_text="$2"
    echo -ne "${CYAN}${prompt_text}${NC}: "
    read -rs input
    echo ""
    eval "$var=\"$input\""
}

yesno() {
    local prompt_text="$1" default="${2:-n}"
    local yn
    if [ "$default" = "y" ]; then
        echo -ne "${CYAN}${prompt_text}${NC} ${DIM}[Y/n]${NC}: "
    else
        echo -ne "${CYAN}${prompt_text}${NC} ${DIM}[y/N]${NC}: "
    fi
    read -r yn
    yn="${yn:-$default}"
    [[ "$yn" =~ ^[Yy] ]]
}

set_env() {
    local key="$1" value="$2"
    if [ -z "$value" ]; then
        return
    fi
    if grep -q "^${key}=" "$OPENCLAW_ENV" 2>/dev/null; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$OPENCLAW_ENV"
    elif grep -q "^# ${key}=" "$OPENCLAW_ENV" 2>/dev/null; then
        sed -i "s|^# ${key}=.*|${key}=${value}|" "$OPENCLAW_ENV"
    else
        echo "${key}=${value}" >> "$OPENCLAW_ENV"
    fi
}

section() {
    echo ""
    echo -e "${BOLD}═══════════════════════════════════════════${NC}"
    echo -e "${BOLD}  $1${NC}"
    echo -e "${BOLD}═══════════════════════════════════════════${NC}"
    echo ""
}

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
skip() { echo -e "  ${DIM}– $1 (skipped)${NC}"; }

# ───────────────────────────────────────────
# Preflight
# ───────────────────────────────────────────

if [ ! -d "$OPENCLAW_DIR" ]; then
    echo -e "${RED}Error: ~/.openclaw not found. Run install.sh first.${NC}"
    exit 1
fi

[ -f "$OPENCLAW_ENV" ] || touch "$OPENCLAW_ENV"

# ───────────────────────────────────────────
# Welcome
# ───────────────────────────────────────────

clear 2>/dev/null || true
echo ""
echo -e "${BOLD}    ╔═══════════════════════════════════════╗${NC}"
echo -e "${BOLD}    ║                                       ║${NC}"
echo -e "${BOLD}    ║        NetClaw Setup Wizard            ║${NC}"
echo -e "${BOLD}    ║                                       ║${NC}"
echo -e "${BOLD}    ║   CCIE-Level AI Network Engineer       ║${NC}"
echo -e "${BOLD}    ║   32 Skills · 15 MCP Servers           ║${NC}"
echo -e "${BOLD}    ║                                       ║${NC}"
echo -e "${BOLD}    ╚═══════════════════════════════════════╝${NC}"
echo ""
echo -e "  This wizard will configure NetClaw for your environment."
echo -e "  You can re-run this anytime: ${BOLD}./scripts/setup.sh${NC}"
echo -e "  Press Ctrl+C to exit at any point."
echo ""
echo -e "  ${DIM}All credentials are stored in ~/.openclaw/.env${NC}"
echo -e "  ${DIM}and never committed to git.${NC}"
echo ""

# ═══════════════════════════════════════════
# Step 1: AI Provider
# ═══════════════════════════════════════════

section "Step 1: AI Provider"

echo "  NetClaw needs an LLM to think. Which provider?"
echo ""
echo "    1) Anthropic Claude  (recommended — Claude Opus/Sonnet)"
echo "    2) OpenAI            (GPT-4o / o1)"
echo "    3) AWS Bedrock       (Claude via Bedrock)"
echo "    4) Google Vertex AI  (Claude via Vertex)"
echo "    5) Skip              (I'll configure this later)"
echo ""

prompt PROVIDER_CHOICE "Select provider [1-5]" "1"

case "$PROVIDER_CHOICE" in
    1)
        echo ""
        echo -e "  Get your API key from: ${BOLD}https://console.anthropic.com/settings/keys${NC}"
        echo ""
        prompt_secret API_KEY "Anthropic API Key (sk-ant-...)"
        if [ -n "$API_KEY" ]; then
            set_env "ANTHROPIC_API_KEY" "$API_KEY"
            ok "Anthropic API key saved"
        else
            echo -e "  ${YELLOW}No key entered. You'll need to set ANTHROPIC_API_KEY later.${NC}"
        fi
        ;;
    2)
        echo ""
        echo -e "  Get your API key from: ${BOLD}https://platform.openai.com/api-keys${NC}"
        echo ""
        prompt_secret API_KEY "OpenAI API Key (sk-...)"
        if [ -n "$API_KEY" ]; then
            set_env "OPENAI_API_KEY" "$API_KEY"
            # Update model config for OpenAI
            if [ -f "$OPENCLAW_DIR/openclaw.json" ]; then
                python3 -c "
import json
with open('$OPENCLAW_DIR/openclaw.json') as f:
    cfg = json.load(f)
cfg.setdefault('agents', {}).setdefault('defaults', {})['model'] = {
    'primary': 'openai/gpt-4o',
    'fallbacks': ['openai/gpt-4o-mini']
}
with open('$OPENCLAW_DIR/openclaw.json', 'w') as f:
    json.dump(cfg, f, indent=2)
" 2>/dev/null && ok "OpenAI model config set (gpt-4o)" || echo -e "  ${YELLOW}Warning: could not update model config${NC}"
            fi
            ok "OpenAI API key saved"
        fi
        ;;
    3)
        echo ""
        prompt AWS_REGION "AWS Region" "us-east-1"
        prompt AWS_PROFILE "AWS Profile (or leave empty for default)" ""
        set_env "AWS_REGION" "$AWS_REGION"
        [ -n "$AWS_PROFILE" ] && set_env "AWS_PROFILE" "$AWS_PROFILE"
        if [ -f "$OPENCLAW_DIR/openclaw.json" ]; then
            python3 -c "
import json
with open('$OPENCLAW_DIR/openclaw.json') as f:
    cfg = json.load(f)
cfg.setdefault('agents', {}).setdefault('defaults', {})['model'] = {
    'primary': 'bedrock/anthropic.claude-opus-4-6-v1',
    'fallbacks': ['bedrock/anthropic.claude-sonnet-4-6-v1']
}
with open('$OPENCLAW_DIR/openclaw.json', 'w') as f:
    json.dump(cfg, f, indent=2)
" 2>/dev/null && ok "Bedrock model config set" || echo -e "  ${YELLOW}Warning: could not update model config${NC}"
        fi
        ok "AWS Bedrock configured"
        ;;
    4)
        echo ""
        prompt GCP_PROJECT "GCP Project ID"
        prompt GCP_REGION "GCP Region" "us-central1"
        set_env "GOOGLE_CLOUD_PROJECT" "$GCP_PROJECT"
        set_env "GOOGLE_CLOUD_LOCATION" "$GCP_REGION"
        if [ -f "$OPENCLAW_DIR/openclaw.json" ]; then
            python3 -c "
import json
with open('$OPENCLAW_DIR/openclaw.json') as f:
    cfg = json.load(f)
cfg.setdefault('agents', {}).setdefault('defaults', {})['model'] = {
    'primary': 'vertex/claude-opus-4-6@20250514',
    'fallbacks': ['vertex/claude-sonnet-4-6@20250514']
}
with open('$OPENCLAW_DIR/openclaw.json', 'w') as f:
    json.dump(cfg, f, indent=2)
" 2>/dev/null && ok "Vertex AI model config set" || echo -e "  ${YELLOW}Warning: could not update model config${NC}"
        fi
        ok "Google Vertex AI configured"
        ;;
    *)
        skip "AI provider"
        ;;
esac

# ═══════════════════════════════════════════
# Step 2: Network Devices (pyATS)
# ═══════════════════════════════════════════

section "Step 2: Network Devices"

echo "  NetClaw uses pyATS to connect to Cisco devices via SSH."
echo "  Your device inventory goes in testbed/testbed.yaml."
echo ""

if yesno "Open testbed.yaml in your editor now?"; then
    EDITOR="${EDITOR:-nano}"
    "$EDITOR" "$NETCLAW_DIR/testbed/testbed.yaml"
    ok "Testbed edited"
else
    skip "Testbed editing (edit testbed/testbed.yaml later)"
fi

# ═══════════════════════════════════════════
# Step 3: Network Platforms
# ═══════════════════════════════════════════

section "Step 3: Network Platforms"

echo "  Which platforms do you have? NetClaw will only enable what you select."
echo "  You can always re-run this wizard to add more later."
echo ""

# --- NetBox ---
if yesno "Do you have a NetBox instance?"; then
    echo ""
    prompt NETBOX_URL "NetBox URL (https://netbox.example.com)" ""
    prompt_secret NETBOX_TOKEN "NetBox API Token"
    [ -n "$NETBOX_URL" ] && set_env "NETBOX_URL" "$NETBOX_URL"
    [ -n "$NETBOX_TOKEN" ] && set_env "NETBOX_TOKEN" "$NETBOX_TOKEN"
    ok "NetBox configured"
else
    skip "NetBox"
fi
echo ""

# --- ServiceNow ---
if yesno "Do you have a ServiceNow instance?"; then
    echo ""
    prompt SNOW_URL "ServiceNow Instance URL (https://xxx.service-now.com)" ""
    prompt SNOW_USER "ServiceNow Username" ""
    prompt_secret SNOW_PASS "ServiceNow Password"
    [ -n "$SNOW_URL" ] && set_env "SERVICENOW_INSTANCE_URL" "$SNOW_URL"
    [ -n "$SNOW_USER" ] && set_env "SERVICENOW_USERNAME" "$SNOW_USER"
    [ -n "$SNOW_PASS" ] && set_env "SERVICENOW_PASSWORD" "$SNOW_PASS"
    ok "ServiceNow configured"
else
    skip "ServiceNow"
fi
echo ""

# --- Cisco ACI ---
if yesno "Do you have a Cisco ACI fabric (APIC)?"; then
    echo ""
    prompt APIC_URL "APIC URL (https://apic.example.com)" ""
    prompt APIC_USER "APIC Username" "admin"
    prompt_secret APIC_PASS "APIC Password"
    [ -n "$APIC_URL" ] && set_env "APIC_URL" "$APIC_URL"
    [ -n "$APIC_USER" ] && set_env "APIC_USERNAME" "$APIC_USER"
    [ -n "$APIC_PASS" ] && set_env "APIC_PASSWORD" "$APIC_PASS"
    ok "Cisco ACI configured"
else
    skip "Cisco ACI"
fi
echo ""

# --- Cisco ISE ---
if yesno "Do you have Cisco ISE with ERS API enabled?"; then
    echo ""
    prompt ISE_BASE "ISE Base URL (https://ise.example.com)" ""
    prompt ISE_USER "ISE ERS Username" ""
    prompt_secret ISE_PASS "ISE ERS Password"
    [ -n "$ISE_BASE" ] && set_env "ISE_BASE" "$ISE_BASE"
    [ -n "$ISE_USER" ] && set_env "ISE_USERNAME" "$ISE_USER"
    [ -n "$ISE_PASS" ] && set_env "ISE_PASSWORD" "$ISE_PASS"
    ok "Cisco ISE configured"
else
    skip "Cisco ISE"
fi
echo ""

# --- F5 BIG-IP ---
if yesno "Do you have an F5 BIG-IP load balancer?"; then
    echo ""
    prompt F5_IP "F5 Management IP/Hostname" ""
    prompt F5_USER "F5 Username" "admin"
    prompt_secret F5_PASS "F5 Password"
    if [ -n "$F5_IP" ]; then
        set_env "F5_IP_ADDRESS" "$F5_IP"
    fi
    if [ -n "$F5_USER" ] && [ -n "$F5_PASS" ]; then
        F5_AUTH=$(echo -n "${F5_USER}:${F5_PASS}" | base64)
        set_env "F5_AUTH_STRING" "$F5_AUTH"
        ok "F5 BIG-IP configured (auth string base64-encoded)"
    fi
else
    skip "F5 BIG-IP"
fi
echo ""

# --- Catalyst Center ---
if yesno "Do you have Cisco Catalyst Center (DNA Center)?"; then
    echo ""
    prompt CCC_HOST "Catalyst Center Hostname/IP" ""
    prompt CCC_USER "Catalyst Center Username" "admin"
    prompt_secret CCC_PWD "Catalyst Center Password"
    [ -n "$CCC_HOST" ] && set_env "CCC_HOST" "$CCC_HOST"
    [ -n "$CCC_USER" ] && set_env "CCC_USER" "$CCC_USER"
    [ -n "$CCC_PWD" ] && set_env "CCC_PWD" "$CCC_PWD"
    ok "Catalyst Center configured"
else
    skip "Catalyst Center"
fi
echo ""

# --- NVD CVE ---
if yesno "Do you want CVE vulnerability scanning? (free NVD API key)"; then
    echo ""
    echo -e "  Get a free API key from: ${BOLD}https://nvd.nist.gov/developers/request-an-api-key${NC}"
    echo ""
    prompt_secret NVD_KEY "NVD API Key"
    if [ -n "$NVD_KEY" ]; then
        set_env "NVD_API_KEY" "$NVD_KEY"
        ok "NVD CVE scanning configured"
    else
        skip "NVD API key (CVE scanning will work without it, just rate-limited)"
    fi
else
    skip "NVD CVE scanning"
fi

# ═══════════════════════════════════════════
# Step 4: Slack Integration
# ═══════════════════════════════════════════

section "Step 4: Slack Integration"

echo "  NetClaw can send alerts, reports, and manage incidents in Slack."
echo "  This requires a Slack bot with the right OAuth scopes."
echo ""

if yesno "Do you have a Slack workspace with a NetClaw bot?"; then
    echo ""
    echo -e "  ${DIM}Your Slack bot needs these scopes: assistant:write, chat:write,${NC}"
    echo -e "  ${DIM}files:write, reactions:write, channels:read, users:read, etc.${NC}"
    echo ""
    prompt_secret SLACK_TOKEN "Slack Bot Token (xoxb-...)"
    if [ -n "$SLACK_TOKEN" ]; then
        set_env "SLACK_BOT_TOKEN" "$SLACK_TOKEN"
        ok "Slack bot token saved"
    fi

    echo ""
    echo "  Configure Slack channels (leave empty to skip):"
    prompt SLACK_ALERTS "Alerts channel" "#netclaw-alerts"
    prompt SLACK_REPORTS "Reports channel" "#netclaw-reports"
    prompt SLACK_GENERAL "General channel" "#netclaw-general"
    prompt SLACK_INCIDENTS "Incidents channel" "#incidents"

    [ -n "$SLACK_ALERTS" ] && set_env "SLACK_CHANNEL_ALERTS" "$SLACK_ALERTS"
    [ -n "$SLACK_REPORTS" ] && set_env "SLACK_CHANNEL_REPORTS" "$SLACK_REPORTS"
    [ -n "$SLACK_GENERAL" ] && set_env "SLACK_CHANNEL_GENERAL" "$SLACK_GENERAL"
    [ -n "$SLACK_INCIDENTS" ] && set_env "SLACK_CHANNEL_INCIDENTS" "$SLACK_INCIDENTS"
    ok "Slack channels configured"
else
    skip "Slack integration"
fi

# ═══════════════════════════════════════════
# Step 5: Your Identity
# ═══════════════════════════════════════════

section "Step 5: About You"

echo "  Help NetClaw work better by telling it about yourself."
echo "  This goes into USER.md (never leaves your machine)."
echo ""

prompt USER_NAME "Your name" ""
prompt USER_ROLE "Your role (e.g., Network Engineer, NetOps Lead)" "Network Engineer"
prompt USER_TZ "Your timezone (e.g., US/Eastern, UTC)" ""

USER_MD="$OPENCLAW_DIR/workspace/USER.md"
if [ -n "$USER_NAME" ] || [ -n "$USER_ROLE" ] || [ -n "$USER_TZ" ]; then
    cat > "$USER_MD" << USEREOF
# About My Human

## Identity
- **Name:** ${USER_NAME:-[your name]}
- **Role:** ${USER_ROLE:-Network Engineer}
- **Timezone:** ${USER_TZ:-[your timezone]}

## Preferences
- Communication style: technical, direct
- Output format: structured tables and bullet points preferred
- Change management: always require ServiceNow CR before config changes
- Escalation: alert me for P1/P2, queue P3/P4 for next business day

## Network
- Edit TOOLS.md with your device IPs, sites, and Slack channels
- Edit testbed/testbed.yaml with your pyATS device inventory
USEREOF
    ok "USER.md personalized"
fi

# ═══════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════

section "Setup Complete"

echo "  Configuration saved to: ~/.openclaw/.env"
echo ""
echo "  What's configured:"

# Check what was configured
[ -n "${API_KEY:-}" ] || [ -n "${AWS_REGION:-}" ] || [ -n "${GCP_PROJECT:-}" ] && ok "AI Provider" || echo -e "  ${YELLOW}! AI Provider (set API key in ~/.openclaw/.env)${NC}"

grep -q "^NETBOX_URL=" "$OPENCLAW_ENV" 2>/dev/null && ok "NetBox" || skip "NetBox"
grep -q "^SERVICENOW_INSTANCE_URL=" "$OPENCLAW_ENV" 2>/dev/null && ok "ServiceNow" || skip "ServiceNow"
grep -q "^APIC_URL=" "$OPENCLAW_ENV" 2>/dev/null && ok "Cisco ACI" || skip "Cisco ACI"
grep -q "^ISE_BASE=" "$OPENCLAW_ENV" 2>/dev/null && ok "Cisco ISE" || skip "Cisco ISE"
grep -q "^F5_IP_ADDRESS=" "$OPENCLAW_ENV" 2>/dev/null && ok "F5 BIG-IP" || skip "F5 BIG-IP"
grep -q "^CCC_HOST=" "$OPENCLAW_ENV" 2>/dev/null && ok "Catalyst Center" || skip "Catalyst Center"
grep -q "^NVD_API_KEY=" "$OPENCLAW_ENV" 2>/dev/null && ok "NVD CVE Scanning" || skip "NVD CVE Scanning"
grep -q "^SLACK_BOT_TOKEN=" "$OPENCLAW_ENV" 2>/dev/null && ok "Slack" || skip "Slack"

echo ""
echo -e "  ${BOLD}Next:${NC}"
echo ""
echo -e "    ${CYAN}openclaw gateway${NC}          # Terminal 1 — start the gateway"
echo -e "    ${CYAN}openclaw chat --new${NC}       # Terminal 2 — talk to NetClaw"
echo ""
echo -e "  Re-run this wizard anytime: ${BOLD}./scripts/setup.sh${NC}"
echo -e "  Edit credentials directly:  ${BOLD}nano ~/.openclaw/.env${NC}"
echo ""
