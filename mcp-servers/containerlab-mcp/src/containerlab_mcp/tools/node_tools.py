"""Node interaction tools for ContainerLab MCP Server.

Provides `node_exec` and `get_node_access` tools for executing commands
on running lab nodes and retrieving node access information.
"""

from __future__ import annotations

import logging
from typing import Any

from containerlab_mcp.server import ServerContext, mcp

logger = logging.getLogger(__name__)

# Maximum allowed command length for node_exec
MAX_COMMAND_LENGTH = 4096


def _get_context(ctx) -> ServerContext:
    """Extract the ServerContext from the MCP request context."""
    return ctx.request_context.lifespan_context


async def _get_running_nodes(ctx) -> tuple[list[dict[str, str]], str | None, int]:
    """Get running nodes by calling `clab inspect --all` and parsing the table output.

    Returns:
        A tuple of (parsed_nodes, error_message, duration_ms).
        If error_message is not None, parsed_nodes will be empty.
    """
    server_ctx = _get_context(ctx)
    executor = server_ctx.executor
    output_parser = server_ctx.output_parser

    result = await executor.execute(
        ["clab", "inspect", "--all"],
        timeout=30.0,
    )

    if result.exit_code != 0:
        return [], f"Failed to inspect labs: {result.stderr}", result.duration_ms

    nodes = output_parser.parse_table(result.stdout)
    return nodes, None, result.duration_ms


def _get_valid_node_names(nodes: list[dict[str, str]], lab_name: str) -> list[str]:
    """Extract valid node names for a given lab from parsed inspect output."""
    valid_names: list[str] = []
    for node in nodes:
        # Match by lab name - the inspect output has a "lab_name" or "lab" column
        node_lab = (
            node.get("lab_name", "")
            or node.get("lab", "")
            or node.get("labname", "")
        )
        if node_lab == lab_name:
            name = node.get("name", "")
            if name:
                valid_names.append(name)
    return valid_names


def _find_node_container(
    nodes: list[dict[str, str]], lab_name: str, node_name: str
) -> str | None:
    """Find the container name/ID for a specific node in a lab.

    The container name in clab follows the pattern: clab-{lab_name}-{node_name}.
    """
    for node in nodes:
        node_lab = (
            node.get("lab_name", "")
            or node.get("lab", "")
            or node.get("labname", "")
        )
        name = node.get("name", "")
        if node_lab == lab_name and name == node_name:
            # Return container ID if available, otherwise construct container name
            container_id = node.get("container_id", "")
            if container_id:
                return container_id
            # Fallback to the clab naming convention
            return f"clab-{lab_name}-{node_name}"
    return None


@mcp.tool(
    description="Execute a command inside a running containerlab node container"
)
async def node_exec(
    lab_name: str,
    node_name: str,
    exec_command: str,
    ctx=None,
) -> dict[str, Any]:
    """Execute a shell command inside a running containerlab node container.

    Runs the specified command via ``docker exec`` on the target node's
    container with a 30-second execution timeout. The command string is
    split on whitespace for execution (no shell interpretation).

    Args:
        lab_name (str): Required. Name of the deployed lab containing
            the target node.
        node_name (str): Required. Name of the node within the lab to
            execute the command on.
        exec_command (str): Required. Shell command string to execute inside
            the node container. Maximum 4096 characters. The command is
            split on spaces — use simple commands without shell operators.
        ctx: MCP context (injected automatically).

    Returns:
        dict: Response with keys:
            - status: "success" or "error"
            - stdout: Command standard output
            - stderr: Command standard error output
            - exit_code: Process exit code (-1 on timeout/validation error)
            - command: The full docker exec command string
            - duration_ms: Execution time in milliseconds

        On validation failure (node not found), stderr contains the list
        of valid node names for the given lab.

    Example:
        >>> node_exec(lab_name="dc-lab", node_name="spine1",
        ...           exec_command="ip address show")
        {"status": "success", "stdout": "1: lo: <LOOPBACK>...",
         "stderr": "", "exit_code": 0,
         "command": "docker exec -it clab-dc-lab-spine1 ip address show",
         "duration_ms": 250}
    """
    # Validate command length
    if len(exec_command) > MAX_COMMAND_LENGTH:
        return {
            "status": "error",
            "stdout": "",
            "stderr": (
                f"Command length {len(exec_command)} exceeds maximum "
                f"of {MAX_COMMAND_LENGTH} characters"
            ),
            "exit_code": -1,
            "command": exec_command[:100] + "..." if len(exec_command) > 100 else exec_command,
            "duration_ms": 0,
        }

    server_ctx = _get_context(ctx)
    executor = server_ctx.executor

    # Get running nodes to validate node_name exists
    nodes, error, inspect_duration = await _get_running_nodes(ctx)
    if error:
        return {
            "status": "error",
            "stdout": "",
            "stderr": error,
            "exit_code": -1,
            "command": "",
            "duration_ms": inspect_duration,
        }

    # Check if the node exists in the lab
    valid_names = _get_valid_node_names(nodes, lab_name)
    if node_name not in valid_names:
        if not valid_names:
            msg = f"No nodes found for lab '{lab_name}'. Verify the lab is deployed."
        else:
            msg = (
                f"Node '{node_name}' not found in lab '{lab_name}'. "
                f"Valid node names: {valid_names}"
            )
        return {
            "status": "error",
            "stdout": "",
            "stderr": msg,
            "exit_code": -1,
            "command": "",
            "duration_ms": inspect_duration,
        }

    # Find the container name for the node
    container_name = _find_node_container(nodes, lab_name, node_name)
    if not container_name:
        container_name = f"clab-{lab_name}-{node_name}"

    # Execute command via docker exec with 30s timeout
    exec_result = await executor.execute(
        ["docker", "exec", "-it", container_name, *exec_command.split()],
        timeout=30.0,
    )

    full_command = f"docker exec -it {container_name} {exec_command}"

    if exec_result.exit_code == -1 and "timed out" in exec_result.stderr:
        return {
            "status": "error",
            "stdout": exec_result.stdout,
            "stderr": "Command execution timed out after 30 seconds",
            "exit_code": -1,
            "command": full_command,
            "duration_ms": exec_result.duration_ms,
        }

    status = "success" if exec_result.exit_code == 0 else "error"
    return {
        "status": status,
        "stdout": exec_result.stdout,
        "stderr": exec_result.stderr,
        "exit_code": exec_result.exit_code,
        "command": full_command,
        "duration_ms": exec_result.duration_ms,
    }


