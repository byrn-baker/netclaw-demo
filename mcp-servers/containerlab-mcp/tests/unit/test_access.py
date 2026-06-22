"""Unit tests for node access detection and credential extraction."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from containerlab_mcp.access import (
    DOCKER_EXEC_KINDS,
    SSH_KINDS,
    WELL_KNOWN_CREDENTIALS,
    NodeAccessDetector,
)


@pytest.fixture
def detector() -> NodeAccessDetector:
    return NodeAccessDetector()


def _write_topology(path: Path, data: dict) -> str:
    """Write topology data to a YAML file and return the path string."""
    filepath = path / "test.clab.yml"
    with open(filepath, "w") as f:
        yaml.dump(data, f)
    return str(filepath)


class TestAccessMethodDetection:
    """Test kind-to-access-method mapping."""

    def test_srl_uses_ssh(self, detector: NodeAccessDetector, tmp_path: Path) -> None:
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {"nodes": {"srl1": {"kind": "srl", "image": "ghcr.io/nokia/srlinux"}}},
        })
        result = detector.detect(topo, "srl1", container_id="abc123", mgmt_ipv4="172.20.20.2")
        assert result.access_method == "ssh"

    def test_ceos_uses_ssh(self, detector: NodeAccessDetector, tmp_path: Path) -> None:
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {"nodes": {"ceos1": {"kind": "ceos", "image": "ceos:latest"}}},
        })
        result = detector.detect(topo, "ceos1", container_id="abc123", mgmt_ipv4="172.20.20.3")
        assert result.access_method == "ssh"

    def test_crpd_uses_ssh(self, detector: NodeAccessDetector, tmp_path: Path) -> None:
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {"nodes": {"crpd1": {"kind": "crpd", "image": "crpd:latest"}}},
        })
        result = detector.detect(topo, "crpd1", container_id="abc123", mgmt_ipv4="172.20.20.4")
        assert result.access_method == "ssh"

    def test_linux_uses_docker_exec(self, detector: NodeAccessDetector, tmp_path: Path) -> None:
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {"nodes": {"host1": {"kind": "linux", "image": "alpine:latest"}}},
        })
        result = detector.detect(topo, "host1", container_id="def456")
        assert result.access_method == "docker_exec"

    def test_bridge_uses_docker_exec(self, detector: NodeAccessDetector, tmp_path: Path) -> None:
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {"nodes": {"br1": {"kind": "bridge"}}},
        })
        result = detector.detect(topo, "br1", container_id="br-container")
        assert result.access_method == "docker_exec"

    def test_unknown_kind_uses_clab_connect(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {"nodes": {"serial1": {"kind": "rare-nos"}}},
        })
        result = detector.detect(
            topo, "serial1", container_id="xyz", lab_name="test-lab"
        )
        assert result.access_method == "clab_connect"

    def test_all_ssh_kinds_detected(self, detector: NodeAccessDetector, tmp_path: Path) -> None:
        for kind in SSH_KINDS:
            nodes = {f"node-{kind}": {"kind": kind, "image": "img"}}
            topo = _write_topology(tmp_path, {
                "name": "lab",
                "topology": {"nodes": nodes},
            })
            result = detector.detect(
                topo, f"node-{kind}", container_id="c1", mgmt_ipv4="10.0.0.1"
            )
            # SSH kinds with well-known creds → ssh; others without creds → docker_exec fallback
            assert result.access_method in ("ssh", "docker_exec")

    def test_all_docker_exec_kinds_detected(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        for kind in DOCKER_EXEC_KINDS:
            nodes = {f"node-{kind}": {"kind": kind}}
            topo = _write_topology(tmp_path, {
                "name": "lab",
                "topology": {"nodes": nodes},
            })
            result = detector.detect(topo, f"node-{kind}", container_id="c1")
            assert result.access_method == "docker_exec"


class TestCredentialExtraction:
    """Test credential precedence: node-level > topology defaults > well-known."""

    def test_node_level_credentials(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {
                "nodes": {
                    "srl1": {
                        "kind": "srl",
                        "env": {"USERNAME": "myuser", "PASSWORD": "mypass"},
                    }
                },
            },
        })
        result = detector.detect(topo, "srl1", container_id="c1", mgmt_ipv4="10.0.0.1")
        assert result.username == "myuser"
        assert result.password == "mypass"
        assert result.access_method == "ssh"

    def test_topology_defaults_credentials(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {
                "defaults": {"env": {"USERNAME": "defuser", "PASSWORD": "defpass"}},
                "nodes": {"srl1": {"kind": "srl"}},
            },
        })
        result = detector.detect(topo, "srl1", container_id="c1", mgmt_ipv4="10.0.0.1")
        assert result.username == "defuser"
        assert result.password == "defpass"
        assert result.access_method == "ssh"

    def test_node_level_overrides_defaults(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {
                "defaults": {"env": {"USERNAME": "defuser", "PASSWORD": "defpass"}},
                "nodes": {
                    "srl1": {
                        "kind": "srl",
                        "env": {"USERNAME": "nodeuser", "PASSWORD": "nodepass"},
                    }
                },
            },
        })
        result = detector.detect(topo, "srl1", container_id="c1", mgmt_ipv4="10.0.0.1")
        assert result.username == "nodeuser"
        assert result.password == "nodepass"

    def test_well_known_srl_credentials(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {"nodes": {"srl1": {"kind": "srl"}}},
        })
        result = detector.detect(topo, "srl1", container_id="c1", mgmt_ipv4="10.0.0.1")
        assert result.username == "admin"
        assert result.password == "NokiaSrl1!"
        assert result.access_method == "ssh"

    def test_well_known_ceos_credentials(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {"nodes": {"ceos1": {"kind": "ceos"}}},
        })
        result = detector.detect(topo, "ceos1", container_id="c1", mgmt_ipv4="10.0.0.1")
        assert result.username == "admin"
        assert result.password == "admin"

    def test_well_known_crpd_credentials(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {"nodes": {"crpd1": {"kind": "crpd"}}},
        })
        result = detector.detect(topo, "crpd1", container_id="c1", mgmt_ipv4="10.0.0.1")
        assert result.username == "root"
        assert result.password == "clab123"

    def test_no_credentials_falls_back_to_docker_exec(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        """SSH kind without any credentials falls back to docker_exec."""
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {"nodes": {"vr1": {"kind": "vr-sros"}}},
        })
        result = detector.detect(topo, "vr1", container_id="c1", mgmt_ipv4="10.0.0.1")
        # vr-sros is an SSH kind but has no well-known credentials
        assert result.access_method == "docker_exec"
        assert result.username is None
        assert result.password is None


class TestConnectionCommandGeneration:
    """Test shell-ready connection command string generation."""

    def test_ssh_command(self, detector: NodeAccessDetector, tmp_path: Path) -> None:
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {"nodes": {"srl1": {"kind": "srl"}}},
        })
        result = detector.detect(topo, "srl1", container_id="c1", mgmt_ipv4="172.20.20.2")
        assert result.connection_command == "ssh admin@172.20.20.2"

    def test_docker_exec_command(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {"nodes": {"host1": {"kind": "linux"}}},
        })
        result = detector.detect(topo, "host1", container_id="clab-test-host1")
        assert result.connection_command == "docker exec -it clab-test-host1 bash"

    def test_clab_connect_command(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        topo = _write_topology(tmp_path, {
            "name": "mylab",
            "topology": {"nodes": {"console1": {"kind": "some-serial-device"}}},
        })
        result = detector.detect(
            topo, "console1", container_id="xyz", lab_name="mylab"
        )
        assert result.connection_command == "containerlab connect --lab-name mylab --node-name console1"

    def test_docker_exec_uses_container_id(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {"nodes": {"host1": {"kind": "linux"}}},
        })
        result = detector.detect(topo, "host1", container_id="abc123deadbeef")
        assert "abc123deadbeef" in result.connection_command

    def test_docker_exec_falls_back_to_node_name(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {"nodes": {"host1": {"kind": "linux"}}},
        })
        result = detector.detect(topo, "host1", container_id="")
        assert "host1" in result.connection_command


class TestDetectAll:
    """Test detect_all() processing of multiple nodes."""

    def test_processes_all_nodes(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        topo = _write_topology(tmp_path, {
            "name": "mixed-lab",
            "topology": {
                "nodes": {
                    "srl1": {"kind": "srl"},
                    "host1": {"kind": "linux", "image": "alpine"},
                    "console1": {"kind": "rare-nos"},
                }
            },
        })
        inspect_data = [
            {"name": "srl1", "container_id": "c1", "ipv4_address": "172.20.20.2/24"},
            {"name": "host1", "container_id": "c2", "ipv4_address": "172.20.20.3/24"},
            {"name": "console1", "container_id": "c3", "ipv4_address": "172.20.20.4/24"},
        ]
        results = detector.detect_all(topo, inspect_data)
        assert len(results) == 3

        by_name = {r.node_name: r for r in results}
        assert by_name["srl1"].access_method == "ssh"
        assert by_name["host1"].access_method == "docker_exec"
        assert by_name["console1"].access_method == "clab_connect"

    def test_strips_cidr_notation(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {"nodes": {"srl1": {"kind": "srl"}}},
        })
        inspect_data = [
            {
                "name": "srl1",
                "container_id": "c1",
                "ipv4_address": "172.20.20.2/24",
                "ipv6_address": "2001:db8::2/64",
            }
        ]
        results = detector.detect_all(topo, inspect_data)
        assert results[0].mgmt_ipv4 == "172.20.20.2"
        assert results[0].mgmt_ipv6 == "2001:db8::2"

    def test_empty_inspect_data(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {"nodes": {"srl1": {"kind": "srl"}}},
        })
        results = detector.detect_all(topo, [])
        assert results == []

    def test_uses_lab_name_from_topology(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        topo = _write_topology(tmp_path, {
            "name": "my-custom-lab",
            "topology": {"nodes": {"serial1": {"kind": "rare-device"}}},
        })
        inspect_data = [
            {"name": "serial1", "container_id": "c1", "ipv4_address": "10.0.0.1/24"}
        ]
        results = detector.detect_all(topo, inspect_data)
        assert "my-custom-lab" in results[0].connection_command

    def test_uses_lab_name_from_inspect_data_when_missing_from_topology(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        topo = _write_topology(tmp_path, {
            "topology": {"nodes": {"serial1": {"kind": "rare-device"}}},
        })
        inspect_data = [
            {
                "name": "serial1",
                "container_id": "c1",
                "ipv4_address": "10.0.0.1/24",
                "lab_name": "fallback-lab",
            }
        ]
        results = detector.detect_all(topo, inspect_data)
        assert "fallback-lab" in results[0].connection_command


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_missing_topology_file(self, detector: NodeAccessDetector) -> None:
        """Gracefully handle non-existent topology file."""
        result = detector.detect(
            "/nonexistent/path.clab.yml",
            "node1",
            container_id="c1",
        )
        # Should fall back to docker_exec when topology can't be loaded
        assert result.access_method == "docker_exec"
        assert result.node_name == "node1"

    def test_node_not_in_topology(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        """Node not defined in topology falls back gracefully."""
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {"nodes": {"srl1": {"kind": "srl"}}},
        })
        result = detector.detect(topo, "nonexistent-node", container_id="c1")
        # Unknown node → empty kind → docker_exec
        assert result.access_method == "docker_exec"

    def test_invalid_yaml_file(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        """Gracefully handle invalid YAML."""
        bad_file = tmp_path / "bad.clab.yml"
        bad_file.write_text(": : invalid [[[")
        result = detector.detect(str(bad_file), "node1", container_id="c1")
        assert result.access_method == "docker_exec"

    def test_topology_with_default_kind(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        """Node without explicit kind uses topology default."""
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {
                "defaults": {"kind": "srl"},
                "nodes": {"node1": {"image": "srlinux:latest"}},
            },
        })
        result = detector.detect(topo, "node1", container_id="c1", mgmt_ipv4="10.0.0.1")
        # Should use default kind "srl" → SSH with well-known creds
        assert result.access_method == "ssh"
        assert result.username == "admin"
        assert result.password == "NokiaSrl1!"

    def test_response_always_has_required_fields(
        self, detector: NodeAccessDetector, tmp_path: Path
    ) -> None:
        """Every response includes node_name, access_method, and connection_command."""
        topo = _write_topology(tmp_path, {
            "name": "test-lab",
            "topology": {"nodes": {"n1": {"kind": "linux"}}},
        })
        result = detector.detect(topo, "n1", container_id="c1")
        assert result.node_name == "n1"
        assert result.access_method in ("ssh", "docker_exec", "clab_connect")
        assert len(result.connection_command) > 0
