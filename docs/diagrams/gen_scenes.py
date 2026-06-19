import json

FRAME_W = 1920
FRAME_H = 1080
GAP = 200

elements = []
eid = 0

def nid():
    global eid
    eid += 1
    return f"el-{eid}"

def frame(x, y, name):
    return {
        "type": "frame",
        "id": nid(),
        "x": x, "y": y,
        "width": FRAME_W, "height": FRAME_H,
        "name": name,
        "strokeColor": "#495057",
        "strokeWidth": 1
    }

def text(x, y, t, size=16, color="#1e1e1e", align="left", family=1, w=None, h=None):
    lines = t.split("\n")
    width = w or max(len(l) for l in lines) * size * 0.6
    height = h or len(lines) * (size + 4)
    return {
        "type": "text", "id": nid(),
        "x": x, "y": y,
        "width": width, "height": height,
        "text": t, "fontSize": size,
        "fontFamily": family,
        "textAlign": align,
        "strokeColor": color
    }

def rect(x, y, w, h, stroke="#1e1e1e", bg="#ffffff", sw=2):
    return {
        "type": "rectangle", "id": nid(),
        "x": x, "y": y, "width": w, "height": h,
        "strokeColor": stroke,
        "backgroundColor": bg,
        "fillStyle": "solid",
        "roundness": {"type": 3},
        "strokeWidth": sw
    }

def arrow(x, y, dx, dy):
    return {
        "type": "line", "id": nid(),
        "x": x, "y": y,
        "width": abs(dx), "height": abs(dy),
        "points": [[0, 0], [dx, dy]],
        "strokeColor": "#1e1e1e",
        "strokeWidth": 2,
        "endArrowhead": "arrow"
    }

# --- SCENE 1: Title Slide ---
sx, sy = 0, 0
elements.append(frame(sx, sy, "Scene 1 — Title"))
elements.append(text(sx+460, sy+300, "NetClaw", 96, "#c92a2a", "center", w=1000))
elements.append(text(sx+460, sy+420, "A CCIE-Level AI Network Engineering Coworker", 32, "#495057", "center", w=1000))
elements.append(text(sx+460, sy+520, "Reach. Grab. Execute.  \U0001f99e", 28, "#868e96", "center", w=1000))
elements.append(text(sx+560, sy+700, "NetGru Demo — cisco.com/go/netgru", 20, "#1971c2", "center", w=800))
elements.append(text(sx+560, sy+760, "Built on OpenClaw | 163 Skills | 66 MCP Integrations", 18, "#868e96", "center", w=800))

# --- SCENE 2: The Problem ---
sx = FRAME_W + GAP
elements.append(frame(sx, sy, "Scene 2 — The Problem"))
elements.append(text(sx+100, sy+80, "The Problem", 48, "#1e1e1e"))
elements.append(text(sx+100, sy+160, "Network automation today:", 24, "#495057"))

elements.append(rect(sx+100, sy+230, 500, 100, "#c92a2a", "#fff5f5"))
elements.append(text(sx+120, sy+245, "Write Ansible playbooks / Python scripts\nMaintain Jinja2 templates per vendor\nManual runbooks that drift from reality\nCopy-paste CLI from documentation", 16, "#c92a2a"))

elements.append(rect(sx+100, sy+380, 500, 100, "#c92a2a", "#fff5f5"))
elements.append(text(sx+120, sy+395, "Tribal knowledge lives in people's heads\nSpreadsheets as source of truth\nNo audit trail for 'who changed what'\nValidation is an afterthought", 16, "#c92a2a"))

elements.append(rect(sx+700, sy+230, 500, 250, "#2f9e44", "#ebfbee"))
elements.append(text(sx+720, sy+245, "What if instead:", 24, "#2f9e44"))
elements.append(text(sx+720, sy+290, "• Source of truth IS the config source\n• AI understands protocol semantics\n• Natural language drives the workflow\n• Every action is audited automatically\n• Validation is built into every change\n\n   Intent in  \u2192  Working network out", 18, "#1e1e1e"))

