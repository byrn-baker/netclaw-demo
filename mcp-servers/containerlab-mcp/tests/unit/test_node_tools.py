"""Unit tests for node interaction tools (node_exec, get_node_access)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from containerlab_mcp.models import ExecutionResult, NodeAccessInfo
from containerlab_mcp.tools.node_tools import (
    MAX_COMMAND_LENGTH,
    _find_node_container,
    _get_valid_node_names,
    get_node_access,
    node_exec,
)


# --- Fixtures ---


SAMPLE_INSPECT_TABLE = """\
+---+------+----------+--------------+------+---------+----------------+----------------------+
| # | Name | Lab Name | Container ID | Kind | State   | IPv4 Address   | IPv6 Address         |
+---+------+----------+--------------+------+---------+----------------+----------------------+
| 1 | srl1 | dc-lab   | abc123def456 | srl  | running | 172.20.20.2/24 | 2001:db8::2/64       |
| 2 | srl2 | dc-lab   | def789abc012 | srl  | running | 172.20.20.3/24 | 2001:db8::3/64       |
| 3 | lin1 | dc-lab   | 111222333444 | linux| running | 172.20.20.4/24 |                      |
+---+------+----------+--------------+------+---------+----------------+----------------------+
"""


def _make_ctx(
    executor_execute_result: ExecutionResult | None = None,
    executor_execute_side_effect=None,
):
    """Create a mock MCP context with ServerContext."""
    from containerlab_mcp.access import NodeAccessDetector
    from containerlab_mcp.parser import OutputParser

    ctx = MagicMock()
    server_ctx = MagicMock()

    # Real parser for parsing table output
    server_ctx.output_parser = OutputParser()
    server_ctx.access_detector = NodeAccessDetector()

    # Mock executor
    executor = AsyncMock()
    if executor_execute_side_effect:
        executor.execute.side_effect = executor_execute_side_effect
    elif executor_execute_result:
        executor.execute.return_value = executor_execute_result
    else:
        executor.execute.return_value = ExecutionResult(
            stdout=SAMPLE_INSPECT_TABLE,
            stderr="",
            exit_code=0,
            duration_ms=100,
            command="clab inspect --all",
        )
    server_ctx.executor = executor

    ctx.request_context.lifespan_context = server_ctx
    return ctx, server_ctx


# --- Helper function tests ---


class TestGetValidNodeNames:
    """Tests for _get_valid_node_names helper."""

    def test_returns_matching_nodes(self):
        nodes = [
            {"name": "srl1", "lab_name": "dc-lab"},
            {"name": "srl2", "lab_name": "dc-lab"},
            {"name": "router1", "lab_name": "other-lab"},
        ]
        result = _get_valid_node_names(nodes, "dc-lab")
        assert result == ["srl1", "srl2"]

    def test_returns_empty_for_unknown_lab(self):
        nodes = [
            {"name": "srl1", "lab_name": "dc-lab"},
        ]
        result = _get_valid_node_names(nodes, "unknown-lab")
        assert result == []

    def test_handles_empty_nodes(self):
        result = _get_valid_node_names([], "dc-lab")
        assert result == []


class TestFindNodeContainer:
    """Tests for _find_node_container helper."""

    def test_finds_container_by_id(self):
        nodes = [
            {"name": "srl1", "lab_name": "dc-lab", "container_id": "abc123"},
        ]
        result = _find_node_container(nodes, "dc-lab", "srl1")
        assert result == "abc123"

    def test_constructs_container_name_when_no_id(self):
        nodes = [
            {"name": "srl1", "lab_name": "dc-lab", "container_id": ""},
        ]
        result = _find_node_container(nodes, "dc-lab", "srl1")
        assert result == "clab-dc-lab-srl1"

    def test_returns_none_for_missing_node(self):
        nodes = [
            {"name": "srl1", "lab_name": "dc-lab", "container_id": "abc123"},
        ]
        result = _find_node_container(nodes, "dc-lab", "nonexistent")
        assert result is None


# --- node_exec tests ---


class TestNodeExec:
    """Tests for the node_exec tool."""

    @pytest.mark.asyncio
    async def test_rejects_command_over_max_length(self):
        ctx, _ = _make_ctx()
        long_command = "x" * (MAX_COMMAND_LENGTH + 1)

        result = await node_exec(
            lab_name="dc-lab",
            node_name="srl1",
            exec_command=long_command,
            ctx=ctx,
        )

        assert result["status"] == "error"
        assert "exceeds maximum" in result["stderr"]
        assert result["exit_code"] == -1
        assert result["duration_ms"] == 0

    @pytest.mark.asyncio
    async def test_accepts_command_at_max_length(self):
        """Command exactly at max length should be accepted."""
        ctx, server_ctx = _make_ctx()

        # First call: inspect returns nodes; second call: docker exec succeeds
        server_ctx.executor.execute.side_effect = [
            ExecutionResult(
                stdout=SAMPLE_INSPECT_TABLE,
                stderr="",
                exit_code=0,
                duration_ms=50,
                command="clab inspect --all",
            ),
            ExecutionResult(
                stdout="output",
                stderr="",
                exit_code=0,
                duration_ms=200,
                command="docker exec -it abc123def456 cmd",
            ),
        ]

        command = "x" * MAX_COMMAND_LENGTH
        result = await node_exec(
            lab_name="dc-lab",
            node_name="srl1",
            exec_command=command,
            ctx=ctx,
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_returns_error_when_node_not_found(self):
        ctx, _ = _make_ctx()

        result = await node_exec(
            lab_name="dc-lab",
            node_name="nonexistent",
            exec_command="ip a",
            ctx=ctx,
        )

        assert result["status"] == "error"
        assert "not found" in result["stderr"]
        assert "srl1" in result["stderr"]
        assert "srl2" in result["stderr"]
        assert "lin1" in result["stderr"]

    @pytest.mark.asyncio
    async def test_returns_error_when_lab_not_found(self):
        ctx, _ = _make_ctx()

        result = await node_exec(
            lab_name="nonexistent-lab",
            node_name="srl1",
            exec_command="ip a",
            ctx=ctx,
        )

        assert result["status"] == "error"
        assert "No nodes found" in result["stderr"]

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        ctx, server_ctx = _make_ctx()

        server_ctx.executor.execute.side_effect = [
            ExecutionResult(
                stdout=SAMPLE_INSPECT_TABLE,
                stderr="",
                exit_code=0,
                duration_ms=50,
                command="clab inspect --all",
            ),
            ExecutionResult(
                stdout="eth0: 172.20.20.2/24\n",
                stderr="",
                exit_code=0,
                duration_ms=150,
                command="docker exec -it abc123def456 ip address show",
            ),
        ]

        result = await node_exec(
            lab_name="dc-lab",
            node_name="srl1",
            exec_command="ip address show",
            ctx=ctx,
        )

        assert result["status"] == "success"
        assert result["stdout"] == "eth0: 172.20.20.2/24\n"
        assert result["exit_code"] == 0
        assert "docker exec -it abc123def456" in result["command"]
        assert result["duration_ms"] == 150

    @pytest.mark.asyncio
    async def test_timeout_returns_error(self):
        ctx, server_ctx = _make_ctx()

        server_ctx.executor.execute.side_effect = [
            ExecutionResult(
                stdout=SAMPLE_INSPECT_TABLE,
                stderr="",
                exit_code=0,
                duration_ms=50,
                command="clab inspect --all",
            ),
            ExecutionResult(
                stdout="",
                stderr="Command timed out after 30.0s",
                exit_code=-1,
                duration_ms=30000,
                command="docker exec -it abc123def456 sleep 60",
            ),
        ]

        result = await node_exec(
            lab_name="dc-lab",
            node_name="srl1",
            exec_command="sleep 60",
            ctx=ctx,
        )

        assert result["status"] == "error"
        assert "timed out" in result["stderr"]
        assert result["exit_code"] == -1
        assert result["duration_ms"] == 30000

    @pytest.mark.asyncio
    async def test_inspect_failure_returns_error(self):
        ctx, server_ctx = _make_ctx()

        server_ctx.executor.execute.return_value = ExecutionResult(
            stdout="",
            stderr="clab not found",
            exit_code=1,
            duration_ms=10,
            command="clab inspect --all",
        )

        result = await node_exec(
            lab_name="dc-lab",
            node_name="srl1",
            exec_command="ip a",
            ctx=ctx,
        )

        assert result["status"] == "error"
        assert "Failed to inspect" in result["stderr"]


# --- get_node_access tests ---


class TestGetNodeAccess:
    """Tests for the get_node_access tool."""

    @pytest.mark.asyncio
    async def test_returns_access_info_without_topology(self):
        ctx, _ = _make_ctx()

        result = await get_node_access(
            lab_name="dc-lab",
            ctx=ctx,
        )

        assert result["status"] == "success"
        assert len(result["data"]) == 3

        # Check first node
        node = result["data"][0]
        assert node["node_name"] == "srl1"
        assert node["container_id"] == "abc123def456"
        assert node["mgmt_ipv4"] == "172.20.20.2"
        assert node["access_method"] == "docker_exec"
        assert "docker exec -it" in node["connection_command"]

    @pytest.mark.asyncio
    async def test_returns_error_when_lab_not_found(self):
        ctx, _ = _make_ctx()

        result = await get_node_access(
            lab_name="nonexistent-lab",
            ctx=ctx,
        )

        assert result["status"] == "error"
        assert "No nodes found" in result["message"]
        assert "dc-lab" in result["message"]

    @pytest.mark.asyncio
    async def test_strips_cidr_from_ipv4(self):
        ctx, _ = _make_ctx()

        result = await get_node_access(
            lab_name="dc-lab",
            ctx=ctx,
        )

        # All IPs should have CIDR stripped
        for node in result["data"]:
            if node["mgmt_ipv4"]:
                assert "/" not in node["mgmt_ipv4"]

    @pytest.mark.asyncio
    async def test_inspect_failure_returns_error(self):
        ctx, server_ctx = _make_ctx()

        server_ctx.executor.execute.return_value = ExecutionResult(
            stdout="",
            stderr="error running inspect",
            exit_code=1,
            duration_ms=10,
            command="clab inspect --all",
        )

        result = await get_node_access(
            lab_name="dc-lab",
            ctx=ctx,
        )

        assert result["status"] == "error"
        assert "Failed to inspect" in result["message"]

    @pytest.mark.asyncio
    async def test_with_topology_file_uses_access_detector(self, tmp_path):
        """When topology_file_path is provided, should use NodeAccessDetector."""
        # Create a minimal topology file
        topo_file = tmp_path / "test.clab.yml"
        topo_file.write_text(
            "name: dc-lab\n"
            "topology:\n"
            "  nodes:\n"
            "    srl1:\n"
            "      kind: srl\n"
            "    srl2:\n"
            "      kind: srl\n"
            "    lin1:\n"
            "      kind: linux\n"
        )

        ctx, _ = _make_ctx()

        result = await get_node_access(
            lab_name="dc-lab",
            topology_file_path=str(topo_file),
            ctx=ctx,
        )

        assert result["status"] == "success"
        assert len(result["data"]) == 3

        # SRL nodes should get SSH access method (since they have well-known creds)
        srl_nodes = [n for n in result["data"] if n["node_name"] in ("srl1", "srl2")]
        for node in srl_nodes:
            assert node["access_method"] == "ssh"
            assert node["username"] == "admin"
            assert node["password"] == "NokiaSrl1!"

        # Linux node should get docker_exec
        linux_nodes = [n for n in result["data"] if n["node_name"] == "lin1"]
        assert linux_nodes[0]["access_method"] == "docker_exec"
