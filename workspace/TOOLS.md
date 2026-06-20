# TOOLS.md — Local Infrastructure Notes

Skills define *how* tools work. This file is for *your* specifics — the environment details that are unique to your deployment.

## Network Devices

Devices are defined in `testbed/testbed.yaml`. IPs are assigned by containerlab on deploy.
Update after: `sudo clab inspect -t lab/demo-sp/demo-sp.clab.yml`

```
### Device Map (demo-sp — containerlab FRR)
- PE1 → 172.20.20.11, Provider Edge, FRR (AS 65000)
- P1  → 172.20.20.12, Core P-router, FRR
- P2  → 172.20.20.13, Core P-router, FRR
- P3  → 172.20.20.14, Core P-router, FRR
- P4  → 172.20.20.15, Core P-router, FRR
- RR1 → 172.20.20.16, Route Reflector, FRR (AS 65000)
```

## Lab Topologies

```
### Containerlab — demo-sp (6-node SP Core)
- Topology: lab/demo-sp/demo-sp.clab.yml
- Nodes: PE1, P1, P2, P3, P4, RR1 (all FRR)
- Underlay: OSPF area 0, iBGP AS 65000, RR1 = route reflector
- Deploy: sudo clab deploy -t lab/demo-sp/demo-sp.clab.yml

### Docker Compose — frr-testbed (IPv6-only, OSPFv3 + MP-BGP)
- Topology: lab/frr-testbed/docker-compose.yml
- Nodes: edge1 (AS 65000), core (RR), edge2 — plus GRE tunnel to WSL NetClaw (AS 65001)
- Address plan: ULA fd00::/48, /127 P2P links
- Deploy: cd lab/frr-testbed && docker compose up -d
```

## Platform Credentials

All credentials are in `~/.openclaw/.env`. Never put credentials in skill files or this document.

