<!--
  Sync Impact Report
  ==================
  Version change: 0.0.0 (template) → 1.0.0 (initial ratification)

  Modified principles: N/A (first ratification)

  Added sections:
    - 16 Core Principles (I through XVI)
    - Operational Constraints section
    - Artifact Coherence Checklist section
    - Development Workflow section
    - Governance section

  Removed sections: All template placeholders replaced

  Templates requiring updates:
    - .specify/templates/plan-template.md — ✅ Compatible (Constitution Check
      section will be populated per-feature from these principles)
    - .specify/templates/spec-template.md — ✅ Compatible (spec requirements
      align with safety-first, verify-after-change, and documentation principles)
    - .specify/templates/tasks-template.md — ✅ Compatible (Phase N Polish
      section aligns with artifact coherence checklist; task phases support
      observe → baseline → change → verify workflow)

  Follow-up TODOs: None
-->

# NetClaw Constitution

## Core Principles

### I. Safety-First Operations (NON-NEGOTIABLE)

- All device interaction MUST begin with observation (`show` commands)
  before any configuration change.
- Destructive commands (`write erase`, `reload`, `delete`, `shutdown`)
  MUST NOT be executed without explicit human approval.
- Device state MUST NOT be assumed or guessed — it MUST be verified
  via live CLI or API query.
- If a device is unreachable or returns unexpected state, the operation
  MUST halt and report rather than proceed with assumptions.

### II. Read-Before-Write

- Every MCP server and skill MUST observe and capture current state
  before making any modification.
- A baseline MUST be recorded (via GAIT or equivalent) prior to any
  configuration change.
- The pattern is always: observe → baseline → modify → verify.

### III. ITSM-Gated Changes

- All production changes MUST have an approved ServiceNow Change
  Request (CR) before execution.
- The CR lifecycle (Assess → Authorize → Implement → Review) MUST
  be followed completely.
- Lab mode is the sole exception — lab devices MAY be modified
  without a CR, but MUST still be GAIT-logged.
- If a CR is rejected or withdrawn mid-execution, the change MUST
  halt immediately and rollback.

### IV. Immutable Audit Trail

- Every session, configuration change, and operational decision MUST
  be recorded in the GAIT (Git-based Audit and Immutable Trail) system.
- No operation MAY execute silently — all actions MUST produce an
  audit record.
- GAIT logs MUST NOT be modified after creation. Corrections are
  recorded as new entries referencing the original.
- Every session MUST end with a GAIT summary commit.

### V. MCP-Native Integration

- All new capabilities MUST be built as MCP (Model Context Protocol)
  servers following the MCP standard.
- No bespoke integration patterns outside the MCP protocol are
  permitted for tool integration.
- Each MCP server MUST implement proper JSON-RPC lifecycle methods
  (`initialize`, `tools/list`, `tools/call`).
- MCP servers MUST declare their transport protocol (stdio, SSE,
  or remote HTTP) explicitly.

### VI. Multi-Vendor Neutrality

- Skills SHOULD be vendor-agnostic where the operation is generic
  (e.g., interface health, routing table inspection).
- Vendor-specific logic MUST reside in vendor-specific MCP servers,
  not in shared skills.
- When a skill spans multiple vendors, it MUST delegate to the
  appropriate vendor MCP server rather than embedding vendor logic.
- New vendor support MUST follow existing MCP server patterns
  (separate server per vendor platform).

### VII. Skill Modularity

- Each skill MUST perform a single, well-defined operational function.
- Skills compose by invoking other skills or MCP tools — they MUST
  NOT duplicate functionality that exists elsewhere.
- A skill MUST NOT exceed a reasonable scope. If a skill grows beyond
  its original charter, it MUST be decomposed.
- Every skill MUST have a corresponding `SKILL.md` file documenting
  its purpose, tools used, and workflow steps.

### VIII. Verify After Every Change

- The change workflow is always: baseline → apply → verify → report.
- If post-change verification fails, the system MUST attempt rollback
  to the captured baseline.
