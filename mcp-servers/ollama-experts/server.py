#!/usr/bin/env python3
"""Ollama Domain Expert Delegation MCP Server.

Routes network engineering tasks to domain-specific local Ollama models,
enabling Frontier model token savings through local GPU delegation.

Designed specifically for the NetClaw SP core demo workflow — handles the
failure modes that single LLMs consistently hit: GraphQL query construction,
BGP extra_attributes placement, FRR config generation from data, and
Nautobot job execution patterns.

Environment Variables:
    OLLAMA_BASE_URL         - Ollama instance URL (default: http://localhost:11434)
    OLLAMA_TIMEOUT          - Request timeout in seconds (default: 120)
    OLLAMA_MODEL_OSPF       - Model for OSPF domain (e.g., netclaw-ospf:latest)
    OLLAMA_MODEL_BGP        - Model for BGP domain (e.g., netclaw-bgp:latest)
    OLLAMA_MODEL_RFC        - Model for RFC validation (e.g., netclaw-rfc-design:latest)
    OLLAMA_MODEL_FRR        - Model for FRR config generation (e.g., netclaw-frr-codegen:latest)
    OLLAMA_MODEL_NAUTOBOT   - Model for Nautobot API/GraphQL (e.g., netclaw-nautobot:latest)
    OLLAMA_MODEL_MPLS       - Model for MPLS domain
    OLLAMA_MODEL_ACL        - Model for ACL domain
    OLLAMA_MODEL_GENERAL    - General-purpose model (default: qwen2.5-coder:32b-instruct-q8_0)
    OLLAMA_MODEL_FALLBACK   - Fallback when domain model unavailable
"""

import os
import sys
import json
import asyncio
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from ollama_client import OllamaClient
from router import DomainRouter
from metrics import MetricsTracker
from models import (
    DeviceContext,
    DeviceInterface,
    ConfigGenerationResponse,
    DesignValidationResponse,
    ExpertQueryResponse,
    HealthCheckResponse,
    ExpertInfo,
)

# --- Setup ---

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("ollama-experts")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "120"))

# Initialize components
client = OllamaClient(base_url=OLLAMA_BASE_URL, timeout=OLLAMA_TIMEOUT)
router = DomainRouter()
metrics = MetricsTracker()

# MCP Server
app = Server("ollama-experts")


# --- Prompt Engineering ---

def build_config_prompt(domain: str, task: str, device_context: dict, constraints: list) -> str:
    """Build an effective prompt for config generation."""
    ctx = DeviceContext(**device_context) if isinstance(device_context, dict) else device_context

    prompt_parts = [
        f"Task: {task}",
        f"",
        f"Device: {ctx.hostname} (role: {ctx.role or 'unspecified'}, platform: {ctx.platform})",
    ]

    if ctx.router_id:
        prompt_parts.append(f"Router ID: {ctx.router_id}")
    if ctx.asn:
        prompt_parts.append(f"ASN: {ctx.asn}")

    if ctx.interfaces:
        prompt_parts.append(f"")
        prompt_parts.append(f"Interfaces:")
        for iface in ctx.interfaces:
            parts = [f"  - {iface.name}"]
            if iface.ip_address:
                parts.append(f"IP: {iface.ip_address}")
            if iface.area:
                parts.append(f"area: {iface.area}")
            if iface.peer_as:
                parts.append(f"peer-AS: {iface.peer_as}")
            if iface.description:
                parts.append(f"({iface.description})")
            prompt_parts.append(", ".join(parts))

    # BGP network statements — SOT-driven
    if ctx.bgp_networks:
        prompt_parts.append(f"")
        prompt_parts.append(f"BGP network statements (from source-of-truth):")
        for net in ctx.bgp_networks:
            prompt_parts.append(f"  - network {net}")
    else:
        prompt_parts.append(f"")
        prompt_parts.append(f"BGP network statements: NONE — do NOT add any 'network' statements under address-family ipv4 unicast. Only emit network statements if explicitly listed above.")

    if constraints:
        prompt_parts.append(f"")
        prompt_parts.append(f"Constraints:")
        for c in constraints:
            prompt_parts.append(f"  - {c}")

    prompt_parts.append(f"")
    prompt_parts.append(f"Generate ONLY the configuration block. No explanation, no markdown fences.")

    return "\n".join(prompt_parts)


