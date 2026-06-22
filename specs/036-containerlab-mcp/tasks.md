# Implementation Plan: ContainerLab MCP Server

## Overview

This plan implements a Python-based MCP server that wraps the ContainerLab CLI, exposing all operations as structured MCP tools. The implementation follows a bottom-up approach: first establishing project structure and data models, then building core services (executor, parser, config), followed by domain logic (topology, access, safety), and finally wiring everything together with the FastMCP tool layer.

## Tasks

- [x] 1. Set up project structure, dependencies, and core data models
  - [x] 1.1 Create project scaffolding with pyproject.toml, src layout, and test directories
    - Create `src/containerlab_mcp/` package with `__init__.py`
    - Create `pyproject.toml` with dependencies: `mcp[cli]`, `pydantic`, `pyyaml`, `asyncssh`, `click`
    - Add dev dependencies: `pytest`, `pytest-asyncio`, `hypothesis`, `pytest-cov`
    - Create `tests/unit/`, `tests/property/`, `tests/integration/` directories with `__init__.py` and `conftest.py`
    - _Requirements: 8.1_

  - [x] 1.2 Implement Pydantic response and configuration models
    - Create `src/containerlab_mcp/models.py` with all data models
    - Implement `StructuredResponse`, `ExecutionResult`, `NodeExecResponse`
    - Implement `TopologyEntry`, `TopologyDetails`, `NodeDefinition`, `LinkDefinition`
    - Implement `NodeAccessInfo`, `ServerConfig`, `LabInstance`, `NodeHealth`
    - Add field validators (e.g., `duration_ms >= 0`, `port` range 1-65535, `cpu_percent` 0-100)
    - _Requirements: 1.9, 4.1, 4.4, 9.3_

  - [x]* 1.3 Write property test for response schema invariant
    - **Property 1: Response Schema Invariant**
    - **Validates: Requirements 1.9, 4.1, 4.4**

- [x] 2. Implement CLI Executor module
  - [x] 2.1 Implement local subprocess execution with timeout and duration tracking
    - Create `src/containerlab_mcp/executor.py` with `CLIExecutor` class
    - Implement `execute()` method using `asyncio.create_subprocess_exec`
    - Add timeout enforcement with `asyncio.wait_for` and process kill on timeout
    - Add wall-clock duration measurement in milliseconds
    - Capture stdout/stderr as strings, return `ExecutionResult`
    - _Requirements: 1.9, 4.4, 4.5_

  - [x] 2.2 Implement remote SSH execution with asyncssh
    - Add `execute_remote()` method to `CLIExecutor`
    - Use `asyncssh` for SSH connection with configurable key path and port
    - Implement 30s connection timeout and 120s command timeout
    - Return `ExecutionResult` with stdout/stderr/exit_code/duration_ms
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x]* 2.3 Write unit tests for CLI Executor
    - Test timeout enforcement kills process and returns error
    - Test duration_ms is populated correctly
    - Test stderr capture on non-zero exit code
    - _Requirements: 4.4, 4.5_

- [x] 3. Implement Output Parser module
  - [x] 3.1 Implement table-to-JSON parser for clab inspect output
    - Create `src/containerlab_mcp/parser.py` with `OutputParser` class
    - Implement `parse_table()` that detects column boundaries from header separators
    - Normalize column headers to lowercase snake_case
    - Handle empty tables (zero data rows → empty array)
    - _Requirements: 4.2, 4.6_

  - [x] 3.2 Implement JSON pass-through parser and error message sanitization
    - Implement `parse_json()` for commands with `--format json`
    - Implement `sanitize_error()` that strips absolute paths and credential-like strings
    - Implement stderr truncation to 4096 characters
    - _Requirements: 1.10, 4.3_

  - [x]* 3.3 Write property test for table parsing correctness
    - **Property 2: Table Parsing Correctness**
    - **Validates: Requirements 4.2, 4.6**

  - [x]* 3.4 Write property tests for error handling
    - **Property 8: Error Response Sanitization**
    - **Property 9: Stderr Truncation**
    - **Validates: Requirements 1.10, 4.3**

- [x] 4. Implement Configuration Manager module
  - [x] 4.1 Implement configuration loading with env > CLI > file precedence
    - Create `src/containerlab_mcp/config.py` with `ConfigManager` class
    - Implement env var reading with `CLAB_MCP_` prefix
    - Implement colon-separated path parsing for `CLAB_MCP_TOPOLOGY_PATHS`
    - Implement log level parsing (case-insensitive, fallback to "info" for invalid)
    - Implement CLI argument parsing with `click` or `argparse`
    - Implement config file loading (YAML/JSON)
    - Merge sources by priority: env > CLI > file > defaults
    - Return `ServerConfig` model
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x]* 4.2 Write property tests for configuration
    - **Property 10: Configuration Precedence**
    - **Property 11: Colon-Separated Path Parsing**
    - **Property 12: Log Level Parsing**
    - **Property 13: Invalid Transport Rejection**
    - **Validates: Requirements 8.1, 8.2, 8.4, 8.5, 6.6**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Topology Parser module
  - [x] 6.1 Implement topology file discovery with depth-limited scanning
    - Create `src/containerlab_mcp/topology.py` with `TopologyParser` class
    - Implement `discover()` that recursively scans for `.clab.yml` files up to max_depth=3
    - Extract lab name and node count from each discovered file
    - Return list of `TopologyEntry` objects with absolute paths
    - Skip unreadable directories with warning log
    - _Requirements: 2.1, 2.2, 8.3_

  - [x] 6.2 Implement topology YAML parsing and detail extraction
    - Implement `parse()` method using PyYAML to load topology file
    - Extract nodes, links, topology name, and kind
    - Map parsed data to `TopologyDetails`, `NodeDefinition`, `LinkDefinition` models
    - Handle parse errors with descriptive error messages
    - Implement `get_node_kinds()` to return node name → kind mapping
    - _Requirements: 2.3, 2.4, 2.5_

  - [x]* 6.3 Write property tests for topology discovery and parsing
    - **Property 3: Topology Discovery Depth Limit**
    - **Property 4: Topology Parsing Round-Trip**
    - **Validates: Requirements 2.1, 2.2, 2.3**

