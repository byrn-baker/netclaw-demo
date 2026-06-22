"""Unit tests for containerlab_mcp.tools.clab_tools module."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from containerlab_mcp.models import ExecutionResult, ServerConfig, StructuredResponse
from containerlab_mcp.parser import OutputParser
from containerlab_mcp.safety import SafetyGate
from containerlab_mcp.tools.clab_tools import (
    _resolve_topology_name,
    deploy,
    destroy,
    generate,
    graph,
    inspect,
    save,
    version,
)


@pytest.fixture
def mock_context():
    """Create a mock MCP Context with ServerContext."""
    ctx = MagicMock()
    server_ctx = MagicMock()
    server_ctx.config = ServerConfig(remote=None)
    server_ctx.executor = AsyncMock()
    server_ctx.output_parser = OutputParser()
    server_ctx.safety_gate = SafetyGate()
    ctx.request_context.lifespan_context = server_ctx
    return ctx


@pytest.fixture
def topology_file(tmp_path):
    """Create a temporary topology YAML file."""
    topo = {
        "name": "test-lab",
        "topology": {
            "nodes": {
                "router1": {"kind": "srl", "image": "ghcr.io/nokia/srlinux"},
                "router2": {"kind": "srl", "image": "ghcr.io/nokia/srlinux"},
            },
            "links": [
                {"endpoints": ["router1:e1-1", "router2:e1-1"]},
            ],
        },
    }
    path = tmp_path / "test.clab.yml"
    path.write_text(yaml.dump(topo))
    return str(path)


class TestResolveTopologyName:
    """Tests for _resolve_topology_name helper."""

    def test_resolves_name_from_yaml(self, topology_file):
        """Should extract the 'name' field from topology YAML."""
        name = _resolve_topology_name(topology_file)
        assert name == "test-lab"

    def test_falls_back_to_filename(self, tmp_path):
        """Should use filename stem when no 'name' field is present."""
        topo = {
            "topology": {
                "nodes": {"n1": {"kind": "linux"}},
                "links": [],
            }
        }
        path = tmp_path / "mylab.clab.yml"
        path.write_text(yaml.dump(topo))
        name = _resolve_topology_name(str(path))
        assert name == "mylab"

    def test_raises_on_invalid_file(self):
        """Should raise ValueError for non-existent file."""
        with pytest.raises(ValueError, match="Cannot read topology file"):
            _resolve_topology_name("/nonexistent/path.clab.yml")

    def test_raises_on_non_mapping(self, tmp_path):
        """Should raise ValueError for non-dict YAML content."""
        path = tmp_path / "bad.clab.yml"
        path.write_text("- a list\n- not a dict\n")
        with pytest.raises(ValueError, match="does not contain a YAML mapping"):
            _resolve_topology_name(str(path))


class TestDeployTool:
    """Tests for the deploy tool."""

    @pytest.mark.asyncio
    async def test_deploy_basic(self, mock_context):
        """Should build correct clab deploy args and return success."""
        mock_context.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout="Lab deployed successfully",
                stderr="",
                exit_code=0,
                duration_ms=5000,
                command="clab deploy --topo /labs/test.clab.yml",
            )
        )

        result = await deploy(
            topology_file_path="/labs/test.clab.yml",
            ctx=mock_context,
        )

        assert result["status"] == "success"
        assert result["duration_ms"] == 5000
        mock_context.request_context.lifespan_context.executor.execute.assert_called_once()
        call_args = mock_context.request_context.lifespan_context.executor.execute.call_args
        assert call_args[0][0] == ["clab", "deploy", "--topo", "/labs/test.clab.yml"]

    @pytest.mark.asyncio
    async def test_deploy_with_options(self, mock_context):
        """Should include lab_name and reconfigure flags."""
        mock_context.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout="done",
                stderr="",
                exit_code=0,
                duration_ms=100,
                command="clab deploy --topo t.yml --name mylab --reconfigure",
            )
        )

        result = await deploy(
            topology_file_path="t.yml",
            lab_name="mylab",
            reconfigure=True,
            ctx=mock_context,
        )

        assert result["status"] == "success"
        call_args = mock_context.request_context.lifespan_context.executor.execute.call_args
        cmd = call_args[0][0]
        assert "--name" in cmd
        assert "mylab" in cmd
        assert "--reconfigure" in cmd

    @pytest.mark.asyncio
    async def test_deploy_error_response(self, mock_context):
        """Should return error with sanitized message on CLI failure."""
        mock_context.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout="",
                stderr="Error: topology file not found",
                exit_code=1,
                duration_ms=50,
                command="clab deploy --topo bad.yml",
            )
        )

        result = await deploy(
            topology_file_path="bad.yml",
            ctx=mock_context,
        )

        assert result["status"] == "error"
        assert result["code"] == 1
        assert "not found" in result["message"]


class TestDestroyTool:
    """Tests for the destroy tool."""

    @pytest.mark.asyncio
    async def test_destroy_safety_rejection_no_confirm(self, mock_context, topology_file):
        """Should reject destroy when confirm_topology_name is missing."""
        result = await destroy(
            topology_file_path=topology_file,
            confirm_topology_name=None,
            ctx=mock_context,
        )

        assert result["status"] == "error"
        assert "confirm_topology_name" in result["message"]
        # Executor should NOT have been called
        mock_context.request_context.lifespan_context.executor.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_destroy_safety_rejection_mismatch(self, mock_context, topology_file):
        """Should reject destroy when confirm_topology_name doesn't match."""
        result = await destroy(
            topology_file_path=topology_file,
            confirm_topology_name="wrong-name",
            ctx=mock_context,
        )

        assert result["status"] == "error"
        assert "mismatch" in result["message"]

    @pytest.mark.asyncio
    async def test_destroy_safety_rejection_cleanup_not_confirmed(
        self, mock_context, topology_file
    ):
        """Should reject when cleanup_artifacts=True but confirm_cleanup is not True."""
        result = await destroy(
            topology_file_path=topology_file,
            confirm_topology_name="test-lab",
            cleanup_artifacts=True,
            confirm_cleanup=None,
            ctx=mock_context,
        )

        assert result["status"] == "error"
        assert "cleanup" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_destroy_success_with_confirmation(self, mock_context, topology_file):
        """Should execute destroy when safety gate passes."""
        mock_context.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout="Lab destroyed",
                stderr="",
                exit_code=0,
                duration_ms=3000,
                command="clab destroy --topo test.clab.yml",
            )
        )

        result = await destroy(
            topology_file_path=topology_file,
            confirm_topology_name="test-lab",
            ctx=mock_context,
        )

        assert result["status"] == "success"
        mock_context.request_context.lifespan_context.executor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_destroy_with_lab_name(self, mock_context):
        """Should use lab_name directly as target when provided."""
        mock_context.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout="Lab destroyed",
                stderr="",
                exit_code=0,
                duration_ms=2000,
                command="clab destroy --name my-lab",
            )
        )

        result = await destroy(
            lab_name="my-lab",
            confirm_topology_name="my-lab",
            ctx=mock_context,
        )

        assert result["status"] == "success"
        call_args = mock_context.request_context.lifespan_context.executor.execute.call_args
        cmd = call_args[0][0]
        assert "--name" in cmd
        assert "my-lab" in cmd

    @pytest.mark.asyncio
    async def test_destroy_requires_topology_or_lab_name(self, mock_context):
        """Should error when neither topology_file_path nor lab_name provided."""
        result = await destroy(
            ctx=mock_context,
        )

        assert result["status"] == "error"
        assert "Either" in result["message"]


