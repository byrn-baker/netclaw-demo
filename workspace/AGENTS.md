# NetClaw Demo — Operating Instructions

## Startup Protocol

1. Read `SOUL.md` — your identity and personality
2. Read the active skill (`skills/netclaw-demo/SKILL.md`) — this is your PRIMARY directive
3. Read `TOOLS.md` — environment details
4. Wait for the user to tell you what to do

**The SKILL.md is authoritative.** If anything in SOUL.md, TOOLS.md, or other files contradicts the skill, the skill wins.

## Demo Context

This is a locked-down demo VM. You have ONE job: run the NetClaw SP core demo.

- **No ServiceNow** — this is a lab, not production. Push configs directly.
- **No pyATS** — use `docker exec ... vtysh` for all device interaction.
- **No NetBox** — the SOT is Nautobot (http://localhost:8080).
- **No GAIT** — GAIT tools may not be available on this VM. Skip if unavailable.
- **No heartbeats** — do not run background checks or post to Slack.

## What You Can Do

1. Deploy the ContainerLab topology
2. Start Nautobot and run the design builder job
3. Query Nautobot via GraphQL and generate FRR configs
4. Push configs to routers via docker exec vtysh
5. Validate OSPF/BGP convergence
6. Join the topology via protocol-mcp (optional)

## What You Cannot Do

- Anything outside the demo scope
- Access the internet
- Install packages
- Modify system configuration
- Create files outside the workspace

---

## Mandatory: Attempt Tracking and Model Escalation

You MUST use the attempt tracker for every task that fails. This is not optional.

### The tracker

```bash
python3 /home/ubuntu/netclaw/scripts/attempt-tracker.py <command> [args]
```

### Rules — follow these exactly:

**When a task fails:**
```bash
python3 /home/ubuntu/netclaw/scripts/attempt-tracker.py log \
  --task "<short description of what you were trying to do>" \
  --error "<the actual error message>" \
  --model "<current model name>"
```

Read the JSON output. If `"should_escalate": true`, you MUST immediately run:
```
/model deepseek-v4-flash:cloud
```
Then re-read the history to understand what already failed:
```bash
python3 /home/ubuntu/netclaw/scripts/attempt-tracker.py history --task "<same task>"
```
Use that context to try a fundamentally different approach.

**Before retrying any task that previously failed:**
```bash
python3 /home/ubuntu/netclaw/scripts/attempt-tracker.py check --task "<task description>"
```
If exit code is 1 (threshold reached), switch models BEFORE retrying.

**When a task succeeds:**
```bash
python3 /home/ubuntu/netclaw/scripts/attempt-tracker.py resolve --task "<task description>"
```

### What counts as a "task"

Use a SHORT, stable description that groups related attempts. Examples:
- `"push frr config to P1"`
- `"query bgp peerings from graphql"`
- `"enable the design job in nautobot"`
- `"validate ospf on P2"`
- `"establish bgp peering with RR1"`

Do NOT use the full error message as the task name. The task name must be the same across retries so the counter works.

### Escalation behavior

| Attempts | Action |
|----------|--------|
| 1 | Fix the specific error, retry |
| 2 | Stop. Read the error carefully. Make ONE targeted fix. |
| 3+ | Switch to `deepseek-v4-flash:cloud`. Re-read history. Try a different approach entirely. |

### After model switch

Once on the escalated model and the problem is solved, resolve the task and optionally switch back:
```bash
python3 /home/ubuntu/netclaw/scripts/attempt-tracker.py resolve --task "<task>"
/model qwen3.5:35b
```

### Anti-patterns the tracker catches

The tracker makes looping visible and enforceable:
- If you keep logging the same task with similar errors, the count goes up and forces escalation
- If you "start over" without resolving, the old count persists — you can't escape by rephrasing
- If you switch approaches without fixing, log it as the SAME task (because the goal hasn't changed)

---

## Error Handling (reinforced)

If something fails:
1. Log it with the attempt tracker
2. Read the error message — identify the SPECIFIC line/field/argument that failed
3. Fix THAT SPECIFIC THING — do not rewrite your entire approach
4. Check the tracker before retrying
5. If threshold reached, switch models

Do NOT rewrite your approach from scratch. Do NOT search the filesystem for files — paths are given to you in the SKILL.md. Do NOT say "let me try a simpler approach" — diagnose the actual error.
