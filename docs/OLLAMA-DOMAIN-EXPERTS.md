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
- **Speed**: Local GPU inference at 42+ tok/s, responses in under 15 seconds
- **Reliability**: Rules are in the system prompt, not in the Frontier's working memory (which overflows)
- **Cost**: Your local GPU cycles cost nothing vs. cloud API tokens
- **Privacy**: Network topology data stays on your hardware

---

## How the "Expert Models" Actually Work (No Training Required)

This is the key insight that's easy to misunderstand: **we are NOT training models**. We're not doing LoRA, QLoRA, RLHF, or any weight modification. What we're doing is much simpler.

### The Technique: System Prompt Engineering via Ollama Modelfiles

An Ollama Modelfile is a packaging format that bundles:

1. **A base model** (the actual neural network weights — e.g., `qwen2.5-coder:7b`)
2. **A system prompt** (plain text rules and examples the model always sees)
3. **Generation parameters** (temperature, top_p, max tokens)

When you run `ollama create netclaw-frr-codegen:7b -f Modelfile`, you're creating a new model *tag* that points to the same underlying weights as the base model, but with a custom system prompt permanently attached. Every time you call this model, it automatically receives that system prompt before your input.

```
┌─────────────────────────────────────────────────────┐
│  Modelfile                                          │
├─────────────────────────────────────────────────────┤
│  FROM qwen2.5-coder:7b          ← base weights     │
│  PARAMETER temperature 0.1       ← deterministic    │
│  PARAMETER num_predict 8192      ← max output       │
│  SYSTEM """                                         │
│    You are an FRR config expert...                  │
│    ## RULES:                                        │
│    1. NEVER add network statements under BGP        │
│    2. Always put route-reflector-client inside AF   │
│    ...28 more rules...                              │
│    ## EXAMPLES:                                     │
│    Input: P1 data → Output: docker exec command     │
│    Input: RR1 data → Output: docker exec command    │
│  """                                                │
└─────────────────────────────────────────────────────┘
```

**Think of it like this:** The "expert" is just a generic code model wearing a very detailed costume (the system prompt). The costume tells it exactly what to do, how to format output, what mistakes to avoid, and shows it worked examples. The model's own code-generation ability handles the rest.

### Why This Works So Well for Config Generation

The Frontier model (Claude/DeepSeek) has already done ALL the reasoning:
- Queried Nautobot GraphQL for device data
- Figured out which devices need configs
- Resolved peer relationships and IP addresses
- Determined the correct OSPF areas and BGP topology

By the time the request hits the local expert, it looks like this:

```
Task: Generate FRR vtysh config for device P1
Device: P1 (role: p-router, platform: frr)
Router ID: 10.255.255.2
ASN: 65000
Interfaces:
  - lo, IP: 10.255.255.2/32, area: 0.0.0.0
  - eth1, IP: 10.0.12.1/30, area: 0.0.0.0, point-to-point
Constraints:
  - passive-interface on loopback
  - neighbor 10.255.255.6 remote-as 65000

Generate ONLY the configuration block.
```

All values are provided. No reasoning needed. The expert just translates structured data into FRR vtysh syntax following its rules. That's why even a 7B model nails it — the task is essentially template-filling with conditional logic.

### What Happens Without the System Prompt

If you give the same input to a generic model (even a large one like Nemotron 30B), it produces invalid FRR syntax:
- Wrong command hierarchy (`group IBGP` instead of `neighbor IBGP peer-group`)
- Misplaced directives (`route-reflector-client` outside address-family)
- Hallucinated commands that don't exist in FRR

