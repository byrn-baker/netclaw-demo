#!/bin/bash
# NetShell Sandbox Wrapper
# Launches NetClaw inside an NVIDIA OpenShell sandbox with security policies
#
# Usage: sandbox-wrapper.sh [command] [args...]
# Example: sandbox-wrapper.sh python -m openclaw

set -euo pipefail

# Configuration
NETSHELL_DIR="${NETSHELL_DIR:-$(dirname "$(dirname "$(readlink -f "$0")")")}"
POLICY_FILE="${NETSHELL_POLICY:-$NETSHELL_DIR/policies/base.yaml}"
WORKSPACE="${WORKSPACE:-$HOME/.openclaw/workspace}"
SANDBOX_IMAGE="${SANDBOX_IMAGE:-netclaw/netshell:latest}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[NetShell]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[NetShell]${NC} $1"
}

log_error() {
    echo -e "${RED}[NetShell]${NC} $1" >&2
}

# Check prerequisites
check_prerequisites() {
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. NetShell requires Docker."
        log_error "Install Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running."
        log_error "Start Docker and try again."
        exit 1
    fi

    # Check OpenShell CLI
    if ! command -v openshell &> /dev/null; then
        log_warn "OpenShell CLI not found. Installing via uv..."
        if command -v uv &> /dev/null; then
            uv tool install openshell
        else
            log_error "uv is not installed. Install OpenShell manually:"
            log_error "  uv tool install openshell"
            exit 1
        fi
    fi

    # Check policy file
    if [[ ! -f "$POLICY_FILE" ]]; then
        log_error "Policy file not found: $POLICY_FILE"
        exit 1
    fi
}

# Build credential injection arguments
build_credential_args() {
    local cred_args=""

    # Extract credentials from policy file
    local creds
    creds=$(grep -A 100 "^credentials:" "$POLICY_FILE" | \
            grep -A 50 "^  inject:" | \
            grep "^\s*-\s" | \
            sed 's/.*- //' | \
            tr -d ' ')

    for cred in $creds; do
        # Only inject if credential is set in environment
        if [[ -n "${!cred:-}" ]]; then
            cred_args="$cred_args -e $cred"
        fi
    done

    echo "$cred_args"
}

# Launch sandbox
launch_sandbox() {
    log_info "Starting NetShell sandbox..."
    log_info "Policy: $POLICY_FILE"
    log_info "Workspace: $WORKSPACE"

    # Build credential arguments
    local cred_args
    cred_args=$(build_credential_args)

    # Create audit log directory
    mkdir -p "$WORKSPACE/logs/audit"

    # Launch via OpenShell
    # shellcheck disable=SC2086
    openshell run \
        --policy "$POLICY_FILE" \
        --workspace "$WORKSPACE" \
        --image "$SANDBOX_IMAGE" \
        $cred_args \
        -- "$@"
}

# Main
main() {
    check_prerequisites

    if [[ $# -eq 0 ]]; then
        # Default command: interactive shell
        launch_sandbox /bin/bash
    else
        launch_sandbox "$@"
    fi
}

main "$@"
