# NetClaw Demo Diagrams

Excalidraw flow diagrams for the NetGru demo presentation.

## Files

| File | Purpose | Use |
|------|---------|-----|
| `01-how-netclaw-works.excalidraw` | Three-layer architecture (SOUL / Skills / MCP / GAIT) | Explaining the agent's structure |
| `02-demo-workflow-pipeline.excalidraw` | SOT → Config Gen → Push → Validate pipeline | The demo's core data flow |
| `03-protocol-participation.excalidraw` | NetClaw joining OSPF/BGP as a live peer | Advanced audience — agent as router |
| `04-mcp-tool-ecosystem.excalidraw` | Hub-and-spoke MCP integration map | Showing the breadth of integrations |
| `05-demo-presentation-scenes.excalidraw` | **Full slide deck** (9 frames/scenes) | Excalidraw+ presentation mode |

## Using the Presentation (05)

The `05-demo-presentation-scenes.excalidraw` file uses Excalidraw's **frame** elements as slides.
Each frame is a 1920x1080 viewport that becomes one slide in presentation mode.

### In Excalidraw+:
1. Open the file in your Excalidraw+ workspace
2. Click the presentation icon (or press `Alt+P`)
3. Navigate between frames with arrow keys
4. Each frame = one slide in the presentation

### Scenes (9 slides):
1. **Title** — NetClaw intro, tagline
2. **The Problem** — Why existing automation falls short
3. **Architecture** — Three-layer agent design (beginners + advanced)
4. **Demo Lab** — 6-node SP core topology
5. **Demo Pipeline** — Phase 1-4 flow with design principles callout
6. **Protocol Participation** — NetClaw as a BGP/OSPF peer (advanced)
7. **MCP Ecosystem** — 66 integrations visualized
8. **Safety & Audit** — Trust through constraints, GAIT, DefenseClaw
9. **Get Started** — Install commands and links

## Opening These Files

- **Excalidraw+** (recommended): Upload to your workspace for collaboration and presentation mode
- **excalidraw.com**: Open any `.excalidraw` file directly in the browser
- **VS Code**: Install the Excalidraw extension for inline preview/edit
- **Obsidian**: Native Excalidraw plugin support

## Regenerating the Presentation

The presentation file is generated from `gen_scenes.py`:

```bash
python3 gen_scenes.py
```

Edit the script to modify slides, then regenerate. The individual diagrams (01-04) are hand-authored.

## Style Guide

- Background: white (`#ffffff`)
- Primary accent: NetClaw red (`#c92a2a`)
- Categories use consistent colors:
  - Blue (`#1971c2`) — SOT, cloud, info
  - Green (`#2f9e44`) — devices, labs, success
  - Orange (`#e8590c`) — ITSM, MCP, warnings
  - Purple (`#862e9c`) — security, observability
  - Gray (`#495057`) — infrastructure, audit
- Font family 1 (hand-drawn) for all text
- Rounded rectangles (`roundness: {type: 3}`) for all boxes
