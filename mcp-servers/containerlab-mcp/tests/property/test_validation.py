"""Property-based tests for command validation.

# Feature: containerlab-mcp, Property 14: Command Length Validation
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from containerlab_mcp.tools.node_tools import MAX_COMMAND_LENGTH, node_exec


# --- Strategies ---


def _valid_command_strategy() -> st.SearchStrategy[str]:
    """Generate command strings within the allowed length (1 to 4096 chars)."""
    return st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789 -_/.",
        min_size=1,
        max_size=MAX_COMMAND_LENGTH,
    ).filter(lambda s: len(s.strip()) > 0)


def _overlong_command_strategy() -> st.SearchStrategy[str]:
    """Generate command strings that exceed the max allowed length (>4096 chars)."""
    # Use a simpler alphabet to avoid excessive entropy
    return st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789 -_/.",
        min_size=MAX_COMMAND_LENGTH + 1,
        max_size=MAX_COMMAND_LENGTH + 500,
    )


# --- Mock Context ---


def _make_mock_ctx(nodes: list[dict[str, str]] | None = None):
    """Create a mock MCP context with a ServerContext that returns given nodes.

    Args:
        nodes: List of node dicts to return from inspect. If None, returns
               a default set with one node in lab "test-lab".
    """
    if nodes is None:
        nodes = [
            {"name": "spine1", "lab_name": "test-lab", "container_id": "abc123"},
        ]

    mock_ctx = MagicMock()
    mock_server_ctx = MagicMock()

    # Mock executor
    mock_executor = AsyncMock()
    # The inspect call returns a table with our nodes
    inspect_result = MagicMock()
    inspect_result.exit_code = 0
    inspect_result.stdout = ""
    inspect_result.stderr = ""
    inspect_result.duration_ms = 10

    # The exec call (if reached) returns success
    exec_result = MagicMock()
    exec_result.exit_code = 0
    exec_result.stdout = "output"
    exec_result.stderr = ""
    exec_result.duration_ms = 50
    exec_result.command = "docker exec"

    mock_executor.execute = AsyncMock(side_effect=[inspect_result, exec_result])

    # Mock output parser
    mock_output_parser = MagicMock()
    mock_output_parser.parse_table = MagicMock(return_value=nodes)

    mock_server_ctx.executor = mock_executor
    mock_server_ctx.output_parser = mock_output_parser
    mock_server_ctx.config = MagicMock()
    mock_server_ctx.config.remote = None

    mock_ctx.request_context = MagicMock()
    mock_ctx.request_context.lifespan_context = mock_server_ctx

    return mock_ctx


# --- Property 14: Command Length Validation ---


class TestCommandLengthValidation:
    """Property 14: Command Length Validation.

    For any command string passed to ``node_exec``, if the string length exceeds
    4096 characters, the tool SHALL reject the invocation with an error response.
    If the string length is ≤ 4096 characters (and the node exists), the command
    SHALL be accepted for execution.

    **Validates: Requirements 1.8**
    """

    @given(command=_overlong_command_strategy())
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large],
    )
    @pytest.mark.asyncio
    async def test_overlong_command_rejected(self, command: str) -> None:
        """Commands exceeding 4096 characters are rejected with an error response.

        # Feature: containerlab-mcp, Property 14: Command Length Validation
        **Validates: Requirements 1.8**
        """
        assert len(command) > MAX_COMMAND_LENGTH

        mock_ctx = _make_mock_ctx()
        result = await node_exec(
            lab_name="test-lab",
            node_name="spine1",
            exec_command=command,
            ctx=mock_ctx,
        )

        assert result["status"] == "error", (
            f"Command of length {len(command)} should be rejected"
        )
        assert result["exit_code"] == -1
        assert "exceeds maximum" in result["stderr"] or "4096" in result["stderr"]
        # duration_ms should be 0 since no execution happened
        assert result["duration_ms"] == 0

    @given(command=_valid_command_strategy())
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large],
    )
    @pytest.mark.asyncio
    async def test_valid_length_command_accepted(self, command: str) -> None:
        """Commands of 4096 characters or fewer are accepted for execution.

        # Feature: containerlab-mcp, Property 14: Command Length Validation
        **Validates: Requirements 1.8**
        """
        assert len(command) <= MAX_COMMAND_LENGTH

        mock_ctx = _make_mock_ctx()
        result = await node_exec(
            lab_name="test-lab",
            node_name="spine1",
            exec_command=command,
            ctx=mock_ctx,
        )

        # Command should be accepted (either success or a non-validation error)
        # It should NOT be rejected due to length
        if result["status"] == "error":
            assert "exceeds maximum" not in result.get("stderr", ""), (
                f"Command of length {len(command)} should not be rejected for length"
            )

    @given(
        base=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=100,
        )
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_boundary_exact_4096_accepted(self, base: str) -> None:
        """A command of exactly 4096 characters is accepted (boundary condition).

        # Feature: containerlab-mcp, Property 14: Command Length Validation
        **Validates: Requirements 1.8**
        """
        # Pad to exactly MAX_COMMAND_LENGTH
        command = (base * (MAX_COMMAND_LENGTH // max(len(base), 1) + 1))[:MAX_COMMAND_LENGTH]
        assert len(command) == MAX_COMMAND_LENGTH

        mock_ctx = _make_mock_ctx()
        result = await node_exec(
            lab_name="test-lab",
            node_name="spine1",
            exec_command=command,
            ctx=mock_ctx,
        )

        # Should NOT be rejected for length
        if result["status"] == "error":
            assert "exceeds maximum" not in result.get("stderr", ""), (
                "Command of exactly 4096 chars should not be rejected for length"
            )

    @given(
        extra=st.integers(min_value=1, max_value=500),
        base=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=1,
            max_size=50,
        ),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large],
    )
    @pytest.mark.asyncio
    async def test_boundary_4097_rejected(self, extra: int, base: str) -> None:
        """A command of 4097+ characters is always rejected (boundary condition).

        # Feature: containerlab-mcp, Property 14: Command Length Validation
        **Validates: Requirements 1.8**
        """
        # Build a command of exactly MAX_COMMAND_LENGTH + extra
        target_len = MAX_COMMAND_LENGTH + extra
        command = (base * (target_len // max(len(base), 1) + 1))[:target_len]
        assert len(command) > MAX_COMMAND_LENGTH

        mock_ctx = _make_mock_ctx()
        result = await node_exec(
            lab_name="test-lab",
            node_name="spine1",
            exec_command=command,
            ctx=mock_ctx,
        )

        assert result["status"] == "error", (
            f"Command of length {len(command)} should be rejected"
        )
        assert result["exit_code"] == -1