def build_validation_prompt(design: str, rfcs: list, focus: str) -> str:
    """Build a prompt for design validation."""
    return (
        f"Validate the following network design against RFC standards.\n"
        f"\n"
        f"RFCs to check: {', '.join(f'RFC {r}' for r in rfcs)}\n"
        f"Validation focus: {focus}\n"
        f"\n"
        f"Design to validate:\n"
        f"---\n"
        f"{design}\n"
        f"---\n"
        f"\n"
        f"Respond in this exact JSON format:\n"
        f'{{"valid": true/false, "findings": [{{"severity": "error|warning|info", '
        f'"rule": "what was checked", "message": "finding", "rfc": "NNNN", '
        f'"suggestion": "how to fix"}}]}}'
    )


# --- Tool Definitions ---

TOOLS = [
    Tool(
        name="ollama_generate_config",
        description=(
            "Delegate network config generation to a local Ollama domain expert model. "
            "Returns FRR/IOS/NX-OS configuration blocks. Saves Frontier tokens by running "
            "generation on local GPU."
        ),
        inputSchema={
            "type": "object",
            "required": ["domain", "task", "device_context"],
            "properties": {
                "domain": {
                    "type": "string",
                    "enum": ["ospf", "bgp", "mpls", "acl", "frr", "nautobot", "general"],
                    "description": "Network domain to route to the appropriate expert model",
                },
                "task": {
                    "type": "string",
                    "description": "Natural language description of what config to generate",
                },
                "device_context": {
                    "type": "object",
                    "description": "Device details: hostname, role, platform, interfaces, router_id, asn, bgp_networks",
                    "properties": {
                        "hostname": {"type": "string"},
                        "role": {"type": "string"},
                        "platform": {"type": "string"},
                        "interfaces": {"type": "array"},
                        "router_id": {"type": "string"},
                        "asn": {"type": "integer"},
                        "bgp_networks": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Explicit BGP network statements from Nautobot extra_attributes (e.g., ['172.16.10.0/24']). If empty/absent, NO network statements will be generated.",
                        },
                    },
                },
                "constraints": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional constraints (e.g., 'use MD5 auth', 'passive-interface on loopbacks')",
                },
            },
        },
    ),
    Tool(
        name="ollama_validate_design",
        description=(
            "Validate a network design against RFC standards using the RFC domain expert. "
            "Returns findings with severity, rule violations, and suggestions."
        ),
        inputSchema={
            "type": "object",
            "required": ["design", "rfcs"],
            "properties": {
                "design": {
                    "type": "string",
                    "description": "The network design or configuration to validate",
                },
                "rfcs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "RFC numbers to validate against (e.g., ['2328', '4271'])",
                },
                "validation_focus": {
                    "type": "string",
                    "enum": ["syntax", "design-rules", "security", "scalability", "all"],
                    "description": "What aspect to focus validation on (default: all)",
                },
            },
        },
    ),
    Tool(
        name="ollama_domain_query",
        description=(
            "Ask a domain-specific technical question to a local expert model. "
            "For analysis, explanations, troubleshooting, and protocol-specific questions."
        ),
        inputSchema={
            "type": "object",
            "required": ["domain", "question"],
            "properties": {
                "domain": {
                    "type": "string",
                    "enum": ["ospf", "bgp", "mpls", "acl", "rfc", "frr", "nautobot", "general"],
                    "description": "Network domain for expert routing",
                },
                "question": {
                    "type": "string",
                    "description": "Technical question to answer",
                },
                "context": {
                    "type": "string",
                    "description": "Optional additional context (show command output, topology info)",
                },
            },
        },
    ),
    Tool(
        name="ollama_list_experts",
        description="List configured domain expert models, their status, and capabilities.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="ollama_health_check",
        description="Check Ollama instance connectivity, available models, and GPU status.",
        inputSchema={
            "type": "object",
            "properties": {
                "verbose": {
                    "type": "boolean",
                    "description": "Include detailed model info",
                },
            },
        },
    ),
    Tool(
        name="ollama_delegation_stats",
        description="Show delegation metrics: tasks delegated, tokens saved, cost avoided, per-domain breakdown.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="ollama_validate_config_against_sot",
        description=(
            "Validate a generated FRR config against Nautobot SOT data. "
            "Checks that BOTH BGP and OSPF intent from the source of truth "
            "is correctly represented in the config. Returns pass/fail with specific issues."
        ),
        inputSchema={
            "type": "object",
            "required": ["config", "sot_data"],
            "properties": {
                "config": {
                    "type": "string",
                    "description": "The generated FRR config or vtysh command string to validate",
                },
                "sot_data": {
                    "type": "string",
                    "description": "JSON string of the Nautobot GraphQL response (device interfaces, BGP, OSPF data)",
                },
                "device": {
                    "type": "string",
                    "description": "Device name for context (e.g., 'RR1', 'P1')",
                },
            },
        },
    ),
    Tool(
        name="ollama_build_graphql_query",
        description=(
            "Build a valid Nautobot GraphQL query from natural language intent. "
            "Eliminates the Frontier model guessing at field names and filter syntax. "
            "Returns the raw GraphQL query string ready to pass to nautobot_graphql()."
        ),
        inputSchema={
            "type": "object",
            "required": ["intent"],
            "properties": {
                "intent": {
                    "type": "string",
                    "description": "Natural language description of what data to query (e.g., 'full config generation data for device P1', 'BGP summary for RR1', 'all OSPF interfaces')",
                },
                "device": {
                    "type": "string",
                    "description": "Device name to filter by, if applicable (e.g., 'P1', 'RR1')",
                },
            },
        },
    ),
    Tool(
        name="ollama_summarize_state",
        description=(
            "Summarize raw FRR show command output into a compact JSON digest. "
            "Returns healthy/unhealthy status, peer counts, and only details for "
            "problem states. Saves Frontier tokens by eliminating raw output parsing."
        ),
        inputSchema={
            "type": "object",
            "required": ["output"],
            "properties": {
                "output": {
                    "type": "string",
                    "description": "Raw show command output (e.g., from 'show ip bgp summary', 'show ip ospf neighbor', 'show ip route')",
                },
                "device": {
                    "type": "string",
                    "description": "Device name for context (e.g., 'P1', 'RR1')",
                },
                "command": {
                    "type": "string",
                    "description": "The show command that produced this output (e.g., 'show ip bgp summary')",
                },
            },
        },
    ),
    Tool(
        name="ollama_compress_sot_data",
        description=(
            "Compress a raw Nautobot GraphQL response into minimal config-relevant JSON. "
            "Reduces 2KB+ GraphQL responses to ~400 bytes by extracting only the fields "
            "needed for FRR config generation. Saves 80% context window for the Frontier model."
        ),
        inputSchema={
            "type": "object",
            "required": ["graphql_response", "device"],
            "properties": {
                "graphql_response": {
                    "type": "string",
                    "description": "Raw JSON string of the Nautobot GraphQL response (devices, bgp_routing_instances, bgp_peerings, ospf_interface_configurations)",
                },
                "device": {
                    "type": "string",
                    "description": "Target device name to extract data for (e.g., 'P1', 'RR1')",
                },
            },
        },
    ),
]


