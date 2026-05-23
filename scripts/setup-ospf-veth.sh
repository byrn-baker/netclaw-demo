#!/bin/bash
# Setup veth pair between host and clab-netclaw-demo-p2 for OSPF peering
# Host side: 10.0.99.1/30 (NetClaw protocol agent)
# P2 side:   10.0.99.2/30 (lab router)
# OSPF Area: 0.0.0.0 (same area as the rest of the lab)

set -e

CONTAINER="clab-netclaw-demo-p2"
VETH_HOST="veth-netclaw"
VETH_PEER="veth-p2"
HOST_IP="10.0.99.1/30"
PEER_IP="10.0.99.2/30"
AREA="0"

echo "=== Setting up veth pair: host ($HOST_IP) <-> P2 ($PEER_IP) ==="

# Get container PID
PID=$(docker inspect "$CONTAINER" --format '{{.State.Pid}}')
if [ -z "$PID" ]; then
    echo "ERROR: Container $CONTAINER not running"
    exit 1
fi

# Clean up any existing veth
ip link del "$VETH_HOST" 2>/dev/null || true

# Create veth pair
ip link add "$VETH_HOST" type veth peer name "$VETH_PEER"

# Move peer end into container namespace
ip link set "$VETH_PEER" netns "$PID"

# Configure host side
ip addr add "$HOST_IP" dev "$VETH_HOST"
ip link set "$VETH_HOST" up

# Configure container side
nsenter -t "$PID" -n ip addr add "$PEER_IP" dev "$VETH_PEER"
nsenter -t "$PID" -n ip link set "$VETH_PEER" up

echo "=== Veth pair up ==="
echo "Host: $VETH_HOST ($HOST_IP)"
echo "P2:   $VETH_PEER ($PEER_IP)"

# Configure OSPF on P2's new interface
docker exec "$CONTAINER" vtysh \
    -c "configure terminal" \
    -c "interface veth-p2" \
    -c "ip ospf area $AREA" \
    -c "ip ospf network point-to-point" \
    -c "exit" \
    -c "exit"

echo "=== OSPF configured on P2 (veth-p2, area $AREA, p2p) ==="

# Add route to lab loopbacks via P2 (so host can reach them for BGP later)
ip route add 10.255.255.0/24 via 10.0.99.2 2>/dev/null || true
ip route add 10.0.0.0/16 via 10.0.99.2 2>/dev/null || true

echo "=== Routes added: 10.255.255.0/24 and 10.0.0.0/16 via 10.0.99.2 ==="
echo "=== Done. Host can now run OSPFv2 on $VETH_HOST ==="
