"""GCF serialization utility for MCP server responses.

Uses the gcf-python package to serialize structured data into GCF format,
which achieves 53-71% token savings on tabular network data. Falls back to
JSON on any error, never failing the operation.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from . import GCFResponse

logger = logging.getLogger("netclaw_tokens.gcf_serializer")


def _estimate_token_count(text: str) -> int:
    """Quick token estimation using len/4 heuristic."""
    return max(1, len(text) // 4)


def _is_binary_data(data: Any) -> bool:
    """Check if data is binary (bytes or contains non-UTF-8 content)."""
    if isinstance(data, (bytes, bytearray)):
        return True
    if isinstance(data, str):
        try:
            data.encode("utf-8")
            return False
        except (UnicodeEncodeError, UnicodeDecodeError):
            return True
    return False


def serialize_response(data: Any) -> GCFResponse:
    """Serialize data to GCF format with JSON fallback.

    Args:
        data: Any JSON-serializable data structure.

    Returns:
        GCFResponse with gcf_data (GCF string or JSON string),
        token counts for both formats, savings calculation,
        and fallback_used flag.

    Behavior:
        - If data is bytes or non-UTF-8: returns JSON, fallback_used=True
        - If encode_generic() fails: returns JSON, fallback_used=True, logs warning
        - Otherwise: returns GCF, fallback_used=False
    """
    # Generate JSON representation for comparison
    try:
        json_str = json.dumps(data, indent=2, default=str)
    except (TypeError, ValueError):
        json_str = str(data)

    json_token_count = _estimate_token_count(json_str)

    # Skip GCF for binary data
    if _is_binary_data(data):
        logger.debug("Binary data detected; skipping GCF, using JSON")
        return GCFResponse(
            gcf_data=json_str,
            json_token_count=json_token_count,
            gcf_token_count=json_token_count,
            savings_tokens=0,
            savings_pct=0.0,
            fallback_used=True,
        )

    # Attempt GCF serialization
    try:
        from gcf import encode_generic

        gcf_str = encode_generic(data)
        gcf_token_count = _estimate_token_count(gcf_str)
        savings_tokens = max(0, json_token_count - gcf_token_count)
        savings_pct = (savings_tokens / json_token_count * 100.0) if json_token_count > 0 else 0.0

        return GCFResponse(
            gcf_data=gcf_str,
            json_token_count=json_token_count,
            gcf_token_count=gcf_token_count,
            savings_tokens=savings_tokens,
            savings_pct=round(savings_pct, 1),
            fallback_used=False,
        )
    except Exception as exc:
        logger.warning(
            "GCF serialization failed (%s: %s); falling back to JSON",
            type(exc).__name__,
            exc,
        )
        return GCFResponse(
            gcf_data=json_str,
            json_token_count=json_token_count,
            gcf_token_count=json_token_count,
            savings_tokens=0,
            savings_pct=0.0,
            fallback_used=True,
        )
