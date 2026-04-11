# Feature Specification: NetShell Security and Governance Layer

**Feature Branch**: `027-netshell-security`
**Created**: 2026-04-11
**Status**: Draft
**Input**: User description: "NetShell: Security and Governance Layer for NetClaw built on NVIDIA OpenShell"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Production Sandbox Isolation (Priority: P1)

As a production user, I want NetClaw to run in an isolated sandbox so that if the agent is compromised (via prompt injection, malicious MCP server, or bug), it cannot access my full machine, credentials, or network.

**Why this priority**: This is the core value proposition - without sandbox isolation, all other governance features are bypassable. Production deployment requires containment of the blast radius.

**Independent Test**: Can be fully tested by running NetClaw in sandbox mode and attempting to access files/endpoints outside the declared policy. Delivers immediate security value.

**Acceptance Scenarios**:

1. **Given** NetShell is enabled, **When** the agent attempts to read ~/.ssh/id_rsa, **Then** the operation is blocked and logged
2. **Given** NetShell is enabled, **When** the agent attempts to connect to an undeclared network endpoint, **Then** the connection is denied
3. **Given** NetShell is enabled, **When** credentials are needed, **Then** they are injected at runtime and never written to the sandbox filesystem
4. **Given** NetShell is disabled (hobby mode), **When** the user runs NetClaw, **Then** it operates with full user privileges (backward compatible)

---

### User Story 2 - Compliance Audit Logging (Priority: P1)

As a compliance officer, I want every tool invocation logged in a standard format so that I can provide evidence for SOC2, PCI-DSS, and HIPAA audits.

**Why this priority**: Enterprise adoption requires audit trails. Without logging, security controls cannot be demonstrated to auditors.

**Independent Test**: Can be fully tested by invoking tools and verifying audit log entries contain required fields (timestamp, actor, tool, arguments, decision). Delivers compliance evidence.

**Acceptance Scenarios**:

1. **Given** audit logging is enabled, **When** any MCP tool is invoked, **Then** an audit record is created with timestamp, skill, MCP, tool, and allow/deny decision
2. **Given** audit logging is enabled, **When** a tool invocation is denied by policy, **Then** the audit record includes the denial reason
3. **Given** audit logs exist, **When** a compliance report is requested, **Then** logs can be exported in standard format for auditor review

---

### User Story 3 - Per-Skill Tool Permissions (Priority: P2)

As a network administrator, I want each skill to only access the MCP tools it explicitly requires so that the principle of least privilege is enforced.

**Why this priority**: Reduces attack surface by limiting what a compromised or misbehaving skill can do. Important for security but requires sandbox (P1) first.

**Independent Test**: Can be fully tested by loading a skill and verifying it can only see/invoke its declared tools. Delivers least-privilege enforcement.

**Acceptance Scenarios**:

1. **Given** a skill declares it needs show_command from pyats-mcp, **When** the skill is loaded, **Then** it can only see and invoke show_command, not configure_device
2. **Given** a skill attempts to invoke a tool not in its allowlist, **When** the invocation is attempted, **Then** it is blocked before reaching the MCP server
3. **Given** a skill's permissions are defined, **When** an administrator reviews them, **Then** the declarations are human-readable and auditable

---

### User Story 4 - Network Egress Control (Priority: P2)

As a security engineer, I want network egress limited to declared API endpoints only so that data exfiltration is prevented.

**Why this priority**: Prevents compromised agents from sending data to attacker-controlled servers. Requires sandbox infrastructure (P1) to enforce.

**Independent Test**: Can be fully tested by declaring allowed endpoints and attempting to connect to others. Delivers exfiltration prevention.

**Acceptance Scenarios**:

1. **Given** an MCP policy declares api.meraki.com as allowed, **When** the MCP connects to api.meraki.com, **Then** the connection succeeds
2. **Given** an MCP policy declares api.meraki.com as allowed, **When** the MCP attempts to connect to attacker.com, **Then** the connection is blocked and logged
3. **Given** default-deny egress is enabled, **When** no policy exists for an endpoint, **Then** the connection is blocked

---

### User Story 5 - Opt-In Installation (Priority: P3)

As a hobby user, I want NetShell to be optional during installation so that I can use NetClaw without the overhead of sandbox configuration.

