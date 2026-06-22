# ContainerLab MCP Server

MCP server wrapping the [ContainerLab](https://containerlab.dev/) CLI for managing container-based network lab topologies. Exposes all ContainerLab operations as structured MCP tools for NetClaw AI agents.

## Overview

- **Transport**: stdio
- **Language**: Python 3.11+
- **Tools**: 13
- **Safety**: Destructive operations require explicit confirmation (safety gate)
- **Execution**: Local or remote via SSH

## Tools (13)

| # | Tool | Description | Safety |
|---|------|-------------|--------|
| 1 | `deploy` | Deploy a topology from a YAML file | Write |
| 2 | `destroy` | Destroy a deployed topology (safety-gated) | Write — requires confirmation |
| 3 | `inspect` | List running labs and node details | Read-only |
| 4 | `save` | Save running topology configuration to disk | Write |
| 5 | `graph` | Generate a topology graph visualization | Read-only |
| 6 | `generate` | Generate a new topology YAML file | Write |
| 7 | `version` | Get installed ContainerLab version | Read-only |
| 8 | `node_exec` | Execute a command inside a running node container | Write |
| 9 | `get_node_access` | Get connection/access info for lab nodes | Read-only |
| 10 | `list_topologies` | Discover .clab.yml files in search paths | Read-only |
| 11 | `get_topology_details` | Parse topology YAML and return structured details | Read-only |
| 12 | `lab_status` | Return status of all deployed lab instances | Read-only |
| 13 | `node_health` | Return CPU/memory/uptime for a node container | Read-only |

## Transport

**stdio** — FastMCP over standard input/output (JSON-RPC).

## Prerequisites

- [ContainerLab](https://containerlab.dev/install/) (`clab` binary on PATH)
- Docker Engine (used by ContainerLab for node containers)
- Python 3.11+

## Installation

```bash
cd mcp-servers/containerlab-mcp
pip install -r requirements.txt
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CLAB_MCP_TOPOLOGY_PATHS` | No | `.` | Colon-separated directories to scan for .clab.yml files |
| `CLAB_MCP_LOG_LEVEL` | No | `info` | Log level: debug, info, warning, error |
| `CLAB_MCP_REMOTE` | No | - | Remote SSH target (user@host) for remote execution |
| `CLAB_MCP_SSH_KEY_PATH` | No | - | SSH private key path for remote execution |
| `CLAB_MCP_SSH_PORT` | No | `22` | SSH port for remote execution |
| `CLAB_MCP_TRANSPORT` | No | `stdio` | Transport mode: stdio or sse |
| `CLAB_MCP_HOST` | No | `0.0.0.0` | Host for SSE transport listener |
| `CLAB_MCP_PORT` | No | `8080` | Port for SSE transport listener |

## Usage

### As MCP Server (stdio transport)

```bash
python3 -u containerlab_mcp_server.py
```

### With remote execution

```bash
CLAB_MCP_REMOTE=admin@clab-host CLAB_MCP_SSH_KEY_PATH=~/.ssh/id_rsa \
  python3 -u containerlab_mcp_server.py
```

### Register in OpenClaw

Add to `config/openclaw.json`:

```json
{
  "mcpServers": {
    "containerlab-mcp": {
      "command": "python3",
      "args": ["-u", "mcp-servers/containerlab-mcp/containerlab_mcp_server.py"],
      "env": {
        "CLAB_MCP_TOPOLOGY_PATHS": "${CLAB_MCP_TOPOLOGY_PATHS:-.}",
        "CLAB_MCP_LOG_LEVEL": "${CLAB_MCP_LOG_LEVEL:-info}",
        "CLAB_MCP_REMOTE": "${CLAB_MCP_REMOTE}",
        "CLAB_MCP_SSH_KEY_PATH": "${CLAB_MCP_SSH_KEY_PATH}",
        "CLAB_MCP_SSH_PORT": "${CLAB_MCP_SSH_PORT:-22}"
      }
    }
  }
}
```

### Docker

```bash
docker build -t containerlab-mcp .
docker run --env-file .env -v /var/run/docker.sock:/var/run/docker.sock containerlab-mcp
```

## Safety Gate (Destroy Protection)

The `destroy` tool requires explicit confirmation to prevent accidental topology destruction:

- `confirm_topology_name` must exactly match the target lab name (case-sensitive)
- If `cleanup_artifacts=True`, `confirm_cleanup=True` must also be set
- Mismatched confirmations return an error without executing any CLI command

## Security

- Error messages are sanitized (no absolute paths or credentials leaked)
- stderr output is truncated to 4096 characters
- SSH connections use key-based authentication
- Remote command timeouts: 30s connect, 120s execution
- All operations are logged to the GAIT audit trail

## Dependencies

- mcp[cli] (MCP framework)
- pydantic (data models and validation)
- pyyaml (topology YAML parsing)
- asyncssh (remote SSH execution)
- click (CLI argument parsing)