```
### Batfish Configuration Analysis (reference only — actual values in .env)
- Batfish Host        → BATFISH_HOST (default: localhost)
- Batfish Port        → BATFISH_PORT (default: 9997)
- Batfish Network     → BATFISH_NETWORK (default: netclaw)
- Docker Container    → batfish/batfish (ports 9997, 9996)

### Connection Details (reference only — actual values in .env)
- pyATS Testbed       → PYATS_TESTBED_PATH
- NetBox              → NETBOX_URL, NETBOX_TOKEN
- ServiceNow          → SERVICENOW_INSTANCE_URL, SERVICENOW_USERNAME, SERVICENOW_PASSWORD
- Cisco APIC          → APIC_URL, APIC_USERNAME, APIC_PASSWORD
- Cisco ISE           → ISE_BASE, ISE_USERNAME, ISE_PASSWORD
- NVD API             → NVD_API_KEY
- F5 BIG-IP           → F5_IP_ADDRESS, F5_AUTH_STRING
- Catalyst Center     → CCC_HOST, CCC_USER, CCC_PWD
- Microsoft Graph     → AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
- SuzieQ              → SUZIEQ_API_URL, SUZIEQ_API_KEY
- gNMI Telemetry      → GNMI_TARGETS (JSON), GNMI_TLS_CA_CERT, GNMI_TLS_CLIENT_CERT, GNMI_TLS_CLIENT_KEY
- Azure Network MCP   → AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_SUBSCRIPTION_ID
- Canvas/A2UI Viz     → No new credentials (uses existing MCP server connections)
- Token Optimization  → ANTHROPIC_API_KEY (reused), NETCLAW_TOKEN_PRICING_OVERRIDE (optional)
- GitLab MCP          → GITLAB_PERSONAL_ACCESS_TOKEN, GITLAB_API_URL (default: gitlab.com)
- Jenkins MCP         → JENKINS_URL, JENKINS_AUTH_BASE64 (remote HTTP, Basic Auth)
- Nautobot            → NAUTOBOT_URL, NAUTOBOT_TOKEN, NAUTOBOT_VERIFY_SSL, NAUTOBOT_TIMEOUT
- EVE-NG              → EVE_URL, EVE_USER, EVE_PASSWORD, EVE_VERIFY_SSL, EVE_CONSOLE_HOST
- GNS3                → GNS3_URL, GNS3_USER, GNS3_PASSWORD, GNS3_VERIFY_SSL
- Prisma SD-WAN       → PAN_CLIENT_ID, PAN_CLIENT_SECRET, PAN_TSG_ID, PAN_REGION
- Datadog             → DD_API_KEY, DD_APP_KEY, DD_SITE
- PagerDuty           → PAGERDUTY_USER_API_KEY, PAGERDUTY_API_HOST
- Splunk              → SPLUNK_HOST, SPLUNK_TOKEN, SPLUNK_VERIFY_SSL
- Terraform Cloud     → TFC_TOKEN, TFC_ORG, TFC_HOST
- HashiCorp Vault     → VAULT_ADDR, VAULT_TOKEN, VAULT_NAMESPACE
- Zscaler ZIA/ZPA     → ZSCALER_ZIA_API_KEY, ZSCALER_ZIA_USERNAME, ZSCALER_ZIA_PASSWORD, ZSCALER_ZIA_CLOUD, ZSCALER_ZPA_CLIENT_ID, ZSCALER_ZPA_CLIENT_SECRET, ZSCALER_ZPA_CUSTOMER_ID
- Cloudflare          → CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID
- Aruba CX            → ARUBA_CX_TARGETS, ARUBA_CX_CONFIG, ARUBA_CX_TIMEOUT
- Protocol MCP        → NETCLAW_ROUTER_ID, NETCLAW_LOCAL_AS, NETCLAW_BGP_PEERS, NETCLAW_OSPF_AREAS, NETCLAW_GRE_TUNNELS, NETCLAW_LAB_MODE
- IPFIX/NetFlow       → IPFIX_PORT (default: 2055), IPFIX_BIND_ADDRESS, IPFIX_RETENTION_HOURS
- SNMP Trap           → SNMPTRAP_PORT (default: 162), SNMPTRAP_BIND_ADDRESS, SNMPTRAP_RETENTION_HOURS
- Syslog              → SYSLOG_PORT (default: 514), SYSLOG_BIND_ADDRESS, SYSLOG_RETENTION_HOURS
- Atlassian           → JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN, CONFLUENCE_URL, CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN
- DevNet Search       → No credentials (public endpoint: https://devnet.cisco.com/v1/foundation-search-mcp/mcp)
```

## GitLab MCP Server

The GitLab MCP server (`@zereight/mcp-gitlab`) provides 98+ tools for GitLab operations via stdio transport:
- **Issues**: list_issues, get_issue, create_issue, update_issue, add_issue_comment, list_issue_comments
- **Merge Requests**: list_merge_requests, get_merge_request, create_merge_request, update_merge_request, merge_merge_request, add_merge_request_comment
- **Pipelines**: list_pipelines, get_pipeline, get_pipeline_jobs, get_pipeline_job_log, create_pipeline, retry_pipeline, cancel_pipeline
- **Repository**: list_repository_tree, get_file_content, list_commits, get_commit, compare_branches
- **Projects**: list_projects, get_project, search_projects
- **Labels**: list_labels, create_label, update_label, delete_label
- **Milestones**: list_milestones, create_milestone, update_milestone
- **Releases**: list_releases, get_release, create_release
- **Wiki**: list_wiki_pages, get_wiki_page, create_wiki_page, update_wiki_page, delete_wiki_page
- Supports gitlab.com and self-hosted instances via `GITLAB_API_URL`
- Read-only mode available via `GITLAB_READ_ONLY_MODE=true`

## Jenkins MCP Server

