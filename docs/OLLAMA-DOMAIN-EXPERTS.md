# Ollama Domain Expert Delegation

## What This Is

A system that lets NetClaw's orchestrating LLM (the "Frontier model" — Claude, DeepSeek, Qwen, etc.) delegate domain-specific tasks to local Ollama models running on your own GPU hardware. Instead of one model doing everything, you get purpose-built specialists that handle the hard parts while the Frontier model focuses on orchestration, user interaction, and validation.

## Why We Built This

### The Problem

Running the NetClaw SP core demo with a single LLM (regardless of size or provider) consistently hits these failure modes:

| # | Failure Mode | Root Cause |
|---|-------------|------------|
| 1 | **Wrong GraphQL queries** | Models guess at Nautobot's BGP Models plugin hierarchy, write invalid field names |
| 2 | **BGP extra_attributes on wrong object** | Models put `route-reflector-client` on PeerEndpoint instead of PeerGroupAddressFamily |
| 3 | **JSON-in-JSON encoding** | `nautobot_run_job(data='{"deployment_name": "Netclaw Demo"}')` confuses models |
| 4 | **Config generation from data** | Translating GraphQL → FRR vtysh requires understanding two schemas simultaneously |
| 5 | **Context overflow on multi-device** | 6 devices × query + config = context balloons, model forgets earlier results |
| 6 | **Network statement hallucination** | Models add `network <loopback>/32` under BGP (wrong — OSPF handles loopbacks) |
| 7 | **Tool selection confusion** | With 40+ MCP tools, models grab wrong tools |

### The Solution

Offload domain-specific tasks to local models with **the rules baked into their system prompts**. The Frontier model stays small/fast for orchestration while domain experts handle the "hard thinking":

```
User: "Push configs to all devices"

Frontier Model (orchestrator):
  1. Calls nautobot_graphql() → gets SOT data
  2. Delegates to ollama_generate_config(domain="frr") → local expert generates vtysh
  3. Delegates to ollama_validate_config_against_sot() → Nautobot expert validates
  4. If valid → push via docker exec
  5. Validate OSPF/BGP convergence
```

### The Benefits

- **Token savings**: 60-80% reduction in Frontier model tokens for config generation tasks
- **Accuracy**: Domain experts have specific rules that prevent known failure modes
- **Speed**: Local GPU inference is free and runs in parallel with Frontier thinking
- **Reliability**: Rules are in the system prompt, not in the Frontier's working memory (which overflows)
- **Cost**: Your local GPU cycles cost nothing vs. cloud API tokens
- **Privacy**: Network topology data stays on your hardware

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│ Frontier Model (Claude / DeepSeek / Qwen)           │
│ Role: Orchestration, user interaction, validation   │
└──────────┬──────────────────────────────────────────┘
           │ MCP tool calls
           ▼
┌─────────────────────────────────────────────────────┐
│ ollama-experts MCP Server (Python, stdio)            │
│ Routes requests by domain tag to local models       │
└──────────┬──────────────────────────────────────────┘
           │ HTTP API calls to Ollama
           ▼
┌─────────────────────────────────────────────────────┐
│ Ollama Instance (your-ollama-host:11434)               │
│                                                     │
│  ┌─────────────────┐  ┌─────────────────┐          │
│  │ netclaw-frr-    │  │ netclaw-        │          │
│  │ codegen (32B)   │  │ nautobot (32B)  │          │
│  └─────────────────┘  └─────────────────┘          │
│  ┌─────────────────┐  ┌─────────────────┐          │
│  │ netclaw-bgp     │  │ netclaw-ospf    │          │
│  │ (16B)           │  │ (16B)           │          │
│  └─────────────────┘  └─────────────────┘          │
│  ┌─────────────────┐                               │
│  │ netclaw-rfc-    │                               │
│  │ design (16B)    │                               │
│  └─────────────────┘                               │
└─────────────────────────────────────────────────────┘
```

## Domain Experts

| Domain | Model | Base | Purpose |
|--------|-------|------|---------|
| `frr` | netclaw-frr-codegen | qwen2.5-coder:32b Q8 | Generates complete vtysh push commands from Nautobot data |
| `nautobot` | netclaw-nautobot | qwen2.5-coder:32b Q8 | GraphQL queries, intent interpretation, config validation |
| `bgp` | netclaw-bgp | deepseek-coder-v2:16b | BGP design, path selection, extra_attributes placement |
| `ospf` | netclaw-ospf | deepseek-coder-v2:16b | OSPF area design, interface-level config |
| `rfc` | netclaw-rfc-design | deepseek-coder-v2:16b | RFC compliance validation |

## MCP Tools Exposed

| Tool | Purpose |
|------|---------|
| `ollama_generate_config` | Delegate config generation to a domain expert |
| `ollama_validate_design` | Validate a network design against RFCs |
| `ollama_domain_query` | Ask a domain expert a technical question |
| `ollama_validate_config_against_sot` | Validate generated config matches Nautobot SOT intent |
| `ollama_list_experts` | List configured domain experts and their status |
| `ollama_health_check` | Verify Ollama connectivity and model availability |
| `ollama_delegation_stats` | Show token savings and delegation metrics |

---

## Setup Guide

### Prerequisites

- Ollama installed on a machine with GPU (your AI host)
- Python 3.11+ on the machine running NetClaw
- Network connectivity between NetClaw and Ollama host

### Step 1: Pull the Base Model

On your Ollama host:

```bash
# For the FRR and Nautobot experts (strongest accuracy)
ollama pull qwen2.5-coder:32b-instruct-q8_0

