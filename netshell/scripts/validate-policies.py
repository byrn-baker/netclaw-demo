#!/usr/bin/env python3
"""
NetShell Policy Validator

Validates base.yaml and MCP policies against their contract schemas.
Usage: python validate-policies.py [--base] [--mcp] [--all]
"""

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


# Schema validation rules from contracts/base-policy.md
BASE_POLICY_RULES = {
    "version": {"required": True, "value": 1},
    "name": {"required": True, "type": str},
    "filesystem_policy.denied": {
        "required": True,
        "must_include": ["/root", "/home", "/etc/shadow"],
    },
    "landlock.enabled": {"required": True, "value": True},
    "process.no_new_privs": {"required": True, "value": True},
    "process.seccomp.deny": {
        "required": True,
        "must_include": ["ptrace", "mount", "reboot"],
    },
    "network_policies.default_action": {"required": True, "value": "deny"},
    "network_policies.core_egress": {
        "required": True,
        "must_include_host": "api.anthropic.com",
    },
    "audit.enabled": {"required": True, "value": True},
    "audit.format": {"required": True, "value": "ocsf"},
}

# Schema validation rules from contracts/mcp-policy.md
MCP_POLICY_RULES = {
    "version": {"required": True, "value": 1},
    "mcp_server": {"required": True, "type": str},
    "network_policies.egress": {"required": True, "min_length": 1},
    "tools": {"required": True, "type": dict},
}


def get_nested(data: dict, path: str) -> Any:
    """Get a nested value from a dict using dot notation."""
    keys = path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    return value


def validate_base_policy(policy: dict) -> list[str]:
    """Validate base policy against contract rules."""
    errors = []

    for path, rules in BASE_POLICY_RULES.items():
        value = get_nested(policy, path)

        if rules.get("required") and value is None:
            errors.append(f"Missing required field: {path}")
            continue

        if "value" in rules and value != rules["value"]:
            errors.append(f"{path}: expected {rules['value']}, got {value}")

        if "type" in rules and not isinstance(value, rules["type"]):
            errors.append(f"{path}: expected type {rules['type'].__name__}")

        if "must_include" in rules and isinstance(value, list):
            missing = [item for item in rules["must_include"] if item not in value]
            if missing:
                errors.append(f"{path}: missing required items: {missing}")

        if "must_include_host" in rules and isinstance(value, list):
            hosts = [e.get("host", "") for e in value if isinstance(e, dict)]
            if rules["must_include_host"] not in hosts:
                errors.append(f"{path}: must include {rules['must_include_host']}")

    return errors


def validate_mcp_policy(policy: dict, filename: str) -> list[str]:
    """Validate MCP policy against contract rules."""
    errors = []

    for path, rules in MCP_POLICY_RULES.items():
        value = get_nested(policy, path)

        if rules.get("required") and value is None:
            errors.append(f"[{filename}] Missing required field: {path}")
            continue

        if "value" in rules and value != rules["value"]:
            errors.append(f"[{filename}] {path}: expected {rules['value']}, got {value}")

        if "type" in rules and not isinstance(value, rules["type"]):
            errors.append(f"[{filename}] {path}: expected type {rules['type'].__name__}")

        if "min_length" in rules and isinstance(value, list):
            if len(value) < rules["min_length"]:
                errors.append(
                    f"[{filename}] {path}: must have at least {rules['min_length']} item(s)"
                )

    # Validate mcp_server matches filename
    mcp_server = policy.get("mcp_server", "")
    expected_name = filename.replace(".yaml", "")
    if mcp_server != expected_name:
        errors.append(
            f"[{filename}] mcp_server '{mcp_server}' does not match filename '{expected_name}'"
        )

    # Validate tools have required fields
    tools = policy.get("tools", {})
    for tool_name, tool_config in tools.items():
        if not isinstance(tool_config, dict):
            errors.append(f"[{filename}] Tool '{tool_name}' must be a dictionary")
            continue
        if "permission" not in tool_config:
            errors.append(f"[{filename}] Tool '{tool_name}' missing 'permission' field")
        if "requires_approval" not in tool_config:
            errors.append(f"[{filename}] Tool '{tool_name}' missing 'requires_approval' field")
        if "audit_level" not in tool_config:
            errors.append(f"[{filename}] Tool '{tool_name}' missing 'audit_level' field")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate NetShell policies")
    parser.add_argument("--base", action="store_true", help="Validate base policy")
    parser.add_argument("--mcp", action="store_true", help="Validate MCP policies")
    parser.add_argument("--all", action="store_true", help="Validate all policies")
    parser.add_argument("--quiet", action="store_true", help="Only show errors")
    args = parser.parse_args()

    if not any([args.base, args.mcp, args.all]):
        args.all = True

    netshell_dir = Path(__file__).parent.parent
    policies_dir = netshell_dir / "policies"
    all_errors = []

    # Validate base policy
    if args.base or args.all:
        base_path = policies_dir / "base.yaml"
        if base_path.exists():
            with open(base_path) as f:
                policy = yaml.safe_load(f)
            errors = validate_base_policy(policy)
            all_errors.extend(errors)
            if not args.quiet:
                if errors:
                    print(f"base.yaml: {len(errors)} error(s)")
                else:
                    print("base.yaml: OK")
        else:
            all_errors.append("base.yaml not found")

    # Validate MCP policies
    if args.mcp or args.all:
        mcp_dir = policies_dir / "mcp"
        if mcp_dir.exists():
            for policy_file in sorted(mcp_dir.glob("*.yaml")):
                with open(policy_file) as f:
                    policy = yaml.safe_load(f)
                errors = validate_mcp_policy(policy, policy_file.name)
                all_errors.extend(errors)
                if not args.quiet:
                    if errors:
                        print(f"{policy_file.name}: {len(errors)} error(s)")
                    else:
                        print(f"{policy_file.name}: OK")
        else:
            all_errors.append("mcp/ directory not found")

    # Print all errors
    if all_errors:
        print(f"\n{len(all_errors)} validation error(s):")
        for error in all_errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        if not args.quiet:
            print("\nAll policies valid!")
        sys.exit(0)


if __name__ == "__main__":
    main()