The Jenkins MCP server (official Jenkins plugin) provides 16 tools via Streamable HTTP transport:
- **Job Management**: getJob, getJobs, triggerBuild, getQueueItem
- **Build Operations**: getBuild, updateBuild, getBuildLog, searchBuildLog
- **SCM Integration**: getJobScm, getBuildScm, getBuildChangeSets, findJobsWithScmUrl
- **System**: whoAmI, getStatus
- **Pipeline**: getPipelineRuns, getPipelineRunLog
- Remote HTTP server running inside Jenkins (Streamable HTTP at `/mcp-server/mcp`)
- Auth: HTTP Basic with Jenkins API token (Base64-encoded username:token)
- Requires Jenkins 2.533+ with MCP Server plugin v0.158+

## Atlassian MCP Server

The Atlassian MCP server (community mcp-atlassian by sooperset) provides 72 tools via stdio transport:
- **Jira Issues**: jira_search, jira_get_issue, jira_create_issue, jira_update_issue, jira_delete_issue, jira_add_comment, jira_batch_create_issues
- **Jira Transitions**: jira_get_transitions, jira_transition_issue
- **Jira Projects/Fields**: jira_get_projects, jira_get_project, jira_get_fields, jira_get_issue_types
- **Jira Links**: jira_link_issues, jira_get_issue_links, jira_get_link_types
- **Confluence Pages**: confluence_search, confluence_get_page, confluence_create_page, confluence_update_page, confluence_delete_page
- **Confluence Comments**: confluence_get_page_comments, confluence_add_comment
- **Confluence Spaces**: confluence_get_spaces, confluence_get_space
- Supports Atlassian Cloud and Server/Data Center deployments
- Auth: API token (Cloud) or Personal Access Token (Server/DC)
- Runs via `uvx mcp-atlassian`

## EVE-NG MCP Server

MCP server for managing EVE-NG network lab environments via stdio transport:
- **Lab Lifecycle**: List, inspect, create, delete, export, and import `.unl` lab files
- **Node Operations**: Add/remove nodes from templates, start/stop individual nodes or whole labs, wipe to factory defaults
- **Network & Topology**: Create virtual bridges, wire node interfaces to networks, inspect full topology
- **Console Execution**: Full telnet console access for IOS/IOL, Junos, VPCS, Arista EOS, NX-OS — mode-aware with automatic bootstrap
- **Config Management**: Read, push, and clear node startup configs; bulk-export all configs
- **System**: EVE-NG status, available images, authentication check
- Supports EVE-NG Community and Professional (tested on Community 6.x)
- Cookie auth with short-lived GET response caching, pagination on high-cardinality tools

## GNS3 MCP Server

MCP server for managing GNS3 network lab environments via stdio transport:
- **Project Lifecycle**: Create, open, close, delete, clone, export/import GNS3 projects
- **Node Operations**: Add nodes from templates, start/stop/suspend/reload, access consoles
- **Link Management**: Create and delete links between node interfaces, isolate nodes
- **Packet Capture**: Start/stop captures on links, retrieve PCAP data
- **Snapshot Management**: Create, restore, and delete project snapshots
- Requires GNS3 Server 2.2.0+ with REST API v3

## Protocol MCP Server (BGP/OSPF/GRE)

Live control-plane participation via 10 tools (source: WontYouBeMyNeighbour):
- **BGP**: bgp_get_peers, bgp_get_rib, bgp_inject_route, bgp_withdraw_route, bgp_adjust_local_pref
- **OSPF**: ospf_get_neighbors, ospf_get_lsdb, ospf_adjust_cost
- **GRE**: gre_tunnel_status
- **Meta**: protocol_summary
- Enables NetClaw to participate as a real BGP/OSPF speaker in the lab topology
- Used with the FRR testbed for live route injection, convergence testing, and path manipulation

## Nautobot MCP Servers (3 servers)

