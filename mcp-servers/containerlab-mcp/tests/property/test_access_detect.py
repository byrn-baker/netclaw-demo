"""Property-based tests for node access detection.

Feature: containerlab-mcp
Property 6: Node Access Method Detection
Property 7: Credential Precedence

Validates: Requirements 3.1, 3.2, 3.3, 3.4
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from containerlab_mcp.access import (
    DOCKER_EXEC_KINDS,
    SSH_KINDS,
    WELL_KNOWN_CREDENTIALS,
    NodeAccessDetector,
)


# --- Strategies ---

# Node names: alphanumeric identifiers
node_name_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    min_size=1,
    max_size=20,
).filter(lambda s: s[0].isalpha())

# Username/password strings (non-empty, printable, no special YAML chars)
credential_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-!@#"),
    min_size=1,
    max_size=30,
).filter(lambda s: len(s.strip()) > 0)

# IPv4 addresses
ipv4_st = st.builds(
    lambda a, b, c, d: f"{a}.{b}.{c}.{d}",
    st.integers(min_value=1, max_value=254),
    st.integers(min_value=0, max_value=254),
    st.integers(min_value=0, max_value=254),
    st.integers(min_value=1, max_value=254),
)

# SSH-capable kinds
ssh_kind_st = st.sampled_from(sorted(SSH_KINDS))

# Docker exec kinds
docker_exec_kind_st = st.sampled_from(sorted(DOCKER_EXEC_KINDS))

# Kinds that result in clab_connect (not in SSH or docker_exec sets)
clab_connect_kind_st = st.sampled_from(["rare", "serial", "mystic", "custom-nos"])

# Lab name strategy
lab_name_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    min_size=1,
    max_size=15,
).filter(lambda s: s[0].isalpha())


def _write_topology(
    tmp_dir: Path,
    node_name: str,
    kind: str,
    node_env: dict | None = None,
    defaults_env: dict | None = None,
    lab_name: str = "testlab",
) -> str:
    """Helper: write a minimal topology YAML and return its path."""
    topology: dict = {
        "name": lab_name,
        "topology": {
            "nodes": {
                node_name: {
                    "kind": kind,
                    "image": f"{kind}:latest",
                }
            },
        },
    }

    if node_env:
        topology["topology"]["nodes"][node_name]["env"] = node_env

    if defaults_env:
        topology["topology"]["defaults"] = {"env": defaults_env}

    topo_file = tmp_dir / "test.clab.yml"
    topo_file.write_text(yaml.dump(topology, default_flow_style=False))
    return str(topo_file)


# --- Property 6: Node Access Method Detection ---
# Feature: containerlab-mcp, Property 6: Node Access Method Detection


class TestNodeAccessMethodDetection:
    """Property 6: Access method matches expected pattern for node kind.

    For any topology with nodes of known kinds, the detected access method SHALL
    match the expected pattern for that kind. The response SHALL always include
    node_name, access_method, and a non-empty connection_command string. If the
    access method is SSH, username and password SHALL be populated.
    """

    @given(
        node_name=node_name_st,
        kind=ssh_kind_st,
        ipv4=ipv4_st,
    )
    @settings(max_examples=100)
    def test_ssh_kinds_detected_as_ssh(
        self, node_name: str, kind: str, ipv4: str
    ) -> None:
        """Validates: Requirements 3.1, 3.2

        SSH kinds (srl, ceos, crpd, vr-sros, etc.) SHALL be detected as SSH
        access method with credentials populated.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            # SSH kinds with well-known credentials will have credentials populated
            topo_path = _write_topology(Path(tmp_dir), node_name, kind)

            detector = NodeAccessDetector()
            result = detector.detect(
                topology_path=topo_path,
                node_name=node_name,
                container_id=f"clab-{node_name}",
                mgmt_ipv4=ipv4,
            )

            # Response always includes these fields
            assert result.node_name == node_name
            assert result.connection_command != ""

            # If the kind has well-known credentials, access_method should be SSH
            if kind in WELL_KNOWN_CREDENTIALS:
                assert result.access_method == "ssh"
                assert result.username is not None
                assert result.password is not None
            else:
                # SSH kinds without well-known creds and no topology creds
                # fall back to docker_exec per the implementation
                assert result.access_method in ("ssh", "docker_exec")

    @given(
        node_name=node_name_st,
        kind=ssh_kind_st,
        username=credential_st,
        password=credential_st,
        ipv4=ipv4_st,
    )
    @settings(max_examples=100)
    def test_ssh_kinds_with_explicit_creds(
        self, node_name: str, kind: str, username: str, password: str, ipv4: str
    ) -> None:
        """Validates: Requirements 3.1, 3.2, 3.3

        SSH kinds with explicit credentials in topology SHALL be detected as SSH
        with those credentials populated.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            node_env = {"USERNAME": username, "PASSWORD": password}
            topo_path = _write_topology(
                Path(tmp_dir), node_name, kind, node_env=node_env
            )

            detector = NodeAccessDetector()
            result = detector.detect(
                topology_path=topo_path,
                node_name=node_name,
                container_id=f"clab-{node_name}",
                mgmt_ipv4=ipv4,
            )

            assert result.node_name == node_name
            assert result.access_method == "ssh"
            assert result.connection_command != ""
            assert result.username == username
            assert result.password == password

    @given(
        node_name=node_name_st,
        kind=docker_exec_kind_st,
    )
    @settings(max_examples=100)
    def test_docker_exec_kinds_detected(
        self, node_name: str, kind: str
    ) -> None:
        """Validates: Requirements 3.1, 3.2

        Docker exec kinds (linux, bridge, ovs-bridge, host) SHALL be detected
        as docker_exec access method.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            topo_path = _write_topology(Path(tmp_dir), node_name, kind)

            detector = NodeAccessDetector()
            result = detector.detect(
                topology_path=topo_path,
                node_name=node_name,
                container_id=f"clab-{node_name}",
            )

            assert result.node_name == node_name
            assert result.access_method == "docker_exec"
            assert result.connection_command != ""
            # docker_exec nodes should not have SSH credentials
            assert result.username is None
            assert result.password is None

    @given(
        node_name=node_name_st,
        kind=clab_connect_kind_st,
    )
    @settings(max_examples=100)
    def test_clab_connect_kinds_detected(
        self, node_name: str, kind: str
    ) -> None:
        """Validates: Requirements 3.1, 3.2

        Rare/serial/unknown-but-specified kinds SHALL be detected as
        clab_connect access method.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            topo_path = _write_topology(
                Path(tmp_dir), node_name, kind, lab_name="mylab"
            )

            detector = NodeAccessDetector()
            result = detector.detect(
                topology_path=topo_path,
                node_name=node_name,
                container_id=f"clab-{node_name}",
                lab_name="mylab",
            )

            assert result.node_name == node_name
            assert result.access_method == "clab_connect"
            assert result.connection_command != ""

    @given(
        node_name=node_name_st,
        kind=st.sampled_from(sorted(SSH_KINDS | DOCKER_EXEC_KINDS) + ["rare", "serial"]),
        ipv4=ipv4_st,
    )
    @settings(max_examples=100)
    def test_response_always_includes_required_fields(
        self, node_name: str, kind: str, ipv4: str
    ) -> None:
        """Validates: Requirements 3.3

        The response SHALL always include node_name, access_method, and a
        non-empty connection_command string regardless of kind.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            topo_path = _write_topology(Path(tmp_dir), node_name, kind)

            detector = NodeAccessDetector()
            result = detector.detect(
                topology_path=topo_path,
                node_name=node_name,
                container_id=f"clab-{node_name}",
                mgmt_ipv4=ipv4,
                lab_name="testlab",
            )

            assert result.node_name == node_name
            assert result.access_method in ("ssh", "docker_exec", "clab_connect")
            assert len(result.connection_command) > 0


