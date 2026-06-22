"""Unit tests for the CLIExecutor module."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import asyncssh
import pytest

from containerlab_mcp.executor import CLIExecutor


class TestCLIExecutorInit:
    """Tests for CLIExecutor initialization."""

    def test_defaults(self):
        executor = CLIExecutor()
        assert executor.remote is None
        assert executor.ssh_key_path is None
        assert executor.ssh_port == 22

    def test_custom_remote_config(self):
        executor = CLIExecutor(
            remote="admin@10.0.0.1",
            ssh_key_path="/home/user/.ssh/id_rsa",
            ssh_port=2222,
        )
        assert executor.remote == "admin@10.0.0.1"
        assert executor.ssh_key_path == "/home/user/.ssh/id_rsa"
        assert executor.ssh_port == 2222


class TestExecuteRemoteNoConfig:
    """Tests for execute_remote when no remote target is configured."""

    @pytest.mark.asyncio
    async def test_no_remote_configured(self):
        executor = CLIExecutor()
        result = await executor.execute_remote(["clab", "inspect"])
        assert result.exit_code == -1
        assert "No remote target configured" in result.stderr
        assert result.command == "clab inspect"
        assert result.duration_ms >= 0


class TestExecuteRemoteConnectionTimeout:
    """Tests for SSH connection timeout handling."""

    @pytest.mark.asyncio
    async def test_connection_timeout(self):
        executor = CLIExecutor(remote="admin@10.0.0.1")

        with patch("containerlab_mcp.executor.asyncssh.connect", new_callable=AsyncMock) as mock_connect:
            # Simulate connection timeout
            mock_connect.side_effect = asyncio.TimeoutError()

            result = await executor.execute_remote(["clab", "version"])

        assert result.exit_code == -1
        assert "SSH connection timed out after 30s" in result.stderr
        assert "admin@10.0.0.1" in result.stderr
        assert result.command == "clab version"
        assert result.duration_ms >= 0


class TestExecuteRemoteAuthFailure:
    """Tests for SSH authentication failure handling."""

    @pytest.mark.asyncio
    async def test_permission_denied(self):
        executor = CLIExecutor(remote="admin@10.0.0.1")

        with patch("containerlab_mcp.executor.asyncssh.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = asyncssh.PermissionDenied("Authentication failed")

            result = await executor.execute_remote(["clab", "inspect"])

        assert result.exit_code == -1
        assert "SSH connection failed" in result.stderr
        assert "admin@10.0.0.1" in result.stderr
        assert result.command == "clab inspect"

    @pytest.mark.asyncio
    async def test_disconnect_error(self):
        executor = CLIExecutor(remote="admin@10.0.0.1")

        with patch("containerlab_mcp.executor.asyncssh.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = asyncssh.DisconnectError(reason=11, code=11)

            result = await executor.execute_remote(["clab", "inspect"])

        assert result.exit_code == -1
        assert "SSH connection failed" in result.stderr
        assert "admin@10.0.0.1" in result.stderr

    @pytest.mark.asyncio
    async def test_os_error_network_unreachable(self):
        executor = CLIExecutor(remote="admin@10.0.0.1")

        with patch("containerlab_mcp.executor.asyncssh.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = OSError("Network is unreachable")

            result = await executor.execute_remote(["clab", "inspect"])

        assert result.exit_code == -1
        assert "SSH connection failed" in result.stderr
        assert "Network is unreachable" in result.stderr


class TestExecuteRemoteSuccess:
    """Tests for successful remote command execution."""

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        executor = CLIExecutor(remote="admin@10.0.0.1", ssh_key_path="/tmp/key")

        mock_result = MagicMock()
        mock_result.stdout = "containerlab version 0.50.0\n"
        mock_result.stderr = ""
        mock_result.exit_status = 0

        mock_conn = AsyncMock()
        mock_conn.run = AsyncMock(return_value=mock_result)
        mock_conn.close = MagicMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        with patch("containerlab_mcp.executor.asyncssh.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_conn

            result = await executor.execute_remote(["clab", "version"])

        assert result.exit_code == 0
        assert result.stdout == "containerlab version 0.50.0\n"
        assert result.stderr == ""
        assert result.command == "clab version"
        assert result.duration_ms >= 0

        # Verify SSH connection args
        mock_connect.assert_called_once()
        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["host"] == "10.0.0.1"
        assert call_kwargs["username"] == "admin"
        assert call_kwargs["port"] == 22
        assert call_kwargs["client_keys"] == ["/tmp/key"]

    @pytest.mark.asyncio
    async def test_successful_execution_with_stderr(self):
        executor = CLIExecutor(remote="admin@10.0.0.1")

        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = "Warning: something happened\n"
        mock_result.exit_status = 1

        mock_conn = AsyncMock()
        mock_conn.run = AsyncMock(return_value=mock_result)
        mock_conn.close = MagicMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        with patch("containerlab_mcp.executor.asyncssh.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_conn

            result = await executor.execute_remote(["clab", "deploy", "-t", "topo.yml"])

        assert result.exit_code == 1
        assert result.stderr == "Warning: something happened\n"
        assert result.command == "clab deploy -t topo.yml"

    @pytest.mark.asyncio
    async def test_custom_port(self):
        executor = CLIExecutor(remote="root@192.168.1.100", ssh_port=2222)

        mock_result = MagicMock()
        mock_result.stdout = "ok"
        mock_result.stderr = ""
        mock_result.exit_status = 0

        mock_conn = AsyncMock()
        mock_conn.run = AsyncMock(return_value=mock_result)
        mock_conn.close = MagicMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        with patch("containerlab_mcp.executor.asyncssh.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_conn

            result = await executor.execute_remote(["clab", "inspect"])

        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["port"] == 2222
        assert call_kwargs["host"] == "192.168.1.100"
        assert call_kwargs["username"] == "root"

    @pytest.mark.asyncio
    async def test_host_only_no_username(self):
        executor = CLIExecutor(remote="10.0.0.1")

        mock_result = MagicMock()
        mock_result.stdout = "ok"
        mock_result.stderr = ""
        mock_result.exit_status = 0

        mock_conn = AsyncMock()
        mock_conn.run = AsyncMock(return_value=mock_result)
        mock_conn.close = MagicMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        with patch("containerlab_mcp.executor.asyncssh.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_conn

            result = await executor.execute_remote(["clab", "version"])

        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["host"] == "10.0.0.1"
        assert "username" not in call_kwargs


class TestExecuteRemoteCommandTimeout:
    """Tests for remote command timeout handling."""

    @pytest.mark.asyncio
    async def test_command_timeout(self):
        executor = CLIExecutor(remote="admin@10.0.0.1")

        mock_conn = AsyncMock()
        mock_conn.run = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_conn.close = MagicMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        with patch("containerlab_mcp.executor.asyncssh.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_conn

            result = await executor.execute_remote(["clab", "deploy", "-t", "big-topo.yml"], timeout=120.0)

        assert result.exit_code == -1
        assert "Command timed out after 120.0s" in result.stderr
        assert "admin@10.0.0.1" in result.stderr
        assert result.command == "clab deploy -t big-topo.yml"

    @pytest.mark.asyncio
    async def test_custom_command_timeout(self):
        executor = CLIExecutor(remote="admin@10.0.0.1")

        mock_conn = AsyncMock()
        mock_conn.run = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_conn.close = MagicMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        with patch("containerlab_mcp.executor.asyncssh.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_conn

            result = await executor.execute_remote(["clab", "inspect"], timeout=60.0)

        assert result.exit_code == -1
        assert "Command timed out after 60.0s" in result.stderr


class TestExecuteLocal:
    """Tests for local execute to confirm __init__ doesn't break existing behavior."""

    @pytest.mark.asyncio
    async def test_local_execute_still_works(self):
        executor = CLIExecutor()
        result = await executor.execute(["echo", "hello"])
        assert result.exit_code == 0
        assert "hello" in result.stdout
        assert result.duration_ms >= 0
        assert result.command == "echo hello"

    @pytest.mark.asyncio
    async def test_local_execute_with_remote_configured(self):
        """Local execute should work regardless of remote config."""
        executor = CLIExecutor(remote="admin@10.0.0.1")
        result = await executor.execute(["echo", "world"])
        assert result.exit_code == 0
        assert "world" in result.stdout


