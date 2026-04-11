#!/usr/bin/env python3
"""
NetShell Policy Compiler

Generates skill policies from SKILL.md netshell: frontmatter sections.
Usage: python compile-policies.py [--skills-dir PATH] [--output-dir PATH]
"""

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader


def parse_skill_frontmatter(skill_path: Path) -> dict | None:
    """Parse YAML frontmatter from SKILL.md file."""
    content = skill_path.read_text()

    # Match YAML frontmatter between --- markers
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None

    try:
        frontmatter = yaml.safe_load(match.group(1))
        return frontmatter if isinstance(frontmatter, dict) else None
    except yaml.YAMLError:
        return None


def load_mcp_policies(mcp_dir: Path) -> dict:
    """Load all MCP policies for permission resolution."""
    policies = {}
    for policy_file in mcp_dir.glob("*.yaml"):
        with open(policy_file) as f:
            policy = yaml.safe_load(f)
            mcp_name = policy.get("mcp_server", policy_file.stem)
            policies[mcp_name] = policy
    return policies


def resolve_permissions(mcp_tools: list, mcp_policies: dict) -> dict:
    """Resolve effective permissions from MCP policies."""
    resolved = {}
    for mcp_entry in mcp_tools:
        mcp_name = mcp_entry.get("mcp", "")
        tools = mcp_entry.get("tools", [])
        mcp_policy = mcp_policies.get(mcp_name, {})
        policy_tools = mcp_policy.get("tools", {})

        for tool in tools:
            key = f"{mcp_name}.{tool}"
            tool_config = policy_tools.get(tool, {})
            resolved[key] = {
                "permission": tool_config.get("permission", "allow"),
                "requires_approval": tool_config.get("requires_approval", False),
                "audit_level": tool_config.get("audit_level", "standard"),
            }
    return resolved


def compile_skill_policy(
    skill_name: str,
    skill_frontmatter: dict,
    mcp_policies: dict,
    template_env: Environment,
) -> str:
    """Compile a skill policy from frontmatter and MCP policies."""
    netshell_config = skill_frontmatter.get("netshell", {})
    mcp_tools = netshell_config.get("mcp_tools", [])
    approval_required = netshell_config.get("approval_required", False)

    resolved = resolve_permissions(mcp_tools, mcp_policies)

    template = template_env.get_template("skill-permission.yaml.j2")
    return template.render(
        skill_name=skill_name,
        skill_description=skill_frontmatter.get("description", ""),
        generated_at=datetime.now(timezone.utc).isoformat(),
        mcp_tools=mcp_tools,
        approval_required=approval_required,
        resolved=resolved,
    )


def main():
    parser = argparse.ArgumentParser(description="Compile NetShell skill policies")
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=Path("workspace/skills"),
        help="Skills directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("netshell/policies/skills"),
        help="Output directory for compiled policies",
    )
    parser.add_argument(
        "--mcp-dir",
        type=Path,
        default=Path("netshell/policies/mcp"),
        help="MCP policies directory",
    )
    parser.add_argument(
        "--templates-dir",
        type=Path,
        default=Path("netshell/templates"),
        help="Templates directory",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    # Resolve paths relative to script location if needed
    script_dir = Path(__file__).parent.parent.parent
    skills_dir = args.skills_dir if args.skills_dir.is_absolute() else script_dir / args.skills_dir
    output_dir = args.output_dir if args.output_dir.is_absolute() else script_dir / args.output_dir
    mcp_dir = args.mcp_dir if args.mcp_dir.is_absolute() else script_dir / args.mcp_dir
    templates_dir = (
        args.templates_dir if args.templates_dir.is_absolute() else script_dir / args.templates_dir
    )

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load MCP policies
    mcp_policies = load_mcp_policies(mcp_dir)
    if args.verbose:
        print(f"Loaded {len(mcp_policies)} MCP policies")

    # Setup Jinja2 environment
    template_env = Environment(loader=FileSystemLoader(templates_dir))

    # Process each skill
    compiled_count = 0
    skipped_count = 0

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        frontmatter = parse_skill_frontmatter(skill_md)
        if not frontmatter:
            if args.verbose:
                print(f"Skipping {skill_dir.name}: no valid frontmatter")
            skipped_count += 1
            continue

        # Check if skill has netshell: section
        if "netshell" not in frontmatter:
            if args.verbose:
                print(f"Skipping {skill_dir.name}: no netshell section")
            skipped_count += 1
            continue

        # Compile the skill policy
        skill_name = frontmatter.get("name", skill_dir.name)
        policy_content = compile_skill_policy(
            skill_name, frontmatter, mcp_policies, template_env
        )

        # Write the policy
        output_file = output_dir / f"{skill_dir.name}.yaml"
        output_file.write_text(policy_content)
        compiled_count += 1

        if args.verbose:
            print(f"Compiled: {skill_dir.name}")

    print(f"\nCompilation complete:")
    print(f"  Compiled: {compiled_count} skill(s)")
    print(f"  Skipped:  {skipped_count} skill(s) (no netshell section)")
    print(f"  Output:   {output_dir}")


if __name__ == "__main__":
    main()
