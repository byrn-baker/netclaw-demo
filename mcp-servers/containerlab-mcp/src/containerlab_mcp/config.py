"""Configuration manager for ContainerLab MCP Server.

Loads and merges configuration from multiple sources with priority:
  environment variables > CLI arguments > config file > defaults
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import yaml

from containerlab_mcp.models import ServerConfig

logger = logging.getLogger(__name__)

_VALID_LOG_LEVELS = {"debug", "info", "warning", "error"}
_VALID_TRANSPORTS = {"stdio", "sse"}
_MAX_TOPOLOGY_PATHS = 64


class ConfigManager:
    """Loads configuration from env vars, CLI args, and config files.

    Priority order: env > CLI > file > defaults.
    """

    def load(self, cli_overrides: dict[str, Any] | None = None) -> ServerConfig:
        """Load and merge configuration from all sources.

        Args:
            cli_overrides: Optional dict of CLI argument overrides.
                Keys should match ServerConfig field names.

        Returns:
            A validated ServerConfig instance.
        """
        file_config = self._load_config_file()
        cli_config = self._parse_cli_overrides(cli_overrides or {})
        env_config = self._load_env_vars()

        # Merge: start with file, overlay CLI, overlay env
        merged: dict[str, Any] = {}
        for key in ServerConfig.model_fields:
            value = _first_defined(
                env_config.get(key),
                cli_config.get(key),
                file_config.get(key),
            )
            if value is not None:
                merged[key] = value

        return ServerConfig(**merged)

    def _load_env_vars(self) -> dict[str, Any]:
        """Read CLAB_MCP_* environment variables."""
        result: dict[str, Any] = {}

        # CLAB_MCP_TOPOLOGY_PATHS — colon-separated list
        topology_paths_raw = os.environ.get("CLAB_MCP_TOPOLOGY_PATHS")
        if topology_paths_raw is not None:
            paths = self._parse_topology_paths(topology_paths_raw)
            if paths:
                result["topology_paths"] = paths

        # CLAB_MCP_LOG_LEVEL — case-insensitive, fallback to "info"
        log_level_raw = os.environ.get("CLAB_MCP_LOG_LEVEL")
        if log_level_raw is not None:
            result["log_level"] = self._parse_log_level(log_level_raw)

        # CLAB_MCP_TRANSPORT
        transport_raw = os.environ.get("CLAB_MCP_TRANSPORT")
        if transport_raw is not None:
            result["transport"] = transport_raw.lower()

        # CLAB_MCP_HOST
        host_raw = os.environ.get("CLAB_MCP_HOST")
        if host_raw is not None:
            result["host"] = host_raw

        # CLAB_MCP_PORT
        port_raw = os.environ.get("CLAB_MCP_PORT")
        if port_raw is not None:
            result["port"] = self._parse_port(port_raw)

        # CLAB_MCP_REMOTE
        remote_raw = os.environ.get("CLAB_MCP_REMOTE")
        if remote_raw is not None:
            result["remote"] = remote_raw

        # CLAB_MCP_SSH_KEY_PATH
        ssh_key_raw = os.environ.get("CLAB_MCP_SSH_KEY_PATH")
        if ssh_key_raw is not None:
            result["ssh_key_path"] = ssh_key_raw

        # CLAB_MCP_SSH_PORT
        ssh_port_raw = os.environ.get("CLAB_MCP_SSH_PORT")
        if ssh_port_raw is not None:
            result["ssh_port"] = self._parse_port(ssh_port_raw)

        return result

    def _parse_cli_overrides(self, overrides: dict[str, Any]) -> dict[str, Any]:
        """Normalize CLI overrides into config dict format.

        Accepts keys matching ServerConfig field names. Strips None values.
        """
        result: dict[str, Any] = {}
        for key, value in overrides.items():
            if value is None:
                continue
            if key == "log_level" and isinstance(value, str):
                result[key] = self._parse_log_level(value)
            elif key == "topology_paths" and isinstance(value, str):
                result[key] = self._parse_topology_paths(value)
            else:
                result[key] = value
        return result

    def _load_config_file(self) -> dict[str, Any]:
        """Load config file specified by CLAB_MCP_CONFIG_FILE env var.

        Supports YAML and JSON formats, detected by file extension.
        Returns empty dict if no config file is specified or file is unreadable.
        """
        config_path_str = os.environ.get("CLAB_MCP_CONFIG_FILE")
        if not config_path_str:
            return {}

        config_path = Path(config_path_str)
        if not config_path.is_file():
            logger.warning(
                "Config file not found: %s", config_path_str
            )
            return {}

        try:
            content = config_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning(
                "Cannot read config file %s: %s", config_path_str, exc
            )
            return {}

        try:
            if config_path.suffix in (".yaml", ".yml"):
                data = yaml.safe_load(content)
            elif config_path.suffix == ".json":
                data = json.loads(content)
            else:
                # Try YAML first, fall back to JSON
                try:
                    data = yaml.safe_load(content)
                except yaml.YAMLError:
                    data = json.loads(content)
        except (yaml.YAMLError, json.JSONDecodeError) as exc:
            logger.warning(
                "Failed to parse config file %s: %s", config_path_str, exc
            )
            return {}

        if not isinstance(data, dict):
            logger.warning(
                "Config file %s does not contain a mapping", config_path_str
            )
            return {}

        # Normalize keys and validate topology_paths from file
        result: dict[str, Any] = {}
        for key, value in data.items():
            normalized_key = key.replace("-", "_")
            if normalized_key == "log_level" and isinstance(value, str):
                result[normalized_key] = self._parse_log_level(value)
            elif normalized_key == "topology_paths":
                if isinstance(value, list):
                    result[normalized_key] = self._validate_topology_paths(value)
                elif isinstance(value, str):
                    result[normalized_key] = self._parse_topology_paths(value)
            else:
                result[normalized_key] = value

        return result

    def _parse_topology_paths(self, raw: str) -> list[str]:
        """Parse colon-separated path string into list, capped at 64 entries.

        Logs a warning for paths that are not accessible directories.
        """
        parts = [p for p in raw.split(":") if p]
        paths = parts[:_MAX_TOPOLOGY_PATHS]
        return self._validate_topology_paths(paths)

    def _validate_topology_paths(self, paths: list[str]) -> list[str]:
        """Validate topology path list. Warn for inaccessible paths but keep them."""
        validated: list[str] = []
        for p in paths[:_MAX_TOPOLOGY_PATHS]:
            if not isinstance(p, str):
                continue
            validated.append(p)
            path_obj = Path(p)
            if not path_obj.exists() or not path_obj.is_dir():
                logger.warning(
                    "Topology path is not accessible: %s", p
                )
        return validated

    def _parse_log_level(self, raw: str) -> str:
        """Parse log level string, case-insensitive. Falls back to 'info' for invalid."""
        normalized = raw.strip().lower()
        if normalized in _VALID_LOG_LEVELS:
            return normalized
        logger.warning(
            "Invalid log level '%s', falling back to 'info'", raw
        )
        return "info"

    def _parse_port(self, raw: str) -> int | None:
        """Parse port string to integer. Returns None if invalid."""
        try:
            port = int(raw)
            if 1 <= port <= 65535:
                return port
            logger.warning("Port value %d out of range 1-65535", port)
            return None
        except ValueError:
            logger.warning("Invalid port value: %s", raw)
            return None


def _first_defined(*values: Any) -> Any:
    """Return the first non-None value, or None if all are None."""
    for v in values:
        if v is not None:
            return v
    return None