# --- SCENE 3: Three-Layer Architecture ---
sx = (FRAME_W + GAP) * 2
elements.append(frame(sx, sy, "Scene 3 — Architecture"))
elements.append(text(sx+100, sy+60, "How NetClaw Works", 48, "#1e1e1e"))
elements.append(text(sx+100, sy+120, "Three-layer agent architecture", 20, "#868e96"))

# Human
elements.append(rect(sx+80, sy+250, 250, 140, "#1e1e1e", "#ffc9c9"))
elements.append(text(sx+100, sy+270, "\U0001f464 Human Operator", 20, "#1e1e1e"))
elements.append(text(sx+100, sy+310, "Slack / WebEx / TUI\n\"Deploy the SP core\"\n\"Check BGP state\"", 14))

# Arrow
elements.append(arrow(sx+330, sy+320, 100, 0))
elements.append(text(sx+340, sy+295, "Natural Language", 12, "#868e96"))

# Agent box
elements.append(rect(sx+450, sy+180, 400, 700, "#1971c2", "#e7f5ff"))
elements.append(text(sx+530, sy+195, "\U0001f99e NetClaw Agent", 24, "#1971c2"))

# SOUL
elements.append(rect(sx+470, sy+240, 360, 100, "#862e9c", "#f3d9fa"))
elements.append(text(sx+490, sy+255, "SOUL.md \u2014 Identity", 18, "#862e9c"))
elements.append(text(sx+490, sy+285, "CCIE expertise \u2022 12 safety rules\nProtocol knowledge \u2022 Personality\n\"Never guess device state\"", 13))

# Skills
elements.append(rect(sx+470, sy+360, 360, 100, "#2f9e44", "#d8f5a2"))
elements.append(text(sx+490, sy+375, "Skills \u2014 Procedures", 18, "#2f9e44"))
elements.append(text(sx+490, sy+405, "163 structured workflows\nRunbooks the agent executes\n\"How to safely push config\"", 13))

# MCP
elements.append(rect(sx+470, sy+480, 360, 100, "#e8590c", "#fff4e6"))
elements.append(text(sx+490, sy+495, "MCP Servers \u2014 Capabilities", 18, "#e8590c"))
elements.append(text(sx+490, sy+525, "66 integrations (stateless tool calls)\nSwap without code changes\n\"USB ports for AI\"", 13))

# GAIT
elements.append(rect(sx+470, sy+600, 360, 100, "#495057", "#dee2e6"))
elements.append(text(sx+490, sy+615, "GAIT \u2014 Audit Trail", 18, "#495057"))
elements.append(text(sx+490, sy+645, "Immutable Git record\nEvery action + decision\n\"What did the AI do and why?\"", 13))

# Arrow to infra
elements.append(arrow(sx+850, sy+450, 100, 0))
elements.append(text(sx+860, sy+425, "Tool Calls", 12, "#868e96"))

# Infra column
elements.append(rect(sx+970, sy+180, 350, 700, "#868e96", "#f8f9fa", 1))
elements.append(text(sx+1050, sy+195, "Infrastructure", 20, "#495057"))
items = [
    ("\U0001f4cb Source of Truth", "Nautobot / NetBox", "#1971c2", "#a5d8ff"),
    ("\U0001f5a7 Devices", "pyATS / gNMI / NETCONF", "#2f9e44", "#b2f2bb"),
    ("\U0001f3ab ITSM", "ServiceNow / Jira", "#e8590c", "#ffec99"),
    ("\U0001f4ca Observability", "Grafana / Prometheus", "#862e9c", "#e5dbff"),
    ("\u2601\ufe0f Cloud", "AWS / Azure / GCP", "#1971c2", "#d0ebff"),
    ("\U0001f512 Security", "Check Point / FMC", "#c92a2a", "#ffc9c9"),
]
for i, (label, sub, sc, bg) in enumerate(items):
    yy = sy + 240 + i * 95
    elements.append(rect(sx+990, yy, 310, 75, sc, bg))
    elements.append(text(sx+1010, yy+10, label, 15, sc))
    elements.append(text(sx+1010, yy+35, sub, 13, "#495057"))

