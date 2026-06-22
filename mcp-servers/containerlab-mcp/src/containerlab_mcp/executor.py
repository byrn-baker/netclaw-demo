"""CLI Executor module for subprocess and SSH execution with timeout management."""

from __future__ import annotations

import asyncio
import time

import asyncssh

from containerlab_mcp.models import ExecutionResult


class CLIExecutor:
    """Handles local subprocess and remote SSH execution with timeout enforcement."""

    def __init__(
        self,
        remote: str | None = None,
        ssh_key_path: str | None = None,
        ssh_port: int = 22,
    ) -> None:
        """Initialize the CLI executor.

        Args:
            remote: Optional remote target in user@host format for SSH execution.
            ssh_key_path: Optional path to the SSH private key file.
            ssh_port: SSH port number (default: 22).
        """
        self.remote = remote
        self.ssh_key_path = ssh_key_path
        self.ssh_port = ssh_port

    async def execute(
        self,
        args: list[str],
        timeout: float = 30.0,
        cwd: str | None = None,
    ) -> ExecutionResult:
        """Execute a command locally via asyncio subprocess.

        Args:
            args: Command and arguments as a list of strings.
            timeout: Maximum execution time in seconds. Process is killed on timeout.
            cwd: Optional working directory for the subprocess.

        Returns:
            ExecutionResult with stdout, stderr, exit_code, duration_ms, and command.
        """
        command_str = " ".join(args)
        start = time.monotonic()

        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            duration_ms = int((time.monotonic() - start) * 1000)

            return ExecutionResult(
                stdout=stdout_bytes.decode(errors="replace"),
                stderr=stderr_bytes.decode(errors="replace"),
                exit_code=process.returncode or 0,
                duration_ms=duration_ms,
                command=command_str,
            )

        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - start) * 1000)
            # Kill the process on timeout
            try:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass

            return ExecutionResult(
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                exit_code=-1,
                duration_ms=duration_ms,
                command=command_str,
            )

    async def execute_remote(
        self,
        args: list[str],
        timeout: float = 120.0,
    ) -> ExecutionResult:
        """Execute a command on a remote host via SSH.

        Uses asyncssh to connect to the configured remote target and execute
        the command. Connection timeout is fixed at 30s; command timeout is
        configurable (default 120s).

        Args:
            args: Command and arguments as a list of strings.
            timeout: Maximum command execution time in seconds (default: 120.0).

        Returns:
            ExecutionResult with stdout, stderr, exit_code, duration_ms, and command.
        """
        command_str = " ".join(args)
        start = time.monotonic()

        # Parse remote into user and host
        if self.remote and "@" in self.remote:
            username, host = self.remote.split("@", 1)
        elif self.remote:
            username = None
            host = self.remote
        else:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ExecutionResult(
                stdout="",
                stderr="No remote target configured",
                exit_code=-1,
                duration_ms=duration_ms,
                command=command_str,
            )

        # Build connection options
        connect_kwargs: dict = {
            "host": host,
            "port": self.ssh_port,
            "known_hosts": None,  # Disable host key checking for lab environments
        }
        if username:
            connect_kwargs["username"] = username
        if self.ssh_key_path:
            connect_kwargs["client_keys"] = [self.ssh_key_path]

        try:
            # Connect with 30s connection timeout
            conn = await asyncio.wait_for(
                asyncssh.connect(**connect_kwargs),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ExecutionResult(
                stdout="",
                stderr=f"SSH connection timed out after 30s to {self.remote}",
                exit_code=-1,
                duration_ms=duration_ms,
                command=command_str,
            )
        except (asyncssh.DisconnectError, asyncssh.PermissionDenied, OSError) as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ExecutionResult(
                stdout="",
                stderr=f"SSH connection failed to {self.remote}: {exc}",
                exit_code=-1,
                duration_ms=duration_ms,
                command=command_str,
            )

        try:
            # Execute command with configurable timeout
            async with conn:
                result = await asyncio.wait_for(
                    conn.run(command_str, check=False),
                    timeout=timeout,
                )

            duration_ms = int((time.monotonic() - start) * 1000)

            return ExecutionResult(
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                exit_code=result.exit_status if result.exit_status is not None else -1,
                duration_ms=duration_ms,
                command=command_str,
            )

        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - start) * 1000)
            # Close the connection on command timeout
            conn.close()
            return ExecutionResult(
                stdout="",
                stderr=f"Command timed out after {timeout}s on {self.remote}",
                exit_code=-1,
                duration_ms=duration_ms,
                command=command_str,
            )