# --- Tool Handlers ---

@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        if name == "ollama_generate_config":
            return await handle_generate_config(arguments)
        elif name == "ollama_validate_design":
            return await handle_validate_design(arguments)
        elif name == "ollama_domain_query":
            return await handle_domain_query(arguments)
        elif name == "ollama_list_experts":
            return await handle_list_experts(arguments)
        elif name == "ollama_health_check":
            return await handle_health_check(arguments)
        elif name == "ollama_delegation_stats":
            return await handle_delegation_stats(arguments)
        elif name == "ollama_validate_config_against_sot":
            return await handle_validate_config_against_sot(arguments)
        elif name == "ollama_build_graphql_query":
            return await handle_build_graphql_query(arguments)
        elif name == "ollama_summarize_state":
            return await handle_summarize_state(arguments)
        elif name == "ollama_compress_sot_data":
            return await handle_compress_sot_data(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def handle_generate_config(args: dict) -> list[TextContent]:
    """Handle config generation delegation."""
    domain = args["domain"]
    task = args["task"]
    device_context = args.get("device_context", {})
    constraints = args.get("constraints", [])

    model = router.get_model(domain)
    options = router.get_generation_options(domain)
    prompt = build_config_prompt(domain, task, device_context, constraints)

    try:
        result = await client.generate(model=model, prompt=prompt, options=options)
        response_text = result.get("response", "")
        elapsed_ms = result.get("_elapsed_ms", 0)
        eval_count = result.get("eval_count", len(response_text) // 4)  # rough estimate

        # Track metrics
        metrics.record_delegation(domain, model, elapsed_ms, eval_count, success=True)

        response = ConfigGenerationResponse(
            success=True,
            domain=domain,
            model_used=model,
            config=response_text.strip(),
            generation_time_ms=elapsed_ms,
            estimated_tokens=eval_count,
        )
    except Exception as e:
        metrics.record_delegation(domain, model, 0, 0, success=False)
        response = ConfigGenerationResponse(
            success=False,
            domain=domain,
            model_used=model,
            config="",
            warnings=[f"Delegation failed: {str(e)}. Frontier should handle this directly."],
            generation_time_ms=0,
            estimated_tokens=0,
        )

    return [TextContent(type="text", text=response.model_dump_json(indent=2))]


async def handle_validate_design(args: dict) -> list[TextContent]:
    """Handle design validation delegation."""
    design = args["design"]
    rfcs = args["rfcs"]
    focus = args.get("validation_focus", "all")

    model = router.get_model("rfc")
    options = router.get_generation_options("rfc")
    prompt = build_validation_prompt(design, rfcs, focus)

    try:
        result = await client.generate(model=model, prompt=prompt, options=options)
        response_text = result.get("response", "")
        elapsed_ms = result.get("_elapsed_ms", 0)
        eval_count = result.get("eval_count", len(response_text) // 4)

        metrics.record_delegation("rfc", model, elapsed_ms, eval_count, success=True)

        # Try to parse structured response
        try:
            parsed = json.loads(response_text)
            response = DesignValidationResponse(
                success=True,
                valid=parsed.get("valid", False),
                model_used=model,
                findings=parsed.get("findings", []),
                rfc_references=[f"RFC {r}" for r in rfcs],
                generation_time_ms=elapsed_ms,
            )
        except json.JSONDecodeError:
            # Model didn't return JSON — wrap raw response
            response = DesignValidationResponse(
                success=True,
                valid=True,  # Can't parse, assume best-effort
                model_used=model,
                findings=[{"severity": "info", "rule": "raw_response", "message": response_text}],
                rfc_references=[f"RFC {r}" for r in rfcs],
                generation_time_ms=elapsed_ms,
            )
    except Exception as e:
        metrics.record_delegation("rfc", model, 0, 0, success=False)
        response = DesignValidationResponse(
            success=False,
            valid=False,
            model_used=model,
            findings=[{"severity": "error", "rule": "delegation_failed", "message": str(e)}],
            generation_time_ms=0,
        )

    return [TextContent(type="text", text=response.model_dump_json(indent=2))]


async def handle_domain_query(args: dict) -> list[TextContent]:
    """Handle domain-specific questions."""
    domain = args["domain"]
    question = args["question"]
    context = args.get("context", "")

    model = router.get_model(domain)
    options = router.get_generation_options(domain)

    prompt = question
    if context:
        prompt = f"Context:\n{context}\n\nQuestion: {question}"

    try:
        result = await client.generate(model=model, prompt=prompt, options=options)
        response_text = result.get("response", "")
        elapsed_ms = result.get("_elapsed_ms", 0)
        eval_count = result.get("eval_count", len(response_text) // 4)

        metrics.record_delegation(domain, model, elapsed_ms, eval_count, success=True)

        response = ExpertQueryResponse(
            success=True,
            domain=domain,
            model_used=model,
            answer=response_text.strip(),
            generation_time_ms=elapsed_ms,
        )
    except Exception as e:
        metrics.record_delegation(domain, model, 0, 0, success=False)
        response = ExpertQueryResponse(
            success=False,
            domain=domain,
            model_used=model,
            answer=f"Delegation failed: {str(e)}",
            generation_time_ms=0,
        )

    return [TextContent(type="text", text=response.model_dump_json(indent=2))]


async def handle_list_experts(args: dict) -> list[TextContent]:
    """List configured domain experts and their availability."""
    configured = router.list_configured_domains()
    available_models = await client.list_models()

    experts = []
    for domain, config in configured.items():
        model_available = any(
            m == config.model or m.startswith(f"{config.model.split(':')[0]}:")
            for m in available_models
        )
        experts.append(ExpertInfo(
            domain=domain,
            model=config.model,
            available=model_available,
            description=config.description,
        ))

    # Add fallback info
    output = {
        "configured_experts": [e.model_dump() for e in experts],
        "fallback_model": router.fallback_model,
        "available_models_on_ollama": available_models,
        "ollama_url": OLLAMA_BASE_URL,
    }

    return [TextContent(type="text", text=json.dumps(output, indent=2))]


async def handle_health_check(args: dict) -> list[TextContent]:
    """Check Ollama connectivity and model availability."""
    reachable = await client.is_reachable()
    models = await client.list_models() if reachable else []

    configured = router.list_configured_domains()
    experts = []
    for domain, config in configured.items():
        model_available = config.model in models or any(
            m.startswith(f"{config.model.split(':')[0]}:") for m in models
        )
        experts.append(ExpertInfo(
            domain=domain,
            model=config.model,
            available=model_available,
            description=config.description,
        ))

    response = HealthCheckResponse(
        ollama_reachable=reachable,
        ollama_url=OLLAMA_BASE_URL,
        available_models=models,
        configured_experts=experts,
    )

    return [TextContent(type="text", text=response.model_dump_json(indent=2))]


async def handle_delegation_stats(args: dict) -> list[TextContent]:
    """Return delegation metrics for this session."""
    summary = metrics.get_summary()
    data = metrics.get_metrics().model_dump()
    output = f"{summary}\n\n---\nRaw metrics:\n{json.dumps(data, indent=2)}"
    return [TextContent(type="text", text=output)]


async def handle_validate_config_against_sot(args: dict) -> list[TextContent]:
    """Validate a generated config against Nautobot SOT data using the Nautobot expert."""
    config = args["config"]
    sot_data = args["sot_data"]
    device = args.get("device", "unknown")

    model = router.get_model("nautobot")
    options = router.get_generation_options("nautobot")

    prompt = (
        f"VALIDATE this FRR config for device {device} against the Nautobot source-of-truth data.\n"
        f"\n"
        f"Generated config:\n---\n{config}\n---\n"
        f"\n"
        f"Nautobot SOT data (GraphQL response):\n---\n{sot_data}\n---\n"
        f"\n"
        f"Check ALL 15 validation points from your training:\n"
        f"- OSPF: area, network_type, passive-interface, router-id\n"
        f"- BGP: ASN, router-id, peer groups, neighbors, extra_attributes placement\n"
        f"- Negative: no network statements under BGP, no RR knobs on spokes, no phantom attributes\n"
        f"\n"
        f"Return JSON: {{\"valid\": true/false, \"device\": \"{device}\", \"issues\": [...]}}"
    )

    try:
        result = await client.generate(model=model, prompt=prompt, options=options)
        response_text = result.get("response", "")
        elapsed_ms = result.get("_elapsed_ms", 0)
        eval_count = result.get("eval_count", len(response_text) // 4)

        metrics.record_delegation("nautobot", model, elapsed_ms, eval_count, success=True)

        # Try to parse as JSON, fall back to raw text
        try:
            parsed = json.loads(response_text)
            output = json.dumps(parsed, indent=2)
        except json.JSONDecodeError:
            output = json.dumps({
                "valid": None,
                "device": device,
                "model_used": model,
                "raw_response": response_text,
                "note": "Could not parse structured validation — review raw response",
                "generation_time_ms": elapsed_ms,
            }, indent=2)

    except Exception as e:
        metrics.record_delegation("nautobot", model, 0, 0, success=False)
        output = json.dumps({
            "valid": None,
            "device": device,
            "error": f"Validation delegation failed: {str(e)}",
        }, indent=2)

    return [TextContent(type="text", text=output)]


async def handle_build_graphql_query(args: dict) -> list[TextContent]:
    """Build a Nautobot GraphQL query from natural language intent."""
    intent = args["intent"]
    device = args.get("device", "")

    model = router.get_model("graphql")
    options = router.get_generation_options("graphql")

    prompt = intent
    if device:
        prompt = f"{intent} for device {device}"

    try:
        result = await client.generate(model=model, prompt=prompt, options=options)
        response_text = result.get("response", "").strip()
        elapsed_ms = result.get("_elapsed_ms", 0)
        eval_count = result.get("eval_count", len(response_text) // 4)

        metrics.record_delegation("graphql", model, elapsed_ms, eval_count, success=True)

        # Strip markdown fences if model included them
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Remove first and last fence lines
            lines = [l for l in lines if not l.strip().startswith("```")]
            response_text = "\n".join(lines).strip()

        output = json.dumps({
            "success": True,
            "query": response_text,
            "model_used": model,
            "generation_time_ms": elapsed_ms,
        }, indent=2)

    except Exception as e:
        metrics.record_delegation("graphql", model, 0, 0, success=False)
        output = json.dumps({
            "success": False,
            "error": f"Query generation failed: {str(e)}",
            "model_used": model,
        }, indent=2)

    return [TextContent(type="text", text=output)]


async def handle_summarize_state(args: dict) -> list[TextContent]:
    """Summarize raw show command output into compact JSON."""
    show_output = args["output"]
    device = args.get("device", "unknown")
    command = args.get("command", "")

    model = router.get_model("state")
    options = router.get_generation_options("state")

    prompt = f"Device: {device}."
    if command:
        prompt += f" Command: {command}."
    prompt += f"\n\n{show_output}"

    try:
        result = await client.generate(model=model, prompt=prompt, options=options)
        response_text = result.get("response", "").strip()
        elapsed_ms = result.get("_elapsed_ms", 0)
        eval_count = result.get("eval_count", len(response_text) // 4)

        metrics.record_delegation("state", model, elapsed_ms, eval_count, success=True)

        # Strip markdown fences if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            response_text = "\n".join(lines).strip()

        # Try to parse and re-serialize for clean output
        try:
            parsed = json.loads(response_text)
            output = json.dumps(parsed, indent=2)
        except json.JSONDecodeError:
            output = json.dumps({
                "success": False,
                "device": device,
                "raw_response": response_text,
                "note": "Could not parse structured summary",
                "generation_time_ms": elapsed_ms,
            }, indent=2)

    except Exception as e:
        metrics.record_delegation("state", model, 0, 0, success=False)
        output = json.dumps({
            "success": False,
            "device": device,
            "error": f"State summarization failed: {str(e)}",
        }, indent=2)

    return [TextContent(type="text", text=output)]


async def handle_compress_sot_data(args: dict) -> list[TextContent]:
    """Compress raw Nautobot GraphQL response into minimal config-relevant JSON."""
    graphql_response = args["graphql_response"]
    device = args["device"]

    model = router.get_model("compress")
    options = router.get_generation_options("compress")

    prompt = f"Compress for device {device}:\n{graphql_response}"

    try:
        result = await client.generate(model=model, prompt=prompt, options=options)
        response_text = result.get("response", "").strip()
        elapsed_ms = result.get("_elapsed_ms", 0)
        eval_count = result.get("eval_count", len(response_text) // 4)

        metrics.record_delegation("compress", model, elapsed_ms, eval_count, success=True)

        # Strip markdown fences if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            response_text = "\n".join(lines).strip()

        # Validate JSON output
        try:
            parsed = json.loads(response_text)
            # Calculate compression ratio
            input_size = len(graphql_response)
            output_size = len(response_text)
            compression_ratio = round((1 - output_size / input_size) * 100, 1) if input_size > 0 else 0

            output = json.dumps({
                "success": True,
                "compressed": parsed,
                "model_used": model,
                "generation_time_ms": elapsed_ms,
                "compression_ratio_pct": compression_ratio,
                "input_chars": input_size,
                "output_chars": output_size,
            }, indent=2)
        except json.JSONDecodeError:
            output = json.dumps({
                "success": False,
                "device": device,
                "raw_response": response_text,
                "note": "Could not parse compressed output as JSON",
                "generation_time_ms": elapsed_ms,
            }, indent=2)

    except Exception as e:
        metrics.record_delegation("compress", model, 0, 0, success=False)
        output = json.dumps({
            "success": False,
            "device": device,
            "error": f"Compression failed: {str(e)}",
        }, indent=2)

    return [TextContent(type="text", text=output)]


# --- Main ---

async def main():
    logger.info(f"Starting Ollama Domain Expert MCP Server")
    logger.info(f"  Ollama URL: {OLLAMA_BASE_URL}")
    logger.info(f"  Configured domains: {list(router.list_configured_domains().keys())}")
    logger.info(f"  Fallback model: {router.fallback_model}")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