# --- SCENE 4: The Demo Lab ---
sx = (FRAME_W + GAP) * 3
elements.append(frame(sx, sy, "Scene 4 — Demo Lab"))
elements.append(text(sx+100, sy+60, "The Lab: 6-Node SP Core", 48, "#1e1e1e"))
elements.append(text(sx+100, sy+120, "FRRouting containers via ContainerLab \u2022 Starts BLANK \u2022 Everything built from Nautobot", 18, "#868e96"))

# Topology nodes
nodes = [
    ("PE1", sx+200, sy+350, "#a5d8ff", "10.255.255.1"),
    ("P1",  sx+500, sy+350, "#b2f2bb", "10.255.255.2"),
    ("P2",  sx+800, sy+350, "#b2f2bb", "10.255.255.3"),
    ("RR1", sx+1100, sy+350, "#ffec99", "10.255.255.6"),
    ("P3",  sx+500, sy+600, "#b2f2bb", "10.255.255.4"),
    ("P4",  sx+800, sy+600, "#b2f2bb", "10.255.255.5"),
]
for name, nx, ny, bg, lo in nodes:
    elements.append(rect(nx, ny, 150, 80, "#1e1e1e", bg))
    elements.append(text(nx+20, ny+10, name, 22, "#1e1e1e", "center", w=110))
    elements.append(text(nx+20, ny+45, lo + "/32", 13, "#495057", "center", w=110))

# Links
links = [
    (350, 390, 150, 0), (650, 390, 150, 0), (950, 390, 150, 0),
    (575, 430, 0, 170), (875, 430, 0, 170), (650, 640, 150, 0),
]
for lx, ly, ldx, ldy in links:
    elements.append({
        "type": "line", "id": nid(),
        "x": sx+lx, "y": sy+ly,
        "width": abs(ldx), "height": abs(ldy),
        "points": [[0,0],[ldx,ldy]],
        "strokeColor": "#495057", "strokeWidth": 3
    })

# Labels
elements.append(text(sx+100, sy+750, "ASN: 65000 (single iBGP domain)", 18))
elements.append(text(sx+100, sy+785, "IGP: OSPFv2 area 0 on all P2P links", 18))
elements.append(text(sx+100, sy+820, "BGP: iBGP full mesh via RR1 (route reflector)", 18))
elements.append(text(sx+100, sy+855, "NOS: FRRouting (latest) in Docker containers", 18))

elements.append(rect(sx+800, sy+750, 500, 120, "#c92a2a", "#fff5f5"))
elements.append(text(sx+820, sy+770, "Key Point:", 18, "#c92a2a"))
elements.append(text(sx+820, sy+800, "Containers start with NO configuration.\nNo IPs, no OSPF, no BGP.\nEverything gets built from Nautobot.", 16))

# --- SCENE 5: Demo Pipeline ---
sx = (FRAME_W + GAP) * 4
elements.append(frame(sx, sy, "Scene 5 — Demo Pipeline"))
elements.append(text(sx+100, sy+60, "SOT-to-Validated-Network Pipeline", 42, "#1e1e1e"))

