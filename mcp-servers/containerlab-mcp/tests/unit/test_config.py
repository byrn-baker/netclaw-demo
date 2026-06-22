"""Unit tests for ConfigManager."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

from containerlab_mcp.config import ConfigManager
from containerlab_mcp.models import ServerConfig


@pytest.fixture
def config_manager():
    return ConfigManager()


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Remove all CLAB_MCP_* env vars before each test."""
    for key in list(os.environ.keys()):
        if key.startswith("CLAB_MCP_"):
            monkeypatch.delenv(key)


class TestDefaults:
    """Test that defaults are applied when no config sources are provided."""

    def test_returns_server_config(self, config_manager):
        config = config_manager.load()
        assert isinstance(config, ServerConfig)

    def test_default_transport(self, config_manager):
        config = config_manager.load()
        assert config.transport == "stdio"

    def test_default_host(self, config_manager):
        config = config_manager.load()
        assert config.host == "0.0.0.0"

    def test_default_port(self, config_manager):
        config = config_manager.load()
        assert config.port == 8080

    def test_default_log_level(self, config_manager):
        config = config_manager.load()
        assert config.log_level == "info"

    def test_default_topology_paths(self, config_manager):
        config = config_manager.load()
        assert config.topology_paths == ["."]

    def test_default_ssh_port(self, config_manager):
        config = config_manager.load()
        assert config.ssh_port == 22


class TestEnvVars:
    """Test environment variable loading."""

    def test_topology_paths_colon_separated(self, config_manager, monkeypatch):
        monkeypatch.setenv("CLAB_MCP_TOPOLOGY_PATHS", "/tmp:/var/labs:/opt/topos")
        config = config_manager.load()
        assert config.topology_paths == ["/tmp", "/var/labs", "/opt/topos"]

    def test_topology_paths_single(self, config_manager, monkeypatch):
        monkeypatch.setenv("CLAB_MCP_TOPOLOGY_PATHS", "/tmp")
        config = config_manager.load()
        assert config.topology_paths == ["/tmp"]

    def test_topology_paths_max_64(self, config_manager, monkeypatch):
        paths = ":".join(f"/path{i}" for i in range(100))
        monkeypatch.setenv("CLAB_MCP_TOPOLOGY_PATHS", paths)
        config = config_manager.load()
        assert len(config.topology_paths) == 64

    def test_log_level_case_insensitive(self, config_manager, monkeypatch):
        monkeypatch.setenv("CLAB_MCP_LOG_LEVEL", "DEBUG")
        config = config_manager.load()
        assert config.log_level == "debug"

    def test_log_level_mixed_case(self, config_manager, monkeypatch):
        monkeypatch.setenv("CLAB_MCP_LOG_LEVEL", "Warning")
        config = config_manager.load()
        assert config.log_level == "warning"

    def test_log_level_invalid_falls_back_to_info(self, config_manager, monkeypatch):
        monkeypatch.setenv("CLAB_MCP_LOG_LEVEL", "verbose")
        config = config_manager.load()
        assert config.log_level == "info"

    def test_transport(self, config_manager, monkeypatch):
        monkeypatch.setenv("CLAB_MCP_TRANSPORT", "sse")
        config = config_manager.load()
        assert config.transport == "sse"

    def test_host(self, config_manager, monkeypatch):
        monkeypatch.setenv("CLAB_MCP_HOST", "127.0.0.1")
        config = config_manager.load()
        assert config.host == "127.0.0.1"

    def test_port(self, config_manager, monkeypatch):
        monkeypatch.setenv("CLAB_MCP_PORT", "9090")
        config = config_manager.load()
        assert config.port == 9090

    def test_remote(self, config_manager, monkeypatch):
        monkeypatch.setenv("CLAB_MCP_REMOTE", "admin@labhost")
        config = config_manager.load()
        assert config.remote == "admin@labhost"

    def test_ssh_key_path(self, config_manager, monkeypatch):
        monkeypatch.setenv("CLAB_MCP_SSH_KEY_PATH", "/home/user/.ssh/id_rsa")
        config = config_manager.load()
        assert config.ssh_key_path == "/home/user/.ssh/id_rsa"

    def test_ssh_port(self, config_manager, monkeypatch):
        monkeypatch.setenv("CLAB_MCP_SSH_PORT", "2222")
        config = config_manager.load()
        assert config.ssh_port == 2222


