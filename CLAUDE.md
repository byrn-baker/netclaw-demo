# netclaw Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-26

## Active Technologies
- N/A (stateless server; subscription state held in-memory during runtime) (003-gnmi-mcp-server)
- Python 3.10+ + FastMCP (MCP framework), azure-mgmt-network, azure-mgmt-resource, azure-identity (DefaultAzureCredential), gait_mcp (audit logging) (004-azure-network-mcp)
- N/A (stateless; reads from Azure ARM APIs) (004-azure-network-mcp)
- JavaScript (ES2022) / HTML5 / CSS3 for Canvas components; SKILL.md for skill definition + OpenClaw Canvas/A2UI framework (rendering primitives), existing MCP servers (data sources) (005-canvas-a2ui-integration)
- N/A (stateless visualization — all data fetched on demand from MCP servers) (005-canvas-a2ui-integration)
- Python 3.10+ + FastMCP (mcp SDK), httpx (async HTTP client), python-dotenv (001-suzieq-mcp-server)
- N/A (stateless proxy to SuzieQ REST API) (001-suzieq-mcp-server)
- Python 3.10+ + anthropic (SDK with count_tokens), toon-format (TOON serialization), FastMCP (existing MCP framework) (006-token-optimization)
- N/A (in-memory session ledger; no persistent storage) (006-token-optimization)

- Python 3.10+ + FastMCP (MCP framework), grpcio + grpcio-tools (gRPC transport), pygnmi (gNMI client library), protobuf, cryptography (TLS handling) (003-gnmi-mcp-server)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.10+: Follow standard conventions

## Recent Changes
- 006-token-optimization: Added Python 3.10+ + anthropic (SDK with count_tokens), toon-format (TOON serialization), FastMCP (existing MCP framework)
- 001-suzieq-mcp-server: Added Python 3.10+ + FastMCP (mcp SDK), httpx (async HTTP client), python-dotenv
- 005-canvas-a2ui-integration: Added JavaScript (ES2022) / HTML5 / CSS3 for Canvas components; SKILL.md for skill definition + OpenClaw Canvas/A2UI framework (rendering primitives), existing MCP servers (data sources)


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
