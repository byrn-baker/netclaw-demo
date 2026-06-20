# TOOLS.md — Demo Environment

This is a NetClaw Demo VM. The ONLY infrastructure available is listed below.

## Lab Topology

- **Type:** ContainerLab (6-node FRR SP Core)
- **Topology file:** `/home/ubuntu/netclaw/lab/netclaw-demo/netclaw-demo.clab.yml`
- **Container prefix:** `clab-netclaw-demo-`
- **Nodes:** PE1, P1, P2, P3, P4, RR1 (all FRRouting)
- **Deploy:** `clab deploy -t /home/ubuntu/netclaw/lab/netclaw-demo/netclaw-demo.clab.yml`
- **Inspect:** `clab inspect -t /home/ubuntu/netclaw/lab/netclaw-demo/netclaw-demo.clab.yml`
- **Destroy:** `clab destroy -t /home/ubuntu/netclaw/lab/netclaw-demo/netclaw-demo.clab.yml`

## Source of Truth

- **Platform:** Nautobot (NOT NetBox)
- **URL:** http://localhost:8080
- **API Token:** `${NAUTOBOT_TOKEN}`
- **Start command:** `cd /home/ubuntu/nautobot-docker-compose && poetry run invoke start`
- **MCP servers:** nautobot-mcp-v2, nautobot-routing-mcp, nautobot-golden-config-mcp

## Device Interaction

- **Method:** `docker exec clab-netclaw-demo-<node> vtysh -c "<command>"`
- **No pyATS, no SSH, no SNMP** — direct vtysh via docker exec only
- **No ServiceNow, no Change Requests** — this is a demo lab, not production

## Protocol MCP (Optional)

- **Setup script:** `sudo /home/ubuntu/netclaw/scripts/setup-ospf-veth.sh`
- **Host interface:** `veth-netclaw` (10.0.99.1/30)
- **P2 interface:** `veth-p2` (10.0.99.2/30)
- **NetClaw AS:** 65001 (eBGP to lab AS 65000)

## Credentials

All credentials are in `~/.openclaw/.env`. Never put credentials in workspace files.
