<p align="center">
  <img src="netclaw.jpg" alt="NetClaw — A CCIE-level AI agent that claws through your network" width="600">
</p>

# NetClaw Demo — Cisco DevNet NetGru Podcast

> **This is NOT the main NetClaw repository.** This is a fork configured specifically for the [Cisco DevNet NetGru Demo Podcast](https://www.youtube.com/watch?v=TsCuyOzrl0w). It exists to let viewers see exactly how NetClaw was set up for that demo.

## Use the real NetClaw instead

👉 **[github.com/automateyournetwork/netclaw](https://github.com/automateyournetwork/netclaw)** 👈

The upstream repo has the latest features, full documentation, installation wizard, and community support. Start there.

---

## What's different in this fork?

This repo contains the exact configuration used for the LocalEdge Datacenter demo environment shown in the NetGru podcast, plus several custom MCP servers and integrations I've been experimenting with.

### Demo infrastructure

- **`config/openclaw-demo.json`** — MCP server config for the ephemeral demo VMs
- **`workspace/skills/netclaw-demo/`** — Locked-down skill set for the 4-hour demo sessions
- **`observability/`** — Vector + Prometheus remote-write pipeline for token usage metrics
- **`testbed/`** — ContainerLab FRR testbed topology (6 routers: PE1, P1–P4, RR1)

The demo runs on [LocalEdge Datacenter](https://localedgedatacenter.com) infrastructure — ephemeral VMs with a 4-hour TTL, automated provisioning via Proxmox + Cloudflare Tunnels, and self-destructing environments.

### Custom MCP servers (built in this fork)

| Server | What it does |
|--------|--------------|
| **`ollama-experts`** | Delegates config generation to local Ollama domain models (FRR, BGP, OSPF, Nautobot, RFC) — saves cloud tokens |
| **`protocol-mcp`** | Live BGP/OSPF/GRE control-plane participation via scapy — the agent peers with real routers |
| **`nautobot-mcp-v2`** | Full Nautobot SOT integration (GraphQL reads + REST writes, ITSM gating) |
| **`nautobot-routing-mcp`** | BGP/OSPF routing model CRUD against Nautobot's routing plugin |
| **`nautobot-golden-config-mcp`** | Golden config compliance and intended/actual/backup comparisons |
| **`gnmi-mcp`** | gNMI streaming telemetry (Get/Set/Subscribe/Capabilities) for IOS-XR, Juniper, Arista, Nokia |
| **`containerlab-mcp`** | Deploy/destroy/inspect ContainerLab topologies via the clab API |
| **`eve-ng-mcp-server`** | EVE-NG lab automation (topology build, node ops, console, config push) |
| **`gns3-mcp-server`** | GNS3 project lifecycle, node operations, packet captures, snapshots |
| **`syslog-mcp`** | Real-time syslog receiver — the agent sees device logs as they arrive |
| **`snmptrap-mcp`** | SNMP trap receiver — events flow directly to the agent |
| **`ipfix-mcp`** | NetFlow/IPFIX collector for flow-based traffic visibility |
| **`memory-mcp`** | Hybrid persistent memory (SQLite + ChromaDB embeddings) across sessions |
| **`suzieq-mcp`** | SuzieQ network observability (state queries, assertions, path tracing) |
| **`batfish-mcp`** | Offline config analysis via Batfish (reachability, routing, ACLs) |
| **`claroty-mcp`** | Claroty xDome OT/IoT/IoMT asset visibility and vulnerability triage |
| **`prisma-sdwan-mcp`** | Palo Alto Prisma SD-WAN read-only monitoring |
| **`azure-network-mcp`** | Azure networking (VNets, NSGs, ExpressRoute, VPN, Firewall, DNS) |
| **`gitlab-mcp`** | GitLab DevOps (issues, MRs, pipelines, repos) |
| **`jenkins-mcp`** | Jenkins CI/CD (jobs, builds, logs, SCM tracking) |

### Other experiments

- **`ui/netclaw-visual/`** — Three.js 3D operations dashboard that visualizes integrations, device fleet, and live BGP topology in the browser
- **`specs/`** — 37 numbered feature specs documenting the design process for each integration
- **`workspace/skills/`** — 180+ skill definitions covering everything from EVE-NG lab builds to Claroty OT triage to Zscaler Zero Trust
- **Token optimization** — TOON serialization for 40-60% token savings on tabular network data, real-time cost tracking per session

## Demo environment overview

```
┌─────────────────────────────────────────────────────────┐
│  Demo VM (4hr TTL, auto-provisioned)                    │
│                                                         │
│  OpenClaw Gateway ──► Claude claude-sonnet-4-5-20250929          │
│       │                                                 │
│       ├── nautobot-mcp ──► Nautobot (localhost:8080)    │
│       ├── nautobot-routing-mcp ──► BGP/OSPF models     │
│       ├── protocol-mcp ──► Live OSPF/BGP speakers      │
│       ├── ollama-experts ──► Local GPU domain models    │
│       └── rfc-lookup ──► IETF RFC search               │
│                                                         │
│  ContainerLab ──► 6x FRR routers (MPLS/BGP/OSPF)      │
│  Nautobot ──► Source of truth (devices, IPs, BGP)      │
│  NetClaw Visual ──► Three.js 3D ops dashboard          │
└─────────────────────────────────────────────────────────┘
```

## Running this yourself

If you want to replicate the demo environment:

1. **Start with the real NetClaw** — clone [automateyournetwork/netclaw](https://github.com/automateyournetwork/netclaw) and run `./scripts/install.sh`
2. **Copy the demo config** — use `config/openclaw-demo.json` as a reference for which MCP servers to enable
3. **Set up ContainerLab** — deploy the topology in `lab/frr-testbed/`
4. **Deploy Nautobot** — use [nautobot-docker-compose](https://github.com/nautobot/nautobot-docker-compose) with the routing models plugin
5. **Set environment variables** — see `.env.example` for all required vars

## Credits

- **NetClaw** by [John Capobianco](https://github.com/automateyournetwork) — the upstream project
- **OpenClaw** — the AI agent framework NetClaw runs on
- **Demo infrastructure** by [Byrn Baker](https://github.com/byrn-baker) / [LocalEdge Datacenter](https://localedgedatacenter.com)

## License

BSL-1.1 (Business Source License) — same as upstream NetClaw. Converts to Apache-2.0 after the change date.