class TestInspectTool:
    """Tests for the inspect tool."""

    @pytest.mark.asyncio
    async def test_inspect_parses_table_output(self, mock_context):
        """Should parse clab inspect table output into structured data."""
        table_output = (
            "+---+------+--------------+-------+\n"
            "| # | Name | Container ID | State |\n"
            "+---+------+--------------+-------+\n"
            "| 1 | r1   | abc123       | run   |\n"
            "| 2 | r2   | def456       | run   |\n"
            "+---+------+--------------+-------+\n"
        )
        mock_context.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout=table_output,
                stderr="",
                exit_code=0,
                duration_ms=200,
                command="clab inspect --all",
            )
        )

        result = await inspect(ctx=mock_context)

        assert result["status"] == "success"
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 2
        assert result["data"][0]["name"] == "r1"
        assert result["data"][1]["container_id"] == "def456"

    @pytest.mark.asyncio
    async def test_inspect_with_filter(self, mock_context):
        """Should pass --name filter to clab inspect."""
        mock_context.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout="",
                stderr="",
                exit_code=0,
                duration_ms=100,
                command="clab inspect --name test-lab",
            )
        )

        result = await inspect(topology_name="test-lab", ctx=mock_context)

        call_args = mock_context.request_context.lifespan_context.executor.execute.call_args
        cmd = call_args[0][0]
        assert "--name" in cmd
        assert "test-lab" in cmd
        assert "--all" not in cmd

    @pytest.mark.asyncio
    async def test_inspect_all_when_no_filter(self, mock_context):
        """Should use --all when no filter is provided."""
        mock_context.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout="",
                stderr="",
                exit_code=0,
                duration_ms=100,
                command="clab inspect --all",
            )
        )

        result = await inspect(ctx=mock_context)

        call_args = mock_context.request_context.lifespan_context.executor.execute.call_args
        cmd = call_args[0][0]
        assert "--all" in cmd