phases = [
    ("Phase 1", "Deploy Lab", "#c92a2a", "#fff5f5",
     "ContainerLab spins up\n6 FRR containers\n\nAll routers: BLANK"),
    ("Phase 2", "Populate SOT", "#1971c2", "#e7f5ff",
     "Design Job creates:\n\u2022 Devices + Interfaces\n\u2022 IPs + Cables\n\u2022 BGP + OSPF models"),
    ("Phase 3", "Gen + Push", "#2f9e44", "#ebfbee",
     "For each device:\n1. GraphQL query\n2. Build FRR config\n3. Push via vtysh\n(dependency order)"),
    ("Phase 4", "Validate", "#862e9c", "#f8f0fc",
     "\u2713 OSPF neighbors FULL\n\u2713 BGP Established\n\u2713 All 6 loopbacks in RIB\n\u2713 Route propagation OK"),
]

for i, (num, title, sc, bg, content) in enumerate(phases):
    px = sx + 80 + i * 440
    py = sy + 200
    elements.append(rect(px, py, 380, 300, sc, bg))
    elements.append(text(px+20, py+15, num, 14, sc))
    elements.append(text(px+20, py+40, title, 24, sc))
    elements.append(text(px+20, py+85, content, 16))
    if i < 3:
        elements.append(arrow(px+390, py+150, 40, 0))

# Bottom insight
elements.append(rect(sx+80, sy+580, 1760, 120, "#e8590c", "#fff4e6"))
elements.append(text(sx+120, sy+600, "The AI Agent IS the Template Engine", 28, "#e8590c"))
elements.append(text(sx+120, sy+645, "No Jinja2. No Ansible. No hand-written Python.\nIt reads structured data from Nautobot, understands protocol semantics, and generates vendor-specific CLI.\nChange the data model \u2192 the config follows automatically.", 16, "#495057"))

# Advanced callout
elements.append(rect(sx+80, sy+750, 1760, 200, "#495057", "#f8f9fa", 1))
elements.append(text(sx+120, sy+770, "For Advanced Viewers \u2014 Design Principles", 22, "#495057"))
elements.append(text(sx+120, sy+810, "\u2460 Data-driven, not template-driven \u2014 derive config from data model semantics\n\u2461 Protocol-aware ordering \u2014 push sequence respects convergence dependencies (OSPF before BGP)\n\u2462 Idempotent intent \u2014 re-run produces same result; FRR merges additive config\n\u2463 SOT-first, always \u2014 never hardcode device facts; always query the source of truth\n\u2464 Validate, don't trust \u2014 match expected state against actual state after every change", 15, "#495057"))

# --- SCENE 6: Protocol Participation ---
sx = (FRAME_W + GAP) * 5
elements.append(frame(sx, sy, "Scene 6 — Protocol Participation"))
elements.append(text(sx+100, sy+60, "NetClaw Joins the Network", 48, "#1e1e1e"))
elements.append(text(sx+100, sy+120, "From operator to participant \u2014 the agent IS a router", 20, "#868e96"))

# NetClaw box
elements.append(rect(sx+80, sy+220, 400, 350, "#c92a2a", "#fff5f5", 3))
elements.append(text(sx+120, sy+240, "\U0001f99e NetClaw (AS 65001)", 22, "#c92a2a"))
elements.append(text(sx+120, sy+280, "Router-ID: 10.0.99.1", 16))
elements.append(text(sx+120, sy+320, "OSPFv2 Speaker (RFC 2328)", 16, "#2f9e44"))
elements.append(text(sx+140, sy+345, "\u2022 FULL adjacency with P2\n\u2022 Learns complete LSDB\n\u2022 Discovers all router-IDs", 14))
elements.append(text(sx+120, sy+420, "BGP Speaker (RFC 4271)", 16, "#862e9c"))
elements.append(text(sx+140, sy+445, "\u2022 eBGP to RR1 loopback\n\u2022 Injects / withdraws routes\n\u2022 Queries remote RIB\n\u2022 Manipulates path attributes", 14))

# veth link
elements.append({
    "type": "line", "id": nid(),
    "x": sx+480, "y": sy+400,
    "width": 120, "height": 0,
    "points": [[0,0],[120,0]],
    "strokeColor": "#c92a2a", "strokeWidth": 3,
    "strokeStyle": "dashed"
})
elements.append(text(sx+490, sy+410, "veth pair\n10.0.99.1/30", 12, "#c92a2a", "center", w=100))

