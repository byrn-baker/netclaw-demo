# MCP Tool Contracts: ContainerLab MCP Server

**Transport**: stdio
**Server Name**: `containerlab-mcp`

## Tool 1: deploy

**Description**: Deploy a ContainerLab topology from a YAML file

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| topology_file_path | string | yes | Absolute or relative path to the .clab.yml topology file |
| lab_name | string | no | Override the lab name defined in the topology YAML |
| reconfigure | boolean | no | Reconfigure an already-deployed lab without destroying it (default: false) |

**Returns**: StructuredResponse with `data.output` containing clab deploy stdout.

**Errors**:
- `TOPOLOGY_NOT_FOUND`: Topology file does not exist
- `DEPLOY_FAILED`: clab deploy returned non-zero exit code

---

## Tool 2: destroy

**Description**: Destroy a deployed ContainerLab topology with safety confirmation

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| topology_file_path | string | no | Path to the .clab.yml topology file |
| lab_name | string | no | Lab name to destroy (alternative to topology_file_path) |
| cleanup_artifacts | boolean | no | Remove lab directory and artifacts after destroy (default: false) |
| confirm_topology_name | string | yes | Must exactly match the target lab name (case-sensitive) |
| confirm_cleanup | boolean | no | Required when cleanup_artifacts=true; must be true |

**Constraints**: Either `topology_file_path` or `lab_name` must be provided. `confirm_topology_name` must match exactly.

**Returns**: StructuredResponse with `data.output` containing clab destroy stdout.

**Errors**:
- `SAFETY_REJECTED`: Confirmation mismatch — no CLI command executed
- `DESTROY_FAILED`: clab destroy returned non-zero exit code

---

## Tool 3: inspect

**Description**: Inspect running ContainerLab topologies and list node details

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| topology_name | string | no | Filter results to a specific topology name |
| lab_name | string | no | Filter results to a specific lab name |

**Returns**: StructuredResponse with `data` as a list of node record dicts (name, lab_name, container_id, ipv4_address, state).

---

## Tool 4: save

**Description**: Save running ContainerLab topology configuration to disk

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| topology_file_path | string | no | Path to the .clab.yml topology file |
| lab_name | string | no | Lab name to save |

**Returns**: StructuredResponse with `data.output` containing clab save stdout.

---

## Tool 5: graph

**Description**: Generate a topology graph visualization from a topology file

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| topology_file_path | string | yes | Path to the .clab.yml topology file to visualize |
| output_format | string | no | Output format: "html", "mermaid", "draw.io" (default: "html") |

**Returns**: StructuredResponse with `data.output` containing clab graph stdout.

---

## Tool 6: generate

**Description**: Generate a new ContainerLab topology file with specified parameters

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| topology_file_path | string | yes | File path where the generated topology will be written |
| node_count | integer | no | Number of nodes (default: 2) |
| topology_type | string | no | Topology pattern: "ring", "full-mesh", "linear" (default: "ring") |

**Returns**: StructuredResponse with `data.output` containing clab generate stdout.

---

## Tool 7: version

**Description**: Get the installed ContainerLab version information

**Parameters**: None

**Returns**: StructuredResponse with `data.output` containing version string.

---

## Tool 8: node_exec

**Description**: Execute a command inside a running containerlab node container

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| lab_name | string | yes | Name of the deployed lab |
| node_name | string | yes | Name of the node within the lab |
| exec_command | string | yes | Command to execute (max 4096 characters) |

**Constraints**: `exec_command` must be ≤ 4096 characters. Node must exist in the lab.

**Returns**: Dict with `status`, `stdout`, `stderr`, `exit_code`, `command`, `duration_ms`.

**Errors**:
- `COMMAND_TOO_LONG`: Command exceeds 4096 characters
- `NODE_NOT_FOUND`: Node name not in lab; error includes list of valid names
- `TIMEOUT`: Command exceeded 30-second timeout

---

## Tool 9: get_node_access

**Description**: Get access information for nodes in a running containerlab topology

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| lab_name | string | yes | Name of the deployed lab |
| topology_file_path | string | no | Path to .clab.yml for enhanced access detection |

**Returns**: StructuredResponse with `data` as a list of NodeAccessInfo dicts.

---

## Tool 10: list_topologies

**Description**: Discover ContainerLab topology files in configured search paths

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| search_paths | string | no | Colon-separated directory paths to scan (default: server config) |

**Returns**: StructuredResponse with `data` as a list of TopologyEntry dicts (path, lab_name, node_count).

---

## Tool 11: get_topology_details

**Description**: Parse a ContainerLab topology file and return structured details

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| topology_file_path | string | yes | Absolute path to the .clab.yml file to parse |

**Returns**: StructuredResponse with `data` as TopologyDetails dict (name, nodes, links, kind).

---

## Tool 12: lab_status

**Description**: Return status of all currently deployed ContainerLab instances

**Parameters**: None

**Returns**: StructuredResponse with `data` as a list of LabInstance dicts (topology_name, node_count, deployed_at).

---

## Tool 13: node_health

**Description**: Return container resource usage for a specific lab node

**Parameters**:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| node_name | string | yes | Full container name (e.g., "clab-dc-lab-spine1") |

**Returns**: StructuredResponse with `data` as NodeHealth dict (cpu_percent, memory_bytes, memory_percent, uptime_seconds).

**Errors**:
- `CONTAINER_NOT_FOUND`: Container name not found or not running
