"""Property-based tests for tool schema completeness and invalid node errors.

# Feature: containerlab-mcp, Property 15: Tool Schema Completeness
# Feature: containerlab-mcp, Property 16: Invalid Node Error Includes Valid Names
"""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from containerlab_mcp.server import mcp
from containerlab_mcp.tools.node_tools import node_exec, get_node_access


# --- Strategies ---


def _node_name_strategy() -> st.SearchStrategy[str]:
    """Generate valid node name strings (alphanumeric + hyphens)."""
    return st.from_regex(r"[a-z][a-z0-9\-]{2,15}", fullmatch=True)


def _lab_name_strategy() -> st.SearchStrategy[str]:
    """Generate valid lab name strings."""
    return st.from_regex(r"[a-z][a-z0-9\-]{2,15}", fullmatch=True)


def _invalid_node_name_strategy(valid_names: list[str]) -> st.SearchStrategy[str]:
    """Generate node names guaranteed not to be in the valid set."""
    return _node_name_strategy().filter(lambda n: n not in valid_names)


# --- Mock Context for Property 16 ---


def _make_mock_ctx_with_nodes(lab_name: str, node_names: list[str]):
    """Create a mock MCP context that returns the specified nodes for a lab.

    Args:
        lab_name: Name of the lab the nodes belong to.
        node_names: List of valid node names in the lab.
    """
    nodes = [
        {"name": name, "lab_name": lab_name, "container_id": f"cid-{name}"}
        for name in node_names
    ]

    mock_ctx = MagicMock()
    mock_server_ctx = MagicMock()

    # Mock executor - inspect call returns success
    mock_executor = AsyncMock()
    inspect_result = MagicMock()
    inspect_result.exit_code = 0
    inspect_result.stdout = ""
    inspect_result.stderr = ""
    inspect_result.duration_ms = 10
    inspect_result.command = "clab inspect --all"

    mock_executor.execute = AsyncMock(return_value=inspect_result)

    # Mock output parser - returns our nodes
    mock_output_parser = MagicMock()
    mock_output_parser.parse_table = MagicMock(return_value=nodes)

    # Mock access detector
    mock_access_detector = MagicMock()

    mock_server_ctx.executor = mock_executor
    mock_server_ctx.output_parser = mock_output_parser
    mock_server_ctx.access_detector = mock_access_detector
    mock_server_ctx.config = MagicMock()
    mock_server_ctx.config.remote = None

    mock_ctx.request_context = MagicMock()
    mock_ctx.request_context.lifespan_context = mock_server_ctx

    return mock_ctx


# --- Property 15: Tool Schema Completeness ---


