# NetClaw Demo — Session Context

## What This Is

A live demonstration of **NetClaw** — a CCIE-level AI network engineering agent built on OpenClaw — performing end-to-end network automation against a containerized SP core lab. The demo proves that an AI agent can populate a source of truth (Nautobot), generate device configurations from that data, push them to live devices, and validate the network is working correctly.

## What We're Building

A 6-node FRR service provider core deployed via ContainerLab:

```
PE1 --- P1 --- P2 --- RR1
         |      |
        P3 --- P4
```

- **NOS:** FRRouting (latest) in Docker containers
- **ASN:** 65000 (single iBGP domain)
- **IGP:** OSPFv2 area 0 on all P2P links
- **BGP:** iBGP full mesh via RR1 as route reflector
- **Topology file:** `lab/netclaw-demo/netclaw-demo.clab.yml`

## What the Demo Proves

1. **SOT-driven automation** — Nautobot is populated with devices, interfaces, IPs, and BGP peerings; the network is configured from that truth
2. **Config generation** — FRR configurations are generated from Nautobot data and pushed to blank containers
3. **Live validation** — OSPF adjacencies and BGP sessions are validated via `docker exec` / vtysh against running FRR containers
4. **Natural language orchestration** — The entire workflow is driven by natural language prompts from the user

## Environment Details

| Component | Location |
|-----------|----------|
| OpenClaw gateway | `systemctl --user start openclaw-gateway.service` (port 18789) |
| Lab topology | `lab/netclaw-demo/netclaw-demo.clab.yml` |
| MCP servers | nautobot-mcp, nautobot-routing-mcp |
| Nautobot | http://localhost:8080 (docker-compose) |
| Skill | `netclaw-demo` (workspace skill) |

## Demo Flow

Run the full demo with this single prompt:

> Run the full demo end to end:
> 1. Start Nautobot using poetry run invoke start from /home/ubuntu/nautobot-docker-compose, wait for it to be healthy
> 2. Deploy the containerlab topology from lab/netclaw-demo/netclaw-demo.clab.yml
> 3. Find and enable the "NetClaw Demo - Populate SP Core" job in Nautobot, then run it with deployment_name "Netclaw Demo"
> 4. Query each device's data from Nautobot via GraphQL (interfaces, IPs, OSPF, BGP peerings) and generate complete FRR configs, then push them to all 6 devices using docker exec vtysh
> 5. Validate OSPF neighbors are FULL on all devices and BGP shows 5 Established peers on RR1
> 6. Set up the veth link to P2, join the OSPF topology via protocol-mcp, and establish a BGP peering with RR1

Or run individual phases:

- **Deploy only:** "Start Nautobot from /home/ubuntu/nautobot-docker-compose using poetry run invoke start, then deploy the containerlab topology from lab/netclaw-demo/netclaw-demo.clab.yml"
- **Populate SOT:** "Find and enable the NetClaw Demo - Populate SP Core job in Nautobot, then run it with deployment_name Netclaw Demo"
- **Push configs:** "Query each device from Nautobot via GraphQL to get interfaces, IPs, OSPF areas, and BGP peerings, then generate FRR configs and push them to all 6 devices using docker exec vtysh"
- **Validate:** "Check OSPF neighbors are FULL on all devices and verify BGP shows 5 Established peers on RR1"
- **Protocol join:** "Run the setup-ospf-veth.sh script to create the veth link to P2, then use protocol-mcp to join OSPF and establish a BGP peering with RR1"

## Key Commands

```bash
# Gateway
systemctl --user start openclaw-gateway.service

# TUI
openclaw tui

# Lab deploy
clab deploy -t lab/netclaw-demo/netclaw-demo.clab.yml
clab inspect -t lab/netclaw-demo/netclaw-demo.clab.yml
clab destroy -t lab/netclaw-demo/netclaw-demo.clab.yml

# FRR interaction
docker exec clab-netclaw-demo-p1 vtysh -c "show ip ospf neighbor"
docker exec clab-netclaw-demo-rr1 vtysh -c "show bgp summary"
```