class TestSaveTool:
    """Tests for the save tool."""

    @pytest.mark.asyncio
    async def test_save_with_topology_file(self, mock_context):
        """Should build correct args with topology file."""
        mock_context.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout="Saved",
                stderr="",
                exit_code=0,
                duration_ms=500,
                command="clab save --topo test.yml",
            )
        )

        result = await save(topology_file_path="test.yml", ctx=mock_context)

        assert result["status"] == "success"
        call_args = mock_context.request_context.lifespan_context.executor.execute.call_args
        cmd = call_args[0][0]
        assert cmd == ["clab", "save", "--topo", "test.yml"]

    @pytest.mark.asyncio
    async def test_save_with_lab_name(self, mock_context):
        """Should build correct args with lab name."""
        mock_context.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout="Saved",
                stderr="",
                exit_code=0,
                duration_ms=500,
                command="clab save --name lab1",
            )
        )

        result = await save(lab_name="lab1", ctx=mock_context)

        assert result["status"] == "success"
        call_args = mock_context.request_context.lifespan_context.executor.execute.call_args
        cmd = call_args[0][0]
        assert "--name" in cmd
        assert "lab1" in cmd


class TestGraphTool:
    """Tests for the graph tool."""

    @pytest.mark.asyncio
    async def test_graph_basic(self, mock_context):
        """Should build correct args for graph generation."""
        mock_context.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout="Graph created: graph.html",
                stderr="",
                exit_code=0,
                duration_ms=300,
                command="clab graph --topo test.yml --format html",
            )
        )

        result = await graph(topology_file_path="test.yml", ctx=mock_context)

        assert result["status"] == "success"
        call_args = mock_context.request_context.lifespan_context.executor.execute.call_args
        cmd = call_args[0][0]
        assert cmd == ["clab", "graph", "--topo", "test.yml", "--format", "html"]

    @pytest.mark.asyncio
    async def test_graph_custom_format(self, mock_context):
        """Should pass custom output format."""
        mock_context.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout="Graph created",
                stderr="",
                exit_code=0,
                duration_ms=200,
                command="clab graph --topo t.yml --format json",
            )
        )

        result = await graph(
            topology_file_path="t.yml", output_format="json", ctx=mock_context
        )

        call_args = mock_context.request_context.lifespan_context.executor.execute.call_args
        cmd = call_args[0][0]
        assert "--format" in cmd
        assert "json" in cmd


class TestGenerateTool:
    """Tests for the generate tool."""

    @pytest.mark.asyncio
    async def test_generate_default_params(self, mock_context):
        """Should use default node_count=2 and topology_type=ring."""
        mock_context.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout="Topology generated",
                stderr="",
                exit_code=0,
                duration_ms=100,
                command="clab generate --name out.yml --nodes 2 --kind ring",
            )
        )

        result = await generate(topology_file_path="out.yml", ctx=mock_context)

        assert result["status"] == "success"
        call_args = mock_context.request_context.lifespan_context.executor.execute.call_args
        cmd = call_args[0][0]
        assert "--nodes" in cmd
        assert "2" in cmd
        assert "--kind" in cmd
        assert "ring" in cmd

    @pytest.mark.asyncio
    async def test_generate_custom_params(self, mock_context):
        """Should pass custom node count and topology type."""
        mock_context.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout="Generated",
                stderr="",
                exit_code=0,
                duration_ms=100,
                command="clab generate --name out.yml --nodes 5 --kind full-mesh",
            )
        )

        result = await generate(
            topology_file_path="out.yml",
            node_count=5,
            topology_type="full-mesh",
            ctx=mock_context,
        )

        assert result["status"] == "success"
        call_args = mock_context.request_context.lifespan_context.executor.execute.call_args
        cmd = call_args[0][0]
        assert "5" in cmd
        assert "full-mesh" in cmd


class TestVersionTool:
    """Tests for the version tool."""

    @pytest.mark.asyncio
    async def test_version_success(self, mock_context):
        """Should return version information on success."""
        mock_context.request_context.lifespan_context.executor.execute.return_value = (
            ExecutionResult(
                stdout="containerlab version 0.48.0",
                stderr="",
                exit_code=0,
                duration_ms=50,
                command="clab version",
            )
        )

        result = await version(ctx=mock_context)

        assert result["status"] == "success"
        assert "0.48.0" in result["data"]["output"]
        assert result["duration_ms"] == 50
        assert result["command"] == "clab version"


class TestRemoteExecution:
    """Tests for remote execution path."""

    @pytest.mark.asyncio
    async def test_uses_remote_executor_when_configured(self, mock_context):
        """Should use execute_remote when remote is configured."""
        mock_context.request_context.lifespan_context.config = ServerConfig(
            remote="user@host"
        )
        mock_context.request_context.lifespan_context.executor.execute_remote.return_value = (
            ExecutionResult(
                stdout="remote version info",
                stderr="",
                exit_code=0,
                duration_ms=200,
                command="clab version",
            )
        )

        result = await version(ctx=mock_context)

        assert result["status"] == "success"
        mock_context.request_context.lifespan_context.executor.execute_remote.assert_called_once()
        mock_context.request_context.lifespan_context.executor.execute.assert_not_called()
