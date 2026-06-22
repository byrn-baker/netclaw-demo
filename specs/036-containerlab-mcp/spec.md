# Feature Specification: ContainerLab MCP Server

**Feature Branch**: `036-containerlab-mcp`
**Created**: 2026-06-15
**Status**: Complete
**Input**: User description: "Build a Python MCP server wrapping the ContainerLab CLI, exposing all containerlab operations as structured tools for AI agents. Enable agents like NetClaw/OpenClaw to programmatically deploy, manage, inspect, and interact with container-based network lab topologies."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Full ContainerLab CLI Command Coverage (Priority: P1)

As an AI agent, I want access to all ContainerLab CLI subcommands as MCP tools, so that I can perform any lab management operation without falling back to raw shell execution.

**Why this priority**: This is the core value proposition. Without CLI tool exposure the server has no purpose. Covers deploy, destroy, inspect, save, graph, generate, version, and node_exec.

**Independent Test**: Can be tested by invoking each tool with valid parameters and verifying structured JSON responses with correct status, data, command, and duration_ms fields.

**Acceptance Scenarios**:

1. **Given** ContainerLab is installed and accessible,
   **When** the agent invokes the `deploy` tool with a valid topology file path,
   **Then** the system executes `clab deploy` and returns a StructuredResponse with status "success" and the CLI output in the data field.

2. **Given** a lab is deployed,
   **When** the agent invokes `node_exec` with a valid lab name, node name, and command string (≤4096 chars),
   **Then** the system executes the command inside the container and returns stdout, stderr, and exit code.

3. **Given** any tool invocation fails,
   **When** the CLI returns a non-zero exit code,
   **Then** the system returns a structured error with sanitized stderr (no paths or credentials leaked) and the exit code.

---

### User Story 2 - Topology File Discovery and Management (Priority: P1)

As an AI agent, I want to discover and list available topology files, so that I can present lab options to users and select the correct topology without requiring exact file paths.

**Why this priority**: Discovery is essential for agents that don't know the filesystem layout.

**Independent Test**: Create a temporary directory tree with `.clab.yml` files at various depths, invoke `list_topologies`, and verify depth-limited discovery and correct metadata extraction.

**Acceptance Scenarios**:

1. **Given** topology files exist within configured search paths,
   **When** the agent invokes `list_topologies`,
   **Then** the system returns all `.clab.yml` files at depth ≤ 3 with path, lab_name, and node_count.

2. **Given** a valid topology file path,
   **When** the agent invokes `get_topology_details`,
   **Then** the system returns parsed nodes, links, topology name, and kind.

---

### User Story 3 - Node Access Detection and Information (Priority: P2)

As an AI agent, I want structured information about how to access each node in a running lab, so that I can execute commands on nodes without guessing connection methods or credentials.

**Why this priority**: Eliminates guesswork about SSH vs docker exec vs clab connect for different node kinds.

**Independent Test**: Deploy a lab with mixed node kinds (srl, linux, crpd), invoke `get_node_access`, and verify correct access method detection and credential extraction per node kind.

**Acceptance Scenarios**:

1. **Given** a deployed lab with SSH-capable nodes (srl, ceos, crpd),
   **When** the agent invokes `get_node_access` with the topology file,
   **Then** the system returns SSH access method with credentials from the topology YAML.

2. **Given** node-level credentials and topology-level defaults both exist,
   **When** `get_node_access` is called,
   **Then** node-level credentials take precedence over defaults.

3. **Given** no credentials are found at either level,
   **When** `get_node_access` is called,
   **Then** the access method falls back to "docker_exec".

---

### User Story 4 - Destructive Operation Safety (Priority: P1)

As an AI agent operator, I want destructive operations to require explicit confirmation, so that labs are not accidentally destroyed by agent mistakes or hallucinated commands.

**Why this priority**: Safety gate prevents catastrophic accidental destruction. Aligns with constitution principle I (Safety-First).

**Independent Test**: Invoke `destroy` with matching and non-matching confirmation strings, verify rejection without CLI execution for mismatches.

**Acceptance Scenarios**:

1. **Given** a deployed lab named "dc-fabric",
   **When** `destroy` is called with `confirm_topology_name="dc-fabric"`,
   **Then** the destroy operation proceeds.

2. **Given** a deployed lab named "dc-fabric",
   **When** `destroy` is called with `confirm_topology_name="DC-FABRIC"` (case mismatch),
   **Then** the operation is rejected without executing any CLI command.

3. **Given** `cleanup_artifacts=True`,
   **When** `confirm_cleanup` is not set to True,
   **Then** the operation is rejected.

---

### User Story 5 - Lab Status and Health Monitoring (Priority: P2)

As an AI agent, I want to query the current state of running labs and their nodes, so that I can make informed decisions about deployments and detect unhealthy containers.

**Why this priority**: Monitoring enables intelligent agent behavior (e.g., check health before deploying over an existing lab).

**Independent Test**: Deploy a lab, invoke `lab_status` and `node_health`, verify correct container state reporting and resource metrics.

**Acceptance Scenarios**:

1. **Given** one or more labs are deployed,
   **When** the agent invokes `lab_status`,
   **Then** the system returns topology names, node counts, and deployment timestamps.

2. **Given** no labs are deployed,
   **When** `lab_status` is called,
   **Then** a success response with an empty list is returned.

3. **Given** a running node container,
   **When** `node_health` is called with the container name,
   **Then** CPU percent, memory bytes, memory percent, and uptime seconds are returned.

---

### User Story 6 - Multiple Transport and Remote Execution (Priority: P3)

As a network engineer, I want to run the MCP server in different transport modes and optionally execute commands on remote hosts via SSH, so that I can use it locally or in distributed setups.

**Why this priority**: Flexibility for different deployment scenarios. stdio is default for NetClaw integration.

**Independent Test**: Start server with `--transport sse` and verify HTTP binding; configure `--remote` and verify SSH command execution.

---

### User Story 7 - Agent-Friendly Tool Descriptions (Priority: P2)

As an AI agent (including less-capable local models), I want clear tool descriptions with examples and parameter documentation, so that I can correctly invoke tools without misunderstanding parameters.

**Why this priority**: Good descriptions reduce hallucination-driven misuse of tools.

**Independent Test**: Introspect all registered tools and verify description ≤120 chars, all params documented, at least one example per tool, parameter names in snake_case with ≥2 words or ≥8 chars.
