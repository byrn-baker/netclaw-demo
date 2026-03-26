"""TOON serialization helper for Azure Network MCP server."""

import json
import os
import sys

# Add netclaw_tokens to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "src"))


def toon_dumps(data, **kwargs) -> str:
    """Serialize data using TOON format with JSON fallback."""
    try:
        from netclaw_tokens.toon_serializer import serialize_response
        result = serialize_response(data)
        return result.toon_data
    except Exception:
        return json.dumps(data, indent=2, default=str)
