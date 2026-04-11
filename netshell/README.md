# NetShell: Security and Governance Layer

NetShell is the optional production security layer for NetClaw, built on NVIDIA OpenShell.

- **NetClaw** = The claws (actions, skills, MCP tools)
- **NetShell** = The shell (protection, governance, permissions)

## What It Does

NetShell wraps NetClaw in a kernel-level sandbox with:

| Protection | Mechanism | Benefit |
|------------|-----------|---------|
| Filesystem isolation | Landlock LSM | Agent can only read/write declared paths |
| Network egress control | Policy engine | Agent can only reach declared endpoints |
| Process restrictions | seccomp | No privilege escalation, limited syscalls |
| Credential protection | Injection | API keys never written to disk |
| MCP tool governance | NetShell policies | Per-skill tool allowlists |
| Audit logging | OCSF format | Every tool call logged for compliance |

## Directory Structure

```
netshell/
├── README.md                 # This file
├── policies/
│   ├── base.yaml             # Default sandbox policy
│   ├── mcp/                  # Per-MCP server policies
│   │   ├── pyats-mcp.yaml
│   │   ├── meraki-mcp.yaml
│   │   └── ...
│   ├── skills/               # Compiled skill policies (generated)
│   └── compliance/           # Compliance templates
│       ├── soc2.yaml
│       ├── pci-dss.yaml
│       └── hipaa.yaml
├── scripts/
│   ├── compile-policies.py   # Generate skill policies from SKILL.md
│   ├── validate-policies.py  # Check policy consistency
│   └── audit-report.py       # Generate compliance reports
└── templates/
    └── skill-policy.yaml.j2  # Template for skill policies
```

## Enabling NetShell

NetShell is opt-in during installation:

```bash
./scripts/install.sh

# ... OpenClaw setup ...
# ... NetClaw setup ...

Enable production security (NetShell)? [y/N]: y
Checking Docker... OK
Pulling netclaw/netshell sandbox image...
Generating policies from skills...
NetShell enabled. NetClaw will run in sandbox.
```

## Requirements

- Docker (required for OpenShell sandbox)
- OpenShell CLI (`uv tool install openshell`)

## Policy Reference

### Base Policy (base.yaml)

Controls sandbox-wide settings:
- Allowed filesystem paths
- Default network egress rules
- Process restrictions
- Credential injection list

### MCP Policies (mcp/*.yaml)

Per-MCP server controls:
- Network endpoints the MCP can reach
- Tool-level allow/deny lists
- Argument validation rules
- Dangerous command patterns

### Skill Policies (skills/*.yaml)

Generated from SKILL.md frontmatter:
- Which MCP tools the skill can invoke
- Argument constraints
- ITSM approval requirements

**Adding Permissions to a Skill**:

Add a `netshell:` section to your SKILL.md frontmatter:

```yaml
---
name: my-skill
description: My skill description
version: 1.0.0

netshell:
  mcp_tools:
    - mcp: pyats-mcp
      tools:
        - pyats_run_show_command    # Read-only
        - pyats_parse_show_command
    - mcp: aruba-cx-mcp
      tools:
        - aruba_get_vlans           # Read-only
        - aruba_create_vlan         # Write - triggers ITSM
  approval_required: false          # Override ITSM per-skill
---
```

**Compile Policies**:

```bash
python netshell/scripts/compile-policies.py --verbose
```

**Check Permissions at Runtime**:

```bash
python netshell/scripts/check-skill-permissions.py \
  --skill pyats-health-check \
  --mcp pyats-mcp \
  --tool pyats_run_show_command
```

See `workspace/skills/SKILL-SCHEMA.md` for full schema reference.

## Audit Logging

All tool invocations are logged in OCSF (Open Cybersecurity Schema Framework) format.

**Log Location**: `/workspace/logs/audit/netshell.log`

**Example Record** (OCSF API Activity - class_uid 4001):

```json
{
  "class_uid": 4001,
  "category_uid": 4,
  "activity_id": 2,
  "time": 1712844000000,
  "severity_id": 1,
  "message": "Tool invocation: pyats-mcp.show_command",
  "status": "success",
  "actor": {"user": "pyats-health-check", "session_id": "ns-1712844000000-1234"},
  "api": {
    "operation": "show_command",
    "service": "pyats-mcp",
    "request": {"device": "router1", "command": "show ip route"},
    "response": {"_truncated": true}
  },
  "metadata": {
    "version": "1.0.0",
    "product": {"name": "NetShell", "version": "1.0.0"}
  }
}
```

**Generate Compliance Reports**:

```bash
# SOC2-style markdown report
python netshell/scripts/audit-report.py --format soc2 --days 30 > audit-report.md

# JSON for SIEM ingestion
python netshell/scripts/audit-report.py --format json --output audit-export.json
```

## Hot-Reload Network Policies

Network policies can be updated without restarting the sandbox:

```bash
# Edit MCP policy
nano netshell/policies/mcp/suzieq-mcp.yaml

# Trigger reload
kill -HUP $(pidof netshell-gateway)
# Or use the helper script:
netshell/scripts/sandbox-wrapper.sh reload-policies
```

**Hot-reloadable settings**:
- `network_policies.egress` rules
- `network_policies.blocked` destinations
- `inference.backends` routing

**Immutable settings** (require sandbox restart):
- `filesystem_policy` (Landlock locked at creation)
- `landlock` configuration
- `process` / `seccomp` settings

## Disabling NetShell

To run NetClaw without sandbox (development/hobby mode):

```bash
# In ~/.openclaw/config/openclaw.json
{
  "netshell": {
    "enabled": false
  }
}
```

## Learn More

- [NVIDIA OpenShell](https://github.com/NVIDIA/OpenShell) - Kernel sandbox runtime
- [OpenShell Docs](https://docs.nvidia.com/openshell/latest/) - Official documentation
- [NetClaw Constitution](../CONSTITUTION.md) - Security principles that generate policies
