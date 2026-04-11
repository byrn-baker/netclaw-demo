# Implementation Plan: NetShell Security and Governance Layer

**Branch**: `027-netshell-security` | **Date**: 2026-04-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/027-netshell-security/spec.md`

## Summary

NetShell adds production-grade security to NetClaw by wrapping it in an NVIDIA OpenShell sandbox with two-layer protection. Layer 0 (OpenShell) provides kernel-level isolation via Landlock LSM, seccomp, and network namespaces. Layer 1 (NetShell) adds MCP protocol governance with per-skill tool permissions, argument validation, and OCSF audit logging. The feature is opt-in during installation, preserving backward compatibility for hobby users.

## Technical Context

**Language/Version**: Python 3.10+ (MCP servers, policy scripts), Bash (installation)
**Primary Dependencies**: NVIDIA OpenShell CLI (uv tool), Docker (container runtime), existing FastMCP servers
**Storage**: Local filesystem for policies and audit logs; no database
**Testing**: Manual validation per quickstart.md scenarios; policy enforcement verification
**Target Platform**: Linux (Docker host), WSL2 supported
**Project Type**: Security layer / configuration-only integration
**Performance Goals**: Cold start <5s, per-tool overhead <5ms
**Constraints**: Docker required when enabled; backward compatible when disabled

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Safety-First Operations | PASS | Sandbox adds safety layer; doesn't change device interaction |
| II. Read-Before-Write | PASS | No device changes; policy is observe-then-enforce |
| III. ITSM-Gated Changes | PASS | Write tools require approval via existing ITSM gates |
| IV. Immutable Audit Trail | PASS | OCSF audit logging satisfies audit requirement |
| V. MCP-Native Integration | PASS | Policies govern MCP servers; no non-MCP patterns |
| VI. Multi-Vendor Neutrality | PASS | Per-MCP policies, vendor-agnostic framework |
| VII. Skill Modularity | PASS | Skills declare permissions in SKILL.md frontmatter |
| VIII. Verify After Every Change | PASS | Sandbox enforces; policy changes verifiable |
| IX. Security by Default | PASS | Core purpose is security enhancement |
| X. Observability | PASS | Audit logs provide observability |
| XI. Full-Stack Artifact Coherence | PASS | Plan includes README, SOUL, install.sh updates |
| XII. Documentation-as-Code | PASS | SKILL.md extended with netshell: section |
| XIII. Credential Safety | PASS | Credentials injected, never written to sandbox |
| XIV. Human-in-the-Loop | PASS | Opt-in installation; no autonomous external comms |
| XV. Backwards Compatibility | PASS | Opt-in; disabled mode unchanged |
| XVI. Spec-Driven Development | PASS | Following speckit workflow |
| XVII. Milestone Documentation | PASS | WordPress blog post at completion |

**Gate Result**: ALL PASS - Proceed with implementation

## Project Structure

### Documentation (this feature)

```text
specs/027-netshell-security/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # OpenShell research (complete)
├── data-model.md        # Policy schema definitions
├── quickstart.md        # Validation scenarios
├── contracts/           # Policy YAML schemas
│   ├── base-policy.md
│   ├── mcp-policy.md
│   └── skill-permission.md
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
netshell/
├── README.md                    # NetShell documentation
├── policies/
│   ├── base.yaml                # Default sandbox policy
│   └── mcp/                     # Per-MCP server policies (23 files)
│       ├── suzieq-mcp.yaml
│       ├── gnmi-mcp.yaml
│       └── ...
├── scripts/
│   ├── compile-policies.py      # Generate policies from skills
│   └── validate-policies.py     # Check policy consistency
└── templates/
    └── skill-permission.yaml.j2 # Template for skill policies

scripts/
└── install.sh                   # Updated with NetShell phase

config/
└── openclaw.json                # Updated with netshell config

workspace/skills/
└── */SKILL.md                   # Extended with netshell: section

SOUL.md                          # Updated with security principles
README.md                        # Updated with NetShell section
```

**Structure Decision**: Configuration-only integration using existing `netshell/` directory (already created with 23 MCP policies). No new MCP server required - OpenShell CLI handles sandbox lifecycle.

## Prior Work Migration

The following artifacts were created before speckit workflow and will be incorporated:

| Artifact | Status | Action |
|----------|--------|--------|
| `netshell/README.md` | Complete | Keep as-is |
| `netshell/policies/base.yaml` | Complete | Keep as-is |
| `netshell/policies/mcp/*.yaml` | Complete (23 files) | Keep as-is |
| `specs/netshell/spec.md` | Superseded | Delete (replaced by 027) |

## Complexity Tracking

> No Constitution violations requiring justification.

| Item | Complexity | Rationale |
|------|------------|-----------|
| Two-layer security | Necessary | OpenShell gap requires Layer 1 for MCP governance |
| 23 MCP policies | Required | Each MCP needs network egress rules |
| Opt-in installation | Required | Backward compatibility per spec |

## Phase Completion Status

### Phase 0: Research (COMPLETE)

- [x] NVIDIA OpenShell architecture research
- [x] Identified MCP security gap (cannot inspect tool calls)
- [x] Designed two-layer solution (OpenShell + NetShell)
- [x] Output: `research.md`

### Phase 1: Design (COMPLETE)

- [x] Data model defined: `data-model.md`
- [x] Policy schemas defined: `contracts/base-policy.md`, `contracts/mcp-policy.md`, `contracts/skill-permission.md`
- [x] Validation scenarios: `quickstart.md`
- [x] Agent context updated: `CLAUDE.md`
- [x] Constitution check: ALL PASS

### Phase 2: Tasks (COMPLETE)

- [x] Run `/speckit.tasks` to generate task list
- [x] Output: `tasks.md`

### Phase 3: Implementation (COMPLETE)

- [x] Run `/speckit.implement` to execute tasks (50 tasks completed)
- [x] Update install.sh with NetShell opt-in phase
- [x] Update SKILL.md schema (`workspace/skills/SKILL-SCHEMA.md`)
- [x] Create policy compilation scripts (`compile-policies.py`, `validate-policies.py`)
- [x] Create audit logging scripts (`audit-logger.py`, `audit-report.py`)
- [x] Create sandbox wrapper (`sandbox-wrapper.sh`)
- [x] Create egress validator (`egress-validator.py`)
- [x] Create permission checker (`check-skill-permissions.py`)
- [x] Update SOUL.md with security principles P18-P25
- [x] WordPress blog post (Post ID: 1579)
- [x] Final contract validation (all 24 policies valid)
