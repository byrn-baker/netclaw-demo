# NetClaw Demo VM — Token Metrics Observability

Pushes LLM token usage and cost metrics from ephemeral demo VMs to the
centralized Prometheus instance on the OBS VM (your-obs-host).

## Architecture

```
Demo VM (ephemeral, 4hr TTL)              OBS VM (your-obs-host)
┌────────────────────────────┐           ┌──────────────────────┐
│ OpenClaw gateway           │           │                      │
│  └─→ /tmp/openclaw/       │           │  Prometheus          │
│       openclaw-*.log       │           │    ← remote_write    │
│           │                │           │    (port 9090)       │
│           ▼                │           │                      │
│  Vector (file source)      │──push────▶│  Grafana dashboard   │
│    parse JSONL tokens/cost │  :9090    │  "NetClaw Demo —     │
│    prometheus_remote_write │           │   Token Usage & Cost" │
└────────────────────────────┘           └──────────────────────┘
```

## Why Push (Not Pull)

Demo VMs are ephemeral — they spin up for 4 hours then get destroyed.
Prometheus can't scrape an IP that doesn't exist. Push via remote-write
means the VM sends metrics while alive; when it dies, data is already
stored in Prometheus with 400-day retention.

## Files

| File | Purpose |
|------|---------|
| `vector.yaml` | Vector pipeline config — tails OpenClaw JSONL, extracts metrics, remote-writes |
| `install-vector-demo.sh` | Installs Vector + deploys config on the demo VM |
| `grafana-dashboard-netclaw-tokens.json` | Grafana dashboard JSON (import into OBS Grafana) |

## Metrics Exported

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `netclaw_model_input_tokens_total` | counter | model, provider, agent | Cumulative input tokens |
| `netclaw_model_output_tokens_total` | counter | model, provider, agent | Cumulative output tokens |
| `netclaw_model_cache_read_tokens_total` | counter | model, provider | Tokens read from prompt cache |
| `netclaw_model_cache_write_tokens_total` | counter | model, provider | Tokens written to prompt cache |
| `netclaw_model_cost_usd_total` | counter | model, provider, agent | Cumulative cost in USD |
| `netclaw_model_calls_total` | counter | model, provider, agent | Total model API calls |
| `netclaw_model_call_duration_ms` | gauge | model, provider | Last call duration (ms) |

All metrics carry `instance="netclaw-demo"`.

## PromQL Recipes

```promql
# Total tokens used across all demo sessions
sum(netclaw_model_input_tokens_total{instance="netclaw-demo"}) +
sum(netclaw_model_output_tokens_total{instance="netclaw-demo"})

# Cost per hour rate
sum(rate(netclaw_model_cost_usd_total{instance="netclaw-demo"}[5m])) * 3600

# Token rate by provider
sum by (provider) (rate(netclaw_model_input_tokens_total{instance="netclaw-demo"}[5m])) * 60

# Cache hit percentage
sum(netclaw_model_cache_read_tokens_total) /
(sum(netclaw_model_input_tokens_total) + sum(netclaw_model_cache_read_tokens_total)) * 100

# Total cost over last 24h
sum(increase(netclaw_model_cost_usd_total{instance="netclaw-demo"}[24h]))
```

## Setup

### On the Demo VM (automatic via cloud-init)

The `demo-start.sh` script calls `install-vector-demo.sh` after `git pull`.
No manual steps needed — Vector is installed and started automatically.

### On the OBS VM (one-time)

1. **Ensure remote-write receiver is enabled** on Prometheus:
   ```yaml
   # In docker-compose.yml, add to prometheus command:
   --web.enable-remote-write-receiver
   ```

2. **Import the Grafana dashboard:**
   ```bash
   curl -X POST http://admin:admin@your-obs-host:3000/api/dashboards/db \
     -H "Content-Type: application/json" \
     -d "{\"dashboard\": $(cat grafana-dashboard-netclaw-tokens.json), \"overwrite\": true}"
   ```

3. **Restart Prometheus** if you added the remote-write flag:
   ```bash
   ssh ubuntu@your-obs-host "cd ~/observability-stack && docker compose restart prometheus"
   ```

## Prerequisites

- Prometheus on your-obs-host must accept remote-write (`--web.enable-remote-write-receiver`)
- Demo VM must have network access to your-obs-host:9090
- OpenClaw gateway must be logging to `/tmp/openclaw/` (default behavior)

## Log Format Expected

OpenClaw writes one JSON object per line to `/tmp/openclaw/openclaw-YYYY-MM-DD.log`.
Vector filters for entries containing token usage data (model call completions)
and extracts:

- `usage.input_tokens` / `inputTokens`
- `usage.output_tokens` / `outputTokens`
- `usage.cache_read_input_tokens` / `cacheReadInputTokens`
- `usage.cache_creation_input_tokens` / `cacheCreationInputTokens`
- `usage.cost` / `cost`
- `model` (with provider prefix stripped)
- `provider`
- `agent_id` / `agent`
- `durationMs`

The VRL transform handles multiple field-name shapes that OpenClaw uses
across different log contexts.
