# Quickstart: ContainerLab MCP Server

## Prerequisites

1. **ContainerLab**: The `clab` binary must be on PATH
2. **Docker**: Container runtime for lab nodes
3. **Python 3.11+**: For the MCP server
4. **NetClaw**: Existing NetClaw/OpenClaw installation

## Step 1: Install ContainerLab

```bash
bash -c "$(curl -sL https://get.containerlab.dev)"
```

Verify installation:
```bash
clab version
```

## Step 2: Install Dependencies

```bash
cd mcp-servers/containerlab-mcp/
pip install -r requirements.txt
```

## Step 3: Configure Environment

Add to your `.env` file or export directly:
```bash
# Directories to scan for .clab.yml topology files
CLAB_MCP_TOPOLOGY_PATHS=/home/user/labs:/opt/topologies

# Log level (optional, default: info)
CLAB_MCP_LOG_LEVEL=info

# For remote execution (optional)
# CLAB_MCP_REMOTE=admin@clab-host
# CLAB_MCP_SSH_KEY_PATH=~/.ssh/id_rsa
```

## Step 4: Register in OpenClaw

The MCP server is registered in `config/openclaw.json`. Verify:
```bash
python3 -c "import json; d=json.load(open('config/openclaw.json')); print(json.dumps(d['mcpServers']['containerlab-mcp'], indent=2))"
```

## Step 5: Test the Server

```bash
# Start the server directly (for testing)
python3 -u mcp-servers/containerlab-mcp/containerlab_mcp_server.py
```

## Example Usage

### Discover Available Topologies

```
Use the list_topologies tool with:
- search_paths: "/home/user/labs" (optional, uses configured paths if omitted)
```

### Deploy a Lab

```
Use the deploy tool with:
- topology_file_path: "/home/user/labs/dc-fabric.clab.yml"
- lab_name: "dc-fabric" (optional override)
```

### Check Lab Status

```
Use the lab_status tool (no parameters required)
```

### Execute Command on a Node

```
Use the node_exec tool with:
- lab_name: "dc-fabric"
- node_name: "spine1"
- exec_command: "ip address show"
```

### Get Node Access Information

```
Use the get_node_access tool with:
- lab_name: "dc-fabric"
- topology_file_path: "/home/user/labs/dc-fabric.clab.yml"
```

### Destroy a Lab (with safety confirmation)

```
Use the destroy tool with:
- topology_file_path: "/home/user/labs/dc-fabric.clab.yml"
- confirm_topology_name: "dc-fabric"  (must match exactly, case-sensitive)
- cleanup_artifacts: false
```

### Check Node Health

```
Use the node_health tool with:
- node_name: "clab-dc-fabric-spine1"
```
