# Batfish MCP Server

First-of-its-kind MCP server wrapping the [Batfish](https://www.batfish.org/) network configuration analysis platform via [pybatfish](https://pybatfish.readthedocs.io/).

## Overview

- **Transport**: stdio
- **Language**: Python 3.10+
- **Tools**: 8
- **Read-only**: Analysis only, never touches live devices
- **GAIT**: All operations logged

## Prerequisites

1. **Docker** -- Batfish runs as a container:
   ```bash
   docker run -d --name batfish -p 9997:9997 -p 9996:9996 batfish/batfish
   ```

2. **Python 3.10+** with pip

## Installation

```bash
cd mcp-servers/batfish-mcp/
pip install -r requirements.txt
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BATFISH_HOST` | No | `localhost` | Batfish service hostname or IP |
| `BATFISH_PORT` | No | `9997` | Batfish coordinator port |
| `BATFISH_NETWORK` | No | `netclaw` | Default Batfish network name |

## Tools (8)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `batfish_upload_snapshot` | `snapshot_name`, `configs` or `config_path`, `network` | Upload device configs and create a Batfish snapshot |
| `batfish_validate_config` | `snapshot_name`, `network` | Validate configs with per-device pass/fail report |
| `batfish_test_reachability` | `snapshot_name`, `src_ip`, `dst_ip`, `protocol`, `dst_port`, `src_port`, `network` | Test traffic reachability between endpoints |
| `batfish_trace_acl` | `snapshot_name`, `device`, `filter_name`, `src_ip`, `dst_ip`, `protocol`, `dst_port`, `network` | Trace packet through ACL/firewall rules |
| `batfish_diff_configs` | `reference_snapshot`, `candidate_snapshot`, `include_routes`, `include_reachability`, `network` | Compare two snapshots for routing/reachability differences |
| `batfish_check_compliance` | `snapshot_name`, `policy_type`, `network` | Check configs against compliance policies |
| `batfish_list_snapshots` | `network` | List all snapshots in a network |
| `batfish_delete_snapshot` | `snapshot_name`, `network` | Delete a snapshot |

## Supported Compliance Policies

- `interface_descriptions` -- All interfaces must have descriptions
- `no_default_route` -- No default routes (0.0.0.0/0)
- `ntp_configured` -- NTP servers must be configured
- `no_shutdown_interfaces` -- No administratively down interfaces
- `bgp_sessions_established` -- All BGP sessions established
- `ospf_adjacencies` -- All OSPF adjacencies compatible

## Multi-Vendor Support

Batfish natively supports: Cisco IOS, IOS-XE, NX-OS, Juniper JunOS, Arista EOS, Palo Alto, F5.

## Running

```bash
python batfish_mcp_server.py
```
