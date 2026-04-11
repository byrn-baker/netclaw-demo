#!/usr/bin/env python3
"""
NetShell Audit Report Generator

Generates compliance reports from OCSF audit logs for SOC2, PCI-DSS, HIPAA audits.
Usage: python audit-report.py [--format FORMAT] [--output PATH] [--days N]
"""

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


def load_audit_logs(log_path: Path, days: int = 30) -> list[dict]:
    """Load audit logs from the specified time period."""
    if not log_path.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_ms = int(cutoff.timestamp() * 1000)

    records = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if record.get("time", 0) >= cutoff_ms:
                    records.append(record)
            except json.JSONDecodeError:
                continue

    return records


def analyze_records(records: list[dict]) -> dict:
    """Analyze audit records for report generation."""
    analysis = {
        "total_events": len(records),
        "time_range": {"start": None, "end": None},
        "status_counts": Counter(),
        "activity_counts": Counter(),
        "severity_counts": Counter(),
        "top_tools": Counter(),
        "top_services": Counter(),
        "top_actors": Counter(),
        "violations": [],
        "blocked_networks": [],
    }

    if not records:
        return analysis

    # Time range
    times = [r.get("time", 0) for r in records]
    analysis["time_range"]["start"] = datetime.fromtimestamp(
        min(times) / 1000, tz=timezone.utc
    ).isoformat()
    analysis["time_range"]["end"] = datetime.fromtimestamp(
        max(times) / 1000, tz=timezone.utc
    ).isoformat()

    # Counters
    activity_names = {1: "Create", 2: "Read", 3: "Update", 4: "Delete", 5: "Other"}
    severity_names = {
        0: "Unknown",
        1: "Info",
        2: "Low",
        3: "Medium",
        4: "High",
        5: "Critical",
    }

    for record in records:
        analysis["status_counts"][record.get("status", "unknown")] += 1
        activity_id = record.get("activity_id", 5)
        analysis["activity_counts"][activity_names.get(activity_id, "Other")] += 1
        severity_id = record.get("severity_id", 0)
        analysis["severity_counts"][severity_names.get(severity_id, "Unknown")] += 1

        api = record.get("api", {})
        analysis["top_tools"][api.get("operation", "unknown")] += 1
        analysis["top_services"][api.get("service", "unknown")] += 1

        actor = record.get("actor", {})
        analysis["top_actors"][actor.get("user", "unknown")] += 1

        # Collect violations and blocked networks
        if record.get("status") == "blocked":
            metadata = record.get("metadata", {})
            violation = {
                "time": datetime.fromtimestamp(
                    record.get("time", 0) / 1000, tz=timezone.utc
                ).isoformat(),
                "actor": actor.get("user", "unknown"),
                "tool": f"{api.get('service', '')}.{api.get('operation', '')}",
                "reason": metadata.get("violation_reason", ""),
                "policy": metadata.get("policy", ""),
            }
            if "network" in api.get("operation", "").lower():
                dst = record.get("dst_endpoint", {})
                violation["destination"] = f"{dst.get('hostname', '')}:{dst.get('port', '')}"
                analysis["blocked_networks"].append(violation)
            else:
                analysis["violations"].append(violation)

    return analysis


