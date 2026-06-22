# Requirements Document

## Introduction

ContainerLab MCP Server is a Python-based Model Context Protocol (MCP) server that wraps the ContainerLab CLI, exposing all containerlab operations as structured tools for AI agents. It enables agents like NetClaw/OpenClaw to programmatically deploy, manage, inspect, and interact with container-based network lab topologies. The server returns structured JSON responses, supports multiple transport modes, and provides intelligent node access detection to accommodate both advanced and less-capable LLM clients.

## Glossary

- **MCP_Server**: The Python MCP server process that exposes ContainerLab operations as MCP tools
- **ContainerLab_CLI**: The `clab` command-line interface for managing container-based network topologies
- **Topology_File**: A YAML file with `.clab.yml` extension that defines a network lab topology
- **Agent**: An AI agent (e.g., NetClaw, OpenClaw, Claude) that consumes MCP tools to orchestrate lab operations
- **Node**: A container instance within a deployed ContainerLab topology
- **Transport**: The communication protocol used between the Agent and the MCP_Server (stdio or SSE/HTTP)
- **Structured_Response**: A JSON object returned by the MCP_Server containing operation results, status, and metadata
- **Access_Method**: The mechanism used to interact with a Node (SSH, docker exec, or containerlab connect)
- **Lab_Instance**: A running ContainerLab topology deployment identified by its topology name

## Requirements

### Requirement 1: Full ContainerLab CLI Command Coverage

**User Story:** As an AI agent, I want access to all ContainerLab CLI subcommands as MCP tools, so that I can perform any lab management operation without falling back to raw shell execution.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose the `deploy` subcommand as an MCP tool that accepts topology file path, lab name override, and reconfigure flag as parameters
2. THE MCP_Server SHALL expose the `destroy` subcommand as an MCP tool that accepts topology file path, lab name, and cleanup flag as parameters
3. THE MCP_Server SHALL expose the `inspect` subcommand as an MCP tool that accepts optional topology name or lab name filter parameters
4. THE MCP_Server SHALL expose the `save` subcommand as an MCP tool that accepts topology file path or lab name as parameters
5. THE MCP_Server SHALL expose the `graph` subcommand as an MCP tool that accepts topology file path and output format as parameters
6. THE MCP_Server SHALL expose the `generate` subcommand as an MCP tool that accepts topology file path, node count, and topology type as parameters
7. THE MCP_Server SHALL expose the `version` subcommand as an MCP tool that returns ContainerLab version information
8. THE MCP_Server SHALL expose a `node_exec` tool that accepts a lab name, node name, and a command string of no more than 4096 characters, and executes the command inside the specified container
9. WHEN any MCP tool completes execution successfully, THE MCP_Server SHALL return a structured response containing the command output and a success indicator
10. IF an MCP tool invocation fails due to an invalid parameter, missing resource, or CLI execution error, THEN THE MCP_Server SHALL return a structured error response containing an error indicator and a message describing the failure reason without exposing internal system paths or credentials

### Requirement 2: Topology File Discovery and Management

**User Story:** As an AI agent, I want to discover and list available topology files, so that I can present lab options to users and select the correct topology without requiring exact file paths.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a `list_topologies` tool that scans configured search paths and returns a list of discovered Topology_File entries with their absolute paths, lab names, and node counts
2. IF a search path is not explicitly configured, THEN THE MCP_Server SHALL default to scanning the current working directory and its subdirectories up to a maximum depth of 3 levels for Topology_File entries
3. THE MCP_Server SHALL expose a `get_topology_details` tool that accepts a Topology_File path and returns parsed topology metadata including node definitions, link definitions, and topology kind
4. IF a Topology_File path does not exist, THEN THE MCP_Server SHALL return a Structured_Response with status "error", an error field containing the invalid path, and a message indicating the file was not found
5. IF a Topology_File exists but cannot be parsed as valid YAML or does not conform to the expected topology schema, THEN THE MCP_Server SHALL return a Structured_Response with status "error" and a message indicating the parsing failure reason

### Requirement 3: Node Access Detection and Information

**User Story:** As an AI agent, I want structured information about how to access each node in a running lab, so that I can execute commands on nodes without guessing connection methods or credentials.

#### Acceptance Criteria