Three specialized Nautobot MCP servers via stdio transport:
- **nautobot-mcp-v2**: Core IPAM/DCIM — devices, interfaces, IPs, prefixes, sites, tenants, circuits
- **nautobot-golden-config-mcp**: Golden config compliance — intended vs actual config diffs, remediation jobs
- **nautobot-routing-mcp**: BGP/OSPF routing models — peerings, ASNs, route policies, prefix lists
- All share NAUTOBOT_URL/NAUTOBOT_TOKEN credentials, ITSM lab mode supported

## IPFIX/NetFlow MCP Server

Receives and queries flow records over UDP:
- **Protocols**: NetFlow v5, NetFlow v9 (template-based), IPFIX (RFC 7011)
- **Tools**: Query flows by IPs/ports/protocol/exporter/time, top talkers analysis
- Template caching with 30-min expiration, hash-based deduplication, token bucket rate limiting
- Default port: 2055

## SNMP Trap MCP Server

Receives and queries SNMP traps over UDP:
- **Protocols**: SNMPv1, SNMPv2c, SNMPv3 (USM)
- **Tools**: Query traps by time, source, version, or OID
- In-memory storage with configurable retention, deduplication, rate limiting
- Default port: 162

## Syslog MCP Server

Receives and queries syslog messages over UDP/TCP:
- **Formats**: RFC 5424 (structured data), RFC 3164 (BSD/Cisco-style)
- **Tools**: Query messages by time, severity, facility, hostname, or content
- In-memory storage with configurable retention, deduplication, rate limiting
- Default port: 514

## Prisma SD-WAN MCP Server

Palo Alto Prisma SD-WAN management via stdio transport:
- Site/branch management, policy control, path quality monitoring
- Auth: OAuth2 via PAN Cloud Services (TSG-scoped)

## Datadog MCP Server

Datadog observability platform via remote MCP (`mcp://datadog.com/mcp`):
- Metrics queries, log search, APM traces, monitors, dashboards
- Auth: DD_API_KEY + DD_APP_KEY

## PagerDuty MCP Server

Incident management via stdio (`uvx pagerduty-mcp --enable-write-tools`):
- Incidents, services, escalation policies, on-call schedules
- Write tools enabled for incident creation/acknowledgment/resolution

## Splunk MCP Server

Splunk log/event search via stdio (`uvx splunk-mcp`):
- SPL queries, saved searches, alerts, dashboards
- Auth: Splunk Bearer token

## Terraform Cloud MCP Server

Terraform Cloud/Enterprise via remote MCP (`mcp://terraform.io/mcp`):
- Workspaces, runs, state, variables, policy checks
- Auth: TFC API token

## HashiCorp Vault MCP Server

Secrets management via remote MCP (`mcp://vault.hashicorp.com/mcp`):
- Secret read/write, dynamic credentials, PKI, transit encryption
- Auth: Vault token, namespace-aware

## Zscaler MCP Server

Zscaler ZIA + ZPA security via remote MCP (`mcp://zscaler.com/mcp`):
- ZIA: URL filtering, firewall policies, DLP, SSL inspection
- ZPA: Application segments, server groups, access policies

## Cloudflare MCP Servers (5 servers)

Cloudflare platform via remote MCP endpoints:
- **dns-analytics**: DNS queries, analytics, zone management
- **security**: WAF rules, rate limiting, bot management, DDoS
- **zero-trust**: Access policies, tunnels, WARP, Gateway
- **analytics**: Web analytics, performance metrics
- **workers**: Workers deployment, KV storage, Durable Objects
- All share CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID

## Aruba CX MCP Server

Aruba CX switch management via stdio transport:
- REST API access to AOS-CX switches
- Configuration, monitoring, interface management
- Multi-target support via ARUBA_CX_TARGETS JSON

## DevNet Content Search MCP Server

Cisco DevNet documentation search via remote MCP (`https://devnet.cisco.com/v1/foundation-search-mcp/mcp`):
- Search Cisco developer documentation, API references, guides
- No credentials required (public endpoint)