@mcp.tool(
    description="Get access information for nodes in a running containerlab topology"
)
async def get_node_access(
    lab_name: str,
    topology_file_path: str | None = None,
    ctx=None,
) -> dict[str, Any]:
    """Get connection access information for nodes in a deployed lab.

    Returns the access method, connection command, and credentials for
    each node in the specified lab. When ``topology_file_path`` is
    provided, uses kind-based detection for enhanced access info
    (SSH credentials, correct access method). Without it, defaults to
    docker_exec with basic container info.

    Args:
        lab_name (str): Required. Name of the deployed lab to retrieve
            access information for.
        topology_file_path (str | None): Optional. Path to the .clab.yml
            topology YAML file for enhanced access detection. Enables
            SSH credential lookup and kind-based method selection.
        ctx: MCP context (injected automatically).

    Returns:
        dict: A StructuredResponse with keys:
            - status: "success" or "error"
            - data: List of NodeAccessInfo dicts on success (each with
              node_name, container_id, mgmt_ipv4, mgmt_ipv6,
              access_method, connection_command, username, password)
            - command: The CLI command executed
            - duration_ms: Execution time in milliseconds
            - message: Error with available labs listed (on error)

    Example:
        >>> get_node_access(lab_name="dc-lab",
        ...                 topology_file_path="/labs/dc.clab.yml")
        {"status": "success",
         "data": [{"node_name": "spine1", "container_id": "abc123",
                   "mgmt_ipv4": "172.20.0.2", "access_method": "ssh",
                   "connection_command": "ssh admin@172.20.0.2",
                   "username": "admin", "password": "admin"}],
         "command": "clab inspect --all", "duration_ms": 400}
    """
    server_ctx = _get_context(ctx)
    executor = server_ctx.executor
    output_parser = server_ctx.output_parser
    access_detector = server_ctx.access_detector

    # Get running nodes for this lab
    result = await executor.execute(
        ["clab", "inspect", "--all"],
        timeout=30.0,
    )

    if result.exit_code != 0:
        return {
            "status": "error",
            "data": None,
            "command": result.command,
            "duration_ms": result.duration_ms,
            "message": f"Failed to inspect labs: {result.stderr}",
        }

    all_nodes = output_parser.parse_table(result.stdout)

    # Filter to the requested lab
    lab_nodes = []
    for node in all_nodes:
        node_lab = (
            node.get("lab_name", "")
            or node.get("lab", "")
            or node.get("labname", "")
        )
        if node_lab == lab_name:
            lab_nodes.append(node)

    if not lab_nodes:
        # Return list of available labs from the inspect data
        available_labs: set[str] = set()
        for node in all_nodes:
            lab = (
                node.get("lab_name", "")
                or node.get("lab", "")
                or node.get("labname", "")
            )
            if lab:
                available_labs.add(lab)

        valid_names = []
        for node in all_nodes:
            name = node.get("name", "")
            if name:
                valid_names.append(name)

        msg = f"No nodes found for lab '{lab_name}'."
        if available_labs:
            msg += f" Available labs: {sorted(available_labs)}"
        return {
            "status": "error",
            "data": None,
            "command": result.command,
            "duration_ms": result.duration_ms,
            "message": msg,
        }

    # If topology file is provided, use NodeAccessDetector for enhanced info
    if topology_file_path:
        access_info_list = access_detector.detect_all(
            topology_path=topology_file_path,
            inspect_data=lab_nodes,
        )
        return {
            "status": "success",
            "data": [info.model_dump() for info in access_info_list],
            "command": result.command,
            "duration_ms": result.duration_ms,
        }

    # Without topology file, build basic access info from inspect data
    access_list = []
    for node in lab_nodes:
        node_name = node.get("name", "")
        container_id = node.get("container_id", "")
        mgmt_ipv4 = node.get("ipv4_address", "") or node.get("ipv4", "")
        mgmt_ipv6 = node.get("ipv6_address", "") or node.get("ipv6", "")

        # Strip CIDR notation if present
        if mgmt_ipv4 and "/" in mgmt_ipv4:
            mgmt_ipv4 = mgmt_ipv4.split("/")[0]
        if mgmt_ipv6 and "/" in mgmt_ipv6:
            mgmt_ipv6 = mgmt_ipv6.split("/")[0]

        # Without topology file, default to docker_exec
        target = container_id or f"clab-{lab_name}-{node_name}"
        connection_cmd = f"docker exec -it {target} bash"

        access_list.append({
            "node_name": node_name,
            "container_id": container_id,
            "mgmt_ipv4": mgmt_ipv4 or None,
            "mgmt_ipv6": mgmt_ipv6 or None,
            "access_method": "docker_exec",
            "connection_command": connection_cmd,
            "username": None,
            "password": None,
        })

    return {
        "status": "success",
        "data": access_list,
        "command": result.command,
        "duration_ms": result.duration_ms,
    }
