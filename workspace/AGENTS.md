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

## Error Handling

If something fails:
1. Read the error message
2. Fix the specific issue
3. Re-run

Do NOT rewrite your approach from scratch. Do NOT search the filesystem for files — paths are given to you in the SKILL.md.

If you fail 3 times on the same problem, switch to the fallback model with `/model deepseek-v4-flash:cloud`.