- If rollback fails, the system MUST halt, alert the operator, and
  mark the ServiceNow CR as failed.
- Verification MUST compare actual device state against expected
  state — not merely confirm command execution succeeded.

### IX. Security by Default

- CIS benchmark auditing and NVD CVE scanning are standard
  operational capabilities, not optional add-ons.
- Least-privilege access MUST be enforced: MCP servers request only
  the permissions they require.
- Security audits (ACL analysis, AAA verification, certificate
  checks) MUST be available for every supported platform.
- New MCP servers MUST document their required privilege level
  and justify any elevated permissions.

### X. Observability as a First-Class Citizen

- Every monitored system MUST have metrics, logs, or both accessible
  via MCP tools.
- New integrations MUST expose health and status endpoints or
  equivalent observability hooks.
- Alerting, dashboarding, and log querying MUST be available for
  all infrastructure under management.
- The Three.js HUD MUST be updated to reflect new integrations
  and their operational status.

### XI. Full-Stack Artifact Coherence (NON-NEGOTIABLE)

- When adding ANY new capability (MCP server, skill, or integration),
  ALL of the following artifacts MUST be updated before the feature
  is considered complete:
  - `README.md` — capability description, architecture diagram, tool
    count, and setup instructions
  - `scripts/install.sh` — installation steps for new dependencies
  - `ui/netclaw-visual/` — Three.js HUD nodes for new integrations
  - `SOUL.md` — skill definitions, identity references, and
    capability summary
  - `workspace/skills/<skill-name>/SKILL.md` — individual skill
    documentation
  - `.env.example` — all new environment variables with descriptions
    (no values)
  - `TOOLS.md` — infrastructure reference updates
  - `config/openclaw.json` — MCP server registration (if applicable)
  - Any other configuration files affected by the addition
- A pull request that adds a capability without updating all required
  artifacts MUST NOT be merged.

### XII. Documentation-as-Code

- Every skill MUST have a `SKILL.md` file documenting: purpose,
  MCP tools used, workflow steps, required environment variables,
  and example usage.
- Every MCP server MUST document: its tools (name, description,
  parameters), required environment variables, transport protocol,
  and installation steps.
- `README.md` MUST accurately reflect the current count and state
  of all skills, MCP servers, and supported platforms.
- Documentation MUST be updated in the same PR as the code change —
  not in a follow-up.

### XIII. Credential Safety

- Secrets and credentials MUST reside in `.env` files, NEVER
  hardcoded in source code or configuration files.
- `.env.example` MUST document all required environment variables
  with descriptive comments but without actual values.
- `.env` files MUST be in `.gitignore` — credentials MUST NOT
  appear in git history.
- MCP servers MUST read credentials from environment variables
  at runtime, not from configuration files.

### XIV. Human-in-the-Loop for External Communications

- The agent MUST ask for explicit human approval before:
  - Sending messages to Slack channels, WebEx rooms, or Teams
  - Creating, updating, or closing ServiceNow tickets
  - Creating or commenting on GitHub issues or PRs
  - Any action visible to people outside the current session
- Automated alerting (e.g., Slack incident alerts) MUST be
  configured explicitly by the operator, not triggered
  autonomously.

### XV. Backwards Compatibility

- New MCP servers and skills MUST NOT break existing ones.
- Changes to shared interfaces (MCP tool schemas, environment
  variable names, configuration formats) MUST maintain backwards
  compatibility or include a documented migration path.
- New dependencies MUST be isolated — they MUST NOT conflict with
  existing Python, Node.js, or system packages.
- Integration testing MUST verify that existing capabilities
  remain functional after additions.

### XVI. Spec-Driven Development

- All new features, MCP servers, and skills MUST follow the SDD
  workflow: specify → plan → task → implement.
- No implementation work begins without a ratified spec.
- Specs live in `.specify/specs/<feature-name>/` and follow the
  Speckit template structure.
- Ad-hoc or undocumented feature additions ("cowboy coding") are
  not permitted.

## Operational Constraints

