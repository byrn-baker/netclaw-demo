# Data Model: NetShell Security and Governance Layer

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Created**: 2026-04-11

## Overview

NetShell uses declarative YAML policies stored in `netshell/policies/`. No database is required - all policies are file-based and loaded at sandbox initialization. Audit logs are appended to local files in OCSF format.

## Entity Definitions

### Policy (Base)

The root sandbox policy defining default security controls.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| version | integer | yes | Schema version (currently 1) |
| name | string | yes | Policy identifier |
| description | string | no | Human-readable description |
| filesystem_policy | FilesystemPolicy | yes | Filesystem access rules |
| landlock | LandlockConfig | yes | Kernel LSM settings |
| process | ProcessPolicy | yes | Process/seccomp restrictions |
| network_policies | NetworkPolicy | yes | Network egress rules |
| inference | InferenceConfig | no | LLM routing configuration |
| credentials | CredentialConfig | yes | Injected secrets |
| audit | AuditConfig | yes | Logging configuration |
| itsm | ItsmConfig | no | Change management integration |

### FilesystemPolicy

Landlock-enforced filesystem access control.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| workspace | PathPermission[] | yes | Read/write paths |
| read_only | string[] | no | Read-only paths |
| denied | string[] | yes | Explicitly blocked paths |

### PathPermission

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| path | string | yes | Absolute path |
| permissions | string[] | yes | Allowed: read, write, execute |

### LandlockConfig

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| enabled | boolean | yes | Whether Landlock is active |
| restrict_self | boolean | yes | Restrict sandbox filesystem |
| exec_paths | string[] | yes | Paths where execution allowed |

### ProcessPolicy

Seccomp and resource limit configuration.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| user | string | yes | Unix user to run as |
| group | string | yes | Unix group |
| no_new_privs | boolean | yes | Prevent privilege escalation |
| seccomp | SeccompConfig | yes | Syscall filtering |
| limits | ResourceLimits | no | Resource constraints |

### SeccompConfig

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| profile | string | yes | Profile name: restricted, permissive |
| deny | string[] | yes | Explicitly blocked syscalls |

### ResourceLimits

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| max_processes | integer | no | Maximum child processes |
| max_open_files | integer | no | Maximum file descriptors |
| max_memory_mb | integer | no | Memory limit in MB |

### NetworkPolicy

Network egress control rules.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| default_action | string | yes | deny or allow |
| log_allowed | boolean | no | Log allowed connections |
| log_denied | boolean | no | Log denied connections |
| core_egress | EgressRule[] | yes | Always-allowed endpoints |
| mcp_egress | EgressRule[] | no | MCP-specific endpoints (populated by compiler) |
| blocked | BlockRule[] | no | Explicitly blocked destinations |

### EgressRule

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | yes | Rule identifier |
| host | string | yes | Hostname, IP, CIDR, or pattern |
| ports | integer[] | yes | Allowed ports |
| protocols | string[] | yes | Allowed: https, http, tcp, udp |
| methods | string[] | no | HTTP methods (for L7 filtering) |

### BlockRule

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| host | string | yes | Blocked hostname pattern |

### CredentialConfig

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| inject | string[] | yes | Environment variables to inject |
| rotation | RotationConfig | no | Auto-rotation settings |

### AuditConfig

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| enabled | boolean | yes | Whether auditing is active |
| format | string | yes | Output format: ocsf |
| events | string[] | yes | Event types to log |
| destinations | AuditDestination[] | yes | Where to send logs |

### AuditDestination

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | string | yes | file, syslog, or webhook |
| path | string | conditional | File path (if type=file) |
| address | string | conditional | Syslog address (if type=syslog) |
| url | string | conditional | Webhook URL (if type=webhook) |

---

## MCP Policy

Per-MCP server policy extending the base.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| version | integer | yes | Schema version (currently 1) |
| mcp_server | string | yes | MCP server identifier |
| description | string | no | Human-readable description |
| network_policies | McpNetworkPolicy | yes | Egress rules for this MCP |
| tools | ToolPermissions | yes | Per-tool access control |
| dangerous_patterns | DangerousPattern[] | no | Blocked command patterns |
| credentials | string[] | no | Required credential env vars |