1. WHEN a lab is deployed, THE MCP_Server SHALL expose a `get_node_access` tool that returns the Access_Method for each Node, including connection parameters (container name, SSH credentials, console port)
2. THE MCP_Server SHALL detect the Access_Method by reading the Topology_File node kind and matching it against known access patterns (SSH for network OS nodes with defined credentials, docker exec for Linux containers, containerlab connect for serial console nodes)
3. THE MCP_Server SHALL include in the `get_node_access` response: node name, container ID, management IPv4 address, management IPv6 address, Access_Method type, and a connection command string that can be executed directly in a shell without modification
4. IF a Node supports SSH access, THEN THE MCP_Server SHALL extract credentials from the Topology_File using the following precedence: node-level configuration overrides topology defaults, and include username and password in the access response; IF no credentials are found at either level, THEN THE MCP_Server SHALL return the Access_Method as "docker exec" as a fallback and omit the credentials fields
5. THE MCP_Server SHALL expose a `node_exec` tool that accepts a node name and command string, auto-detects the appropriate Access_Method, and executes the command inside the container with a maximum execution timeout of 30 seconds, returning stdout, stderr, and exit code as structured fields
6. IF the `node_exec` or `get_node_access` tool is called with a node name that does not exist in the deployed lab, THEN THE MCP_Server SHALL return an error response indicating the node was not found, along with the list of valid node names
7. IF the `node_exec` tool execution exceeds the 30-second timeout or the target container is not in a running state, THEN THE MCP_Server SHALL return an error response indicating the failure reason, with stderr populated and a non-zero exit code

### Requirement 4: Structured JSON Output

**User Story:** As an AI agent, I want all MCP tool responses in structured JSON format, so that I can programmatically parse results without dealing with raw CLI table formatting.

#### Acceptance Criteria

1. THE MCP_Server SHALL return all tool responses as valid JSON Structured_Response objects containing at minimum: a `status` field (value "success" or "error"), a `data` field with the operation result, and a `command` field containing the CLI command string that was executed
2. WHEN the ContainerLab_CLI returns tabular output (e.g., from `inspect`), THE MCP_Server SHALL parse the output into a JSON array of objects with named fields corresponding to column headers, representing each row as one object in the array
3. IF the ContainerLab_CLI returns a non-zero exit code, THEN THE MCP_Server SHALL return a Structured_Response with status "error", the stderr content (truncated to 4096 characters if longer) in a `message` field, and the numeric exit code in a `code` field
4. THE MCP_Server SHALL include a `duration_ms` field as a non-negative integer in every Structured_Response indicating the elapsed wall-clock time in milliseconds to execute the underlying CLI command
5. IF the ContainerLab_CLI does not return within 30 seconds, THEN THE MCP_Server SHALL terminate the CLI process and return a Structured_Response with status "error" and a `message` field indicating a timeout occurred
6. WHEN the ContainerLab_CLI returns tabular output containing zero data rows, THE MCP_Server SHALL return a Structured_Response with status "success" and the `data` field set to an empty JSON array

### Requirement 5: Destructive Operation Safety

**User Story:** As an AI agent operator, I want destructive operations to require explicit confirmation, so that labs are not accidentally destroyed by agent mistakes or hallucinated commands.

#### Acceptance Criteria

1. WHEN the `destroy` tool is called, THE MCP_Server SHALL require a `confirm_topology_name` parameter whose value must be a case-sensitive exact string match against the target topology name (as resolved from the topology file or the explicit lab name parameter)
2. IF the `confirm_topology_name` parameter is missing or does not exactly match the target topology name, THEN THE MCP_Server SHALL reject the operation without executing any ContainerLab_CLI command and return a Structured_Response with status "error" and a message indicating the confirmation mismatch
3. WHEN the `destroy` tool is called with `cleanup: true`, THE MCP_Server SHALL require both a matching `confirm_topology_name` parameter and an additional `confirm_cleanup: true` parameter
4. IF `cleanup: true` is specified but `confirm_cleanup` is missing or set to false, THEN THE MCP_Server SHALL reject the operation without executing any ContainerLab_CLI command and return a Structured_Response with status "error" and a message indicating the missing cleanup confirmation

### Requirement 6: Multiple Transport Support

**User Story:** As a network engineer, I want to run the MCP server in different transport modes, so that I can use it locally via stdio for same-box setups or remotely via SSE/HTTP for client/server deployments.

#### Acceptance Criteria

1. THE MCP_Server SHALL support stdio transport mode where communication occurs over standard input/output streams
2. THE MCP_Server SHALL support SSE/HTTP transport mode where the server listens on a configurable host and port for incoming MCP connections
3. WHEN started in SSE/HTTP mode, THE MCP_Server SHALL accept a `--host` parameter (default: 0.0.0.0) and a `--port` parameter (default: 8080) for binding the HTTP listener, where `--port` accepts an integer in the range 1 to 65535
4. THE MCP_Server SHALL accept a `--transport` command-line argument with values `stdio` or `sse` to select the transport mode at startup, defaulting to `stdio` when the argument is omitted
5. WHEN started in SSE/HTTP mode, THE MCP_Server SHALL support at least 10 concurrent Agent connections
6. IF the `--transport` argument is provided with a value other than `stdio` or `sse`, THEN THE MCP_Server SHALL exit with a non-zero exit code and print an error message indicating the accepted values
7. IF the MCP_Server is started in SSE/HTTP mode and the specified port is unavailable, THEN THE MCP_Server SHALL exit with a non-zero exit code and print an error message indicating the port conflict

### Requirement 7: Remote Execution via SSH