# --- Property 7: Credential Precedence ---
# Feature: containerlab-mcp, Property 7: Credential Precedence


class TestCredentialPrecedence:
    """Property 7: Node-level credentials override topology defaults.

    For any topology where credentials are defined at both node and defaults level,
    the response SHALL use node-level credentials. If only defaults exist, those
    SHALL be used. If no credentials at either level, access falls back to docker_exec.
    """

    @given(
        node_name=node_name_st,
        kind=ssh_kind_st,
        node_user=credential_st,
        node_pass=credential_st,
        default_user=credential_st,
        default_pass=credential_st,
        ipv4=ipv4_st,
    )
    @settings(max_examples=100)
    def test_node_level_wins_over_defaults(
        self,
        node_name: str,
        kind: str,
        node_user: str,
        node_pass: str,
        default_user: str,
        default_pass: str,
        ipv4: str,
    ) -> None:
        """Validates: Requirements 3.4

        When credentials exist at both node and defaults level, node-level wins.
        """
        # Ensure they differ so we can verify precedence
        assume(node_user != default_user or node_pass != default_pass)

        with tempfile.TemporaryDirectory() as tmp_dir:
            node_env = {"USERNAME": node_user, "PASSWORD": node_pass}
            defaults_env = {"USERNAME": default_user, "PASSWORD": default_pass}
            topo_path = _write_topology(
                Path(tmp_dir), node_name, kind,
                node_env=node_env, defaults_env=defaults_env,
            )

            detector = NodeAccessDetector()
            result = detector.detect(
                topology_path=topo_path,
                node_name=node_name,
                container_id=f"clab-{node_name}",
                mgmt_ipv4=ipv4,
            )

            assert result.access_method == "ssh"
            assert result.username == node_user
            assert result.password == node_pass

    @given(
        node_name=node_name_st,
        kind=ssh_kind_st,
        default_user=credential_st,
        default_pass=credential_st,
        ipv4=ipv4_st,
    )
    @settings(max_examples=100)
    def test_defaults_used_when_no_node_creds(
        self,
        node_name: str,
        kind: str,
        default_user: str,
        default_pass: str,
        ipv4: str,
    ) -> None:
        """Validates: Requirements 3.4

        When credentials exist only at defaults level, those SHALL be used.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            defaults_env = {"USERNAME": default_user, "PASSWORD": default_pass}
            topo_path = _write_topology(
                Path(tmp_dir), node_name, kind,
                node_env=None, defaults_env=defaults_env,
            )

            detector = NodeAccessDetector()
            result = detector.detect(
                topology_path=topo_path,
                node_name=node_name,
                container_id=f"clab-{node_name}",
                mgmt_ipv4=ipv4,
            )

            assert result.access_method == "ssh"
            assert result.username == default_user
            assert result.password == default_pass

    @given(
        node_name=node_name_st,
        kind=ssh_kind_st,
        ipv4=ipv4_st,
    )
    @settings(max_examples=100)
    def test_no_creds_falls_back_to_docker_exec(
        self,
        node_name: str,
        kind: str,
        ipv4: str,
    ) -> None:
        """Validates: Requirements 3.4

        When no credentials at node or defaults level (and no well-known creds),
        access falls back to docker_exec.
        """
        # Use kinds that don't have well-known credentials
        assume(kind not in WELL_KNOWN_CREDENTIALS)

        with tempfile.TemporaryDirectory() as tmp_dir:
            topo_path = _write_topology(
                Path(tmp_dir), node_name, kind,
                node_env=None, defaults_env=None,
            )

            detector = NodeAccessDetector()
            result = detector.detect(
                topology_path=topo_path,
                node_name=node_name,
                container_id=f"clab-{node_name}",
                mgmt_ipv4=ipv4,
            )

            assert result.access_method == "docker_exec"
            assert result.username is None
            assert result.password is None