# SP core mini topology
elements.append(rect(sx+600, sy+220, 700, 350, "#868e96", "#f8f9fa", 1))
elements.append(text(sx+850, sy+230, "SP Core \u2014 AS 65000", 18, "#495057", "center", w=200))

mini_nodes = [
    ("P2", sx+620, sy+370), ("P1", sx+780, sy+370),
    ("RR1", sx+940, sy+370), ("PE1", sx+1100, sy+370),
    ("P4", sx+620, sy+480), ("P3", sx+780, sy+480),
]
for name, nx, ny in mini_nodes:
    bg = "#ffec99" if name == "RR1" else "#b2f2bb" if name.startswith("P") else "#a5d8ff"
    elements.append(rect(nx, ny, 100, 50, "#495057", bg))
    elements.append(text(nx+10, ny+15, name, 16, "#1e1e1e", "center", w=80))

# BGP dashed line
elements.append({
    "type": "line", "id": nid(),
    "x": sx+280, "y": sy+220,
    "width": 700, "height": 0,
    "points": [[0,170],[700,170]],
    "strokeColor": "#862e9c", "strokeWidth": 2,
    "strokeStyle": "dashed"
})
elements.append(text(sx+550, sy+180, "eBGP session (AS 65001 \u2194 65000)", 14, "#862e9c", "center", w=300))

# Use cases
elements.append(text(sx+100, sy+630, "What This Enables:", 22, "#1e1e1e"))
cases = [
    ("\U0001f504 Convergence Testing", "Inject/withdraw, measure reconvergence"),
    ("\U0001f9ea What-If Analysis", "Advertise with different attrs, watch traffic shift"),
    ("\U0001f310 Cross-Domain Peering", "Two NetClaws peer over ngrok (IXP model)"),
    ("\U0001f6a8 Incident Simulation", "Flap a prefix, measure blast radius"),
]
for i, (title, desc) in enumerate(cases):
    cx = sx + 100 + i * 430
    elements.append(rect(cx, sy+670, 400, 80, "#1971c2", "#e7f5ff"))
    elements.append(text(cx+15, sy+680, title, 16, "#1971c2"))
    elements.append(text(cx+15, sy+710, desc, 13, "#495057"))

elements.append(text(sx+500, sy+800, "The agent doesn't just READ the routing table \u2014 it CONTRIBUTES to it.", 20, "#c92a2a", "center", w=900))

# --- SCENE 7: MCP Ecosystem ---
sx = (FRAME_W + GAP) * 6
elements.append(frame(sx, sy, "Scene 7 — MCP Ecosystem"))
elements.append(text(sx+100, sy+60, "MCP: Universal Tool Interface", 48, "#1e1e1e"))
elements.append(text(sx+100, sy+120, "Model Context Protocol \u2014 one spec, 66 integrations, infinite composability", 20, "#868e96"))

# Center agent
elements.append({
    "type": "ellipse", "id": nid(),
    "x": sx+810, "y": sy+380,
    "width": 300, "height": 300,
    "strokeColor": "#c92a2a",
    "backgroundColor": "#fff5f5",
    "fillStyle": "solid", "strokeWidth": 3
})
elements.append(text(sx+880, sy+490, "\U0001f99e NetClaw\n66 MCP Servers", 20, "#c92a2a", "center", w=160))

