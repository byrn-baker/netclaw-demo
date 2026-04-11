#!/usr/bin/env python3
"""
NetShell Skill Permission Checker

Runtime permission checking for skill MCP tool invocations.
Used by the NetShell gateway to enforce per-skill tool allowlists.

Usage:
    from check_skill_permissions import PermissionChecker
    checker = PermissionChecker()
    result = checker.check(skill="pyats-health-check", mcp="pyats-mcp", tool="show_command")
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml


@dataclass
class PermissionResult:
    """Result of a permission check."""

    allowed: bool
    reason: str
    requires_approval: bool = False
    audit_level: str = "standard"
    matched_policy: str = ""


class PermissionChecker:
    """Check skill permissions against MCP policies."""

    def __init__(
        self,
        skills_dir: Path | None = None,
        mcp_policies_dir: Path | None = None,
        skill_policies_dir: Path | None = None,
    ):
        """Initialize permission checker.

        Args:
            skills_dir: Path to workspace/skills/
            mcp_policies_dir: Path to netshell/policies/mcp/
            skill_policies_dir: Path to netshell/policies/skills/
        """
        base_dir = Path(__file__).parent.parent.parent

        self.skills_dir = skills_dir or base_dir / "workspace" / "skills"
        self.mcp_policies_dir = mcp_policies_dir or base_dir / "netshell" / "policies" / "mcp"
        self.skill_policies_dir = (
            skill_policies_dir or base_dir / "netshell" / "policies" / "skills"
        )

        self._skill_cache: dict[str, dict] = {}
        self._mcp_cache: dict[str, dict] = {}

    def _load_skill_frontmatter(self, skill_name: str) -> dict | None:
        """Load and cache skill frontmatter."""
        if skill_name in self._skill_cache:
            return self._skill_cache[skill_name]

        skill_path = self.skills_dir / skill_name / "SKILL.md"
        if not skill_path.exists():
            return None

        content = skill_path.read_text()
        match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return None

        try:
            frontmatter = yaml.safe_load(match.group(1))
            self._skill_cache[skill_name] = frontmatter
            return frontmatter
        except yaml.YAMLError:
            return None

    def _load_mcp_policy(self, mcp_name: str) -> dict | None:
        """Load and cache MCP policy."""
        if mcp_name in self._mcp_cache:
            return self._mcp_cache[mcp_name]

        policy_path = self.mcp_policies_dir / f"{mcp_name}.yaml"
        if not policy_path.exists():
            return None

        try:
            with open(policy_path) as f:
                policy = yaml.safe_load(f)
                self._mcp_cache[mcp_name] = policy
                return policy
        except (yaml.YAMLError, OSError):
            return None

    def _check_dangerous_patterns(
        self, mcp_policy: dict, tool: str, arguments: dict
    ) -> tuple[bool, str]:
        """Check if arguments match dangerous patterns.

        Returns:
            Tuple of (is_dangerous, pattern_description)
        """
        patterns = mcp_policy.get("dangerous_patterns", [])
        if not patterns:
            return False, ""

        # Convert arguments to string for pattern matching
        arg_str = " ".join(str(v) for v in arguments.values())

        for pattern_config in patterns:
            pattern = pattern_config.get("pattern", "")
            if not pattern:
                continue

            try:
                if re.search(pattern, arg_str, re.IGNORECASE):
                    return True, pattern_config.get("description", f"Matches pattern: {pattern}")
            except re.error:
                continue

        return False, ""

    def check(
        self,
        skill: str,
        mcp: str,
        tool: str,
        arguments: dict | None = None,
    ) -> PermissionResult:
        """Check if a skill is allowed to invoke an MCP tool.

        Args:
            skill: Skill name (e.g., "pyats-health-check")
            mcp: MCP server name (e.g., "pyats-mcp")
            tool: Tool name (e.g., "show_command")
            arguments: Tool arguments for dangerous pattern checking

        Returns:
            PermissionResult with allowed status and reason
        """
        arguments = arguments or {}

        # Step 1: Check skill has netshell section
        frontmatter = self._load_skill_frontmatter(skill)
        if not frontmatter:
            return PermissionResult(
                allowed=False,
                reason=f"Skill '{skill}' not found or has no valid frontmatter",
            )

        netshell_config = frontmatter.get("netshell")
        if not netshell_config:
            return PermissionResult(
                allowed=False,
                reason=f"Skill '{skill}' has no netshell permissions declared",
                matched_policy=f"workspace/skills/{skill}/SKILL.md",
            )

        # Step 2: Check MCP is in skill's mcp_tools
        mcp_tools = netshell_config.get("mcp_tools", [])
        mcp_entry = None
        for entry in mcp_tools:
            if entry.get("mcp") == mcp:
                mcp_entry = entry
                break

        if not mcp_entry:
            return PermissionResult(
                allowed=False,
                reason=f"Skill '{skill}' is not allowed to use MCP '{mcp}'",
                matched_policy=f"workspace/skills/{skill}/SKILL.md",
            )

        # Step 3: Check tool is in MCP's tools list
        allowed_tools = mcp_entry.get("tools", [])
        if tool not in allowed_tools:
            return PermissionResult(
                allowed=False,
                reason=f"Skill '{skill}' is not allowed to invoke '{mcp}.{tool}'",
                matched_policy=f"workspace/skills/{skill}/SKILL.md",
            )

        # Step 4: Check MCP policy allows the tool
        mcp_policy = self._load_mcp_policy(mcp)
        if not mcp_policy:
            return PermissionResult(
                allowed=False,
                reason=f"MCP policy not found for '{mcp}'",
            )

        tool_config = mcp_policy.get("tools", {}).get(tool)
        if not tool_config:
            # Tool not explicitly configured in MCP policy - allow by default
            pass
        elif tool_config.get("permission") == "deny":
            return PermissionResult(
                allowed=False,
                reason=f"MCP policy denies tool '{mcp}.{tool}'",
                matched_policy=f"netshell/policies/mcp/{mcp}.yaml",
            )

        # Step 5: Check dangerous patterns
        is_dangerous, pattern_desc = self._check_dangerous_patterns(
            mcp_policy, tool, arguments
        )
        if is_dangerous:
            return PermissionResult(
                allowed=False,
                reason=f"Dangerous pattern detected: {pattern_desc}",
                matched_policy=f"netshell/policies/mcp/{mcp}.yaml",
            )

        # Step 6: Determine approval and audit requirements
        requires_approval = False
        audit_level = "standard"

        if tool_config:
            requires_approval = tool_config.get("requires_approval", False)
            audit_level = tool_config.get("audit_level", "standard")

        # Skill-level override
        if netshell_config.get("approval_required"):
            requires_approval = True

        return PermissionResult(
            allowed=True,
            reason=f"Tool '{mcp}.{tool}' allowed for skill '{skill}'",
            requires_approval=requires_approval,
            audit_level=audit_level,
            matched_policy=f"workspace/skills/{skill}/SKILL.md",
        )


def check_permission(
    skill: str, mcp: str, tool: str, arguments: dict | None = None
) -> PermissionResult:
    """Convenience function to check a single permission."""
    checker = PermissionChecker()
    return checker.check(skill, mcp, tool, arguments)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Check skill permissions")
    parser.add_argument("--skill", required=True, help="Skill name")
    parser.add_argument("--mcp", required=True, help="MCP server name")
    parser.add_argument("--tool", required=True, help="Tool name")
    parser.add_argument("--arg", action="append", help="Arguments (key=value)")
    args = parser.parse_args()

    # Parse arguments
    arguments = {}
    if args.arg:
        for arg in args.arg:
            if "=" in arg:
                key, value = arg.split("=", 1)
                arguments[key] = value

    result = check_permission(args.skill, args.mcp, args.tool, arguments)

    print(f"Skill: {args.skill}")
    print(f"MCP: {args.mcp}")
    print(f"Tool: {args.tool}")
    print(f"Arguments: {arguments}")
    print()
    print(f"Allowed: {result.allowed}")
    print(f"Reason: {result.reason}")
    if result.allowed:
        print(f"Requires Approval: {result.requires_approval}")
        print(f"Audit Level: {result.audit_level}")
    if result.matched_policy:
        print(f"Matched Policy: {result.matched_policy}")
