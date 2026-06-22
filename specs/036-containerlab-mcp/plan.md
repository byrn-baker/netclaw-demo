# Implementation Plan: ContainerLab MCP Server

**Branch**: `036-containerlab-mcp` | **Date**: 2026-06-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/036-containerlab-mcp/spec.md`

## Summary

Build a Python MCP server wrapping the ContainerLab CLI, exposing 13 tools across 4 domains (CLI lifecycle, node operations, topology management, monitoring). The server uses FastMCP over stdio transport, supports remote SSH execution, includes a safety gate for destructive operations, and returns structured JSON responses with error sanitization.

## Technical Context

**Language/Version**: Python 3.11+ with FastMCP framework
**Primary Dependencies**: mcp[cli] (FastMCP), pydantic (data models), pyyaml (topology parsing), asyncssh (SSH execution), click (CLI args)
**Storage**: Stateless — ContainerLab/Docker manage all state
**Testing**: pytest with Hypothesis property-based testing; unit tests for all modules
**Target Platform**: Linux (requires Docker and clab binary)
**Project Type**: MCP server (stdio transport, optional SSE)
**Constraints**: Requires `clab` binary on PATH; Docker access for container operations
**Scale/Scope**: Manages labs with up to hundreds of nodes; supports local and remote execution

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Safety-First Operations | PASS | Destroy requires explicit case-sensitive confirmation (safety gate) |
| II. Read-Before-Write | PASS | Inspect/status tools enable read-before-write workflows |
| III. ITSM-Gated Changes | N/A | Lab environments, not production |
| IV. Immutable Audit Trail | PASS | GAIT logging on all operations |
| V. MCP-Native Integration | PASS | Built as FastMCP server with stdio transport |
| VI. Multi-Vendor Neutrality | PASS | ContainerLab supports all vendors via container images |
| VII. Skill Modularity | PASS | Single-purpose MCP server (lab management) |
| VIII. Verify After Every Change | PASS | `lab_status` and `node_health` tools for post-change verification |
| IX. Security by Default | PASS | Error sanitization, no path/credential leakage |
| X. Observability | PASS | Structured logging to stderr, GAIT audit trail |
| XI. Artifact Coherence | PASS | All spec artifacts, README, openclaw.json entry created |
| XII. Documentation-as-Code | PASS | README.md with tool table, env vars, usage examples |
| XIII. Credential Safety | PASS | Credentials from env vars/topology YAML only, never logged |
| XIV. Human-in-the-Loop | PASS | Safety gate prevents unconfirmed destruction |
| XV. Backwards Compatibility | PASS | New server, isolated dependencies |
| XVI. Spec-Driven Development | PASS | Full spec → design → implement → test workflow |

**Gate Result**: PASS — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/036-containerlab-mcp/
├── spec.md              # Feature specification with user stories
├── plan.md              # This file (implementation plan)
├── research.md          # Design decisions and rationale
├── data-model.md        # Entity/model definitions
├── quickstart.md        # Quick setup guide
├── contracts/
│   └── mcp-tools.md    # MCP tool schemas and contracts
├── checklists/
│   └── requirements.md # Quality checklist
└── tasks.md             # Implementation tasks
```

### Source Code (repository root)

```text
mcp-servers/containerlab-mcp/
├── containerlab_mcp_server.py   # Top-level entry point (NetClaw stdio pattern)
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Container build
├── README.md                    # Server documentation
├── .env.example                 # Environment variable template
├── pyproject.toml               # Build system (dev tooling)
├── src/containerlab_mcp/        # Internal package
│   ├── server.py                # FastMCP instance, lifespan, CLI
│   ├── models.py                # Pydantic data models
│   ├── executor.py              # CLI subprocess + SSH execution
│   ├── parser.py                # Output parsing + sanitization
│   ├── topology.py              # Topology discovery + YAML parsing
│   ├── access.py                # Node access detection
│   ├── config.py                # Configuration management
│   ├── safety.py                # Destroy safety gate
│   └── tools/                   # MCP tool registrations
│       ├── clab_tools.py        # deploy, destroy, inspect, save, graph, generate, version
│       ├── node_tools.py        # node_exec, get_node_access
│       └── monitoring_tools.py  # list_topologies, get_topology_details, lab_status, node_health
└── tests/
    ├── unit/                    # Example-based unit tests
    └── property/                # Hypothesis property-based tests
```
