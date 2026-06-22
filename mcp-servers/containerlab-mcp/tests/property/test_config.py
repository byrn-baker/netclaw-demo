"""Property-based tests for configuration management.

Feature: containerlab-mcp
Properties 10, 11, 12, 13: Configuration Precedence, Path Parsing, Log Level, Transport Rejection

Validates: Requirements 8.1, 8.2, 8.4, 8.5, 6.6
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from unittest.mock import patch

import pytest
import yaml
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from containerlab_mcp.config import ConfigManager, _VALID_LOG_LEVELS, _VALID_TRANSPORTS


# --- Strategies ---

# Path segments: printable strings without colons or null bytes
path_segment_st = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        blacklist_characters=":\x00/",
    ),
    min_size=1,
    max_size=30,
).map(lambda s: s.strip()).filter(lambda s: len(s) > 0)

# Full path strings: /segment/segment (no colons)
path_st = st.builds(
    lambda parts: "/" + "/".join(parts),
    st.lists(path_segment_st, min_size=1, max_size=5),
)

# Valid log levels in various cases
valid_log_levels = sorted(_VALID_LOG_LEVELS)
valid_log_level_st = st.sampled_from(valid_log_levels).flatmap(
    lambda level: st.sampled_from(
        [level, level.upper(), level.capitalize(), level.swapcase()]
    )
)

# Invalid log levels: strings that don't match any valid level (case-insensitive)
invalid_log_level_st = st.text(min_size=1, max_size=20).filter(
    lambda s: s.strip().lower() not in _VALID_LOG_LEVELS
)

# Config values for precedence testing
config_value_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
).filter(lambda s: len(s.strip()) > 0)


# --- Property 10: Configuration Precedence ---
# Feature: containerlab-mcp, Property 10: Configuration Precedence


class TestConfigPrecedence:
    """Property 10: env var wins over CLI wins over file."""

    @given(
        env_level=st.sampled_from(valid_log_levels),
        cli_level=st.sampled_from(valid_log_levels),
        file_level=st.sampled_from(valid_log_levels),
    )
    @settings(max_examples=100)
    def test_env_wins_over_cli_and_file(
        self, env_level: str, cli_level: str, file_level: str, tmp_path_factory
    ) -> None:
        """Validates: Requirements 8.1

        When log_level is set in env, CLI, and file, the env value wins.
        """
        # Create a config file with file_level
        config_dir = tmp_path_factory.mktemp("config")
        config_file = config_dir / "config.yaml"
        config_file.write_text(yaml.dump({"log_level": file_level}))

        env_vars = {
            "CLAB_MCP_LOG_LEVEL": env_level,
            "CLAB_MCP_CONFIG_FILE": str(config_file),
        }

        with patch.dict(os.environ, env_vars, clear=False):
            manager = ConfigManager()
            config = manager.load(cli_overrides={"log_level": cli_level})

        assert config.log_level == env_level

    @given(
        cli_level=st.sampled_from(valid_log_levels),
        file_level=st.sampled_from(valid_log_levels),
    )
    @settings(max_examples=100)
    def test_cli_wins_over_file(
        self, cli_level: str, file_level: str, tmp_path_factory
    ) -> None:
        """Validates: Requirements 8.1

        When log_level is set in CLI and file (but not env), CLI value wins.
        """
        config_dir = tmp_path_factory.mktemp("config")
        config_file = config_dir / "config.yaml"
        config_file.write_text(yaml.dump({"log_level": file_level}))

        env_vars = {
            "CLAB_MCP_CONFIG_FILE": str(config_file),
        }
        # Remove CLAB_MCP_LOG_LEVEL from env if present
        cleaned_env = {
            k: v for k, v in os.environ.items() if k != "CLAB_MCP_LOG_LEVEL"
        }
        cleaned_env.update(env_vars)

        with patch.dict(os.environ, cleaned_env, clear=True):
            manager = ConfigManager()
            config = manager.load(cli_overrides={"log_level": cli_level})

        assert config.log_level == cli_level

    @given(file_level=st.sampled_from(valid_log_levels))
    @settings(max_examples=100)
    def test_file_used_when_no_env_or_cli(
        self, file_level: str, tmp_path_factory
    ) -> None:
        """Validates: Requirements 8.1

        When log_level is only set in file, that value is used.
        """
        config_dir = tmp_path_factory.mktemp("config")
        config_file = config_dir / "config.yaml"
        config_file.write_text(yaml.dump({"log_level": file_level}))

        env_vars = {
            "CLAB_MCP_CONFIG_FILE": str(config_file),
        }
        cleaned_env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("CLAB_MCP_LOG_LEVEL", "CLAB_MCP_CONFIG_FILE")
        }
        cleaned_env.update(env_vars)

        with patch.dict(os.environ, cleaned_env, clear=True):
            manager = ConfigManager()
            config = manager.load(cli_overrides={})

        assert config.log_level == file_level


# --- Property 11: Colon-Separated Path Parsing ---
# Feature: containerlab-mcp, Property 11: Colon-Separated Path Parsing


class TestColonPathParsing:
    """Property 11: any list of 1-64 paths joined by colon, parsing produces original list."""

    @given(paths=st.lists(path_st, min_size=1, max_size=64))
    @settings(max_examples=100)
    def test_colon_join_roundtrip(self, paths: list[str]) -> None:
        """Validates: Requirements 8.2

        For any list of 1-64 path strings (no colons), joining with colon and
        parsing via CLAB_MCP_TOPOLOGY_PATHS produces the original list.
        """
        # Ensure no path contains a colon (strategy guarantees this but double-check)
        assume(all(":" not in p for p in paths))
        # Ensure no empty paths after potential stripping
        assume(all(len(p) > 0 for p in paths))

        raw = ":".join(paths)

        # Clear other env vars that might interfere
        cleaned_env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith("CLAB_MCP_")
        }
        cleaned_env["CLAB_MCP_TOPOLOGY_PATHS"] = raw

        with patch.dict(os.environ, cleaned_env, clear=True):
            manager = ConfigManager()
            config = manager.load(cli_overrides={})

        assert config.topology_paths == paths


# --- Property 12: Log Level Parsing ---
# Feature: containerlab-mcp, Property 12: Log Level Parsing


class TestLogLevelParsing:
    """Property 12: case-insensitive match of valid levels; invalid falls back to 'info'."""

    @given(level=valid_log_level_st)
    @settings(max_examples=100)
    def test_valid_log_level_accepted_case_insensitive(self, level: str) -> None:
        """Validates: Requirements 8.4

        Any case variant of debug/info/warning/error is accepted as a valid log level.
        """
        manager = ConfigManager()
        result = manager._parse_log_level(level)
        assert result == level.strip().lower()
        assert result in _VALID_LOG_LEVELS

    @given(level=invalid_log_level_st)
    @settings(max_examples=100)
    def test_invalid_log_level_falls_back_to_info(self, level: str) -> None:
        """Validates: Requirements 8.5

        Any string that doesn't match a valid level falls back to 'info'.
        """
        manager = ConfigManager()
        result = manager._parse_log_level(level)
        assert result == "info"


# --- Property 13: Invalid Transport Rejection ---
# Feature: containerlab-mcp, Property 13: Invalid Transport Rejection


class TestInvalidTransportRejection:
    """Property 13: any string not 'stdio'/'sse' should be rejected."""

    @given(
        transport=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P", "S"),
                blacklist_characters="\x00",
            ),
            min_size=1,
            max_size=20,
        ).filter(lambda s: s.lower() not in _VALID_TRANSPORTS)
    )
    @settings(max_examples=100, deadline=None)
    def test_invalid_transport_rejected_with_nonzero_exit(
        self, transport: str
    ) -> None:
        """Validates: Requirements 6.6

        Any transport value that is not 'stdio' or 'sse' should cause
        the server to exit with a non-zero exit code.
        """
        # Run the server CLI with an invalid transport value via subprocess
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "containerlab_mcp.server",
                "--transport",
                transport,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            ),
        )

        assert result.returncode != 0, (
            f"Expected non-zero exit code for transport={transport!r}, "
            f"got {result.returncode}"
        )