### McpNetworkPolicy

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| egress | EgressRule[] | yes | Allowed endpoints for this MCP |

### ToolPermissions

Map of tool name to permission configuration.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| [tool_name] | ToolPermission | yes | Permission for each tool |

### ToolPermission

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| permission | string | yes | allow or deny |
| requires_approval | boolean | yes | ITSM gate required |
| audit_level | string | yes | standard, full, or none |
| description | string | no | Tool purpose |

### DangerousPattern

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| pattern | string | yes | Regex pattern to block |
| description | string | yes | Why this is dangerous |

---

## Skill Permission

Per-skill tool allowlist declared in SKILL.md frontmatter.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| netshell | SkillNetshell | no | NetShell configuration section |

### SkillNetshell

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| mcp_tools | McpToolGrant[] | yes | Tools this skill can invoke |
| approval_required | boolean | no | Override ITSM requirement |

### McpToolGrant

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| mcp | string | yes | MCP server name |
| tools | string[] | yes | Allowed tool names |

---

## Audit Record

OCSF-formatted audit log entry.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| class_uid | integer | yes | OCSF class (4001 = API Activity) |
| category_uid | integer | yes | OCSF category (4 = Network Activity) |
| activity_id | integer | yes | Activity type |
| time | integer | yes | Unix timestamp (ms) |
| severity_id | integer | yes | 0=Unknown, 1=Info, 2=Low, 3=Medium, 4=High, 5=Critical |
| message | string | yes | Human-readable description |
| status | string | yes | success, failure, blocked |
| actor | ActorInfo | yes | Who initiated the action |
| api | ApiInfo | yes | Tool/API details |
| src_endpoint | EndpointInfo | no | Source information |
| dst_endpoint | EndpointInfo | no | Destination information |
| metadata | Metadata | yes | Additional context |

### ActorInfo

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| user | string | yes | Skill name or "agent" |
| session_id | string | yes | Session identifier |

### ApiInfo

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| operation | string | yes | Tool name |
| service | string | yes | MCP server name |
| request | object | no | Tool arguments (sanitized) |
| response | object | no | Tool response (truncated) |

### Metadata

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| version | string | yes | Log schema version |
| product | object | yes | Product info (name: "NetShell") |
| policy | string | no | Policy that matched |
| violation_reason | string | no | Why blocked (if applicable) |

---

## Relationships

```
┌─────────────────┐         ┌─────────────────┐
│   Base Policy   │ extends │   MCP Policy    │
│  (base.yaml)    │◄────────│  (mcp/*.yaml)   │
└────────┬────────┘         └────────┬────────┘
         │                           │
         │ enforces                  │ governs
         ▼                           ▼
┌─────────────────┐         ┌─────────────────┐
│    Sandbox      │         │   MCP Server    │
│   (OpenShell)   │         │    (FastMCP)    │
└────────┬────────┘         └────────┬────────┘
         │                           │
         │ runs                      │ tools
         ▼                           ▼
┌─────────────────┐  invokes ┌─────────────────┐
│     Agent       │─────────►│     Skill       │
│   (Claude)      │          │   (SKILL.md)    │
└────────┬────────┘          └────────┬────────┘
         │                            │
         │ logs                       │ declares
         ▼                            ▼
┌─────────────────┐         ┌─────────────────┐
│  Audit Record   │         │Skill Permission │
│    (OCSF)       │         │  (netshell:)    │
└─────────────────┘         └─────────────────┘
```

## Storage Details

| Data | Location | Format | Lifecycle |
|------|----------|--------|-----------|
| Base Policy | `netshell/policies/base.yaml` | YAML | Static, reload on restart |
| MCP Policies | `netshell/policies/mcp/*.yaml` | YAML | Hot-reloadable (network only) |
| Skill Permissions | `workspace/skills/*/SKILL.md` | YAML frontmatter | Loaded at skill invocation |
| Audit Logs | `/workspace/logs/audit/netshell.log` | JSON (OCSF) | Append-only, rotate daily |
| Compiled Policy | In-memory | Python dict | Regenerated on reload |