### Technology Stack

- **AI Runtime**: OpenClaw gateway with Anthropic Claude
  (Opus 4.6 primary, Sonnet 4.6 fallback)
- **Integration Protocol**: MCP (Model Context Protocol) exclusively
- **Device Automation**: pyATS (Cisco), PyEZ (Juniper), iControl
  REST (F5), vendor REST APIs
- **Languages**: Python 3.10+ (MCP servers, scripts),
  Node.js 18+ (UI, some MCP servers), Bash (installation)
- **Audit**: GAIT (Git-based Audit and Immutable Trail)
- **ITSM**: ServiceNow (change management, incidents, CMDB)
- **Observability**: Grafana, Prometheus, Loki

### Forbidden Operations

- `write erase`, `reload`, `format flash:` on any device
- `rm -rf`, `drop database`, or equivalent destructive commands
- Force-pushing to shared branches
- Committing `.env` files or credentials
- Bypassing ServiceNow CR approval for production changes
- Silent operations without GAIT logging

### MCP Server Standards

- Each MCP server MUST implement a `README.md` with:
  tool inventory, environment variables, transport protocol,
  and installation instructions.
- MCP servers MUST use FastMCP (Python) or the official MCP SDK
  (Node.js) — no custom protocol implementations.
- Read-only MCP servers are preferred. Write operations MUST be
  explicitly flagged and gated.

## Artifact Coherence Checklist

When adding a new capability, use this checklist to verify
completeness. Every item MUST be checked before merge:

```
[ ] README.md updated (description, architecture, counts)
[ ] scripts/install.sh updated (new dependencies, setup steps)
[ ] ui/netclaw-visual/ updated (new HUD node or panel)
[ ] SOUL.md updated (skill definition, capability summary)
[ ] workspace/skills/<name>/SKILL.md created (full documentation)
[ ] .env.example updated (new variables with descriptions)
[ ] TOOLS.md updated (infrastructure reference)
[ ] config/openclaw.json updated (MCP server registration)
[ ] mcp-servers/<name>/README.md created (if new MCP server)
[ ] GAIT session log recorded
[ ] Existing skills verified unbroken
```

## Development Workflow

### SDD Lifecycle

Every new capability follows this sequence:

1. **Specify** (`/speckit.specify`) — Define the feature, user
   stories, acceptance criteria, and requirements.
2. **Clarify** (`/speckit.clarify`, optional) — Resolve ambiguities
   before planning.
3. **Plan** (`/speckit.plan`) — Research, design, and create the
   implementation plan with data models and contracts.
4. **Tasks** (`/speckit.tasks`) — Generate dependency-ordered,
   parallelizable task lists.
5. **Analyze** (`/speckit.analyze`, optional) — Cross-artifact
   consistency check.
6. **Implement** (`/speckit.implement`) — Execute tasks in order,
   verifying each checkpoint.
7. **Coherence** — Run the Artifact Coherence Checklist above.
8. **Review** — PR review with constitution compliance verification.

### Constitution Compliance in Reviews

Every PR MUST be evaluated against this constitution. The reviewer
MUST verify:

- Safety principles (I, II, VIII) are respected in any device-facing
  code
- Artifact coherence (XI) is complete — all touchpoints updated
- Documentation (XII) is current and accurate
- Credentials (XIII) are handled safely
- Spec exists (XVI) for any new capability

## Governance

- This constitution supersedes all other development practices
  for the NetClaw project.
- Amendments require: (1) a documented rationale, (2) review of
  impact on existing principles, and (3) a version bump following
  semantic versioning (MAJOR for removals/redefinitions, MINOR for
  additions, PATCH for clarifications).
- All contributors MUST read this constitution before submitting
  changes.
- Compliance with this constitution is verified during PR review
  and enforced by the Artifact Coherence Checklist.
- Use `.specify/` templates and workflows for all runtime
  development guidance.

**Version**: 1.0.0 | **Ratified**: 2026-03-26 | **Last Amended**: 2026-03-26