- [x] 7. Implement Node Access Detector module
  - [x] 7.1 Implement access method detection and credential extraction
    - Create `src/containerlab_mcp/access.py` with `NodeAccessDetector` class
    - Implement `detect()` with kind-to-access-method mapping (srl/ceos/crpd → SSH, linux → docker_exec, serial → clab_connect)
    - Extract credentials with precedence: node-level > topology defaults
    - Fall back to docker_exec when no credentials found
    - Generate shell-ready connection command strings
    - Implement `detect_all()` to process all nodes in a topology
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x]* 7.2 Write property tests for access detection
    - **Property 6: Node Access Method Detection**
    - **Property 7: Credential Precedence**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

- [x] 8. Implement Safety Gate module
  - [x] 8.1 Implement destroy confirmation validation logic
    - Create `src/containerlab_mcp/safety.py` with `SafetyGate` class
    - Implement `validate_destroy()` with exact case-sensitive string matching
    - Validate cleanup flag requires both `confirm_topology_name` match AND `confirm_cleanup: true`
    - Return `ValidationResult` with pass/fail and descriptive error message
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x]* 8.2 Write property test for destroy safety gate
    - **Property 5: Destroy Safety Gate**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement FastMCP Server and tool registration
  - [x] 10.1 Implement server entry point with startup checks and transport selection
    - Create `src/containerlab_mcp/server.py` with FastMCP instance
    - Implement startup lifespan context that verifies `clab` binary is on PATH
    - Implement `--transport` argument handling (stdio/sse), exit non-zero for invalid values
    - Implement `--host`, `--port` arguments for SSE mode
    - Implement `--remote`, SSH key path, SSH port arguments
    - Wire `ConfigManager` to load and merge all configuration
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.6, 6.7, 8.6, 8.7_

  - [x] 10.2 Implement ContainerLab CLI tools (deploy, destroy, inspect, save, graph, generate, version)
    - Register `deploy` tool with topology_file_path, lab_name, reconfigure params
    - Register `destroy` tool with safety gate integration (confirm_topology_name, cleanup, confirm_cleanup)
    - Register `inspect` tool with optional topology_name/lab_name filter
    - Register `save`, `graph`, `generate`, `version` tools with appropriate params
    - Each tool: validate params → execute via CLIExecutor → parse output → return StructuredResponse
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.9, 1.10, 5.1, 5.2, 5.3, 5.4_

  - [x] 10.3 Implement node interaction tools (node_exec, get_node_access)
    - Register `node_exec` tool with lab_name, node_name, command (max 4096 chars) params
    - Validate command length, return error with valid node names if node not found
    - Implement 30s timeout with error response on exceed
    - Register `get_node_access` tool returning NodeAccessInfo per node
    - Return error with valid node names list if node not found
    - _Requirements: 1.8, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x] 10.4 Implement topology and monitoring tools (list_topologies, get_topology_details, lab_status, node_health)
    - Register `list_topologies` tool using TopologyParser.discover()
    - Register `get_topology_details` tool using TopologyParser.parse()
    - Register `lab_status` tool returning LabInstance list with container states
    - Register `node_health` tool returning NodeHealth with CPU/memory/uptime
    - Handle empty results (no labs → empty list with success status)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x]* 10.5 Write property tests for command validation and tool schemas
    - **Property 14: Command Length Validation**
    - **Property 15: Tool Schema Completeness**
    - **Property 16: Invalid Node Error Includes Valid Names**
    - **Validates: Requirements 1.8, 10.1, 10.2, 10.3, 3.6**

- [x] 11. Implement tool descriptions, examples, and metadata
  - [x] 11.1 Add comprehensive tool descriptions, parameter docs, and usage examples to all tools
    - Add description (≤120 chars) to each @mcp.tool() decorator
    - Add parameter descriptions with types, defaults, and required/optional designation
    - Add examples field with at least one invocation example per tool
    - Ensure all parameter names are snake_case with ≥2 words or ≥8 characters
    - Document structured value encoding (JSON string vs native object) where applicable
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The design specifies Python with FastMCP, Pydantic, asyncio, asyncssh, and Hypothesis — all tasks use these technologies
- Integration tests (lifecycle, SSH remote, transport concurrency) are not included as tasks since they require a running ContainerLab + Docker environment

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "2.1", "3.1", "4.1"] },
    { "id": 3, "tasks": ["2.2", "3.2", "4.2"] },
    { "id": 4, "tasks": ["2.3", "3.3", "3.4"] },
    { "id": 5, "tasks": ["6.1", "8.1"] },
    { "id": 6, "tasks": ["6.2", "6.3", "8.2"] },
    { "id": 7, "tasks": ["7.1"] },
    { "id": 8, "tasks": ["7.2"] },
    { "id": 9, "tasks": ["10.1"] },
    { "id": 10, "tasks": ["10.2", "10.3", "10.4"] },
    { "id": 11, "tasks": ["10.5", "11.1"] }
  ]
}
```
