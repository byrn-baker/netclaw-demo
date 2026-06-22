"""Monitoring tools for ContainerLab MCP Server.

Provides tools for topology discovery, topology details, lab status,
and node health monitoring.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from containerlab_mcp.models import (
    NodeHealth,
    StructuredResponse,
)
from containerlab_mcp.server import ServerContext, mcp

logger = logging.getLogger(__name__)


def _get_context(ctx) -> ServerContext:
    """Extract the ServerContext from the MCP request context."""
    return ctx.request_context.lifespan_context


@mcp.tool(
    description="Discover ContainerLab topology files in configured search paths"
)
async def list_topologies(search_paths: str | None = None, ctx=None) -> dict:
    """Discover ContainerLab topology files in configured search paths.

    Scans directories recursively (up to depth 3) for ``.clab.yml`` files
    and returns metadata for each discovered topology. Falls back to
    server-configured ``topology_paths`` if no explicit paths are given.

    Args:
        search_paths (str | None): Optional. Colon-separated directory
            paths to scan for topology files (e.g. "/labs:/opt/topos").
            Falls back to server config topology_paths if omitted.
        ctx: MCP context (injected automatically).

    Returns:
        dict: A StructuredResponse with keys:
            - status: "success" or "error"
            - data: List of topology entry dicts, each containing:
                - path: Absolute path to the .clab.yml file
                - lab_name: Name of the lab (from YAML or filename)
                - node_count: Number of nodes defined in the topology
            - command: "topology_discover"
            - duration_ms: Scan time in milliseconds

    Example:
        >>> list_topologies(search_paths="/home/user/labs:/opt/topologies")
        {"status": "success",
         "data": [{"path": "/home/user/labs/demo.clab.yml",
                   "lab_name": "demo", "node_count": 4}],
         "command": "topology_discover", "duration_ms": 12}
    """
    start = time.monotonic()

    server_ctx = _get_context(ctx)

    # Determine search paths
    if search_paths is not None:
        paths = [p.strip() for p in search_paths.split(":") if p.strip()]
    else:
        paths = server_ctx.config.topology_paths

    # Discover topology files
    entries = server_ctx.topology_parser.discover(paths)

    duration_ms = int((time.monotonic() - start) * 1000)

    return StructuredResponse(
        status="success",
        data=[entry.model_dump() for entry in entries],
        command="topology_discover",
        duration_ms=duration_ms,
    ).model_dump()


@mcp.tool(
    description="Parse a ContainerLab topology file and return structured details"
)
async def get_topology_details(topology_file_path: str, ctx=None) -> dict:
    """Parse a ContainerLab topology YAML file and return structured details.

    Reads the specified ``.clab.yml`` file and extracts node definitions,
    link definitions, topology name, and node kinds. Use this to
    understand the structure of a topology before deploying.

    Args:
        topology_file_path (str): Required. Absolute path to the .clab.yml
            topology file to parse.
        ctx: MCP context (injected automatically).

    Returns:
        dict: A StructuredResponse with keys:
            - status: "success" or "error"
            - data: Parsed topology dict on success containing:
                - name: Topology/lab name
                - nodes: List of node definitions (name, kind, image)
                - links: List of link definitions (endpoints)
                - kind: Default node kind (if set)
            - command: "topology_parse"
            - duration_ms: Parse time in milliseconds
            - message: Error description (on error, e.g. file not found)

    Example:
        >>> get_topology_details(
        ...     topology_file_path="/home/user/labs/demo.clab.yml")
        {"status": "success",
         "data": {"name": "demo",
                  "nodes": [{"name": "srl1", "kind": "nokia_srlinux",
                             "image": "ghcr.io/nokia/srlinux"}],
                  "links": [{"endpoints": ["srl1:e1-1", "srl2:e1-1"]}],
                  "kind": "nokia_srlinux"},
         "command": "topology_parse", "duration_ms": 5}
    """
    start = time.monotonic()

    server_ctx = _get_context(ctx)

    try:
        details = server_ctx.topology_parser.parse(topology_file_path)
    except FileNotFoundError:
        duration_ms = int((time.monotonic() - start) * 1000)
        return StructuredResponse(
            status="error",
            command="topology_parse",
            duration_ms=duration_ms,
            message=f"Topology file not found: {topology_file_path}",
        ).model_dump()
    except ValueError as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        return StructuredResponse(
            status="error",
            command="topology_parse",
            duration_ms=duration_ms,
            message=str(exc),
        ).model_dump()

    duration_ms = int((time.monotonic() - start) * 1000)

    return StructuredResponse(
        status="success",
        data=details.model_dump(),
        command="topology_parse",
        duration_ms=duration_ms,
    ).model_dump()


@mcp.tool(
    description="Return status of all currently deployed ContainerLab instances"
)
async def lab_status(ctx=None) -> dict:
    """Return status of all currently deployed ContainerLab lab instances.

    Queries running labs via ``clab inspect --all --format json`` and
    returns topology names, node counts, deployment times, and container
    states. Returns an empty list (with success status) if no labs are
    deployed.

    Args:
        ctx: MCP context (injected automatically).

    Returns:
        dict: A StructuredResponse with keys:
            - status: "success" or "error"
            - data: List of lab instance dicts, each containing:
                - topology_name: Name of the lab
                - node_count: Number of containers in the lab
                - deployed_at: ISO 8601 UTC timestamp of deployment
                - container_states: (only if non-running nodes exist)
                  Dict mapping node names to their state
            - command: The CLI command executed
            - duration_ms: Execution time in milliseconds

    Example:
        >>> lab_status()
        {"status": "success",
         "data": [{"topology_name": "dc-lab", "node_count": 4,
                   "deployed_at": "2024-01-15T10:30:00Z"}],
         "command": "clab inspect --all --format json",
         "duration_ms": 250}
    """
    server_ctx = _get_context(ctx)

    result = await server_ctx.executor.execute(
        ["clab", "inspect", "--all", "--format", "json"],
        timeout=30.0,
    )

    if result.exit_code != 0:
        # If no labs are running, clab may return non-zero or empty output
        if "no containers found" in result.stderr.lower() or not result.stdout.strip():
            return StructuredResponse(
                status="success",
                data=[],
                command=result.command,
                duration_ms=result.duration_ms,
            ).model_dump()

        return StructuredResponse(
            status="error",
            command=result.command,
            duration_ms=result.duration_ms,
            message=result.stderr[:4096] if result.stderr else "clab inspect failed",
            code=result.exit_code,
        ).model_dump()

    # Parse JSON output
    stdout = result.stdout.strip()
    if not stdout:
        return StructuredResponse(
            status="success",
            data=[],
            command=result.command,
            duration_ms=result.duration_ms,
        ).model_dump()

    try:
        inspect_data = json.loads(stdout)
    except json.JSONDecodeError:
        return StructuredResponse(
            status="error",
            command=result.command,
            duration_ms=result.duration_ms,
            message="Failed to parse clab inspect JSON output",
        ).model_dump()

    # Group containers by lab name
    labs: dict[str, dict] = {}

    # inspect_data can be a dict with "containers" key or a list
    containers: list = []
    if isinstance(inspect_data, dict):
        containers = inspect_data.get("containers", [])
    elif isinstance(inspect_data, list):
        containers = inspect_data

    for container in containers:
        if not isinstance(container, dict):
            continue

        lab_name = container.get("lab_name", container.get("labName", "unknown"))
        state = container.get("state", "unknown")

        if lab_name not in labs:
            labs[lab_name] = {
                "topology_name": lab_name,
                "node_count": 0,
                "deployed_at": "",
                "nodes": [],
            }

        labs[lab_name]["node_count"] += 1
        node_info: dict = {"name": container.get("name", "unknown"), "state": state}
        labs[lab_name]["nodes"].append(node_info)

        # Use the earliest container start time as deployed_at
        started_at = container.get("created", container.get("startedAt", ""))
        if started_at and (
            not labs[lab_name]["deployed_at"]
            or started_at < labs[lab_name]["deployed_at"]
        ):
            labs[lab_name]["deployed_at"] = started_at

    # Build response list
    lab_instances: list[dict] = []
    for lab_name, lab_data in labs.items():
        entry: dict = {
            "topology_name": lab_data["topology_name"],
            "node_count": lab_data["node_count"],
            "deployed_at": lab_data["deployed_at"] or datetime.now(timezone.utc).isoformat(),
        }

        # Include per-node container states if any node is not "running"
        non_running = [
            n for n in lab_data["nodes"] if n["state"] != "running"
        ]
        if non_running:
            entry["container_states"] = {
                n["name"]: n["state"] for n in lab_data["nodes"]
            }

        lab_instances.append(entry)

    return StructuredResponse(
        status="success",
        data=lab_instances,
        command=result.command,
        duration_ms=result.duration_ms,
    ).model_dump()


@mcp.tool(
    description="Return container resource usage for a specific lab node"
)
async def node_health(node_name: str, ctx=None) -> dict:
    """Return CPU, memory, and uptime metrics for a specific lab node container.

    Queries Docker for real-time resource usage of the named container.
    The ``node_name`` should be the full container name (e.g.
    ``clab-<lab>-<node>``).

    Args:
        node_name (str): Required. The container name of the node to
            check health for. Use the full clab container name
            (e.g. "clab-dc-lab-spine1").
        ctx: MCP context (injected automatically).

    Returns:
        dict: A StructuredResponse with keys:
            - status: "success" or "error"
            - data: NodeHealth dict on success containing:
                - node_name: Container name
                - cpu_percent: CPU usage percentage (0-100)
                - memory_bytes: Memory usage in bytes
                - memory_percent: Memory usage percentage (0-100)
                - uptime_seconds: Container uptime in seconds
            - command: The docker stats command executed
            - duration_ms: Execution time in milliseconds
            - message: Error if container not found or not running

    Example:
        >>> node_health(node_name="clab-dc-lab-spine1")
        {"status": "success",
         "data": {"node_name": "clab-dc-lab-spine1",
                  "cpu_percent": 12.5, "memory_bytes": 524288000,
                  "memory_percent": 25.0, "uptime_seconds": 3600},
         "command": "docker stats clab-dc-lab-spine1 --no-stream",
         "duration_ms": 150}
    """
    server_ctx = _get_context(ctx)

    # Get CPU and memory stats
    stats_result = await server_ctx.executor.execute(
        [
            "docker", "stats", node_name, "--no-stream",
            "--format", "{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}",
        ],
        timeout=30.0,
    )

    if stats_result.exit_code != 0:
        return StructuredResponse(
            status="error",
            command=f"docker stats {node_name} --no-stream",
            duration_ms=stats_result.duration_ms,
            message=f"Container not found or not running: {node_name}",
            code=stats_result.exit_code,
        ).model_dump()

    # Get container start time for uptime calculation
    inspect_result = await server_ctx.executor.execute(
        [
            "docker", "inspect",
            "--format", "{{.State.StartedAt}}",
            node_name,
        ],
        timeout=30.0,
    )

    total_duration_ms = stats_result.duration_ms + inspect_result.duration_ms
    command_str = f"docker stats {node_name} --no-stream"

    if inspect_result.exit_code != 0:
        return StructuredResponse(
            status="error",
            command=command_str,
            duration_ms=total_duration_ms,
            message=f"Container not found or not running: {node_name}",
            code=inspect_result.exit_code,
        ).model_dump()

    # Parse stats output: "CPU%\tMEM USAGE / LIMIT\tMEM%"
    stats_line = stats_result.stdout.strip()
    try:
        parts = stats_line.split("\t")
        cpu_str = parts[0].strip().rstrip("%")
        mem_usage_str = parts[1].strip()
        mem_percent_str = parts[2].strip().rstrip("%")

        cpu_percent = float(cpu_str)
        memory_percent = float(mem_percent_str)

        # Parse memory usage (e.g., "512MiB / 2GiB" → extract used bytes)
        mem_used_str = mem_usage_str.split("/")[0].strip()
        memory_bytes = _parse_memory_string(mem_used_str)
    except (IndexError, ValueError) as exc:
        return StructuredResponse(
            status="error",
            command=command_str,
            duration_ms=total_duration_ms,
            message=f"Failed to parse docker stats output: {exc}",
        ).model_dump()

    # Calculate uptime from started_at timestamp
    started_at_str = inspect_result.stdout.strip()
    try:
        # Docker returns ISO 8601 format like "2024-01-15T10:30:00.123456789Z"
        # Truncate nanoseconds to microseconds for Python parsing
        if "." in started_at_str:
            base, frac = started_at_str.split(".", 1)
            # Remove timezone suffix and truncate fractional seconds
            frac_clean = ""
            tz_suffix = ""
            for i, ch in enumerate(frac):
                if ch.isdigit():
                    frac_clean += ch
                else:
                    tz_suffix = frac[i:]
                    break
            # Truncate to 6 digits (microseconds)
            frac_clean = frac_clean[:6]
            started_at_str = f"{base}.{frac_clean}{tz_suffix}"

        # Handle Z suffix
        started_at_str = started_at_str.replace("Z", "+00:00")
        started_at = datetime.fromisoformat(started_at_str)
        now = datetime.now(timezone.utc)
        uptime_seconds = max(0, int((now - started_at).total_seconds()))
    except (ValueError, TypeError):
        uptime_seconds = 0

    health = NodeHealth(
        node_name=node_name,
        cpu_percent=min(cpu_percent, 100.0),
        memory_bytes=memory_bytes,
        memory_percent=min(memory_percent, 100.0),
        uptime_seconds=uptime_seconds,
    )

    return StructuredResponse(
        status="success",
        data=health.model_dump(),
        command=command_str,
        duration_ms=total_duration_ms,
    ).model_dump()


def _parse_memory_string(mem_str: str) -> int:
    """Parse a Docker memory string like '512MiB' or '1.5GiB' to bytes.

    Args:
        mem_str: Memory string with unit suffix (B, KiB, MiB, GiB, TiB,
                 or KB, MB, GB, TB).

    Returns:
        Memory value in bytes.
    """
    mem_str = mem_str.strip()

    units = {
        "B": 1,
        "KiB": 1024,
        "MiB": 1024**2,
        "GiB": 1024**3,
        "TiB": 1024**4,
        "KB": 1000,
        "MB": 1000**2,
        "GB": 1000**3,
        "TB": 1000**4,
        "kB": 1000,
    }

    for unit, multiplier in sorted(units.items(), key=lambda x: -len(x[0])):
        if mem_str.endswith(unit):
            value_str = mem_str[: -len(unit)].strip()
            return int(float(value_str) * multiplier)

    # Fallback: try parsing as plain bytes
    try:
        return int(float(mem_str))
    except ValueError:
        return 0
