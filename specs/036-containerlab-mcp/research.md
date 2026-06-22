# Research: ContainerLab MCP Server

**Feature Branch**: `036-containerlab-mcp`
**Date**: 2026-06-15

## Research Task 1: ContainerLab CLI Interface and Subcommands

**Decision**: Wrap all `clab` subcommands via `asyncio.create_subprocess_exec` rather than importing any Go library or using a REST API.

**Rationale**: ContainerLab is a Go binary with no Python bindings. All interaction must go through subprocess execution. The CLI is stable, well-documented, and returns consistent output formats (tables for `inspect`, JSON with `--format json` for some commands). Using async subprocess execution allows non-blocking operation in the MCP server.

**Key CLI patterns**:
- `clab deploy --topo <path> [--name <name>] [--reconfigure]`
- `clab destroy --topo <path> [--cleanup] [--name <name>]`
- `clab inspect [--name <name>] [--all] [--format json]`
- `clab save --topo <path>`
- `clab graph --topo <path> [--format html|mermaid|draw.io]`
- `clab generate --name <path> --nodes <N> --kind <type>`
- `clab version`

**Alternatives considered**:
- Direct Docker API: Would bypass clab's topology management logic. Rejected.
- Go library bindings via cgo: Too complex for Python integration. Rejected.

## Research Task 2: FastMCP Server Pattern for NetClaw

**Decision**: Use `mcp.server.fastmcp.FastMCP` with `@mcp.tool()` decorators, async lifespan context for startup checks, and stdio transport as the default for NetClaw integration.

**Rationale**: All existing NetClaw MCP servers follow this pattern (batfish-mcp, gnmi-mcp, eve-ng-mcp). The top-level entry point is a `*_mcp_server.py` file that imports the server instance and runs `mcp.run(transport="stdio")`. A flat entry point is required for `config/openclaw.json` registration (`python3 -u <file>.py`).

**Alternatives considered**:
- Low-level MCP server: More boilerplate, no automatic schema generation. Rejected.
- SSE-only: Not compatible with NetClaw's stdio-based gateway. Rejected (stdio is default, SSE is optional).

## Research Task 3: Output Parsing Strategy

**Decision**: Parse ContainerLab's table output by detecting column boundaries from header separator lines (`+---+---+`). Use JSON pass-through when `--format json` is available. Normalize column headers to lowercase snake_case.

**Rationale**: `clab inspect` returns table output with pipe-delimited columns and `+---+` separators. Parsing these into structured dicts makes the output agent-friendly. Some commands support `--format json` which can be passed through directly.

**Key parsing rules**:
- Detect columns from separator rows
- Normalize headers: lowercase, replace spaces/hyphens with underscores
- Handle empty tables (zero data rows → empty array)
- Sanitize error output (strip paths, credentials)
- Truncate stderr to 4096 characters

## Research Task 4: Node Access Detection from Topology YAML

**Decision**: Map node `kind` field to access method: SSH kinds (srl, ceos, crpd, vr-sros) → SSH with credential lookup; Docker exec kinds (linux, bridge) → docker exec; Unknown kinds → clab connect.

**Rationale**: ContainerLab topology YAML defines node kinds that directly correlate with access methods. Network OS nodes typically expose SSH with well-known default credentials (e.g., srl: admin/NokiaSrl1!, ceos: admin/admin). Linux containers use docker exec. The credential precedence is node-level env > topology defaults env > well-known defaults > fallback to docker_exec.

**Well-known credentials by kind**:
- `srl` (Nokia SR Linux): admin / NokiaSrl1!
- `ceos` (Arista cEOS): admin / admin
- `crpd` (Juniper cRPD): root / clab123
- `vr-sros` (Nokia SR OS): admin / admin

## Research Task 5: Safety Gate Design

**Decision**: Implement a SafetyGate class that validates destroy operations using exact case-sensitive string matching. No fuzzy matching, no "are you sure?" prompts — just hard parameter validation.

**Rationale**: AI agents can hallucinate or misinterpret lab names. Requiring exact case-sensitive confirmation prevents accidental destruction. The cleanup flag adds a second gate for file removal. This follows constitution principle I (Safety-First) without requiring interactive confirmation (which doesn't work for automated agent flows).

## Research Task 6: Configuration Layering

**Decision**: Environment variables (`CLAB_MCP_*`) > CLI arguments > config file (YAML/JSON) > defaults. Follow 12-factor app principles.

**Rationale**: Env vars are the standard for container deployments and NetClaw's `openclaw.json` env passthrough. CLI args allow per-invocation overrides during development. Config files support complex multi-path topology scanning setups.

## Research Task 7: GAIT Audit Logging

**Decision**: Emit structured JSON log entries to stderr with `"gait": true` marker, matching the pattern used by gnmi-mcp and other NetClaw servers.

**Rationale**: GAIT (the audit trail system) captures structured log entries from stderr for all MCP server operations. Using the same format as gnmi-mcp ensures compatibility with the GAIT stdio wrapper.
