# SKILL.md Schema Reference

This document defines the YAML frontmatter schema for NetClaw skill definitions.

## Full Schema

```yaml
---
# Required fields
name: string                    # Skill identifier (lowercase, hyphens)
description: string             # Human-readable description
version: string                 # Semantic version (e.g., "1.0.0")

# Optional metadata
author: string                  # Skill author
tags: [string]                  # Categorization tags
priority: integer               # Execution priority (lower = higher priority)

# MCP dependencies
mcp_servers: [string]           # List of MCP servers this skill uses

# NetShell permissions (optional - for production security)
netshell:
  mcp_tools:                    # Tools this skill is allowed to invoke
    - mcp: string               # MCP server name (e.g., "pyats-mcp")
      tools: [string]           # Allowed tool names (e.g., ["show_command", "get_config"])
  approval_required: boolean    # Override ITSM requirement (default: from MCP policy)
---
```

## Field Descriptions

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique skill identifier. Use lowercase with hyphens (e.g., `pyats-health-check`). |
| `description` | string | Brief explanation of what the skill does. |
| `version` | string | Semantic version for tracking changes. |

### NetShell Section

The `netshell` section is **optional** but required for skills to work when NetShell is enabled.

| Field | Type | Description |
|-------|------|-------------|
| `netshell.mcp_tools` | array | List of MCP tool grants. |
| `netshell.mcp_tools[].mcp` | string | MCP server name (must match policy file name). |
| `netshell.mcp_tools[].tools` | array | Tool names this skill can invoke from the MCP. |
| `netshell.approval_required` | boolean | Force ITSM approval for all write operations. |

## Examples

### Read-Only Skill

```yaml
---
name: network-inventory
description: Discover and inventory network devices
version: 1.0.0
author: netclaw
tags: [inventory, discovery]

netshell:
  mcp_tools:
    - mcp: suzieq-mcp
      tools:
        - suzieq_show
        - suzieq_summarize
        - suzieq_path
    - mcp: batfish-mcp
      tools:
        - analyze_config
        - get_reachability
---
```

### Read/Write Skill

```yaml
---
name: vlan-provisioner
description: Provision VLANs across network devices
version: 1.0.0
author: netclaw
tags: [provisioning, vlan]

netshell:
  mcp_tools:
    - mcp: aruba-cx-mcp
      tools:
        - aruba_get_vlans         # Read
        - aruba_create_vlan       # Write (triggers ITSM)
        - aruba_delete_vlan       # Write (triggers ITSM)
    - mcp: meraki-magic-mcp
      tools:
        - get_network_vlans       # Read
        - create_network_vlan     # Write (triggers ITSM)
  approval_required: true         # Require ITSM for all writes
---
```

### Documentation Skill (No Network Access)

```yaml
---
name: api-docs-lookup
description: Search API documentation
version: 1.0.0
author: netclaw
tags: [documentation, api]

netshell:
  mcp_tools:
    - mcp: devnet-content-search
      tools:
        - Meraki-API-Doc-Search
        - CatalystCenter-API-Doc-Search
        - Meraki-API-OperationId-Search
---
```

## Backward Compatibility

- Skills **without** a `netshell` section work normally when NetShell is **disabled**
- When NetShell is **enabled**, skills without `netshell` section cannot invoke MCP tools
- Adding `netshell` section to existing skills is opt-in

## Validation

Run the policy compiler to validate skill permissions:

```bash
python netshell/scripts/compile-policies.py --verbose
```

This will:
1. Parse all SKILL.md files in `workspace/skills/`
2. Validate MCP and tool names exist
3. Generate compiled policies to `netshell/policies/skills/`
4. Report any validation errors
