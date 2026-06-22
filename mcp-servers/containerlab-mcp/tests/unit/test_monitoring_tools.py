"""Unit tests for monitoring tools (list_topologies, get_topology_details, lab_status, node_health)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from containerlab_mcp.models import (
    ExecutionResult,
    ServerConfig,
    TopologyDetails,
    TopologyEntry,
    NodeDefinition,
    LinkDefinition,
)
from containerlab_mcp.tools.monitoring_tools import (
    _parse_memory_string,
    list_topologies,
    get_topology_details,
    lab_status,
    node_health,
)


@pytest.fixture
def mock_server_ctx():
    """Create a mock ServerContext for testing."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context.config = ServerConfig(
        topology_paths=["/default/path"]
    )
    ctx.request_context.lifespan_context.topology_parser = MagicMock()
    ctx.request_context.lifespan_context.executor = AsyncMock()
    return ctx


class TestListTopologies:
    """Tests for the list_topologies tool."""

    @pytest.mark.asyncio
    async def test_uses_config_paths_when_no_search_paths_provided(self, mock_server_ctx):
        """Should fall back to config.topology_paths when search_paths is None."""
        mock_server_ctx.request_context.lifespan_context.topology_parser.discover.return_value = []

        result = await list_topologies(search_paths=None, ctx=mock_server_ctx)

        mock_server_ctx.request_context.lifespan_context.topology_parser.discover.assert_called_once_with(
            ["/default/path"]
        )
        assert result["status"] == "success"
        assert result["data"] == []

    @pytest.mark.asyncio
    async def test_parses_colon_separated_search_paths(self, mock_server_ctx):
        """Should split colon-separated paths into a list."""
        mock_server_ctx.request_context.lifespan_context.topology_parser.discover.return_value = []

        result = await list_topologies(
            search_paths="/path/a:/path/b:/path/c", ctx=mock_server_ctx
        )

        mock_server_ctx.request_context.lifespan_context.topology_parser.discover.assert_called_once_with(
            ["/path/a", "/path/b", "/path/c"]
        )
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_returns_topology_entries(self, mock_server_ctx):
        """Should return discovered topology entries as dicts."""
        entries = [
            TopologyEntry(path="/labs/demo.clab.yml", lab_name="demo", node_count=4),
            TopologyEntry(path="/labs/spine.clab.yml", lab_name="spine", node_count=2),
        ]
        mock_server_ctx.request_context.lifespan_context.topology_parser.discover.return_value = entries

        result = await list_topologies(search_paths=None, ctx=mock_server_ctx)

        assert result["status"] == "success"
        assert len(result["data"]) == 2
        assert result["data"][0]["path"] == "/labs/demo.clab.yml"
        assert result["data"][0]["lab_name"] == "demo"
        assert result["data"][0]["node_count"] == 4
        assert result["command"] == "topology_discover"
        assert result["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_empty_search_paths_string_uses_config(self, mock_server_ctx):
        """Should handle empty/whitespace-only colon-separated string."""
        mock_server_ctx.request_context.lifespan_context.topology_parser.discover.return_value = []

        # Whitespace-only paths should be filtered out, resulting in empty list
        result = await list_topologies(search_paths="  :  : ", ctx=mock_server_ctx)

        mock_server_ctx.request_context.lifespan_context.topology_parser.discover.assert_called_once_with([])
        assert result["status"] == "success"
        assert result["data"] == []


class TestGetTopologyDetails:
    """Tests for the get_topology_details tool."""

    @pytest.mark.asyncio
    async def test_returns_parsed_topology(self, mock_server_ctx):
        """Should return parsed topology details on success."""
        details = TopologyDetails(
            name="demo",
            nodes=[
                NodeDefinition(name="srl1", kind="srl", image="ghcr.io/nokia/srlinux"),
                NodeDefinition(name="linux1", kind="linux", image="alpine:latest"),
            ],
            links=[LinkDefinition(endpoints=["srl1:e1-1", "linux1:eth1"])],
            kind="srl",
        )
        mock_server_ctx.request_context.lifespan_context.topology_parser.parse.return_value = details

        result = await get_topology_details(
            topology_file_path="/labs/demo.clab.yml", ctx=mock_server_ctx
        )

        assert result["status"] == "success"
        assert result["data"]["name"] == "demo"
        assert len(result["data"]["nodes"]) == 2
        assert result["data"]["nodes"][0]["name"] == "srl1"
        assert result["command"] == "topology_parse"
        assert result["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_handles_file_not_found(self, mock_server_ctx):
        """Should return error when topology file doesn't exist."""
        mock_server_ctx.request_context.lifespan_context.topology_parser.parse.side_effect = (
            FileNotFoundError("Topology file not found: /nonexistent.clab.yml")
        )

        result = await get_topology_details(
            topology_file_path="/nonexistent.clab.yml", ctx=mock_server_ctx
        )

        assert result["status"] == "error"
        assert "not found" in result["message"].lower()
        assert "/nonexistent.clab.yml" in result["message"]

    @pytest.mark.asyncio
    async def test_handles_value_error(self, mock_server_ctx):
        """Should return error when topology file cannot be parsed."""
        mock_server_ctx.request_context.lifespan_context.topology_parser.parse.side_effect = (
            ValueError("Invalid YAML structure")
        )

        result = await get_topology_details(
            topology_file_path="/labs/invalid.clab.yml", ctx=mock_server_ctx
        )

        assert result["status"] == "error"
        assert "Invalid YAML structure" in result["message"]


class TestLabStatus:
    """Tests for the lab_status tool."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_labs(self, mock_server_ctx):
        """Should return success with empty list when no labs are running."""
        mock_server_ctx.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout="",
                stderr="no containers found",
                exit_code=1,
                duration_ms=50,
                command="clab inspect --all --format json",
            )
        )

        result = await lab_status(ctx=mock_server_ctx)

        assert result["status"] == "success"
        assert result["data"] == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_empty_stdout(self, mock_server_ctx):
        """Should return success with empty list when stdout is empty."""
        mock_server_ctx.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout="",
                stderr="",
                exit_code=0,
                duration_ms=50,
                command="clab inspect --all --format json",
            )
        )

        result = await lab_status(ctx=mock_server_ctx)

        assert result["status"] == "success"
        assert result["data"] == []

    @pytest.mark.asyncio
    async def test_parses_lab_instances_from_json(self, mock_server_ctx):
        """Should parse clab inspect JSON output into lab instances."""
        containers = {
            "containers": [
                {
                    "lab_name": "demo",
                    "name": "clab-demo-srl1",
                    "state": "running",
                    "created": "2024-01-15T10:30:00Z",
                },
                {
                    "lab_name": "demo",
                    "name": "clab-demo-linux1",
                    "state": "running",
                    "created": "2024-01-15T10:30:05Z",
                },
            ]
        }
        mock_server_ctx.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout=json.dumps(containers),
                stderr="",
                exit_code=0,
                duration_ms=100,
                command="clab inspect --all --format json",
            )
        )

        result = await lab_status(ctx=mock_server_ctx)

        assert result["status"] == "success"
        assert len(result["data"]) == 1
        assert result["data"][0]["topology_name"] == "demo"
        assert result["data"][0]["node_count"] == 2
        assert result["data"][0]["deployed_at"] == "2024-01-15T10:30:00Z"
        # All running → no container_states field
        assert "container_states" not in result["data"][0]

    @pytest.mark.asyncio
    async def test_includes_container_states_for_non_running(self, mock_server_ctx):
        """Should include container_states when some nodes are not running."""
        containers = {
            "containers": [
                {
                    "lab_name": "demo",
                    "name": "clab-demo-srl1",
                    "state": "running",
                    "created": "2024-01-15T10:30:00Z",
                },
                {
                    "lab_name": "demo",
                    "name": "clab-demo-linux1",
                    "state": "exited",
                    "created": "2024-01-15T10:30:05Z",
                },
            ]
        }
        mock_server_ctx.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout=json.dumps(containers),
                stderr="",
                exit_code=0,
                duration_ms=100,
                command="clab inspect --all --format json",
            )
        )

        result = await lab_status(ctx=mock_server_ctx)

        assert result["status"] == "success"
        assert "container_states" in result["data"][0]
        assert result["data"][0]["container_states"]["clab-demo-srl1"] == "running"
        assert result["data"][0]["container_states"]["clab-demo-linux1"] == "exited"

    @pytest.mark.asyncio
    async def test_groups_by_lab_name(self, mock_server_ctx):
        """Should group containers by lab name into separate entries."""
        containers = {
            "containers": [
                {
                    "lab_name": "lab1",
                    "name": "clab-lab1-node1",
                    "state": "running",
                    "created": "2024-01-15T10:00:00Z",
                },
                {
                    "lab_name": "lab2",
                    "name": "clab-lab2-node1",
                    "state": "running",
                    "created": "2024-01-15T11:00:00Z",
                },
            ]
        }
        mock_server_ctx.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout=json.dumps(containers),
                stderr="",
                exit_code=0,
                duration_ms=100,
                command="clab inspect --all --format json",
            )
        )

        result = await lab_status(ctx=mock_server_ctx)

        assert result["status"] == "success"
        assert len(result["data"]) == 2
        names = {entry["topology_name"] for entry in result["data"]}
        assert names == {"lab1", "lab2"}

    @pytest.mark.asyncio
    async def test_handles_json_parse_failure(self, mock_server_ctx):
        """Should return error when JSON parsing fails."""
        mock_server_ctx.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout="not valid json",
                stderr="",
                exit_code=0,
                duration_ms=50,
                command="clab inspect --all --format json",
            )
        )

        result = await lab_status(ctx=mock_server_ctx)

        assert result["status"] == "error"
        assert "parse" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_handles_execution_error(self, mock_server_ctx):
        """Should return error when clab inspect fails with a real error."""
        mock_server_ctx.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout="some output",
                stderr="permission denied",
                exit_code=1,
                duration_ms=50,
                command="clab inspect --all --format json",
            )
        )

        result = await lab_status(ctx=mock_server_ctx)

        assert result["status"] == "error"
        assert result["code"] == 1


class TestNodeHealth:
    """Tests for the node_health tool."""

    @pytest.mark.asyncio
    async def test_returns_health_metrics(self, mock_server_ctx):
        """Should return parsed health metrics on success."""
        # Mock docker stats
        mock_server_ctx.request_context.lifespan_context.executor.execute = AsyncMock(
            side_effect=[
                ExecutionResult(
                    stdout="12.50%\t512MiB / 2GiB\t25.00%",
                    stderr="",
                    exit_code=0,
                    duration_ms=100,
                    command="docker stats clab-demo-srl1 --no-stream --format ...",
                ),
                ExecutionResult(
                    stdout="2024-01-15T10:30:00.123456789Z",
                    stderr="",
                    exit_code=0,
                    duration_ms=50,
                    command="docker inspect --format '{{.State.StartedAt}}' clab-demo-srl1",
                ),
            ]
        )

        result = await node_health(node_name="clab-demo-srl1", ctx=mock_server_ctx)

        assert result["status"] == "success"
        assert result["data"]["node_name"] == "clab-demo-srl1"
        assert result["data"]["cpu_percent"] == 12.5
        assert result["data"]["memory_bytes"] == 512 * 1024 * 1024  # 512 MiB
        assert result["data"]["memory_percent"] == 25.0
        assert result["data"]["uptime_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_returns_error_when_container_not_found(self, mock_server_ctx):
        """Should return error when docker stats fails."""
        mock_server_ctx.request_context.lifespan_context.executor.execute = AsyncMock(
            return_value=ExecutionResult(
                stdout="",
                stderr="No such container: nonexistent",
                exit_code=1,
                duration_ms=30,
                command="docker stats nonexistent --no-stream --format ...",
            )
        )

        result = await node_health(node_name="nonexistent", ctx=mock_server_ctx)

        assert result["status"] == "error"
        assert "not found or not running" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_returns_error_when_inspect_fails(self, mock_server_ctx):
        """Should return error when docker inspect fails."""
        mock_server_ctx.request_context.lifespan_context.executor.execute = AsyncMock(
            side_effect=[
                ExecutionResult(
                    stdout="5.00%\t256MiB / 1GiB\t25.00%",
                    stderr="",
                    exit_code=0,
                    duration_ms=100,
                    command="docker stats clab-demo-srl1 --no-stream --format ...",
                ),
                ExecutionResult(
                    stdout="",
                    stderr="Error: No such object",
                    exit_code=1,
                    duration_ms=30,
                    command="docker inspect ...",
                ),
            ]
        )

        result = await node_health(node_name="clab-demo-srl1", ctx=mock_server_ctx)

        assert result["status"] == "error"
        assert "not found or not running" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_handles_malformed_stats_output(self, mock_server_ctx):
        """Should return error when docker stats output cannot be parsed."""
        mock_server_ctx.request_context.lifespan_context.executor.execute = AsyncMock(
            side_effect=[
                ExecutionResult(
                    stdout="malformed output",
                    stderr="",
                    exit_code=0,
                    duration_ms=100,
                    command="docker stats clab-demo-srl1 --no-stream --format ...",
                ),
                ExecutionResult(
                    stdout="2024-01-15T10:30:00Z",
                    stderr="",
                    exit_code=0,
                    duration_ms=50,
                    command="docker inspect ...",
                ),
            ]
        )

        result = await node_health(node_name="clab-demo-srl1", ctx=mock_server_ctx)

        assert result["status"] == "error"
        assert "parse" in result["message"].lower()


class TestParseMemoryString:
    """Tests for the _parse_memory_string helper."""

    def test_parse_mib(self):
        assert _parse_memory_string("512MiB") == 512 * 1024**2

    def test_parse_gib(self):
        assert _parse_memory_string("2GiB") == 2 * 1024**3

    def test_parse_kib(self):
        assert _parse_memory_string("1024KiB") == 1024 * 1024

    def test_parse_mb(self):
        assert _parse_memory_string("500MB") == 500 * 1000**2

    def test_parse_fractional(self):
        assert _parse_memory_string("1.5GiB") == int(1.5 * 1024**3)

    def test_parse_bytes_only(self):
        assert _parse_memory_string("1024B") == 1024

    def test_parse_plain_number(self):
        assert _parse_memory_string("1048576") == 1048576

    def test_parse_invalid_returns_zero(self):
        assert _parse_memory_string("invalid") == 0

    def test_parse_with_whitespace(self):
        assert _parse_memory_string("  512MiB  ") == 512 * 1024**2
