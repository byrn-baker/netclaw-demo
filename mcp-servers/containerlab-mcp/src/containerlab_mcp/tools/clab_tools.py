"""ContainerLab CLI tools exposed as MCP tool functions.

Registers deploy, destroy, inspect, save, graph, generate, and version
tools on the FastMCP server instance.
"""

from __future__ import annotations

import logging

import yaml
from mcp.server.fastmcp import Context

from containerlab_mcp.models import StructuredResponse
from containerlab_mcp.server import ServerContext, mcp

logger = logging.getLogger(__name__)


def _get_context(ctx: Context) -> ServerContext:
    """Extract the ServerContext from the MCP request context."""
    return ctx.request_context.lifespan_context


def _resolve_topology_name(topology_file_path: str) -> str:
    """Parse a topology YAML file to extract the lab name.

    Args:
        topology_file_path: Path to the .clab.yml file.

    Returns:
        The lab name from the YAML 'name' field, or derived from filename.

    Raises:
        ValueError: If the file cannot be read or parsed.
    """
    try:
        with open(topology_file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(
            f"Cannot read topology file to resolve lab name: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError("Topology file does not contain a YAML mapping")

    name = data.get("name", "")
    if not name:
        # Fall back to filename stem
        from pathlib import Path

        name = Path(topology_file_path).stem.replace(".clab", "")
    return str(name)


async def _execute_clab(
    ctx: Context,
    args: list[str],
    timeout: float = 30.0,
) -> StructuredResponse:
    """Execute a clab command and return a StructuredResponse.

    Chooses local or remote execution based on server configuration.
    On success, returns parsed data. On failure, returns sanitized error.

    Args:
        ctx: The MCP Context object.
        args: The clab command arguments (e.g., ["clab", "version"]).
        timeout: Command timeout in seconds.

    Returns:
        StructuredResponse instance.
    """
    server_ctx = _get_context(ctx)
    executor = server_ctx.executor
    output_parser = server_ctx.output_parser

    if server_ctx.config.remote:
        result = await executor.execute_remote(args, timeout=timeout)
    else:
        result = await executor.execute(args, timeout=timeout)

    if result.exit_code == 0:
        return StructuredResponse(
            status="success",
            data={"output": result.stdout},
            command=result.command,
            duration_ms=result.duration_ms,
        )
    else:
        sanitized_msg = output_parser.sanitize_error(result.stderr)
        return StructuredResponse(
            status="error",
            command=result.command,
            duration_ms=result.duration_ms,
            message=sanitized_msg,
            code=result.exit_code,
        )


@mcp.tool(
    description="Deploy a ContainerLab topology from a YAML file"
)
async def deploy(
    topology_file_path: str,
    lab_name: str | None = None,
    reconfigure: bool = False,
    ctx: Context = None,
) -> dict:
    """Deploy a ContainerLab topology from a YAML definition file.

    Runs ``clab deploy`` with the given topology file. Use this to bring
    up a new lab or reconfigure an existing one without tearing it down.

    Args:
        topology_file_path (str): Required. Absolute or relative path to
            the .clab.yml topology file to deploy.
        lab_name (str | None): Optional. Override the lab name defined in
            the topology YAML. Defaults to the name in the file.
        reconfigure (bool): Optional. When true, reconfigure an already-
            deployed lab without destroying it first. Default: False.
        ctx: MCP context (injected automatically).

    Returns:
        dict: A StructuredResponse with keys:
            - status: "success" or "error"
            - data: {"output": "<clab stdout>"} on success
            - command: The CLI command executed
            - duration_ms: Execution time in milliseconds
            - message: Error description (only on error)

    Example:
        >>> deploy(topology_file_path="/home/user/labs/dc.clab.yml",
        ...        lab_name="dc-lab", reconfigure=False)
        {"status": "success", "data": {"output": "..."},
         "command": "clab deploy --topo /home/user/labs/dc.clab.yml --name dc-lab",
         "duration_ms": 4500}
    """
    args = ["clab", "deploy", "--topo", topology_file_path]

    if lab_name:
        args.extend(["--name", lab_name])
    if reconfigure:
        args.append("--reconfigure")

    response = await _execute_clab(ctx, args, timeout=120.0)
    return response.model_dump()


@mcp.tool(
    description="Destroy a deployed ContainerLab topology with safety confirmation"
)
async def destroy(
    topology_file_path: str | None = None,
    lab_name: str | None = None,
    cleanup_artifacts: bool = False,
    confirm_topology_name: str | None = None,
    confirm_cleanup: bool | None = None,
    ctx: Context = None,
) -> dict:
    """Destroy a deployed ContainerLab topology with safety confirmation.

    Requires explicit confirmation: ``confirm_topology_name`` must exactly
    match the target lab name (case-sensitive). If ``cleanup_artifacts`` is
    true, ``confirm_cleanup`` must also be true. Rejection returns an error
    without executing any CLI command.

    Args:
        topology_file_path (str | None): Optional. Path to the .clab.yml
            topology file. Either this or lab_name must be provided.
        lab_name (str | None): Optional. Lab name to destroy (alternative
            to topology_file_path).
        cleanup_artifacts (bool): Optional. Remove lab directory and generated
            artifacts after destroy. Default: False.
        confirm_topology_name (str | None): Required for execution. Must
            exactly match the target topology name (case-sensitive).
        confirm_cleanup (bool | None): Required when cleanup_artifacts=True.
            Must be set to true to confirm file cleanup.
        ctx: MCP context (injected automatically).

    Returns:
        dict: A StructuredResponse with keys:
            - status: "success" or "error"
            - data: {"output": "<clab stdout>"} on success
            - command: The CLI command executed
            - duration_ms: Execution time in milliseconds
            - message: Safety rejection or error description (on error)

    Example:
        >>> destroy(topology_file_path="/labs/dc.clab.yml",
        ...         confirm_topology_name="dc-lab", cleanup_artifacts=False)
        {"status": "success", "data": {"output": "..."},
         "command": "clab destroy --topo /labs/dc.clab.yml",
         "duration_ms": 3200}
    """
    server_ctx = _get_context(ctx)
    safety_gate = server_ctx.safety_gate

    # Resolve target topology name
    if lab_name:
        target_name = lab_name
    elif topology_file_path:
        try:
            target_name = _resolve_topology_name(topology_file_path)
        except ValueError as exc:
            return StructuredResponse(
                status="error",
                command="clab destroy",
                duration_ms=0,
                message=str(exc),
                code=1,
            ).model_dump()
    else:
        return StructuredResponse(
            status="error",
            command="clab destroy",
            duration_ms=0,
            message="Either topology_file_path or lab_name must be provided",
            code=1,
        ).model_dump()

    # Validate with SafetyGate
    validation = safety_gate.validate_destroy(
        target_name=target_name,
        confirm_topology_name=confirm_topology_name,
        cleanup=cleanup_artifacts,
        confirm_cleanup=confirm_cleanup,
    )

    if not validation.passed:
        return StructuredResponse(
            status="error",
            command="clab destroy",
            duration_ms=0,
            message=validation.error_message,
            code=1,
        ).model_dump()

    # Build CLI args
    args = ["clab", "destroy"]

    if topology_file_path:
        args.extend(["--topo", topology_file_path])
    if lab_name:
        args.extend(["--name", lab_name])
    if cleanup_artifacts:
        args.append("--cleanup")

    response = await _execute_clab(ctx, args, timeout=120.0)
    return response.model_dump()


@mcp.tool(
    description="Inspect running ContainerLab topologies and list node details"
)
async def inspect(
    topology_name: str | None = None,
    lab_name: str | None = None,
    ctx: Context = None,
) -> dict:
    """Inspect running ContainerLab topologies and list node details.

    Returns structured node information including container IDs,
    management IPs, and runtime status for all nodes. When called with
    no filters, inspects all running labs.

    Args:
        topology_name (str | None): Optional. Filter results to a specific
            topology name.
        lab_name (str | None): Optional. Filter results to a specific lab
            name. Ignored if topology_name is set.
        ctx: MCP context (injected automatically).

    Returns:
        dict: A StructuredResponse with keys:
            - status: "success" or "error"
            - data: List of node record dicts (each with name, lab_name,
              container_id, ipv4_address, state, etc.) on success
            - command: The CLI command executed
            - duration_ms: Execution time in milliseconds

    Example:
        >>> inspect(topology_name="dc-lab")
        {"status": "success",
         "data": [{"name": "spine1", "lab_name": "dc-lab",
                   "container_id": "abc123", "ipv4_address": "172.20.0.2/24",
                   "state": "running"}],
         "command": "clab inspect --name dc-lab", "duration_ms": 350}
    """
    args = ["clab", "inspect"]

    if topology_name:
        args.extend(["--name", topology_name])
    elif lab_name:
        args.extend(["--name", lab_name])
    else:
        args.append("--all")

    server_ctx = _get_context(ctx)
    executor = server_ctx.executor
    output_parser = server_ctx.output_parser

    if server_ctx.config.remote:
        result = await executor.execute_remote(args, timeout=30.0)
    else:
        result = await executor.execute(args, timeout=30.0)

    if result.exit_code == 0:
        # Parse the table output from inspect
        parsed_data = output_parser.parse_table(result.stdout)
        return StructuredResponse(
            status="success",
            data=parsed_data,
            command=result.command,
            duration_ms=result.duration_ms,
        ).model_dump()
    else:
        sanitized_msg = output_parser.sanitize_error(result.stderr)
        return StructuredResponse(
            status="error",
            command=result.command,
            duration_ms=result.duration_ms,
            message=sanitized_msg,
            code=result.exit_code,
        ).model_dump()


@mcp.tool(
    description="Save running ContainerLab topology configuration to disk"
)
async def save(
    topology_file_path: str | None = None,
    lab_name: str | None = None,
    ctx: Context = None,
) -> dict:
    """Save the running configuration of a deployed ContainerLab topology.

    Persists the current node configurations (startup-config state) to
    the lab directory on disk. Useful before destroying a lab.

    Args:
        topology_file_path (str | None): Optional. Path to the .clab.yml
            topology file identifying the lab to save.
        lab_name (str | None): Optional. Lab name to save (alternative
            to topology_file_path).
        ctx: MCP context (injected automatically).

    Returns:
        dict: A StructuredResponse with keys:
            - status: "success" or "error"
            - data: {"output": "<clab stdout>"} on success
            - command: The CLI command executed
            - duration_ms: Execution time in milliseconds
            - message: Error description (only on error)

    Example:
        >>> save(topology_file_path="/labs/dc.clab.yml")
        {"status": "success", "data": {"output": "..."},
         "command": "clab save --topo /labs/dc.clab.yml",
         "duration_ms": 1200}
    """
    args = ["clab", "save"]

    if topology_file_path:
        args.extend(["--topo", topology_file_path])
    if lab_name:
        args.extend(["--name", lab_name])

    response = await _execute_clab(ctx, args, timeout=30.0)
    return response.model_dump()


@mcp.tool(
    description="Generate a topology graph visualization from a topology file"
)
async def graph(
    topology_file_path: str,
    output_format: str = "html",
    ctx: Context = None,
) -> dict:
    """Generate a visual graph of a ContainerLab topology.

    Creates an HTML or other format graph showing nodes and links.
    The output file is written alongside the topology file.

    Args:
        topology_file_path (str): Required. Path to the .clab.yml
            topology file to visualize.
        output_format (str): Optional. Output format for the graph
            file. Supported: "html", "mermaid", "draw.io".
            Default: "html".
        ctx: MCP context (injected automatically).

    Returns:
        dict: A StructuredResponse with keys:
            - status: "success" or "error"
            - data: {"output": "<clab stdout>"} on success
            - command: The CLI command executed
            - duration_ms: Execution time in milliseconds
            - message: Error description (only on error)

    Example:
        >>> graph(topology_file_path="/labs/dc.clab.yml",
        ...       output_format="html")
        {"status": "success", "data": {"output": "..."},
         "command": "clab graph --topo /labs/dc.clab.yml --format html",
         "duration_ms": 800}
    """
    args = ["clab", "graph", "--topo", topology_file_path]

    if output_format:
        args.extend(["--format", output_format])

    response = await _execute_clab(ctx, args, timeout=30.0)
    return response.model_dump()


@mcp.tool(
    description="Generate a new ContainerLab topology file with specified parameters"
)
async def generate(
    topology_file_path: str,
    node_count: int = 2,
    topology_type: str = "ring",
    ctx: Context = None,
) -> dict:
    """Generate a new ContainerLab topology YAML file from parameters.

    Creates a .clab.yml file with the specified number of nodes
    connected in the requested topology pattern.

    Args:
        topology_file_path (str): Required. File path where the generated
            topology YAML will be written.
        node_count (int): Optional. Number of nodes to include in the
            generated topology. Default: 2.
        topology_type (str): Optional. Topology interconnection pattern.
            Supported: "ring", "full-mesh", "linear". Default: "ring".
        ctx: MCP context (injected automatically).

    Returns:
        dict: A StructuredResponse with keys:
            - status: "success" or "error"
            - data: {"output": "<clab stdout>"} on success
            - command: The CLI command executed
            - duration_ms: Execution time in milliseconds
            - message: Error description (only on error)

    Example:
        >>> generate(topology_file_path="/labs/new.clab.yml",
        ...          node_count=4, topology_type="ring")
        {"status": "success", "data": {"output": "..."},
         "command": "clab generate --name /labs/new.clab.yml --nodes 4 --kind ring",
         "duration_ms": 200}
    """
    args = [
        "clab",
        "generate",
        "--name", topology_file_path,
        "--nodes", str(node_count),
        "--kind", topology_type,
    ]

    response = await _execute_clab(ctx, args, timeout=30.0)
    return response.model_dump()


@mcp.tool(
    description="Get the installed ContainerLab version information"
)
async def version(
    ctx: Context = None,
) -> dict:
    """Get the installed ContainerLab CLI version information.

    Returns the clab binary version string. Use this to verify
    ContainerLab is installed and check compatibility.

    Args:
        ctx: MCP context (injected automatically).

    Returns:
        dict: A StructuredResponse with keys:
            - status: "success" or "error"
            - data: {"output": "<version string>"} on success
            - command: The CLI command executed
            - duration_ms: Execution time in milliseconds

    Example:
        >>> version()
        {"status": "success",
         "data": {"output": "containerlab version 0.56.0"},
         "command": "clab version", "duration_ms": 50}
    """
    args = ["clab", "version"]

    response = await _execute_clab(ctx, args, timeout=10.0)
    return response.model_dump()