The system prompt eliminates these errors by:
- Explicitly listing 28 rules with ❌ "NEVER do X" markers
- Providing complete worked examples showing exact output format
- Setting temperature to 0.1 (almost deterministic — follows patterns, doesn't improvise)

---

## Model Selection: How We Chose qwen2.5-coder:7b

### The Benchmarking Process (June 2026)

We tested progressively smaller models on the same prompts to find the minimum viable size that still produces correct FRR output:

| Model | Size | Eval Rate | Config Correct? | Notes |
|-------|------|-----------|----------------|-------|
| `qwen2.5-coder:32b` Q8_0 | 35 GB | 6.22 tok/s | ✅ | Original — too slow, caused orchestration timeouts |
| `qwen2.5-coder:32b` Q4_K_M | 19 GB | 10.38 tok/s | ✅ | 67% faster, same output |
| `qwen2.5-coder:14b` | 9 GB | 21.44 tok/s | ✅ | 3.4x faster, identical output |
| **`qwen2.5-coder:7b`** | **4.7 GB** | **42.49 tok/s** | ✅ | **6.8x faster, identical output** |
| `nemotron-3-nano:30b` | 24 GB | ~35 tok/s | ❌ | Wrong FRR syntax, can't follow the rules |
| `codestral:22b` | 12.5 GB | ~30 tok/s | ❌ | Returns abstract JSON, not vtysh commands |

### Why qwen2.5-coder Works and Others Don't

The `qwen2.5-coder` family was trained heavily on code and DSL-like syntax. FRR's vtysh grammar is essentially a DSL, so even the 7B model "understands" the structure — it just needs the system prompt to nail down the specific rules and ordering.

General reasoning models (Nemotron, Gemma) lack this code/DSL pattern recognition in their training data, so no amount of prompt engineering compensates.

### Why Smaller is Better Here

| Factor | 32B Q8 | 7B |
|--------|--------|-----|
| VRAM usage | ~35 GB | ~5 GB |
| Tokens/sec | 6.22 | 42.49 |
| Time per device | ~60s | ~13s |
| 6 devices total | ~6 min | ~80s |
| Orchestration timeout risk | **High** | None |
| VRAM left for other models | Almost none | ~30 GB free |
| Output quality | Correct | Correct (identical) |

The 32B model was **correct but too slow**. The orchestrating Frontier model has a timeout — if the local expert takes over 60s to respond, the orchestration gives up. Moving to 7B eliminated this problem entirely.

### The Critical Insight

For this specific task (structured data → config output with explicit rules), model size barely matters above a threshold. The system prompt is doing the heavy lifting. Going from 32B to 7B didn't degrade quality because:

1. All input values are pre-computed by the orchestrator
2. The output format is rigidly defined with examples
3. Temperature 0.1 means the model follows patterns, doesn't create
4. The rules explicitly block known failure modes

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│ Frontier Model (Claude / DeepSeek)                  │
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
│  All models: qwen2.5-coder:7b base (~5 GB each)    │
│  (Same weights, different system prompts)           │
│                                                     │
│  ┌─────────────────┐  ┌─────────────────┐          │
│  │ netclaw-frr-    │  │ netclaw-        │          │
│  │ codegen:7b      │  │ nautobot:7b     │          │
│  └─────────────────┘  └─────────────────┘          │
│  ┌─────────────────┐  ┌─────────────────┐          │
│  │ netclaw-bgp:7b  │  │ netclaw-ospf:7b │          │
│  └─────────────────┘  └─────────────────┘          │
│  ┌─────────────────┐                               │
│  │ netclaw-rfc-    │                               │
│  │ design:7b       │                               │
│  └─────────────────┘                               │
└─────────────────────────────────────────────────────┘
```

**Key point:** All five "expert" models share the same base weights (`qwen2.5-coder:7b`). Only their system prompts differ. Ollama deduplicates the shared layers on disk, so you're not storing 5 × 5GB — it's approximately 5GB total for the weights plus a few KB per system prompt.

## Domain Experts

| Domain | Model Tag | Base | System Prompt Focus | Speed |
|--------|-----------|------|--------------------| ------|
| `frr` | `netclaw-frr-codegen:7b` | qwen2.5-coder:7b | 28 rules for vtysh generation, topology context, worked examples | 42 tok/s |
| `nautobot` | `netclaw-nautobot:7b` | qwen2.5-coder:7b | GraphQL schema, validation checklist, SOT comparison | 44 tok/s |
| `bgp` | `netclaw-bgp:7b` | qwen2.5-coder:7b | BGP design, path selection, extra_attributes | 43 tok/s |
| `ospf` | `netclaw-ospf:7b` | qwen2.5-coder:7b | OSPF area design, interface config, timer defaults | 43 tok/s |
| `rfc` | `netclaw-rfc-design:7b` | qwen2.5-coder:7b | RFC compliance checking, JSON output format | 43 tok/s |
| `graphql` | `netclaw-graphql-builder:7b` | qwen2.5-coder:7b | Nautobot GraphQL schema, intent-to-query mapping, filter rules | 44 tok/s |
| `state` | `netclaw-state-summarizer:7b` | qwen2.5-coder:7b | FRR show command parsing, health criteria, compact JSON output | 44 tok/s |
| `compress` | `netclaw-context-compressor:7b` | qwen2.5-coder:7b | GraphQL response → minimal config-relevant JSON extraction | 44 tok/s |

## MCP Tools Exposed

| Tool | Purpose |
|------|---------|
| `ollama_generate_config` | Delegate config generation to a domain expert |
| `ollama_validate_design` | Validate a network design against RFCs |
| `ollama_domain_query` | Ask a domain expert a technical question |
| `ollama_validate_config_against_sot` | Validate generated config matches Nautobot SOT intent |
| `ollama_build_graphql_query` | Build valid Nautobot GraphQL queries from natural language intent |
| `ollama_summarize_state` | Compress show command output into pass/fail JSON signals |
| `ollama_compress_sot_data` | Reduce raw GraphQL responses to minimal config-relevant JSON |
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
# Single base model for all experts
ollama pull qwen2.5-coder:7b
```

That's it. One download (~5 GB). All experts share these weights.

### Step 2: Create Domain Expert Models

Each expert is created by applying a Modelfile (system prompt + parameters) to the base model.

**Option A: From the pre-built Modelfiles in this repo:**

```bash
cd mcp-servers/ollama-experts/modelfiles/

ollama create netclaw-frr-codegen:7b -f Modelfile.frr-codegen-7b
ollama create netclaw-nautobot:7b -f Modelfile.nautobot-7b
ollama create netclaw-bgp:7b -f Modelfile.bgp-7b
ollama create netclaw-ospf:7b -f Modelfile.ospf-7b
ollama create netclaw-rfc-design:7b -f Modelfile.rfc-design-7b
```

**Option B: From an existing larger model (re-basing to 7B):**

If you already have a `:latest` tag pointing at a larger base (32B, 16B), you can rebase it to 7B while keeping the same system prompt:

```bash
# Export the Modelfile from the existing model
ollama show netclaw-frr-codegen:latest --modelfile > /tmp/current.Modelfile

# Replace the FROM line with the 7B base
sed 's|^FROM .*|FROM qwen2.5-coder:7b|' /tmp/current.Modelfile > /tmp/new.Modelfile

# Create the 7B version
ollama create netclaw-frr-codegen:7b -f /tmp/new.Modelfile
```

This works because the "expertise" lives entirely in the system prompt text, not in the model weights. Swapping the base model just changes inference speed and VRAM usage.

Verify:
```bash
ollama list | grep netclaw
```

### Step 3: Configure Environment

In `config/openclaw-demo.json` (the demo's MCP config), the `ollama-experts` entry should reference the `:7b` tags:

```json
{
  "ollama-experts": {
    "command": "/home/ubuntu/netclaw/.venv/bin/python3",
    "args": ["-u", "/home/ubuntu/netclaw/mcp-servers/ollama-experts/server.py"],
    "env": {
      "OLLAMA_BASE_URL": "http://your-ollama-host:11434",
      "OLLAMA_TIMEOUT": "60",
      "OLLAMA_MODEL_FRR": "netclaw-frr-codegen:7b",
      "OLLAMA_MODEL_NAUTOBOT": "netclaw-nautobot:7b",
      "OLLAMA_MODEL_BGP": "netclaw-bgp:7b",
      "OLLAMA_MODEL_OSPF": "netclaw-ospf:7b",
      "OLLAMA_MODEL_RFC": "netclaw-rfc-design:7b",
      "OLLAMA_MODEL_GENERAL": "qwen2.5-coder:7b",
      "OLLAMA_MODEL_FALLBACK": "qwen2.5-coder:7b"
    }
  }
}
```

### Step 4: Install MCP Server Dependencies

```bash
cd mcp-servers/ollama-experts/
pip install -r requirements.txt
```

The MCP server is already registered in `config/openclaw-demo.json`.

---

## Creating or Modifying an Expert

### The Process

1. Write a system prompt with rules, examples, and output format
2. Package it as a Modelfile with `FROM qwen2.5-coder:7b`
3. Run `ollama create your-model-name:7b -f your.Modelfile`
4. Test with representative inputs
5. Add the env var to your config

### What Makes a Good Expert System Prompt

The system prompt is the only thing that differentiates one expert from another. A good one includes:

1. **Role statement** — "You are an FRR configuration expert"
2. **Exact task description** — "You receive structured device data and produce a docker exec vtysh command string"
3. **Output format** — "Output ONLY the executable command. No markdown, no explanation"
4. **Hard rules** — "❌ NEVER add network statements under BGP" (models respect strong negatives)
5. **Worked examples** — Complete input → output pairs for every case the model will encounter
6. **Common mistakes** — Explicitly list what NOT to do, because models tend to make the same errors

### Tips

- **Temperature 0.1** — For config generation, you want deterministic output. Keep it low.
- **Worked examples are critical** — The model pattern-matches against examples more than it "reasons" about rules.
- **❌ markers work** — Models trained on instruction data respond to emoji-prefixed negative constraints.
- **Test the hard case first** — If your model handles the most complex input correctly (e.g., RR1 with peer-groups and extra_attributes), simpler cases will be fine.

### Adding a New Domain Expert

1. Create `mcp-servers/ollama-experts/modelfiles/Modelfile.<domain>-7b`
2. Run `ollama create netclaw-<domain>:7b -f Modelfile.<domain>-7b`
3. Add `OLLAMA_MODEL_<DOMAIN>=netclaw-<domain>:7b` to your env
4. The router picks it up automatically — no code changes needed

---

## Upgrading or Downsizing Expert Models

Since expertise lives in the system prompt, you can freely change the base model size:

```bash
# Current: 7B (fast, lightweight)
ollama show netclaw-frr-codegen:7b --modelfile > /tmp/frr.Modelfile

# Want to try 14B? (more capacity for complex cases)
sed 's|^FROM .*|FROM qwen2.5-coder:14b|' /tmp/frr.Modelfile > /tmp/frr-14b.Modelfile
ollama create netclaw-frr-codegen:14b -f /tmp/frr-14b.Modelfile

# Want to try 3B? (even faster, might work for simple cases)
sed 's|^FROM .*|FROM qwen2.5-coder:3b|' /tmp/frr.Modelfile > /tmp/frr-3b.Modelfile
ollama create netclaw-frr-codegen:3b -f /tmp/frr-3b.Modelfile
```

**Rules of thumb:**
- **7B** — sweet spot for structured config generation with detailed system prompts (~42 tok/s)
- **14B** — slightly better for free-form domain questions (~21 tok/s)
- **32B** — overkill for structured tasks, useful if you have complex multi-step reasoning
- **3B** — too small; starts missing rules and hallucinating syntax

---

## Using Ollama Cloud Models (deepseek-v4-flash:cloud)

Ollama supports cloud-proxied models via their registry. You can mix local and cloud models:

```bash
OLLAMA_MODEL_FRR=netclaw-frr-codegen:7b           # Local (fastest, free)
OLLAMA_MODEL_GENERAL=deepseek-v4-flash:cloud       # Cloud (for fallback)
```

**Tradeoffs:**

| Factor | Local 7B | Cloud via Ollama |
|--------|----------|-----------------|
| Cost | Free (your GPU) | API credits |
| Latency | ~13s total | 2-5s (cloud infra) |
| Custom system prompt | ✅ Baked in (always active) | ❌ Must send per-request |
| Privacy | 100% local | Data goes to cloud |
| Availability | Always (if GPU is on) | Requires internet |

---

## Validated Test Results

Tested 2026-06-23 against live infrastructure with 7B models:

| Step | Result |
|------|--------|
| FRR expert generates P1 spoke config | ✅ Correct vtysh syntax (42 tok/s) |
| FRR expert generates RR1 with peer-groups | ✅ route-reflector-client inside address-family |
| Nautobot expert validates config against SOT | ✅ Returns valid JSON in 2.5s |
| RFC expert validates design against RFC 4271/2328 | ✅ Correct "valid: true" with citations (43 tok/s) |
| No `network` statements under BGP anywhere | ✅ |
| Spokes have NO route-reflector-client | ✅ |
| All experts respond under 15s | ✅ |

### Performance Comparison (same prompt, same GPU)

| Model Config | Eval Rate | Total Time | Orchestration Timeout? |
|-------------|-----------|-----------|----------------------|
| 32B Q8_0 (original) | 6.22 tok/s | 78s | ⚠️ Yes — caused failures |
| 32B Q4_K_M | 10.38 tok/s | 48s | Borderline |
| 14B | 21.44 tok/s | 20s | No |
| **7B (current)** | **42.49 tok/s** | **13s** | **No — 4x safety margin** |

---

## File Layout

```
mcp-servers/ollama-experts/
├── server.py                    # MCP server (10 tools, stdio transport)
├── router.py                    # Domain → model routing via env vars
├── ollama_client.py             # Async Ollama HTTP client
├── models.py                    # Pydantic request/response schemas
├── metrics.py                   # Token savings tracker
├── requirements.txt             # mcp, httpx, pydantic
└── modelfiles/                  # Ollama Modelfiles (your experts)
    ├── Modelfile.frr-codegen    # FRR config generation
    ├── Modelfile.nautobot       # Nautobot SOT validation
    ├── Modelfile.bgp            # BGP protocol design
    ├── Modelfile.ospf           # OSPF interface config
    ├── Modelfile.rfc-design     # RFC compliance validation
    ├── Modelfile.graphql-builder    # Nautobot GraphQL query construction
    ├── Modelfile.state-summarizer   # Show command → JSON digest
    └── Modelfile.context-compressor # GraphQL response compression

config/openclaw-demo.json        # MCP server config with env vars pointing to :7b tags
```
