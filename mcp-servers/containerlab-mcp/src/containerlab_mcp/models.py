"""Pydantic response and configuration models for ContainerLab MCP Server."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# --- Response Models ---


class StructuredResponse(BaseModel):
    """Base response for all tool invocations."""

    status: Literal["success", "error"]
    data: dict | list | None = None
    command: str = Field(description="The CLI command that was executed")
    duration_ms: int = Field(ge=0, description="Execution time in milliseconds")
    message: str | None = Field(
        default=None, description="Error message when status is error"
    )
    code: int | None = Field(default=None, description="Exit code on error")


class ExecutionResult(BaseModel):
    """Internal result from CLI execution."""

    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int = Field(ge=0)
    command: str


class NodeExecResponse(BaseModel):
    """Response from node_exec tool."""

    status: Literal["success", "error"]
    stdout: str
    stderr: str
    exit_code: int
    command: str
    duration_ms: int = Field(ge=0)


# --- Topology Models ---


class TopologyEntry(BaseModel):
    """Discovered topology file metadata."""

    path: str = Field(description="Absolute path to the .clab.yml file")
    lab_name: str = Field(description="Lab name derived from topology")
    node_count: int = Field(ge=0, description="Number of nodes defined")


class NodeDefinition(BaseModel):
    """A node within a topology."""

    name: str
    kind: str
    image: str | None = None
    startup_config: str | None = None


class LinkDefinition(BaseModel):
    """A link between two endpoints."""

    endpoints: list[str]


class TopologyDetails(BaseModel):
    """Parsed topology content."""

    name: str
    nodes: list[NodeDefinition]
    links: list[LinkDefinition]
    kind: str | None = None


# --- Node Access Models ---


class NodeAccessInfo(BaseModel):
    """Access information for a running node."""

    node_name: str
    container_id: str
    mgmt_ipv4: str | None = None
    mgmt_ipv6: str | None = None
    access_method: Literal["ssh", "docker_exec", "clab_connect"]
    connection_command: str = Field(
        description="Shell-ready command to access the node"
    )
    username: str | None = None
    password: str | None = None


# --- Configuration Models ---


class ServerConfig(BaseModel):
    """Server runtime configuration."""

    transport: Literal["stdio", "sse"] = "stdio"
    host: str = "0.0.0.0"
    port: int = Field(default=8080, ge=1, le=65535)
    topology_paths: list[str] = Field(default_factory=lambda: ["."])
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    remote: str | None = None  # user@host
    ssh_key_path: str | None = None
    ssh_port: int = Field(default=22, ge=1, le=65535)


# --- Monitoring Models ---


class LabInstance(BaseModel):
    """A running lab deployment."""

    topology_name: str
    node_count: int = Field(ge=0)
    deployed_at: str  # ISO 8601 UTC


class NodeHealth(BaseModel):
    """Container resource usage for a node."""

    node_name: str
    cpu_percent: float = Field(ge=0.0, le=100.0)
    memory_bytes: int = Field(ge=0)
    memory_percent: float = Field(ge=0.0, le=100.0)
    uptime_seconds: int = Field(ge=0)