class TestToolSchemaCompleteness:
    """Property 15: Tool Schema Completeness.

    For any registered MCP tool in the server, the tool schema SHALL include:
    a description of no more than 120 characters, all parameters documented
    with types and required/optional designation, and at least one usage example.
    Every parameter name SHALL be in snake_case and consist of at least two words
    or at least 8 characters.

    **Validates: Requirements 10.1, 10.2, 10.3**
    """

    def _get_all_tools(self) -> list[tuple[str, object]]:
        """Retrieve all registered MCP tools and their schemas.

        Returns list of (tool_name, tool_object) tuples.
        """
        tools = []
        tm = mcp._tool_manager
        for name, tool in tm._tools.items():
            tools.append((name, tool))
        return tools

    def _get_tool_descriptions(self) -> dict[str, str]:
        """Get all tool short descriptions (the description= arg in @mcp.tool).

        These are the top-level descriptions that must be ≤120 characters.
        """
        descriptions = {}
        for name, tool in self._get_all_tools():
            descriptions[name] = tool.description
        return descriptions

    def _get_tool_parameter_names(self) -> dict[str, list[str]]:
        """Get parameter names for each registered tool.

        Excludes 'ctx' which is injected automatically by the framework.
        """
        param_names: dict[str, list[str]] = {}
        for name, tool in self._get_all_tools():
            params = []
            if hasattr(tool, "parameters") and isinstance(tool.parameters, dict):
                properties = tool.parameters.get("properties", {})
                for pname in properties:
                    if pname == "ctx":
                        continue  # Framework-injected, not visible to agents
                    params.append(pname)
            param_names[name] = params
        return param_names

    @given(data=st.data())
    @settings(max_examples=100)
    def test_all_tool_descriptions_within_120_chars(self, data) -> None:
        """Every registered tool has a description of at most 120 characters.

        # Feature: containerlab-mcp, Property 15: Tool Schema Completeness
        **Validates: Requirements 10.1, 10.2, 10.3**
        """
        descriptions = self._get_tool_descriptions()
        assume(len(descriptions) > 0)

        # Pick a random tool from the registered set
        tool_name = data.draw(st.sampled_from(sorted(descriptions.keys())))
        desc = descriptions[tool_name]

        assert len(desc) <= 120, (
            f"Tool '{tool_name}' description is {len(desc)} chars, exceeds 120: "
            f"'{desc}'"
        )

    @given(data=st.data())
    @settings(max_examples=100)
    def test_all_parameter_names_are_snake_case(self, data) -> None:
        """Every parameter name is snake_case and has ≥2 words or ≥8 characters.

        # Feature: containerlab-mcp, Property 15: Tool Schema Completeness
        **Validates: Requirements 10.1, 10.2, 10.3**
        """
        param_names = self._get_tool_parameter_names()
        assume(len(param_names) > 0)

        # Collect all tools that have parameters
        tools_with_params = {
            k: v for k, v in param_names.items() if len(v) > 0
        }
        assume(len(tools_with_params) > 0)

        tool_name = data.draw(st.sampled_from(sorted(tools_with_params.keys())))
        params = tools_with_params[tool_name]
        param = data.draw(st.sampled_from(params))

        # Check snake_case pattern (lowercase, underscores, digits)
        assert re.match(r"^[a-z][a-z0-9_]*$", param), (
            f"Parameter '{param}' in tool '{tool_name}' is not snake_case"
        )

        # Check: at least two words (contains underscore) OR at least 8 characters
        has_two_words = "_" in param
        has_eight_chars = len(param) >= 8
        assert has_two_words or has_eight_chars, (
            f"Parameter '{param}' in tool '{tool_name}' must have ≥2 words "
            f"(contain underscore) or ≥8 characters, but has {len(param)} chars "
            f"and no underscore"
        )

    @given(data=st.data())
    @settings(max_examples=100)
    def test_all_tools_have_docstrings_with_examples(self, data) -> None:
        """Every registered tool has a docstring containing at least one example.

        # Feature: containerlab-mcp, Property 15: Tool Schema Completeness
        **Validates: Requirements 10.1, 10.2, 10.3**
        """
        tools = self._get_all_tools()
        assume(len(tools) > 0)

        tool_name, tool = data.draw(st.sampled_from(tools))

        # Get the docstring from the tool function
        docstring = ""
        if hasattr(tool, "fn") and tool.fn.__doc__:
            docstring = tool.fn.__doc__
        elif hasattr(tool, "__doc__") and tool.__doc__:
            docstring = tool.__doc__

        assert len(docstring) > 0, (
            f"Tool '{tool_name}' has no docstring"
        )

        # Check for usage example markers
        has_example = (
            "Example:" in docstring
            or ">>>" in docstring
            or "example" in docstring.lower()
        )
        assert has_example, (
            f"Tool '{tool_name}' docstring does not contain a usage example"
        )

    @given(data=st.data())
    @settings(max_examples=100)
    def test_all_tools_have_parameter_documentation(self, data) -> None:
        """Every registered tool documents all its parameters with types.

        # Feature: containerlab-mcp, Property 15: Tool Schema Completeness
        **Validates: Requirements 10.1, 10.2, 10.3**
        """
        tools = self._get_all_tools()
        assume(len(tools) > 0)

        tool_name, tool = data.draw(st.sampled_from(tools))

        # Get docstring
        docstring = ""
        if hasattr(tool, "fn") and tool.fn.__doc__:
            docstring = tool.fn.__doc__
        elif hasattr(tool, "__doc__") and tool.__doc__:
            docstring = tool.__doc__

        # Get parameter names (excluding ctx)
        params = []
        if hasattr(tool, "fn"):
            import inspect
            sig = inspect.signature(tool.fn)
            params = [p for p in sig.parameters if p != "ctx"]

        # Check each parameter is mentioned in docstring
        for param in params:
            assert param in docstring, (
                f"Parameter '{param}' of tool '{tool_name}' is not documented "
                f"in docstring"
            )


# --- Property 16: Invalid Node Error Includes Valid Names ---


