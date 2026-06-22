#!/usr/bin/env python3
"""ContainerLab MCP Server — entry point for NetClaw integration.

13 tools across 4 domains:
  CLI Lifecycle (7) — deploy, destroy, inspect, save, graph, generate, version
  Node Ops      (2) — node_exec, get_node_access
  Topology      (2) — list_topologies, get_topology_details
  Monitoring    (2) — lab_status, node_health

Environment variables:
  CLAB_MCP_TOPOLOGY_PATHS  — Colon-separated list of directories to scan for .clab.yml files
  CLAB_MCP_LOG_LEVEL       — Log level: debug, info, warning, error (default: info)
  CLAB_MCP_REMOTE          — Remote SSH target in user@host format
  CLAB_MCP_SSH_KEY_PATH    — Path to SSH private key for remote execution
  CLAB_MCP_SSH_PORT        — SSH port for remote execution (default: 22)
  CLAB_MCP_TRANSPORT       — Transport mode: stdio or sse (default: stdio)
  CLAB_MCP_HOST            — Host to bind SSE listener (default: 0.0.0.0)
  CLAB_MCP_PORT            — Port for SSE listener (default: 8080)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

# Add src/ to path for the internal package
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
# Add netclaw_tokens to path for GCF serialization
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

# ---------------------------------------------------------------------------
# Logging (stderr only — stdout is reserved for MCP JSON-RPC)
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("containerlab-mcp")

# ---------------------------------------------------------------------------
# Import the server (triggers tool registration)
# ---------------------------------------------------------------------------

from containerlab_mcp.server import mcp  # noqa: E402

# ---------------------------------------------------------------------------
# GAIT Audit Logging Helper
# ---------------------------------------------------------------------------


def _gait_log(operation: str, **kwargs) -> None:
    """Emit a structured GAIT audit log entry to stderr."""
    entry = {
        "gait": True,
        "operation": operation,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }
    logger.info("GAIT: %s", json.dumps(entry, default=str))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("ContainerLab MCP Server starting")
    logger.info("Topology paths: %s", os.getenv("CLAB_MCP_TOPOLOGY_PATHS", "."))
    logger.info("Remote target:  %s", os.getenv("CLAB_MCP_REMOTE", "local"))
    logger.info("Log level:      %s", os.getenv("CLAB_MCP_LOG_LEVEL", "info"))
    mcp.run(transport="stdio")
