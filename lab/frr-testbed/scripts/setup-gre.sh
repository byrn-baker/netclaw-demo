#!/usr/bin/env bash
# Setup GRE tunnel from host (WSL/Linux) to Edge1 container — IPv6-only inner plane
#
# Underlay transport: IPv4 GRE (Docker bridge 10.0.100.0/24 — unchanged)
# Inner addressing:   IPv6 /127 per RFC 6164
#   Edge1 GRE:        fd00:ee::0/127
#   Host  GRE:        fd00:ee::1/127
#   Host  identity:   fd00::4/128 (on lo — WSL NetClaw BGP router-id)
#
# Requires: sudo, Docker running, edge1 container on 10.0.100.1
set -euo pipefail

HOST_PEERING_IP="${HOST_PEERING_IP:-10.0.100.100}"
EDGE1_PEERING_IP="${EDGE1_PEERING_IP:-10.0.100.1}"
HOST_TUNNEL_ADDR="${HOST_TUNNEL_ADDR:-fd00:ee::1}"
EDGE1_TUNNEL_ADDR="${EDGE1_TUNNEL_ADDR:-fd00:ee::0}"
HOST_IDENTITY="${HOST_IDENTITY:-fd00::4}"

echo "=== NetClaw GRE Tunnel Setup (IPv6-only inner plane) ==="
echo ""
echo "NOTE: Docker bridge networks disable IPv6 on veth interfaces by default."
echo "      This script fixes container net namespaces via nsenter (requires sudo)."
echo ""
# --- Step 0: Fix IPv6 sysctl in each container via nsenter ---
# Docker overrides disable_ipv6 on bridge-attached veth interfaces at container start.
# Must be fixed with nsenter since sysctl write inside container is read-only in WSL.
echo "[0/5] Enabling IPv6 on container interfaces via nsenter..."
for CTR in netclaw-edge1 netclaw-core netclaw-edge2; do
  PID=$(docker inspect "$CTR" --format '{{.State.Pid}}' 2>/dev/null || echo "")
  if [ -n "$PID" ] && [ "$PID" != "0" ]; then
    nsenter -t "$PID" -n -- sysctl -w net.ipv6.conf.eth0.disable_ipv6=0 >/dev/null 2>&1 || true
    nsenter -t "$PID" -n -- sysctl -w net.ipv6.conf.eth1.disable_ipv6=0 >/dev/null 2>&1 || true
    nsenter -t "$PID" -n -- sysctl -w net.ipv6.conf.all.forwarding=1     >/dev/null 2>&1 || true
    # Trigger zebra to re-apply IPv6 addresses from frr.conf
    docker exec "$CTR" vtysh -f /etc/frr/frr.conf >/dev/null 2>&1 || true
    echo "  $CTR: IPv6 enabled"
  fi
done
echo ""
echo "  Outer: $HOST_PEERING_IP → $EDGE1_PEERING_IP  (IPv4 Docker underlay)"
echo "  Inner: $HOST_TUNNEL_ADDR/127 ↔ $EDGE1_TUNNEL_ADDR/127  (IPv6 /127 RFC 6164)"
echo "  WSL identity: $HOST_IDENTITY/128"
echo ""

# --- Step 1: Host peering IP on Docker bridge ---
echo "[1/5] Adding host IP to peering bridge..."
PEERING_NET_ID=$(docker network inspect frr-testbed_peering -f '{{.Id}}' 2>/dev/null | cut -c1-12 || echo "")
if [ -n "$PEERING_NET_ID" ]; then
  PEERING_BRIDGE="br-${PEERING_NET_ID}"
fi

if [ -z "${PEERING_BRIDGE:-}" ] || ! ip link show "$PEERING_BRIDGE" &>/dev/null; then
  PEERING_BRIDGE=$(ip route show 10.0.100.0/24 2>/dev/null | awk '{print $3}' || echo "")
fi

if [ -z "${PEERING_BRIDGE:-}" ]; then
  echo "ERROR: Cannot find peering network bridge. Is docker compose up?"
  exit 1
fi

echo "  Found bridge: $PEERING_BRIDGE"
ip addr add "$HOST_PEERING_IP/24" dev "$PEERING_BRIDGE" 2>/dev/null || \
  echo "  (IPv4 peering IP already assigned — OK)"

# --- Step 2: GRE tunnel (IPv4 outer) ---
echo "[2/5] Creating GRE tunnel on host (IPv4 outer: $HOST_PEERING_IP → $EDGE1_PEERING_IP)..."
ip tunnel del gre-netclaw 2>/dev/null || true
ip tunnel add gre-netclaw mode gre \
  local "$HOST_PEERING_IP" \
  remote "$EDGE1_PEERING_IP" \
  ttl 255
ip link set gre-netclaw up

# --- Step 3: IPv6 inner addressing on host GRE ---
echo "[3/5] Assigning IPv6 /127 inner address to host GRE ($HOST_TUNNEL_ADDR/127)..."
ip -6 addr add "$HOST_TUNNEL_ADDR/127" dev gre-netclaw 2>/dev/null || \
  echo "  (address already assigned — OK)"

# --- Step 4: GRE tunnel inside Edge1 + IPv6 inner address ---
echo "[4/5] Creating GRE tunnel inside Edge1 container..."
docker exec netclaw-edge1 ip tunnel del gre-netclaw 2>/dev/null || true
docker exec netclaw-edge1 ip tunnel add gre-netclaw mode gre \
  local "$EDGE1_PEERING_IP" \
  remote "$HOST_PEERING_IP" \
  ttl 255
# FRR zebra assigns fd00:ee::0/127 from frr.conf once the interface exists
# Add manually here as a fallback in case zebra hasn't run yet
docker exec netclaw-edge1 ip link set gre-netclaw up
docker exec netclaw-edge1 ip -6 addr add "$EDGE1_TUNNEL_ADDR/127" dev gre-netclaw 2>/dev/null || \
  echo "  (address already assigned by FRR or script — OK)"

# --- Step 5: Host identity route + IPv6 routes to lab networks via GRE ---
echo "[5/5] Adding WSL identity route and lab IPv6 routes via GRE..."
ip -6 addr add "$HOST_IDENTITY/128" dev lo 2>/dev/null || \
  echo "  (identity $HOST_IDENTITY/128 already on lo — OK)"

# Route to edge1 loopback (fd00::1) and further lab prefixes via GRE inner
ip -6 route add fd00::1/128   via "$EDGE1_TUNNEL_ADDR" dev gre-netclaw 2>/dev/null || true
ip -6 route add fd00::2/128   via "$EDGE1_TUNNEL_ADDR" dev gre-netclaw 2>/dev/null || true
ip -6 route add fd00::3/128   via "$EDGE1_TUNNEL_ADDR" dev gre-netclaw 2>/dev/null || true
ip -6 route add fd00:12::/127 via "$EDGE1_TUNNEL_ADDR" dev gre-netclaw 2>/dev/null || true
ip -6 route add fd00:23::/127 via "$EDGE1_TUNNEL_ADDR" dev gre-netclaw 2>/dev/null || true

echo ""
echo "=== GRE Tunnel Ready (IPv6-only inner plane) ==="
echo "  ping6 $EDGE1_TUNNEL_ADDR          (Edge1 GRE inner)"
echo "  ping6 fd00::1                     (Edge1 loopback via OSPFv3)"
echo "  NetClaw can now eBGP-peer with Edge1 at $EDGE1_TUNNEL_ADDR (AS 65000)"
echo "  WSL identity route: $HOST_IDENTITY/128"