class TestInvalidNodeErrorIncludesValidNames:
    """Property 16: Invalid Node Error Includes Valid Names.

    For any deployed lab with a known set of node names, calling ``node_exec``
    or ``get_node_access`` with a node name not in that set SHALL return an
    error response that includes the complete list of valid node names.

    **Validates: Requirements 3.6**
    """

    @given(
        lab_name=_lab_name_strategy(),
        valid_nodes=st.lists(
            _node_name_strategy(),
            min_size=1,
            max_size=8,
            unique=True,
        ),
        data=st.data(),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_node_exec_invalid_node_includes_valid_names(
        self, lab_name: str, valid_nodes: list[str], data
    ) -> None:
        """node_exec with invalid node name returns error listing all valid names.

        # Feature: containerlab-mcp, Property 16: Invalid Node Error Includes Valid Names
        **Validates: Requirements 3.6**
        """
        # Generate a node name that's NOT in the valid set
        invalid_node = data.draw(
            _node_name_strategy().filter(lambda n: n not in valid_nodes)
        )

        mock_ctx = _make_mock_ctx_with_nodes(lab_name, valid_nodes)
        result = await node_exec(
            lab_name=lab_name,
            node_name=invalid_node,
            exec_command="ip addr",
            ctx=mock_ctx,
        )

        assert result["status"] == "error", (
            f"Expected error for invalid node '{invalid_node}'"
        )

        # The error message should include all valid node names
        error_msg = result.get("stderr", "")
        for valid_name in valid_nodes:
            assert valid_name in error_msg, (
                f"Valid node name '{valid_name}' not found in error message: "
                f"'{error_msg}'"
            )

    @given(
        lab_name=_lab_name_strategy(),
        valid_nodes=st.lists(
            _node_name_strategy(),
            min_size=1,
            max_size=8,
            unique=True,
        ),
        data=st.data(),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_get_node_access_invalid_lab_returns_error(
        self, lab_name: str, valid_nodes: list[str], data
    ) -> None:
        """get_node_access with a lab that has no nodes returns an error.

        When the lab doesn't exist (no matching nodes), get_node_access returns
        an error. This validates the error path for invalid node lookups.

        # Feature: containerlab-mcp, Property 16: Invalid Node Error Includes Valid Names
        **Validates: Requirements 3.6**
        """
        # Use an invalid lab name that won't match the nodes
        invalid_lab = data.draw(
            _lab_name_strategy().filter(lambda n: n != lab_name)
        )

        mock_ctx = _make_mock_ctx_with_nodes(lab_name, valid_nodes)
        result = await get_node_access(
            lab_name=invalid_lab,
            topology_file_path=None,
            ctx=mock_ctx,
        )

        assert result["status"] == "error", (
            f"Expected error for invalid lab '{invalid_lab}'"
        )
        # The error message should mention that no nodes were found
        error_msg = result.get("message", "")
        assert "no nodes found" in error_msg.lower() or invalid_lab in error_msg.lower(), (
            f"Error message should mention invalid lab: '{error_msg}'"
        )

    @given(
        lab_name=_lab_name_strategy(),
        valid_nodes=st.lists(
            _node_name_strategy(),
            min_size=2,
            max_size=8,
            unique=True,
        ),
        data=st.data(),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_node_exec_error_contains_complete_node_list(
        self, lab_name: str, valid_nodes: list[str], data
    ) -> None:
        """The error message contains ALL valid node names, not just some.

        # Feature: containerlab-mcp, Property 16: Invalid Node Error Includes Valid Names
        **Validates: Requirements 3.6**
        """
        invalid_node = data.draw(
            _node_name_strategy().filter(lambda n: n not in valid_nodes)
        )

        mock_ctx = _make_mock_ctx_with_nodes(lab_name, valid_nodes)
        result = await node_exec(
            lab_name=lab_name,
            node_name=invalid_node,
            exec_command="show version",
            ctx=mock_ctx,
        )

        assert result["status"] == "error"
        error_msg = result.get("stderr", "")

        # ALL valid node names must appear
        missing_names = [
            name for name in valid_nodes if name not in error_msg
        ]
        assert len(missing_names) == 0, (
            f"Error message is missing valid node names: {missing_names}. "
            f"Full error: '{error_msg}'"
        )

    @given(
        lab_name=_lab_name_strategy(),
        valid_nodes=st.lists(
            _node_name_strategy(),
            min_size=1,
            max_size=8,
            unique=True,
        ),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_node_exec_valid_node_not_rejected(
        self, lab_name: str, valid_nodes: list[str]
    ) -> None:
        """node_exec with a valid node name does NOT return a 'not found' error.

        # Feature: containerlab-mcp, Property 16: Invalid Node Error Includes Valid Names
        **Validates: Requirements 3.6**
        """
        # Pick a valid node
        node_name = valid_nodes[0]

        mock_ctx = _make_mock_ctx_with_nodes(lab_name, valid_nodes)
        result = await node_exec(
            lab_name=lab_name,
            node_name=node_name,
            exec_command="ip addr",
            ctx=mock_ctx,
        )

        # Should not get a "not found" error
        if result["status"] == "error":
            error_msg = result.get("stderr", "")
            assert "not found" not in error_msg.lower(), (
                f"Valid node '{node_name}' should not get 'not found' error"
            )