**User Story:** As a network engineer, I want to manage ContainerLab on a remote host without running an MCP server there, so that I can control remote labs from my local agent using SSH as the transport layer.

#### Acceptance Criteria

1. THE MCP_Server SHALL support a `--remote` configuration that specifies an SSH connection string in the format `user@host` for executing ContainerLab_CLI commands on a remote machine
2. WHILE configured with a remote target, THE MCP_Server SHALL execute all ContainerLab_CLI commands over SSH instead of locally
3. WHILE configured with a remote target, THE MCP_Server SHALL accept an optional SSH key path parameter and an optional SSH port parameter, defaulting to port 22 when no port is specified
4. IF an SSH connection to the remote host is not established within 30 seconds, THEN THE MCP_Server SHALL return a Structured_Response with status "error" and a message indicating the connection timeout and target host
5. IF an SSH connection to the remote host fails due to authentication or network error, THEN THE MCP_Server SHALL return a Structured_Response with status "error" and a message indicating the failure reason and target host
6. IF a ContainerLab_CLI command executed on the remote host does not complete within 120 seconds, THEN THE MCP_Server SHALL terminate the remote command and return a Structured_Response with status "error" and a message indicating the command timed out

### Requirement 8: Configuration and Initialization

**User Story:** As a network engineer, I want to configure the MCP server with search paths, defaults, and runtime options, so that I can adapt it to different environments without modifying code.

#### Acceptance Criteria

1. THE MCP_Server SHALL accept configuration via environment variables, command-line arguments, or a configuration file (in that priority order), where a value set in a higher-priority source overrides the same setting from a lower-priority source
2. THE MCP_Server SHALL support a `CLAB_MCP_TOPOLOGY_PATHS` environment variable containing a colon-separated list of up to 64 directory paths to scan for Topology_File entries
3. IF a directory listed in `CLAB_MCP_TOPOLOGY_PATHS` does not exist or is not readable, THEN THE MCP_Server SHALL skip that directory and log a warning message indicating which path was inaccessible
4. THE MCP_Server SHALL support a `CLAB_MCP_LOG_LEVEL` environment variable with values `debug`, `info`, `warning`, or `error` (default: `info`, case-insensitive matching)
5. IF `CLAB_MCP_LOG_LEVEL` is set to a value other than `debug`, `info`, `warning`, or `error`, THEN THE MCP_Server SHALL fall back to the default level `info` and log a warning message indicating the invalid value
6. WHEN the MCP_Server starts, THE MCP_Server SHALL verify that the `clab` binary is available on the system PATH
7. IF the `clab` binary is not found on the system PATH during startup, THEN THE MCP_Server SHALL log an error message indicating the binary is missing along with installation guidance, and SHALL terminate with a non-zero exit code

### Requirement 9: Lab Status and Health Monitoring

**User Story:** As an AI agent, I want to query the current state of running labs and their nodes, so that I can make informed decisions about deployments and detect unhealthy containers.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a `lab_status` tool that returns a list of all currently deployed Lab_Instance entries with their topology names, node counts, and deployment timestamps in ISO 8601 UTC format
2. WHEN a Lab_Instance contains nodes in a non-running state, THE MCP_Server SHALL include the container state (running, exited, restarting, paused, or dead) for each Node in the status response
3. THE MCP_Server SHALL expose a `node_health` tool that accepts a node name and returns container resource usage as CPU percentage (0.0 to 100.0), memory usage in bytes and as a percentage of the container memory limit, and uptime in seconds
4. IF the `node_health` tool is called with a node name that does not exist or references a container that is not in a running state, THEN THE MCP_Server SHALL return a Structured_Response with status "error" and a message indicating the node is unavailable
5. WHEN no Lab_Instance entries are currently deployed, THE MCP_Server SHALL return a Structured_Response with status "success" and an empty list in the data field

### Requirement 10: Agent-Friendly Tool Descriptions and Metadata

**User Story:** As an AI agent (including less-capable local models), I want clear tool descriptions with examples and parameter documentation, so that I can correctly invoke tools without misunderstanding parameters or their formats.

#### Acceptance Criteria

1. THE MCP_Server SHALL provide MCP tool descriptions that include a summary of no more than 120 characters, parameter descriptions with types and defaults, a required/optional designation for each parameter, and at least one usage example per tool
2. THE MCP_Server SHALL use parameter names in snake_case consisting of at least two words or at least 8 characters that convey the parameter's purpose (e.g., `topology_file_path` instead of `topo`, `node_name` instead of `n`)
3. THE MCP_Server SHALL include an `examples` field in each tool schema containing at least one invocation example that provides values for all required parameters and shows the expected response structure including top-level fields and their types
4. IF a tool parameter accepts a structured value, THEN THE MCP_Server SHALL document in the parameter description whether the value must be provided as a JSON-encoded string or as a native object, and the usage example SHALL demonstrate the correct encoding
