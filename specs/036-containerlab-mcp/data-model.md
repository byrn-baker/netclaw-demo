# Data Model: ContainerLab MCP Server

**Feature Branch**: `036-containerlab-mcp`
**Date**: 2026-06-15

## Entities

### StructuredResponse

Base response for all tool invocations.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| status | Literal["success", "error"] | Operation outcome | Required; exactly "success" or "error" |
| data | dict \| list \| None | Operation result payload | Present when status="success" |
| command | str | CLI command that was executed | Required; non-empty string |
| duration_ms | int | Wall-clock execution time in milliseconds | Required; >= 0 |
| message | str \| None | Error description | Present when status="error" |
| code | int \| None | CLI exit code on error | Optional; 1-255 on error |

**Notes**: If status is "success", `data` SHALL be present. If status is "error", `message` SHALL be present.

---

### ExecutionResult

Internal result from CLI execution (not exposed to agents directly).

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| stdout | str | Standard output capture | Required |
| stderr | str | Standard error capture | Required |
| exit_code | int | Process exit code | Required; -1 for timeout |
| duration_ms | int | Execution time in milliseconds | Required; >= 0 |
| command | str | The full command string | Required |

---

### TopologyEntry

Discovered topology file metadata (returned by `list_topologies`).

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| path | str | Absolute path to the .clab.yml file | Required; absolute path |
| lab_name | str | Lab name derived from topology YAML | Required; non-empty |
| node_count | int | Number of nodes defined | Required; >= 0 |

---

### TopologyDetails

Parsed topology content (returned by `get_topology_details`).

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| name | str | Topology/lab name | Required |
| nodes | list[NodeDefinition] | Node definitions | Required |
| links | list[LinkDefinition] | Link definitions | Required |
| kind | str \| None | Default node kind | Optional |

### NodeDefinition

| Field | Type | Description |
|-------|------|-------------|
| name | str | Node identifier |
| kind | str | Node kind (srl, ceos, linux, etc.) |
| image | str \| None | Container image |
| startup_config | str \| None | Path to startup configuration |

### LinkDefinition

| Field | Type | Description |
|-------|------|-------------|
| endpoints | list[str] | Two endpoint strings (e.g., ["srl1:e1-1", "srl2:e1-1"]) |

---

### NodeAccessInfo

Access information for a running node (returned by `get_node_access`).

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| node_name | str | Node identifier | Required |
| container_id | str | Docker container ID | Required |
| mgmt_ipv4 | str \| None | Management IPv4 address | Optional |
| mgmt_ipv6 | str \| None | Management IPv6 address | Optional |
| access_method | Literal["ssh", "docker_exec", "clab_connect"] | Connection method | Required |
| connection_command | str | Shell-ready command to access the node | Required; non-empty |
| username | str \| None | SSH username | Present when access_method="ssh" |
| password | str \| None | SSH password | Present when access_method="ssh" |

---

### ServerConfig

Server runtime configuration.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| transport | Literal["stdio", "sse"] | Transport mode | Default: "stdio" |
| host | str | SSE listener bind address | Default: "0.0.0.0" |
| port | int | SSE listener port | Default: 8080; range 1-65535 |
| topology_paths | list[str] | Directories to scan for topologies | Default: ["."] |
| log_level | Literal["debug", "info", "warning", "error"] | Logging level | Default: "info" |
| remote | str \| None | SSH target (user@host) | Optional |
| ssh_key_path | str \| None | SSH private key path | Optional |
| ssh_port | int | SSH port | Default: 22 |

---

### LabInstance

A running lab deployment (returned by `lab_status`).

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| topology_name | str | Lab name | Required |
| node_count | int | Number of containers | Required; >= 0 |
| deployed_at | str | ISO 8601 UTC timestamp | Required |

---

### NodeHealth

Container resource usage (returned by `node_health`).

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| node_name | str | Container name | Required |
| cpu_percent | float | CPU usage percentage | Required; 0.0-100.0 |
| memory_bytes | int | Memory usage in bytes | Required; >= 0 |
| memory_percent | float | Memory usage percentage | Required; 0.0-100.0 |
| uptime_seconds | int | Container uptime | Required; >= 0 |

---

### ValidationResult

Safety gate validation outcome (internal).

| Field | Type | Description |
|-------|------|-------------|
| passed | bool | Whether validation passed |
| error_message | str \| None | Reason for rejection (None if passed) |