class TestLocalTimeoutEnforcement:
    """Tests that timeout kills the local process and returns an error."""

    @pytest.mark.asyncio
    async def test_timeout_kills_process_and_returns_error(self):
        """A long-running process should be killed on timeout with exit_code=-1."""
        executor = CLIExecutor()
        result = await executor.execute(["sleep", "60"], timeout=0.5)
        assert result.exit_code == -1
        assert "timed out" in result.stderr
        assert result.command == "sleep 60"
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_timeout_stderr_contains_timeout_value(self):
        """The timeout error message should include the timeout duration."""
        executor = CLIExecutor()
        result = await executor.execute(["sleep", "10"], timeout=1.0)
        assert result.exit_code == -1
        assert "1.0s" in result.stderr


class TestLocalDurationMs:
    """Tests that duration_ms is populated correctly and reflects wall-clock time."""

    @pytest.mark.asyncio
    async def test_duration_ms_non_negative(self):
        """duration_ms must always be >= 0."""
        executor = CLIExecutor()
        result = await executor.execute(["echo", "fast"])
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_duration_ms_reflects_execution_time(self):
        """duration_ms should approximately match the time the command takes."""
        executor = CLIExecutor()
        # Sleep 0.2s — duration should be between 150ms and 1000ms
        result = await executor.execute(["sleep", "0.2"])
        assert result.exit_code == 0
        assert result.duration_ms >= 150
        assert result.duration_ms < 1000

    @pytest.mark.asyncio
    async def test_duration_ms_populated_on_timeout(self):
        """duration_ms should reflect actual elapsed time even on timeout."""
        executor = CLIExecutor()
        result = await executor.execute(["sleep", "60"], timeout=0.3)
        assert result.exit_code == -1
        # Should be at least 250ms (close to the 300ms timeout)
        assert result.duration_ms >= 250
        assert result.duration_ms < 2000


class TestLocalStderrCapture:
    """Tests that stderr is captured correctly on non-zero exit code."""

    @pytest.mark.asyncio
    async def test_stderr_captured_on_nonzero_exit(self):
        """stderr should be captured when command exits with non-zero code."""
        executor = CLIExecutor()
        # Write to stderr and exit 1
        result = await executor.execute(
            ["bash", "-c", "echo 'error message' >&2; exit 1"]
        )
        assert result.exit_code == 1
        assert "error message" in result.stderr

    @pytest.mark.asyncio
    async def test_stdout_and_stderr_captured_independently(self):
        """stdout and stderr should be captured as separate fields."""
        executor = CLIExecutor()
        result = await executor.execute(
            ["bash", "-c", "echo 'out data'; echo 'err data' >&2; exit 2"]
        )
        assert result.exit_code == 2
        assert "out data" in result.stdout
        assert "err data" in result.stderr
        # Ensure no cross-contamination
        assert "err data" not in result.stdout
        assert "out data" not in result.stderr
