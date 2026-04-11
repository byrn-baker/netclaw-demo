# NetShell Research: NVIDIA OpenShell Analysis

## Sources Analyzed

1. [NVIDIA OpenShell GitHub](https://github.com/NVIDIA/OpenShell)
2. [OpenShell Overview Docs](https://docs.nvidia.com/openshell/latest/about/overview)
3. [OpenShell Getting Started](https://docs.nvidia.com/openshell/latest/get-started)
4. [OpenShell Community](https://github.com/NVIDIA/OpenShell-Community)
5. [NVIDIA Build - OpenShell](https://build.nvidia.com/openshell)
6. [Deconvolute - MCP Protocol Security](https://deconvoluteai.com/blog/nvidia-openshell-mcp-protocol-layer)
7. [Cisco AI Defense + OpenShell](https://blogs.cisco.com/ai/securing-enterprise-agents-with-nvidia-and-cisco-ai-defense)

## What is NVIDIA OpenShell?

OpenShell is "the safe, private runtime for autonomous AI agents" that:
- Runs agents in isolated container environments (K3s inside Docker)
- Enforces policies via declarative YAML
- Controls filesystem, network, process, and inference access
- Uses kernel-level mechanisms (Landlock, seccomp, network namespaces)

## Core Architecture

### Four Components

1. **Gateway**: Control-plane API that coordinates sandbox lifecycle and acts as auth boundary
2. **Sandbox**: Isolated runtime with container supervision and policy-enforced egress routing
3. **Policy Engine**: Enforces filesystem, network, and process constraints from app layer to kernel
4. **Privacy Router**: Privacy-aware LLM routing that keeps sensitive context on sandbox compute

### Four Protection Layers

| Layer | Protection | Mechanism | Timing |
|-------|------------|-----------|--------|
| Filesystem | Prevent unauthorized reads/writes | Landlock LSM | Locked at creation |
| Network | Block unauthorized outbound | Egress policies | Hot-reloadable |
| Process | Block privilege escalation | seccomp | Locked at creation |
| Inference | Route to controlled backends | Privacy router | Hot-reloadable |

## Policy System

### Static vs Dynamic Policies

- **Static** (locked at sandbox creation): `filesystem_policy`, `landlock`, `process`
- **Dynamic** (hot-reloadable): `network_policies`, inference routing

### Egress Enforcement

Every outbound connection is intercepted:
- **Allow**: Matches destination and binary policy rules
- **Route for inference**: Strips caller credentials, injects backend credentials
- **Deny**: Blocks and logs request

### Example Policy Structure

```yaml
version: 1
filesystem_policy:
  allowed_paths:
    - /workspace
    - /tmp
landlock:
  read_only_paths:
    - /etc
process:
  no_new_privs: true
  seccomp_profile: default
network_policies:
  egress:
    - host: "api.anthropic.com"
      ports: [443]
      methods: ["POST"]
    - host: "*.meraki.com"
      ports: [443]
      methods: ["GET", "POST", "PUT", "DELETE"]
  deny_default: true
```

## Credential Management

- Credentials are **never written to sandbox filesystem**
- Injected as environment variables at sandbox creation
- Auto-discovery for Claude, Codex, OpenCode, Copilot
- Named "providers" for explicit credential bundles

## The MCP Security Gap

**Critical Finding**: OpenShell cannot inspect MCP protocol content.

When an agent opens a TLS connection to an MCP server:
1. OpenShell evaluates network policy → allows connection
2. For REST endpoints with L7 config, can inspect HTTP method and path
3. **Cannot inspect request body** where MCP tool names, arguments, schemas live

This means OpenShell alone cannot enforce:
- Which MCP tools an agent can invoke
- What arguments are valid for a tool
- Per-skill tool allowlists

## Solution: Protocol-Layer Enforcement

### Deconvolute Approach

A protocol-layer firewall that:
1. Enforces least privilege at tool invocation using declarative YAML + CEL
2. Filters tool discovery (blocked tools removed before agent sees them)
3. Validates arguments before requests reach MCP servers

### NetShell Approach

Adapt Deconvolute's concepts for NetClaw:
1. Skill YAML declares required tools
2. Policy engine filters tool lists per skill
3. Argument validation using CEL expressions
4. Audit logging in OCSF format

## Existing OpenClaw Integration

OpenShell already supports OpenClaw as a sandbox backend:
- `backend: "openshell"` in openclaw.json
- Reuses SSH transport and remote filesystem bridge
- OpenShell-specific lifecycle (create/get/delete)
- Optional mirror workspace mode

## Current Status

**Alpha Software** (as of April 2026):
- Single-player mode only
- One developer, one environment, one gateway
- Multi-tenant enterprise deployment is future goal
- Breaking changes expected between releases

## Supported Agents

Out of the box:
- Claude Code
- Codex
- OpenCode
- GitHub Copilot CLI
- OpenClaw/Ollama (via community catalog)

## Key Takeaways for NetShell

1. **OpenShell provides Layer 0** (kernel sandbox) - adopt as-is
2. **Need Layer 1 for MCP governance** - build NetShell policy engine
3. **Declarative YAML policies** - align with existing NetClaw patterns
4. **Per-skill permissions** - extend SKILL.md frontmatter
5. **Constitution integration** - generate policies from principles
6. **Audit logging** - OCSF format for compliance
7. **ITSM gates** - leverage existing ServiceNow integration
8. **Hot-reloadable network policies** - no restart for egress changes

## Risks and Mitigations

| Risk | Status | Mitigation |
|------|--------|------------|
| Alpha software | Acknowledged | Pin versions, test extensively |
| MCP inspection gap | Understood | Layer 1 policy engine |
| Breaking changes | Expected | Version lock, migration scripts |
| Performance | Unknown | Benchmark before production |
| Complexity | Moderate | Start permissive, tighten |

## Next Steps

1. Create OpenShell sandbox image with NetClaw dependencies
2. Define base network policy for 71 MCP servers
3. Extend SKILL.md schema with permission declarations
4. Build policy compiler (skill declarations → enforcement rules)
5. Implement audit logging
6. Update constitution with security principles
