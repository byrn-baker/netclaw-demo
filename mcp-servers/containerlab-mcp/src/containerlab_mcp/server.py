"""ContainerLab MCP Server entry point with FastMCP instance and CLI interface."""

from __future__ import annotations

import logging
import shutil
import socket
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import click
from mcp.server.fastmcp import FastMCP

from containerlab_mcp.access import NodeAccessDetector
from containerlab_mcp.config import ConfigManager
from containerlab_mcp.executor import CLIExecutor
from containerlab_mcp.models import ServerConfig
from containerlab_mcp.parser import OutputParser
from containerlab_mcp.safety import SafetyGate
from containerlab_mcp.topology import TopologyParser

logger = logging.getLogger(__name__)


@dataclass
class ServerContext:
    """Holds all service instances created during server lifespan."""

    config: ServerConfig
    executor: CLIExecutor
    topology_parser: TopologyParser
    access_detector: NodeAccessDetector
    output_parser: OutputParser
    safety_gate: SafetyGate


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[ServerContext]:
    """Lifespan context manager for the MCP server.

    Performs startup checks and creates service instances:
    - Loads configuration via ConfigManager
    - Verifies clab binary is on PATH
    - Creates CLIExecutor, TopologyParser, NodeAccessDetector, OutputParser, SafetyGate
    """
    # Retrieve CLI overrides stored on the server instance
    cli_overrides: dict[str, Any] = getattr(server, "_cli_overrides", {})

    # Load merged configuration
    config_manager = ConfigManager()
    config = config_manager.load(cli_overrides=cli_overrides)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Verify clab binary is available
    if shutil.which("clab") is None:
        logger.error(
            "The 'clab' binary was not found on PATH. "
            "Please install ContainerLab: https://containerlab.dev/install/"
        )
        sys.exit(1)

    # Create service instances
    executor = CLIExecutor(
        remote=config.remote,
        ssh_key_path=config.ssh_key_path,
        ssh_port=config.ssh_port,
    )
    topology_parser = TopologyParser()
    access_detector = NodeAccessDetector()
    output_parser = OutputParser()
    safety_gate = SafetyGate()

    logger.info(
        "ContainerLab MCP Server starting (transport=%s, remote=%s)",
        config.transport,
        config.remote or "local",
    )

    ctx = ServerContext(
        config=config,
        executor=executor,
        topology_parser=topology_parser,
        access_detector=access_detector,
        output_parser=output_parser,
        safety_gate=safety_gate,
    )

    yield ctx

    logger.info("ContainerLab MCP Server shutting down")


# Create the FastMCP server instance with lifespan
mcp = FastMCP(
    "containerlab-mcp",
    instructions="ContainerLab MCP server for managing container-based network lab topologies",
    lifespan=server_lifespan,
)


def _check_port_available(host: str, port: int) -> bool:
    """Check if a port is available for binding."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            return True
    except OSError:
        return False


@click.command()
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"], case_sensitive=False),
    default="stdio",
    help="Transport mode: stdio (default) or sse.",
)
@click.option(
    "--host",
    type=str,
    default="0.0.0.0",
    help="Host to bind the SSE/HTTP listener (default: 0.0.0.0).",
)
@click.option(
    "--port",
    type=int,
    default=8080,
    help="Port for the SSE/HTTP listener (default: 8080).",
)
@click.option(
    "--remote",
    type=str,
    default=None,
    help="Remote SSH target in user@host format.",
)
@click.option(
    "--ssh-key-path",
    type=str,
    default=None,
    help="Path to SSH private key for remote execution.",
)
@click.option(
    "--ssh-port",
    type=int,
    default=22,
    help="SSH port for remote execution (default: 22).",
)
def main(
    transport: str,
    host: str,
    port: int,
    remote: str | None,
    ssh_key_path: str | None,
    ssh_port: int,
) -> None:
    """ContainerLab MCP Server - Manage container-based network lab topologies."""
    # Build CLI overrides dict (only include non-default values)
    cli_overrides: dict[str, Any] = {
        "transport": transport.lower(),
        "host": host,
        "port": port,
        "ssh_port": ssh_port,
    }
    if remote is not None:
        cli_overrides["remote"] = remote
    if ssh_key_path is not None:
        cli_overrides["ssh_key_path"] = ssh_key_path

    # Store overrides on the mcp instance for the lifespan to pick up
    mcp._cli_overrides = cli_overrides  # type: ignore[attr-defined]

    # For SSE mode, check port availability before starting
    if transport.lower() == "sse":
        if not _check_port_available(host, port):
            click.echo(
                f"Error: Port {port} is unavailable on {host}. "
                f"Please choose a different port or free the existing binding.",
                err=True,
            )
            sys.exit(1)

    # Start the server with the selected transport
    if transport.lower() == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


import containerlab_mcp.tools.clab_tools  # noqa: F401, E402
import containerlab_mcp.tools.monitoring_tools  # noqa: F401, E402
import containerlab_mcp.tools.node_tools  # noqa: F401, E402


if __name__ == "__main__":
    main()