## Blender MCP Server

Blender 3D visualization via stdio (`uvx blender-mcp`):
- 3D network topology visualization and rendering
- Scene manipulation, object creation, material assignment

## Token Optimization Infrastructure

The `netclaw_tokens` shared library (`src/netclaw_tokens/`) provides token counting, TOON serialization, and cost tracking:
- **counter.py** — Token counting via Anthropic `count_tokens()` API with `len/4` fallback
- **toon_serializer.py** — TOON format serialization for MCP responses (40-60% savings on tabular data)
- **cost_calculator.py** — Model-aware pricing: Opus ($5/$25), Sonnet ($3/$15), Haiku ($1/$5) per 1M tokens
- **session_ledger.py** — Thread-safe cumulative session tracking with per-tool breakdown
- **footer.py** — Mandatory token/cost footer formatter for every interaction
- **toon_wrapper.py** — TOON conversion wrapper for community/remote MCP servers
- Pricing override via `NETCLAW_TOKEN_PRICING_OVERRIDE` env var (JSON format)
- Prompt caching discount: 90% off cached input tokens
- Demo config uses Qwen 3.5 397B (ollama) with zero-cost pricing

## gNMI Infrastructure

The gNMI MCP server provides 10 tools for streaming telemetry and model-driven configuration:
- **gnmi_get** / **gnmi_set** / **gnmi_subscribe** / **gnmi_unsubscribe** / **gnmi_get_subscriptions** / **gnmi_get_subscription_updates** / **gnmi_capabilities** / **gnmi_browse_yang_paths** / **gnmi_compare_with_cli** / **gnmi_list_targets**
- Supported vendors: Cisco IOS-XR (port 57400), Juniper (32767), Arista (6030), Nokia SR OS (57400)
- YANG models: OpenConfig and vendor-native
- TLS mandatory, mTLS supported, max 50 concurrent subscriptions

## Slack Integration

```
### Channels
- #netclaw-alerts     → P1/P2 critical alerts
- #netclaw-reports    → Scheduled health reports, audit results
- #netclaw-general    → General queries, P3/P4 notifications
- #incidents          → Active incident threads
```

## Microsoft Teams Integration

```
### Teams Channels (if using Microsoft Graph for Teams delivery)
- #netclaw-alerts     → P1/P2 critical alerts, CVE exposure
- #netclaw-reports    → Health reports, audit results, reconciliation
- #netclaw-changes    → Change request updates, completion notices
- #network-general    → P3/P4 notifications, topology updates

### SharePoint Sites
- Network Engineering → Topology diagrams, audit reports, config backups
```

## SSH Access

```
### Jump Hosts / Bastion
- (your bastion host, if applicable)

### Console Servers
- (your console server, if applicable)
```

## Site Information

```
### Sites
- Site-A → Primary data center
- Site-B → DR site
- Lab    → Non-production test environment (relaxed change control)
```

## MemPalace AI Memory

19 MCP tools for persistent, structured, local-only AI memory across sessions ([source](https://github.com/milla-jovovich/mempalace)):
- **Palace**: status, wings, rooms, taxonomy, search, duplicates, AAAK spec, add/delete drawers
- **Knowledge Graph**: entity query, add/invalidate temporal triples, timeline, stats
- **Navigation**: room traversal, cross-wing tunnels, graph stats
- **Agent Diary**: write/read specialist agent journals (AAAK-compressed)
- Transport: stdio, Python 3.9+, no credentials, fully offline
- `MEMPALACE_MCP_SCRIPT` → cloned repo `mcp_server.py`

## Notes

- Add whatever helps NetClaw do its job — device nicknames, maintenance windows, ISP circuit IDs, TAC case numbers, anything environment-specific.
- This file is yours. Skills are shared. Keeping them apart means you can update skills without losing your notes.