# Satellite categories
cats = [
    (sx+100, sy+200, "\U0001f5a7 Device Automation", "pyATS \u2022 gNMI \u2022 JunOS\nArista \u2022 F5 \u2022 NSO", "#2f9e44", "#b2f2bb"),
    (sx+100, sy+380, "\U0001f4cb Source of Truth", "Nautobot \u2022 NetBox\nInfrahub \u2022 Infoblox", "#1971c2", "#a5d8ff"),
    (sx+100, sy+560, "\U0001f3ab ITSM & DevOps", "ServiceNow \u2022 Jira \u2022 GitHub\nGitLab \u2022 Jenkins", "#e8590c", "#ffec99"),
    (sx+100, sy+740, "\U0001f4ca Observability", "Grafana \u2022 Prometheus \u2022 Splunk\nDatadog \u2022 Kubeshark", "#862e9c", "#e5dbff"),
    (sx+1400, sy+200, "\U0001f512 Security", "Check Point (15 MCPs)\nFMC \u2022 Panorama \u2022 Zscaler\nCloudflare \u2022 FortiMgr", "#c92a2a", "#ffc9c9"),
    (sx+1400, sy+380, "\u2601\ufe0f Cloud & SD-WAN", "AWS (27 tools) \u2022 Azure\nGCP \u2022 Meraki \u2022 Prisma\nCisco SD-WAN", "#1971c2", "#d0ebff"),
    (sx+1400, sy+560, "\U0001f9ea Lab & Simulation", "Cisco CML \u2022 ContainerLab\nGNS3 \u2022 EVE-NG \u2022 Batfish", "#2f9e44", "#ebfbee"),
    (sx+1400, sy+740, "\U0001f4d0 Visualization", "Draw.io \u2022 Markmap \u2022 Kroki\nCanvas A2UI \u2022 Blender 3D", "#495057", "#e9ecef"),
]
for cx, cy, title, desc, sc, bg in cats:
    elements.append(rect(cx, cy, 320, 100, sc, bg))
    elements.append(text(cx+15, cy+10, title, 16, sc))
    elements.append(text(cx+15, cy+40, desc, 13, "#495057"))

# Bottom analogy
elements.append(rect(sx+300, sy+900, 1300, 80, "#e8590c", "#fff4e6"))
elements.append(text(sx+350, sy+915, "Think of MCP like USB for AI: one standard \u2192 any tool plugs in \u2192 agent uses it immediately", 20, "#e8590c", "center", w=1200))
elements.append(text(sx+350, sy+950, "Add a new MCP server \u2192 zero code changes to the agent \u2192 new capability unlocked", 16, "#495057", "center", w=1200))

# --- SCENE 8: Safety & Audit ---
sx = (FRAME_W + GAP) * 7
elements.append(frame(sx, sy, "Scene 8 — Safety and Audit"))
elements.append(text(sx+100, sy+60, "Trust Through Constraints", 48, "#1e1e1e"))
elements.append(text(sx+100, sy+120, "How NetClaw earns production access", 20, "#868e96"))

# Safety rules
rules = [
    "Never guess device state \u2014 always run a show command first",
    "Never apply config without a pre-change baseline",
    "Never run destructive commands (write erase, reload, format)",
    "Never skip the Change Request \u2014 ServiceNow CR must be Approved",
    "Always verify after changes \u2014 if verification fails, escalate",
    "Always commit to GAIT \u2014 immutable audit trail every session",
]
elements.append(rect(sx+80, sy+180, 800, 380, "#c92a2a", "#fff5f5"))
elements.append(text(sx+100, sy+195, "Non-Negotiable Safety Rules", 22, "#c92a2a"))
for i, rule in enumerate(rules):
    elements.append(text(sx+120, sy+240 + i*50, f"\u2716 {rule}", 16))

# GAIT
elements.append(rect(sx+950, sy+180, 700, 200, "#495057", "#dee2e6"))
elements.append(text(sx+970, sy+195, "GAIT \u2014 Git-based AI Tracking", 22, "#495057"))
elements.append(text(sx+970, sy+240, "Every session records:\n\u2022 What was asked\n\u2022 What data was collected (and from where)\n\u2022 What was changed (and on what device)\n\u2022 What the verification result was\n\u2022 What tickets were created\n\n\u2192 \"What did the AI do and why?\" always has an answer", 15))