def format_soc2_report(analysis: dict, title: str = "NetShell Audit Report") -> str:
    """Format analysis as SOC2-style report."""
    lines = [
        f"# {title}",
        "",
        f"**Generated**: {datetime.now(timezone.utc).isoformat()}",
        f"**Report Type**: SOC2 Type II Evidence",
        "",
        "## Executive Summary",
        "",
        f"- **Total Events**: {analysis['total_events']}",
        f"- **Time Period**: {analysis['time_range']['start']} to {analysis['time_range']['end']}",
        "",
        "### Event Outcomes",
        "",
        "| Status | Count |",
        "|--------|-------|",
    ]

    for status, count in sorted(analysis["status_counts"].items()):
        lines.append(f"| {status} | {count} |")

    lines.extend(
        [
            "",
            "### Activity Types",
            "",
            "| Activity | Count |",
            "|----------|-------|",
        ]
    )

    for activity, count in sorted(
        analysis["activity_counts"].items(), key=lambda x: -x[1]
    ):
        lines.append(f"| {activity} | {count} |")

    lines.extend(
        [
            "",
            "### Severity Distribution",
            "",
            "| Severity | Count |",
            "|----------|-------|",
        ]
    )

    for severity, count in analysis["severity_counts"].items():
        lines.append(f"| {severity} | {count} |")

    lines.extend(
        [
            "",
            "## Access Control Evidence",
            "",
            "### Top MCP Services Accessed",
            "",
            "| Service | Invocations |",
            "|---------|-------------|",
        ]
    )

    for service, count in analysis["top_services"].most_common(10):
        lines.append(f"| {service} | {count} |")

    lines.extend(
        [
            "",
            "### Top Tools Invoked",
            "",
            "| Tool | Invocations |",
            "|------|-------------|",
        ]
    )

    for tool, count in analysis["top_tools"].most_common(10):
        lines.append(f"| {tool} | {count} |")

    lines.extend(
        [
            "",
            "### Top Actors (Skills)",
            "",
            "| Actor | Invocations |",
            "|-------|-------------|",
        ]
    )

    for actor, count in analysis["top_actors"].most_common(10):
        lines.append(f"| {actor} | {count} |")

    # Security Violations
    lines.extend(
        [
            "",
            "## Security Violations",
            "",
        ]
    )

    if analysis["violations"]:
        lines.extend(
            [
                f"**Total Violations**: {len(analysis['violations'])}",
                "",
                "| Time | Actor | Tool | Reason |",
                "|------|-------|------|--------|",
            ]
        )
        for v in analysis["violations"][:20]:  # Limit to 20
            lines.append(f"| {v['time']} | {v['actor']} | {v['tool']} | {v['reason']} |")
    else:
        lines.append("No policy violations recorded.")

    # Blocked Network Connections
    lines.extend(
        [
            "",
            "## Blocked Network Connections",
            "",
        ]
    )

    if analysis["blocked_networks"]:
        lines.extend(
            [
                f"**Total Blocked**: {len(analysis['blocked_networks'])}",
                "",
                "| Time | Actor | Destination | Reason |",
                "|------|-------|-------------|--------|",
            ]
        )
        for b in analysis["blocked_networks"][:20]:
            lines.append(
                f"| {b['time']} | {b['actor']} | {b.get('destination', '')} | {b['reason']} |"
            )
    else:
        lines.append("No blocked network connections recorded.")

    lines.extend(
        [
            "",
            "---",
            "",
            "*This report was generated by NetShell Audit Reporter using OCSF-formatted logs.*",
            "*Audit logs are stored at: /workspace/logs/audit/netshell.log*",
        ]
    )

    return "\n".join(lines)


def format_json_report(analysis: dict) -> str:
    """Format analysis as JSON for machine processing."""
    # Convert Counters to dicts for JSON serialization
    output = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "report_type": "netshell_audit",
        "total_events": analysis["total_events"],
        "time_range": analysis["time_range"],
        "status_counts": dict(analysis["status_counts"]),
        "activity_counts": dict(analysis["activity_counts"]),
        "severity_counts": dict(analysis["severity_counts"]),
        "top_tools": dict(analysis["top_tools"].most_common(20)),
        "top_services": dict(analysis["top_services"].most_common(20)),
        "top_actors": dict(analysis["top_actors"].most_common(20)),
        "violations": analysis["violations"][:50],
        "blocked_networks": analysis["blocked_networks"][:50],
    }
    return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Generate NetShell audit report")
    parser.add_argument(
        "--log",
        type=Path,
        default=Path("/workspace/logs/audit/netshell.log"),
        help="Path to audit log file",
    )
    parser.add_argument(
        "--format",
        choices=["soc2", "json", "markdown"],
        default="soc2",
        help="Output format",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to include in report",
    )
    parser.add_argument(
        "--title",
        default="NetShell Audit Report",
        help="Report title",
    )
    args = parser.parse_args()

    # Load and analyze logs
    records = load_audit_logs(args.log, args.days)
    analysis = analyze_records(records)

    # Generate report
    if args.format == "json":
        report = format_json_report(analysis)
    else:
        report = format_soc2_report(analysis, args.title)

    # Output
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report)
        print(f"Report written to: {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
