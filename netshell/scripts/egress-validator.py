#!/usr/bin/env python3
"""
NetShell Egress Validator

Validates network egress rules in MCP policies for common security issues.
Usage: python egress-validator.py [--mcp-dir PATH] [--base-policy PATH]
"""

import argparse
import ipaddress
from pathlib import Path

import yaml


# Security warnings
WARNINGS = {
    "wildcard_host": "Wildcard host pattern (*) allows any destination",
    "all_ports": "All ports allowed (0 or empty)",
    "http_without_https": "HTTP allowed without HTTPS (consider upgrading)",
    "private_cidr_large": "Large private CIDR block (consider narrowing)",
    "metadata_accessible": "Cloud metadata service IP not explicitly blocked",
    "missing_anthropic": "Anthropic API not in core_egress (required for LLM)",
}

# Known cloud metadata IPs to block
METADATA_IPS = [
    "169.254.169.254",  # AWS, Azure, GCP
    "fd00:ec2::254",  # AWS IPv6
]


def load_policy(path: Path) -> dict:
    """Load a YAML policy file."""
    with open(path) as f:
        return yaml.safe_load(f)


def validate_egress_rule(rule: dict, policy_name: str) -> list[dict]:
    """Validate a single egress rule."""
    issues = []
    host = rule.get("host", "")
    ports = rule.get("ports", [])
    protocols = rule.get("protocols", [])

    # Check for wildcard host
    if host == "*":
        issues.append(
            {
                "severity": "HIGH",
                "policy": policy_name,
                "rule": rule.get("name", "unnamed"),
                "issue": WARNINGS["wildcard_host"],
                "host": host,
            }
        )

    # Check for overly permissive ports
    if 0 in ports or not ports:
        issues.append(
            {
                "severity": "MEDIUM",
                "policy": policy_name,
                "rule": rule.get("name", "unnamed"),
                "issue": WARNINGS["all_ports"],
                "ports": ports,
            }
        )

    # Check for HTTP without HTTPS
    if "http" in protocols and "https" not in protocols:
        issues.append(
            {
                "severity": "LOW",
                "policy": policy_name,
                "rule": rule.get("name", "unnamed"),
                "issue": WARNINGS["http_without_https"],
                "protocols": protocols,
            }
        )

    # Check for large private CIDRs
    if "/" in host:
        try:
            network = ipaddress.ip_network(host, strict=False)
            if network.is_private and network.prefixlen < 16:
                issues.append(
                    {
                        "severity": "LOW",
                        "policy": policy_name,
                        "rule": rule.get("name", "unnamed"),
                        "issue": WARNINGS["private_cidr_large"],
                        "host": host,
                        "size": network.num_addresses,
                    }
                )
        except ValueError:
            pass

    return issues


def validate_base_policy(policy: dict, path: Path) -> list[dict]:
    """Validate the base policy for required configurations."""
    issues = []
    policy_name = path.name

    network_policies = policy.get("network_policies", {})

    # Check default action is deny
    if network_policies.get("default_action") != "deny":
        issues.append(
            {
                "severity": "CRITICAL",
                "policy": policy_name,
                "issue": "default_action must be 'deny' for security",
                "current": network_policies.get("default_action"),
            }
        )

    # Check core_egress includes Anthropic API
    core_egress = network_policies.get("core_egress", [])
    anthropic_found = any(
        "anthropic" in rule.get("host", "").lower() for rule in core_egress
    )
    if not anthropic_found:
        issues.append(
            {
                "severity": "HIGH",
                "policy": policy_name,
                "issue": WARNINGS["missing_anthropic"],
            }
        )

    # Check blocked list includes metadata IPs
    blocked = network_policies.get("blocked", [])
    blocked_hosts = [b.get("host", "") for b in blocked]
    for metadata_ip in METADATA_IPS:
        if metadata_ip not in blocked_hosts:
            issues.append(
                {
                    "severity": "MEDIUM",
                    "policy": policy_name,
                    "issue": f"Cloud metadata IP {metadata_ip} not explicitly blocked",
                }
            )

    # Validate all egress rules
    for rule in core_egress:
        issues.extend(validate_egress_rule(rule, policy_name))

    return issues


def validate_mcp_policy(policy: dict, path: Path) -> list[dict]:
    """Validate an MCP policy."""
    issues = []
    policy_name = path.name

    network_policies = policy.get("network_policies", {})
    egress = network_policies.get("egress", [])

    # Must have at least one egress rule
    if not egress:
        issues.append(
            {
                "severity": "MEDIUM",
                "policy": policy_name,
                "issue": "No egress rules defined - MCP cannot make network calls",
            }
        )

    # Validate each egress rule
    for rule in egress:
        issues.extend(validate_egress_rule(rule, policy_name))

    return issues


def main():
    parser = argparse.ArgumentParser(description="Validate NetShell egress policies")
    parser.add_argument(
        "--mcp-dir",
        type=Path,
        default=Path("netshell/policies/mcp"),
        help="MCP policies directory",
    )
    parser.add_argument(
        "--base-policy",
        type=Path,
        default=Path("netshell/policies/base.yaml"),
        help="Base policy file",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Resolve paths
    script_dir = Path(__file__).parent.parent.parent
    mcp_dir = args.mcp_dir if args.mcp_dir.is_absolute() else script_dir / args.mcp_dir
    base_policy = (
        args.base_policy if args.base_policy.is_absolute() else script_dir / args.base_policy
    )

    all_issues = []

    # Validate base policy
    if base_policy.exists():
        policy = load_policy(base_policy)
        issues = validate_base_policy(policy, base_policy)
        all_issues.extend(issues)
    else:
        all_issues.append({"severity": "CRITICAL", "issue": f"Base policy not found: {base_policy}"})

    # Validate MCP policies
    if mcp_dir.exists():
        for policy_file in sorted(mcp_dir.glob("*.yaml")):
            policy = load_policy(policy_file)
            issues = validate_mcp_policy(policy, policy_file)
            all_issues.extend(issues)
    else:
        all_issues.append({"severity": "HIGH", "issue": f"MCP directory not found: {mcp_dir}"})

    # Output
    if args.json:
        import json

        print(json.dumps(all_issues, indent=2))
    else:
        # Group by severity
        by_severity = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
        for issue in all_issues:
            severity = issue.get("severity", "LOW")
            by_severity.setdefault(severity, []).append(issue)

        print("NetShell Egress Policy Validation")
        print("=" * 40)

        for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            issues = by_severity.get(severity, [])
            if issues:
                print(f"\n{severity} ({len(issues)}):")
                for issue in issues:
                    policy = issue.get("policy", "")
                    msg = issue.get("issue", "")
                    print(f"  [{policy}] {msg}")

        total = len(all_issues)
        critical = len(by_severity.get("CRITICAL", []))
        high = len(by_severity.get("HIGH", []))

        print(f"\nTotal issues: {total}")
        if critical > 0 or high > 0:
            print("Please address CRITICAL and HIGH severity issues before production use.")
            exit(1)
        elif total > 0:
            print("Consider addressing MEDIUM and LOW severity issues.")
        else:
            print("All policies validated successfully!")


if __name__ == "__main__":
    main()