**Why this priority**: Preserves the current easy onboarding experience for non-production use cases. Lower priority because it's about UX, not security.

**Independent Test**: Can be fully tested by running install.sh and declining NetShell. Delivers backward compatibility.

**Acceptance Scenarios**:

1. **Given** the user runs install.sh, **When** prompted "Enable production security?", **Then** they can answer No and proceed without NetShell
2. **Given** the user enables NetShell, **When** Docker is not installed, **Then** a clear error message explains the requirement
3. **Given** NetShell is enabled, **When** installation completes, **Then** NetClaw runs inside the sandbox by default

---

### Edge Cases

- What happens when a sandbox crashes mid-operation? Agent state should be recoverable, no partial configurations applied.
- How does the system handle policy hot-reload? Network policies should update without restarting the sandbox.
- What happens when an MCP server is unreachable? Clear error message, no credential exposure in logs.
- How are credentials rotated? Sandbox restart with new injected credentials, no manual file editing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an opt-in installation path for production security features
- **FR-002**: System MUST check for container runtime before enabling security features
- **FR-003**: System MUST run the NetClaw agent in an isolated environment when security is enabled
- **FR-004**: System MUST restrict filesystem access to declared paths only
- **FR-005**: System MUST restrict network egress to declared endpoints only
- **FR-006**: System MUST inject credentials at runtime without persisting them to the isolated environment
- **FR-007**: System MUST enforce per-skill tool allowlists at the protocol layer
- **FR-008**: System MUST block tool invocations not in a skill's declared permissions
- **FR-009**: System MUST log all tool invocations with timestamp, actor, tool, and decision
- **FR-010**: System MUST log all policy violations with denial reason
- **FR-011**: System MUST support audit log export in standard compliance format
- **FR-012**: System MUST define network policies per MCP server
- **FR-013**: System MUST support policy updates without full restart for network rules
- **FR-014**: System MUST maintain backward compatibility when security features are disabled
- **FR-015**: System MUST provide clear error messages when security prerequisites are missing
- **FR-016**: System MUST prevent privilege escalation within the isolated environment
- **FR-017**: System MUST block dangerous command patterns (e.g., destructive operations)

### Key Entities

- **Sandbox**: Isolated execution environment with restricted access to host resources
- **Policy**: Declarative rules defining allowed filesystem paths, network endpoints, and tool permissions
- **Skill Permission**: Declaration of which MCP tools a skill requires and is allowed to invoke
- **MCP Policy**: Network egress rules and tool-level controls for a specific MCP server
- **Audit Record**: Immutable log entry capturing tool invocations and policy decisions
- **Credential**: Secret injected at runtime, never persisted in the sandbox

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Compromised agent cannot access files outside declared paths (100% block rate in testing)
- **SC-002**: Compromised agent cannot connect to undeclared network endpoints (100% block rate in testing)
- **SC-003**: Credentials are never written to sandbox filesystem (verifiable via filesystem scan)
- **SC-004**: All tool invocations are logged with required fields (100% coverage)
- **SC-005**: Skills can only invoke tools in their declared allowlist (100% enforcement)
- **SC-006**: Installation with security disabled completes in same time as before (no performance regression)
- **SC-007**: Cold start overhead for sandbox is under 5 seconds
- **SC-008**: Per-tool-invocation overhead is under 5 milliseconds
- **SC-009**: Audit logs support at least SOC2 Type II evidence requirements

## Assumptions

- Users enabling production security have Docker installed and running
- Existing MCP servers and skills continue to work without modification when security is disabled
- Audit logs are stored locally; remote log shipping is out of scope for initial version
- ITSM integration (change request approval) leverages existing ServiceNow integration
- Constitution principles will be extended to include security-specific guidelines
- The 23 MCP policies already created will be migrated into the speckit implementation

## Prior Work

The following artifacts were created before speckit workflow and should be incorporated:

- `netshell/README.md` - NetShell documentation
- `netshell/policies/base.yaml` - Base sandbox policy
- `netshell/policies/mcp/*.yaml` - 23 MCP server policies (all current MCP servers)
- `specs/027-netshell-security/research.md` - NVIDIA OpenShell research findings