# For BGP/OSPF/RFC experts (faster, still good)
ollama pull deepseek-coder-v2:16b
```

### Step 2: Create Domain Expert Models

Copy the Modelfiles from `mcp-servers/ollama-experts/modelfiles/` to your Ollama host, then:

```bash
ollama create netclaw-frr-codegen -f Modelfile.frr-codegen
ollama create netclaw-nautobot -f Modelfile.nautobot
ollama create netclaw-bgp -f Modelfile.bgp
ollama create netclaw-ospf -f Modelfile.ospf
ollama create netclaw-rfc-design -f Modelfile.rfc-design
```

Verify:
```bash
ollama list | grep netclaw
```

### Step 3: Configure Environment

Add to your `.env`:

```bash
OLLAMA_BASE_URL=http://<your-ollama-host>:11434
OLLAMA_MODEL_FRR=netclaw-frr-codegen:latest
OLLAMA_MODEL_NAUTOBOT=netclaw-nautobot:latest
OLLAMA_MODEL_BGP=netclaw-bgp:latest
OLLAMA_MODEL_OSPF=netclaw-ospf:latest
OLLAMA_MODEL_RFC=netclaw-rfc-design:latest
OLLAMA_MODEL_GENERAL=qwen2.5-coder:32b-instruct-q8_0
OLLAMA_MODEL_FALLBACK=qwen2.5-coder:32b-instruct-q8_0
```

### Step 4: Install MCP Server Dependencies

```bash
cd mcp-servers/ollama-experts/
pip install -r requirements.txt
```

The MCP server is already registered in `config/openclaw-demo.json`.

---

## How to Create Your Own Domain Expert Models

### Understanding Ollama Modelfiles

A Modelfile is a text file that defines a custom model by layering a system prompt and parameters on top of a base model. No training required — just prompt engineering.

```
FROM <base-model>              ← Which model to start from
PARAMETER temperature 0.1      ← How creative (low = deterministic)
PARAMETER num_predict 4096     ← Max output tokens
SYSTEM """<your rules>"""      ← The domain expertise
```

### Level 1: System Prompt Engineering (5 minutes, no ML knowledge)

This is what we did for all 5 netclaw experts. You write a detailed system prompt that encodes:

1. **What the model is** — "You are an OSPF expert..."
2. **Output format** — "Output ONLY valid FRR vtysh commands. No markdown."
3. **Explicit rules** — "NEVER add network statements under BGP"
4. **Worked examples** — Show the exact input → output format
5. **Common mistakes** — "Do NOT put route-reflector-client on PeerEndpoint"

**Tips for effective system prompts:**

- Lower temperature (0.1) = more deterministic output for config generation
- Include complete worked examples — models follow patterns they've seen
- State constraints as hard rules with ❌ (models respect strong negatives)
- Be specific about output format — "no markdown fences, no explanation"
- Include the actual data model/schema the model needs to work with

### Level 2: RAG-Augmented Prompts (1-2 hours)

Instead of cramming everything into the system prompt, dynamically inject relevant context (RFC sections, config examples) based on the specific task. The MCP server can select relevant chunks before calling Ollama.

### Level 3: QLoRA Fine-Tuning (4-8 hours, requires GPU)

Full fine-tuning for maximum accuracy. See `mcp-servers/ollama-experts/training/README.md` for the complete pipeline:

1. Curate training data (50-200 examples per domain)
2. Train with Unsloth/QLoRA (4-bit quantized, single GPU)
3. Export to GGUF format
4. Import to Ollama via Modelfile

### Adding a New Domain Expert

1. Create `mcp-servers/ollama-experts/modelfiles/Modelfile.<domain>`
2. Run `ollama create netclaw-<domain> -f Modelfile.<domain>`
3. Add `OLLAMA_MODEL_<DOMAIN>=netclaw-<domain>:latest` to your env
4. The router picks it up automatically — no code changes needed

---

## Using Ollama Cloud Models (deepseek-v4-flash:cloud)

Yes, this works. Ollama supports cloud-proxied models via their registry. When you set a domain expert to use a cloud model like `deepseek-v4-flash:cloud`, the MCP server sends the request through Ollama's API which proxies to the cloud endpoint.

**How it works with NetClaw:**

```bash
# You can mix local and cloud models
OLLAMA_MODEL_FRR=netclaw-frr-codegen:latest      # Local 32B (fastest, free)
OLLAMA_MODEL_NAUTOBOT=netclaw-nautobot:latest     # Local 32B
OLLAMA_MODEL_GENERAL=deepseek-v4-flash:cloud      # Cloud (for fallback/general)
```

**Tradeoffs:**

| Factor | Local Model (32B) | Cloud via Ollama (deepseek-v4-flash) |
|--------|-------------------|--------------------------------------|
| Cost | Free (your GPU) | Ollama cloud credits or API cost |
| Latency | 5-15s for 32B | 2-5s (smaller model, cloud infra) |
| Custom system prompt | ✅ Baked into Modelfile | ❌ Must be sent per-request |
| Privacy | 100% local | Data goes to cloud |
| Availability | Always (if GPU is on) | Requires internet |
| Quality | Very good for structured tasks | Excellent general reasoning |

**The key difference**: With a local Modelfile, the system prompt is baked in — every call automatically gets the domain rules. With a cloud model, you'd need to send the full system prompt with each request (consuming more tokens and adding latency). The MCP server handles this transparently — it sends the system prompt as context regardless of whether the model is local or cloud.

**Recommendation for the demo**: Use local models for `frr` and `nautobot` (the two that matter most and benefit from baked-in rules). Use `deepseek-v4-flash:cloud` as the `OLLAMA_MODEL_FALLBACK` for anything that doesn't have a dedicated expert.

---

## Validated Test Results

Tested 2026-06-22 against live infrastructure:

| Step | Result |
|------|--------|
| Nautobot GraphQL query (live, localhost:8080) | ✅ All 6 devices, BGP, OSPF data returned |
| FRR expert generates configs (all 6 devices) | ✅ Correct syntax, correct structure |
| RR1 has route-reflector-client under address-family | ✅ |
| Spokes have NO route-reflector-client | ✅ |
| No `network` statements under BGP anywhere | ✅ |
| Config push to ContainerLab (192.168.17.4) | ✅ All 6 devices |
| OSPF FULL adjacencies | ✅ All neighbors FULL |
| BGP 5 Established peers on RR1 | ✅ |

---

## File Layout

```
mcp-servers/ollama-experts/
├── server.py                    # MCP server (7 tools, stdio transport)
├── router.py                    # Domain → model routing via env vars
├── ollama_client.py             # Async Ollama HTTP client
├── models.py                    # Pydantic request/response schemas
├── metrics.py                   # Token savings tracker
├── requirements.txt             # mcp, httpx, pydantic
├── modelfiles/                  # Ollama Modelfiles (your experts)
│   ├── Modelfile.frr-codegen    # FRR config generation (32B, demo-specific)
│   ├── Modelfile.nautobot       # Nautobot SOT intent + validation (32B)
│   ├── Modelfile.bgp            # BGP protocol design (16B)
│   ├── Modelfile.ospf           # OSPF interface config (16B)
│   └── Modelfile.rfc-design     # RFC compliance validation (16B)
└── training/                    # Fine-tuning resources
    ├── README.md                # Progressive learning path guide
    └── datasets/                # Example training data (JSONL)

specs/037-ollama-domain-experts/
├── spec.md                      # Feature specification
├── plan.md                      # Implementation plan
├── research.md                  # Fine-tuning approaches
├── data-model.md                # MCP tool schemas
├── tasks.md                     # Implementation tasks
└── quickstart.md                # 5-minute getting started
```