# DefenseClaw
elements.append(rect(sx+950, sy+420, 700, 200, "#862e9c", "#f8f0fc"))
elements.append(text(sx+970, sy+435, "DefenseClaw \u2014 Enterprise Security (Optional)", 20, "#862e9c"))
elements.append(text(sx+970, sy+475, "Ring 1: NVIDIA OpenShell (container isolation)\nRing 2: Cisco DefenseClaw (runtime guardrails)\nRing 3: NetClaw agent (constrained by both)\n\nLLM inspection \u2022 Tool call filtering \u2022 SIEM export\nSecret exfiltration prevention \u2022 Audit logging", 14))

# Bottom
elements.append(rect(sx+80, sy+680, 1560, 100, "#2f9e44", "#ebfbee"))
elements.append(text(sx+120, sy+700, "Production-Grade AI Automation = Capability + Constraints + Auditability", 24, "#2f9e44"))
elements.append(text(sx+120, sy+740, "The agent CAN do powerful things. The safety model ensures it does them CORRECTLY.", 16, "#495057"))

# --- SCENE 9: Closing / Links ---
sx = (FRAME_W + GAP) * 8
elements.append(frame(sx, sy, "Scene 9 — Get Started"))
elements.append(text(sx+460, sy+150, "Get Started", 64, "#1e1e1e", "center", w=1000))

elements.append(rect(sx+360, sy+280, 1200, 200, "#1971c2", "#e7f5ff"))
elements.append(text(sx+380, sy+300, "git clone https://github.com/automateyournetwork/netclaw.git", 20, "#1e1e1e", "left", 3))
elements.append(text(sx+380, sy+340, "cd netclaw && ./scripts/install.sh", 20, "#1e1e1e", "left", 3))
elements.append(text(sx+380, sy+400, "That's it. 163 skills, 66 MCP integrations, setup wizard.", 18, "#495057"))
elements.append(text(sx+380, sy+430, "Works with Anthropic Claude, OpenAI, AWS Bedrock, 30+ LLM providers.", 18, "#495057"))

elements.append(text(sx+360, sy+550, "Links", 28, "#1e1e1e"))
elements.append(text(sx+360, sy+600, "NetClaw:       github.com/automateyournetwork/netclaw", 18, "#1971c2", "left", 3))
elements.append(text(sx+360, sy+635, "OpenClaw:      github.com/openclaw/openclaw", 18, "#1971c2", "left", 3))
elements.append(text(sx+360, sy+670, "MCP Spec:      modelcontextprotocol.io", 18, "#1971c2", "left", 3))
elements.append(text(sx+360, sy+705, "ContainerLab:  containerlab.dev", 18, "#1971c2", "left", 3))
elements.append(text(sx+360, sy+740, "NetGru Blog:   blogs.cisco.com/tag/netgru", 18, "#1971c2", "left", 3))
elements.append(text(sx+360, sy+775, "NetGru Live:   youtube.com/playlist?list=PL2k86RlAekM-Vv4pLLFYsQ6Re9BBIj4dt", 18, "#1971c2", "left", 3))

elements.append(text(sx+460, sy+880, "NetClaw \u2014 Reach. Grab. Execute. \U0001f99e", 36, "#c92a2a", "center", w=1000))

# --- Write the file ---
doc = {
    "type": "excalidraw",
    "version": 2,
    "source": "netclaw-demo",
    "elements": elements,
    "appState": {
        "viewBackgroundColor": "#ffffff",
        "gridSize": 20
    }
}

with open("/home/ubuntu/netclaw-demo/docs/diagrams/05-demo-presentation-scenes.excalidraw", "w") as f:
    json.dump(doc, f, indent=2)

print(f"Generated {len(elements)} elements across 9 scenes/frames")
print("Frames (slides):")
for el in elements:
    if el.get("type") == "frame":
        print(f"  - {el['name']}")