class TestConfigFile:
    """Test config file loading (YAML and JSON)."""

    def test_yaml_config_file(self, config_manager, monkeypatch, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "transport": "sse",
            "host": "10.0.0.1",
            "port": 3000,
            "log_level": "debug",
        }))
        monkeypatch.setenv("CLAB_MCP_CONFIG_FILE", str(config_file))
        config = config_manager.load()
        assert config.transport == "sse"
        assert config.host == "10.0.0.1"
        assert config.port == 3000
        assert config.log_level == "debug"

    def test_json_config_file(self, config_manager, monkeypatch, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "transport": "sse",
            "port": 4000,
        }))
        monkeypatch.setenv("CLAB_MCP_CONFIG_FILE", str(config_file))
        config = config_manager.load()
        assert config.transport == "sse"
        assert config.port == 4000

    def test_missing_config_file_uses_defaults(self, config_manager, monkeypatch):
        monkeypatch.setenv("CLAB_MCP_CONFIG_FILE", "/nonexistent/config.yaml")
        config = config_manager.load()
        assert config.transport == "stdio"

    def test_invalid_yaml_uses_defaults(self, config_manager, monkeypatch, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(":::invalid yaml{{{")
        monkeypatch.setenv("CLAB_MCP_CONFIG_FILE", str(config_file))
        config = config_manager.load()
        assert config.transport == "stdio"

    def test_topology_paths_list_in_file(self, config_manager, monkeypatch, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "topology_paths": ["/lab1", "/lab2", "/lab3"],
        }))
        monkeypatch.setenv("CLAB_MCP_CONFIG_FILE", str(config_file))
        config = config_manager.load()
        assert config.topology_paths == ["/lab1", "/lab2", "/lab3"]


class TestPrecedence:
    """Test configuration priority: env > CLI > file > defaults."""

    def test_env_overrides_cli(self, config_manager, monkeypatch):
        monkeypatch.setenv("CLAB_MCP_LOG_LEVEL", "error")
        config = config_manager.load(cli_overrides={"log_level": "debug"})
        assert config.log_level == "error"

    def test_cli_overrides_file(self, config_manager, monkeypatch, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"port": 3000}))
        monkeypatch.setenv("CLAB_MCP_CONFIG_FILE", str(config_file))
        config = config_manager.load(cli_overrides={"port": 5000})
        assert config.port == 5000

    def test_file_overrides_defaults(self, config_manager, monkeypatch, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"host": "192.168.1.1"}))
        monkeypatch.setenv("CLAB_MCP_CONFIG_FILE", str(config_file))
        config = config_manager.load()
        assert config.host == "192.168.1.1"

    def test_env_overrides_file(self, config_manager, monkeypatch, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"port": 3000}))
        monkeypatch.setenv("CLAB_MCP_CONFIG_FILE", str(config_file))
        monkeypatch.setenv("CLAB_MCP_PORT", "9999")
        config = config_manager.load()
        assert config.port == 9999

    def test_full_precedence_chain(self, config_manager, monkeypatch, tmp_path):
        # File sets port=3000, CLI sets port=5000, env sets port=8888
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({"port": 3000}))
        monkeypatch.setenv("CLAB_MCP_CONFIG_FILE", str(config_file))
        monkeypatch.setenv("CLAB_MCP_PORT", "8888")
        config = config_manager.load(cli_overrides={"port": 5000})
        assert config.port == 8888


class TestCLIOverrides:
    """Test CLI argument override handling."""

    def test_cli_transport(self, config_manager):
        config = config_manager.load(cli_overrides={"transport": "sse"})
        assert config.transport == "sse"

    def test_cli_none_values_ignored(self, config_manager):
        config = config_manager.load(cli_overrides={"port": None, "host": None})
        assert config.port == 8080
        assert config.host == "0.0.0.0"

    def test_cli_topology_paths_string(self, config_manager):
        config = config_manager.load(
            cli_overrides={"topology_paths": "/a:/b:/c"}
        )
        assert config.topology_paths == ["/a", "/b", "/c"]

    def test_cli_topology_paths_list(self, config_manager):
        config = config_manager.load(
            cli_overrides={"topology_paths": ["/x", "/y"]}
        )
        assert config.topology_paths == ["/x", "/y"]

    def test_cli_log_level_case_insensitive(self, config_manager):
        config = config_manager.load(cli_overrides={"log_level": "ERROR"})
        assert config.log_level == "error"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_topology_paths_env(self, config_manager, monkeypatch):
        monkeypatch.setenv("CLAB_MCP_TOPOLOGY_PATHS", "")
        config = config_manager.load()
        # Empty string splits to empty list, falls through to default
        assert config.topology_paths == ["."]

    def test_invalid_port_env_uses_default(self, config_manager, monkeypatch):
        monkeypatch.setenv("CLAB_MCP_PORT", "not_a_number")
        config = config_manager.load()
        assert config.port == 8080

    def test_port_out_of_range_uses_default(self, config_manager, monkeypatch):
        monkeypatch.setenv("CLAB_MCP_PORT", "99999")
        config = config_manager.load()
        assert config.port == 8080
