#!/usr/bin/env python3
"""
NetShell Audit Logger

OCSF-compliant audit logging for MCP tool invocations and policy decisions.
Implements Open Cybersecurity Schema Framework (OCSF) API Activity (class_uid: 4001).

Usage:
    from audit_logger import AuditLogger
    logger = AuditLogger()
    logger.log_tool_invocation(skill="pyats-health-check", mcp="pyats-mcp", tool="show_command", ...)
    logger.log_policy_violation(skill="...", reason="...", ...)
"""

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

# OCSF Constants
OCSF_CLASS_UID = 4001  # API Activity
OCSF_CATEGORY_UID = 4  # Network Activity

# Activity IDs per OCSF spec
ACTIVITY_CREATE = 1
ACTIVITY_READ = 2
ACTIVITY_UPDATE = 3
ACTIVITY_DELETE = 4
ACTIVITY_OTHER = 5

# Severity levels
SEVERITY_UNKNOWN = 0
SEVERITY_INFO = 1
SEVERITY_LOW = 2
SEVERITY_MEDIUM = 3
SEVERITY_HIGH = 4
SEVERITY_CRITICAL = 5

# Status values
STATUS_SUCCESS = "success"
STATUS_FAILURE = "failure"
STATUS_BLOCKED = "blocked"


@dataclass
class Actor:
    """Actor information for audit records."""

    user: str  # Skill name or "agent"
    session_id: str = ""


@dataclass
class ApiInfo:
    """API/tool information for audit records."""

    operation: str  # Tool name
    service: str  # MCP server name
    request: dict = field(default_factory=dict)
    response: dict = field(default_factory=dict)


@dataclass
class Endpoint:
    """Network endpoint information."""

    ip: str = ""
    hostname: str = ""
    port: int = 0


@dataclass
class Metadata:
    """Audit record metadata."""

    version: str = "1.0.0"
    product: dict = field(default_factory=lambda: {"name": "NetShell", "version": "1.0.0"})
    policy: str = ""
    violation_reason: str = ""


