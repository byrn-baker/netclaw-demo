# Tasks: NetShell Security and Governance Layer

**Input**: Design documents from `/specs/027-netshell-security/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Not explicitly requested in spec - skipped per template guidelines.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Prior Work Status

The following artifacts were created before speckit workflow and are complete:

| Artifact | Status | Action |
|----------|--------|--------|
| `netshell/README.md` | Complete | Verify alignment |
| `netshell/policies/base.yaml` | Complete | Validate against contract |
| `netshell/policies/mcp/*.yaml` | Complete (23 files) | Validate against contract |
| `netshell/scripts/` | Directory exists, empty | Create scripts |

---

## Phase 1: Setup (Verify Prior Work)

**Purpose**: Validate existing artifacts against contracts and establish project structure

- [x] T001 Validate netshell/policies/base.yaml against contracts/base-policy.md schema
- [x] T002 [P] Validate netshell/policies/mcp/*.yaml against contracts/mcp-policy.md schema (23 files)
- [x] T003 [P] Verify netshell/README.md aligns with spec.md user stories

---

## Phase 2: Foundational (Core Infrastructure)

**Purpose**: Core scripts and infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Create netshell/scripts/validate-policies.py for schema validation
- [x] T005 [P] Create netshell/templates/skill-permission.yaml.j2 for skill policy generation
- [x] T006 Create netshell/scripts/compile-policies.py to generate skill policies from SKILL.md
- [x] T007 [P] Create OCSF audit record schema in netshell/schemas/ocsf-api-activity.json
- [x] T008 Add pyyaml, jsonschema dependencies to project requirements (if not present)

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Production Sandbox Isolation (Priority: P1)

**Goal**: Run NetClaw in an isolated sandbox so that compromised agents cannot access unauthorized files, credentials, or network endpoints

**Independent Test**: Run NetClaw in sandbox mode and attempt to access files/endpoints outside declared policy - all should be blocked

### Implementation for User Story 1

- [x] T009 [US1] Verify base.yaml filesystem_policy.denied includes /root, /home, /etc/shadow per contract
- [x] T010 [P] [US1] Verify base.yaml landlock.enabled is true per contract
- [x] T011 [P] [US1] Verify base.yaml process.no_new_privs is true per contract
- [x] T012 [P] [US1] Verify base.yaml process.seccomp.deny includes ptrace, mount, reboot per contract
- [x] T013 [US1] Verify base.yaml credentials.inject list matches required environment variables
- [x] T014 [US1] Create netshell/scripts/sandbox-wrapper.sh for OpenShell sandbox invocation
- [x] T015 [US1] Add --netshell CLI flag handling in scripts/openclaw-cli (or equivalent)

**Checkpoint**: Sandbox isolation functional - agent cannot access unauthorized paths or escalate privileges

---

## Phase 4: User Story 2 - Compliance Audit Logging (Priority: P1)

**Goal**: Log every tool invocation in OCSF format for SOC2, PCI-DSS, HIPAA compliance evidence

**Independent Test**: Invoke tools and verify audit log entries contain required fields (timestamp, actor, tool, arguments, decision)

### Implementation for User Story 2

- [x] T016 [US2] Create netshell/scripts/audit-logger.py implementing OCSF 4001 (API Activity) schema
- [x] T017 [P] [US2] Add audit_record() function for tool_invocation events
- [x] T018 [P] [US2] Add audit_record() function for policy_violation events with denial reason
- [x] T019 [US2] Verify base.yaml audit.enabled is true per contract
- [x] T020 [US2] Verify base.yaml audit.format is "ocsf" per contract
- [x] T021 [US2] Create netshell/scripts/audit-report.py for compliance export (SOC2 format)
- [x] T022 [US2] Document audit log location in netshell/README.md (/workspace/logs/audit/netshell.log)

**Checkpoint**: All tool invocations logged with OCSF-compliant fields - ready for compliance audit

---

## Phase 5: User Story 3 - Per-Skill Tool Permissions (Priority: P2)

**Goal**: Each skill can only invoke MCP tools explicitly declared in its SKILL.md netshell: section

**Independent Test**: Load a skill with limited permissions and verify it can only see/invoke declared tools

### Implementation for User Story 3

- [x] T023 [US3] Document netshell: SKILL.md schema in workspace/skills/SKILL-SCHEMA.md
- [x] T024 [US3] Update netshell/scripts/compile-policies.py to parse netshell: section from SKILL.md frontmatter
- [x] T025 [US3] Generate compiled skill policies to netshell/policies/skills/*.yaml
- [x] T026 [P] [US3] Create netshell/scripts/check-skill-permissions.py for runtime permission checks
- [x] T027 [US3] Add 5 example netshell: sections to existing skills (batch 1):
  - workspace/skills/meraki-network-ops/SKILL.md
  - workspace/skills/pyats-health-check/SKILL.md
  - workspace/skills/catc-inventory/SKILL.md
  - workspace/skills/gns3-mcp-related skill if exists
  - workspace/skills/suzieq-related skill if exists
- [x] T028 [US3] Add 5 more example netshell: sections to existing skills (batch 2):
  - workspace/skills/aws-network-ops/SKILL.md
  - workspace/skills/gcp-compute-ops/SKILL.md
  - workspace/skills/gitlab-related skill if exists
  - workspace/skills/jenkins-related skill if exists
  - workspace/skills/datadog-related skill if exists
- [x] T029 [US3] Update netshell/README.md with skill permission documentation

**Checkpoint**: Skills have declared permissions - tool invocations outside allowlist are blocked

---

## Phase 6: User Story 4 - Network Egress Control (Priority: P2)

**Goal**: Limit network egress to declared API endpoints only, preventing data exfiltration

**Independent Test**: Declare allowed endpoints and attempt to connect to undeclared endpoints - all should be blocked

### Implementation for User Story 4

- [x] T030 [US4] Verify all 23 MCP policies have valid network_policies.egress sections
- [x] T031 [P] [US4] Verify base.yaml network_policies.default_action is "deny" per contract
- [x] T032 [P] [US4] Verify base.yaml network_policies.core_egress includes api.anthropic.com
- [x] T033 [US4] Create netshell/scripts/egress-validator.py to check egress rules for common issues
- [x] T034 [US4] Add network_policies logging configuration (log_denied: true) to base.yaml
- [x] T035 [US4] Document hot-reload mechanism for network policies in netshell/README.md

**Checkpoint**: Network egress controlled - connections to undeclared endpoints blocked and logged

---

## Phase 7: User Story 5 - Opt-In Installation (Priority: P3)

**Goal**: NetShell is optional during installation, preserving easy onboarding for hobby users

**Independent Test**: Run install.sh, decline NetShell, verify NetClaw works without sandbox

### Implementation for User Story 5

- [x] T036 [US5] Add NetShell opt-in prompt to scripts/install.sh
- [x] T037 [US5] Add Docker availability check to scripts/install.sh (with clear error message if missing)
- [x] T038 [P] [US5] Add OpenShell CLI installation step (uv tool install openshell)
- [x] T039 [US5] Add policy compilation step to install.sh when NetShell enabled
- [x] T040 [US5] Update config/openclaw.json schema with netshell.enabled flag
- [x] T041 [US5] Create netshell/scripts/netshell-enable.sh for post-install enablement
- [x] T042 [US5] Create netshell/scripts/netshell-disable.sh for disabling NetShell
- [x] T043 [US5] Document installation flow in netshell/README.md

**Checkpoint**: Opt-in installation complete - users can choose sandbox or hobby mode

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation updates, validation, and final integration

- [x] T044 Update SOUL.md with NetShell security principles (P18-P25 per research.md)
- [x] T045 [P] Update main README.md with NetShell section
- [x] T046 [P] Update CLAUDE.md with NetShell context for agent awareness
- [x] T047 Run quickstart.md validation scenarios 1-9 (documented for manual runtime testing)
- [x] T048 [P] Remove superseded specs/netshell/spec.md (N/A - no superseded file exists)
- [x] T049 Create WordPress blog post for NetShell feature announcement (Post ID: 1579)
- [x] T050 Final review: verify all contracts satisfied (validate-policies.py: all 24 policies OK)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - validate existing artifacts
- **Foundational (Phase 2)**: Depends on Setup - creates core scripts
- **US1 Sandbox (Phase 3)**: Depends on Foundational - implements isolation
- **US2 Audit (Phase 4)**: Depends on Foundational - can run parallel with US1
- **US3 Permissions (Phase 5)**: Depends on Foundational - can run parallel with US1/US2
- **US4 Egress (Phase 6)**: Depends on Foundational - can run parallel with US1/US2/US3
- **US5 Installation (Phase 7)**: Depends on US1-US4 (needs all features to install)
- **Polish (Phase 8)**: Depends on US1-US5 completion

### User Story Dependencies

- **US1 (Sandbox)**: Foundational only - no other story dependencies
- **US2 (Audit)**: Foundational only - independent of US1
- **US3 (Permissions)**: Foundational only - independent of US1/US2
- **US4 (Egress)**: Foundational only - independent of US1/US2/US3
- **US5 (Installation)**: Depends on ALL prior stories (installs all features)

### Parallel Opportunities

- All Setup tasks (T001-T003) can validate in parallel
- Foundational tasks T005, T007 can run in parallel with T004
- US1 tasks T010-T012 can run in parallel (different validation checks)
- US2 tasks T017-T018 can run in parallel (different audit functions)
- US3 tasks can run after compile-policies.py is done
- US4 tasks T031-T032 can run in parallel (different validation checks)
- US5 tasks T038 can run in parallel (OpenShell install while editing install.sh)
- Polish tasks T044-T046, T048 can all run in parallel

---

## Parallel Example: Phase 2 Foundational

```bash
# These can run in parallel (different files):
Task: "Create netshell/scripts/validate-policies.py"
Task: "Create netshell/templates/skill-permission.yaml.j2"
Task: "Create OCSF audit record schema in netshell/schemas/ocsf-api-activity.json"
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup validation
2. Complete Phase 2: Foundational scripts
3. Complete Phase 3: US1 Sandbox Isolation
4. Complete Phase 4: US2 Audit Logging
5. **STOP and VALIDATE**: Test sandbox + audit independently
6. Deploy/demo if ready (sandbox + compliance logging)

### Full Feature Delivery

1. MVP (US1 + US2) → Sandbox isolation + compliance logging
2. Add US3 → Per-skill tool permissions
3. Add US4 → Network egress control
4. Add US5 → Opt-in installation flow
5. Polish → Documentation, blog, final validation

### Task Count Summary

| Phase | Tasks | Parallelizable |
|-------|-------|----------------|
| Setup | 3 | 2 |
| Foundational | 5 | 3 |
| US1 Sandbox | 7 | 3 |
| US2 Audit | 7 | 2 |
| US3 Permissions | 7 | 1 |
| US4 Egress | 6 | 2 |
| US5 Installation | 8 | 1 |
| Polish | 7 | 4 |
| **Total** | **50** | **18** |

---

## Notes

- Prior work (23 MCP policies, base.yaml, README.md) is preserved
- Skill netshell: sections added in batches of 5 to manage context
- OCSF format (class_uid 4001) used for audit logging per spec
- OpenShell CLI installed via uv tool (not pip) per research.md
- Docker required only when NetShell enabled (hobby mode works without)
- Constitution principles P18-P25 to be added to SOUL.md