class AuditLogger:
    """OCSF-compliant audit logger for NetShell."""

    def __init__(self, log_path: str | Path | None = None):
        """Initialize audit logger.

        Args:
            log_path: Path to audit log file. Defaults to /workspace/logs/audit/netshell.log
        """
        if log_path is None:
            log_path = os.environ.get(
                "NETSHELL_AUDIT_LOG", "/workspace/logs/audit/netshell.log"
            )
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._session_id = self._generate_session_id()

    def _generate_session_id(self) -> str:
        """Generate a unique session identifier."""
        return f"ns-{int(time.time() * 1000)}-{os.getpid()}"

    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds."""
        return int(datetime.now(timezone.utc).timestamp() * 1000)

    def _classify_activity(self, tool_name: str) -> int:
        """Classify tool operation type based on naming conventions."""
        tool_lower = tool_name.lower()

        if any(
            prefix in tool_lower
            for prefix in ["create", "add", "insert", "new", "register"]
        ):
            return ACTIVITY_CREATE
        elif any(
            prefix in tool_lower
            for prefix in ["get", "show", "list", "read", "query", "fetch", "search"]
        ):
            return ACTIVITY_READ
        elif any(
            prefix in tool_lower
            for prefix in ["update", "modify", "set", "change", "edit", "configure"]
        ):
            return ACTIVITY_UPDATE
        elif any(
            prefix in tool_lower for prefix in ["delete", "remove", "drop", "erase"]
        ):
            return ACTIVITY_DELETE
        else:
            return ACTIVITY_OTHER

    def _sanitize_request(self, request: dict) -> dict:
        """Remove sensitive data from request before logging."""
        if not request:
            return {}

        sanitized = {}
        sensitive_keys = {
            "password",
            "secret",
            "token",
            "key",
            "credential",
            "auth",
            "api_key",
            "apikey",
        }

        for key, value in request.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_request(value)
            else:
                sanitized[key] = value

        return sanitized

    def _truncate_response(self, response: dict, max_size: int = 1000) -> dict:
        """Truncate large responses to avoid bloating audit logs."""
        if not response:
            return {}

        response_str = json.dumps(response)
        if len(response_str) <= max_size:
            return response

        return {"_truncated": True, "_size": len(response_str), "_preview": response_str[:500]}

    def _write_record(self, record: dict) -> None:
        """Write audit record to log file."""
        with open(self.log_path, "a") as f:
            f.write(json.dumps(record) + "\n")

    def audit_record(
        self,
        activity_id: int,
        message: str,
        status: Literal["success", "failure", "blocked"],
        actor: Actor,
        api: ApiInfo,
        severity_id: int = SEVERITY_INFO,
        src_endpoint: Endpoint | None = None,
        dst_endpoint: Endpoint | None = None,
        metadata: Metadata | None = None,
    ) -> dict:
        """Create and write an OCSF-compliant audit record.

        Args:
            activity_id: OCSF activity type (1=Create, 2=Read, 3=Update, 4=Delete, 5=Other)
            message: Human-readable event description
            status: Outcome (success, failure, blocked)
            actor: Who initiated the action
            api: Tool/API details
            severity_id: OCSF severity (0-5)
            src_endpoint: Source network info
            dst_endpoint: Destination network info
            metadata: Additional context

        Returns:
            The audit record that was written
        """
        if metadata is None:
            metadata = Metadata()

        record = {
            "class_uid": OCSF_CLASS_UID,
            "category_uid": OCSF_CATEGORY_UID,
            "activity_id": activity_id,
            "time": self._get_timestamp(),
            "severity_id": severity_id,
            "message": message,
            "status": status,
            "actor": {
                "user": actor.user,
                "session_id": actor.session_id or self._session_id,
            },
            "api": {
                "operation": api.operation,
                "service": api.service,
                "request": self._sanitize_request(api.request),
                "response": self._truncate_response(api.response),
            },
            "metadata": {
                "version": metadata.version,
                "product": metadata.product,
                "policy": metadata.policy,
                "violation_reason": metadata.violation_reason,
            },
        }

        if src_endpoint:
            record["src_endpoint"] = {
                "ip": src_endpoint.ip,
                "hostname": src_endpoint.hostname,
            }

        if dst_endpoint:
            record["dst_endpoint"] = {
                "ip": dst_endpoint.ip,
                "hostname": dst_endpoint.hostname,
                "port": dst_endpoint.port,
            }

        self._write_record(record)
        return record

    def log_tool_invocation(
        self,
        skill: str,
        mcp: str,
        tool: str,
        request: dict | None = None,
        response: dict | None = None,
        success: bool = True,
        dst_host: str = "",
        dst_port: int = 443,
    ) -> dict:
        """Log a successful tool invocation.

        Args:
            skill: Name of the invoking skill
            mcp: MCP server name
            tool: Tool name
            request: Tool arguments
            response: Tool response
            success: Whether the invocation succeeded
            dst_host: Destination hostname
            dst_port: Destination port

        Returns:
            The audit record
        """
        status = STATUS_SUCCESS if success else STATUS_FAILURE
        severity = SEVERITY_INFO if success else SEVERITY_LOW

        return self.audit_record(
            activity_id=self._classify_activity(tool),
            message=f"Tool invocation: {mcp}.{tool}",
            status=status,
            actor=Actor(user=skill),
            api=ApiInfo(
                operation=tool,
                service=mcp,
                request=request or {},
                response=response or {},
            ),
            severity_id=severity,
            dst_endpoint=Endpoint(hostname=dst_host, port=dst_port) if dst_host else None,
        )

    def log_policy_violation(
        self,
        skill: str,
        mcp: str,
        tool: str,
        reason: str,
        policy: str = "",
        request: dict | None = None,
    ) -> dict:
        """Log a policy violation (blocked tool invocation).

        Args:
            skill: Name of the invoking skill
            mcp: MCP server name
            tool: Tool name
            reason: Why the invocation was blocked
            policy: Which policy blocked it
            request: Tool arguments (sanitized)

        Returns:
            The audit record
        """
        metadata = Metadata(policy=policy, violation_reason=reason)

        return self.audit_record(
            activity_id=self._classify_activity(tool),
            message=f"Policy violation: {mcp}.{tool} blocked - {reason}",
            status=STATUS_BLOCKED,
            actor=Actor(user=skill),
            api=ApiInfo(
                operation=tool,
                service=mcp,
                request=request or {},
            ),
            severity_id=SEVERITY_MEDIUM,
            metadata=metadata,
        )

    def log_network_blocked(
        self,
        skill: str,
        host: str,
        port: int,
        reason: str,
        policy: str = "",
    ) -> dict:
        """Log a blocked network connection.

        Args:
            skill: Name of the skill attempting the connection
            host: Destination hostname
            port: Destination port
            reason: Why the connection was blocked
            policy: Which policy blocked it

        Returns:
            The audit record
        """
        metadata = Metadata(policy=policy, violation_reason=reason)

        return self.audit_record(
            activity_id=ACTIVITY_OTHER,
            message=f"Network egress blocked: {host}:{port} - {reason}",
            status=STATUS_BLOCKED,
            actor=Actor(user=skill),
            api=ApiInfo(
                operation="network_connect",
                service="netshell",
            ),
            severity_id=SEVERITY_HIGH,
            dst_endpoint=Endpoint(hostname=host, port=port),
            metadata=metadata,
        )


# Module-level logger instance
_logger: AuditLogger | None = None


def get_logger() -> AuditLogger:
    """Get or create the global audit logger instance."""
    global _logger
    if _logger is None:
        _logger = AuditLogger()
    return _logger


def log_tool_invocation(*args: Any, **kwargs: Any) -> dict:
    """Convenience function to log tool invocations."""
    return get_logger().log_tool_invocation(*args, **kwargs)


def log_policy_violation(*args: Any, **kwargs: Any) -> dict:
    """Convenience function to log policy violations."""
    return get_logger().log_policy_violation(*args, **kwargs)


def log_network_blocked(*args: Any, **kwargs: Any) -> dict:
    """Convenience function to log blocked network connections."""
    return get_logger().log_network_blocked(*args, **kwargs)


if __name__ == "__main__":
    # Demo/test
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        test_log = f.name

    logger = AuditLogger(test_log)

    # Log a successful tool invocation
    logger.log_tool_invocation(
        skill="pyats-health-check",
        mcp="pyats-mcp",
        tool="show_command",
        request={"device": "router1", "command": "show ip route"},
        response={"output": "..."},
        success=True,
    )

    # Log a policy violation
    logger.log_policy_violation(
        skill="malicious-skill",
        mcp="pyats-mcp",
        tool="configure_device",
        reason="Tool not in skill allowlist",
        policy="skill-malicious-skill.yaml",
    )

    # Log a blocked network connection
    logger.log_network_blocked(
        skill="agent",
        host="attacker.com",
        port=443,
        reason="Host not in MCP egress allowlist",
        policy="base.yaml",
    )

    print(f"Demo audit log written to: {test_log}")
    print("\nLog contents:")
    with open(test_log) as f:
        for line in f:
            record = json.loads(line)
            print(json.dumps(record, indent=2))
