"""Node access detection and credential extraction for ContainerLab MCP Server."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from containerlab_mcp.models import NodeAccessInfo

logger = logging.getLogger(__name__)

# Kinds that use SSH access (network OS nodes)
SSH_KINDS: set[str] = {
    "srl",
    "ceos",
    "crpd",
    "vr-sros",
    "vr-xrv9k",
    "vr-csr",
    "vr-nxos",
    "sonic-vs",
}

# Kinds that use docker exec access (Linux containers)
DOCKER_EXEC_KINDS: set[str] = {
    "linux",
    "bridge",
    "ovs-bridge",
    "host",
}

# Well-known default credentials per kind
WELL_KNOWN_CREDENTIALS: dict[str, tuple[str, str]] = {
    "srl": ("admin", "NokiaSrl1!"),
    "ceos": ("admin", "admin"),
    "crpd": ("root", "clab123"),
}


class NodeAccessDetector:
    """Determines how to connect to each node based on topology definitions."""

    def detect(
        self,
        topology_path: str,
        node_name: str,
        container_id: str = "",
        mgmt_ipv4: str | None = None,
        mgmt_ipv6: str | None = None,
        lab_name: str | None = None,
    ) -> NodeAccessInfo:
        """Detect access method for a single node.

        Args:
            topology_path: Path to the .clab.yml topology file.
            node_name: Name of the node to detect access for.
            container_id: Docker container ID or name.
            mgmt_ipv4: Management IPv4 address from inspect data.
            mgmt_ipv6: Management IPv6 address from inspect data.
            lab_name: Lab name for clab_connect commands.

        Returns:
            NodeAccessInfo with detected access method and connection command.
        """
        topology_data = self._load_topology(topology_path)
        kind = self._get_node_kind(topology_data, node_name)
        access_method = self._determine_access_method(kind)

        username: str | None = None
        password: str | None = None

        if access_method == "ssh":
            username, password = self._extract_credentials(
                topology_data, node_name, kind
            )
            # Fall back to docker_exec if no credentials found
            if username is None or password is None:
                access_method = "docker_exec"
                username = None
                password = None

        connection_command = self._generate_connection_command(
            access_method=access_method,
            node_name=node_name,
            container_id=container_id,
            mgmt_ipv4=mgmt_ipv4,
            username=username,
            lab_name=lab_name,
        )

        return NodeAccessInfo(
            node_name=node_name,
            container_id=container_id,
            mgmt_ipv4=mgmt_ipv4,
            mgmt_ipv6=mgmt_ipv6,
            access_method=access_method,
            connection_command=connection_command,
            username=username,
            password=password,
        )

    def detect_all(
        self,
        topology_path: str,
        inspect_data: list[dict[str, Any]],
    ) -> list[NodeAccessInfo]:
        """Detect access methods for all nodes in a topology.

        Args:
            topology_path: Path to the .clab.yml topology file.
            inspect_data: List of dicts from `clab inspect` parsed output.
                Each dict should contain keys like 'name', 'container_id',
                'ipv4_address', 'ipv6_address', 'lab_name'.

        Returns:
            List of NodeAccessInfo objects for all nodes.
        """
        topology_data = self._load_topology(topology_path)
        lab_name = self._extract_lab_name(topology_data, inspect_data)
        results: list[NodeAccessInfo] = []

        for node_data in inspect_data:
            node_name = node_data.get("name", "")
            container_id = node_data.get("container_id", "")
            mgmt_ipv4 = node_data.get("ipv4_address")
            mgmt_ipv6 = node_data.get("ipv6_address")

            # Strip CIDR notation if present (e.g., "172.20.20.2/24" → "172.20.20.2")
            if mgmt_ipv4 and "/" in mgmt_ipv4:
                mgmt_ipv4 = mgmt_ipv4.split("/")[0]
            if mgmt_ipv6 and "/" in mgmt_ipv6:
                mgmt_ipv6 = mgmt_ipv6.split("/")[0]

            kind = self._get_node_kind(topology_data, node_name)
            access_method = self._determine_access_method(kind)

            username: str | None = None
            password: str | None = None

            if access_method == "ssh":
                username, password = self._extract_credentials(
                    topology_data, node_name, kind
                )
                if username is None or password is None:
                    access_method = "docker_exec"
                    username = None
                    password = None

            connection_command = self._generate_connection_command(
                access_method=access_method,
                node_name=node_name,
                container_id=container_id,
                mgmt_ipv4=mgmt_ipv4,
                username=username,
                lab_name=lab_name,
            )

            results.append(
                NodeAccessInfo(
                    node_name=node_name,
                    container_id=container_id,
                    mgmt_ipv4=mgmt_ipv4,
                    mgmt_ipv6=mgmt_ipv6,
                    access_method=access_method,
                    connection_command=connection_command,
                    username=username,
                    password=password,
                )
            )

        return results

    def _load_topology(self, topology_path: str) -> dict[str, Any]:
        """Load and return the topology YAML data."""
        path = Path(topology_path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as exc:
            logger.warning("Failed to load topology file %s: %s", topology_path, exc)
            return {}

        if not isinstance(data, dict):
            return {}
        return data

    def _get_node_kind(self, topology_data: dict[str, Any], node_name: str) -> str:
        """Get the kind for a node from topology data.

        Checks node-level kind first, then topology-level default kind.
        """
        topology_section = topology_data.get("topology", {})
        if not isinstance(topology_section, dict):
            return ""

        # Check node-level kind
        nodes = topology_section.get("nodes", {})
        if isinstance(nodes, dict):
            node_config = nodes.get(node_name, {})
            if isinstance(node_config, dict):
                node_kind = node_config.get("kind", "")
                if node_kind:
                    return str(node_kind)

        # Fall back to topology-level default kind
        defaults = topology_section.get("defaults", {})
        if isinstance(defaults, dict):
            default_kind = defaults.get("kind", "")
            if default_kind:
                return str(default_kind)

        return ""

    def _determine_access_method(self, kind: str) -> str:
        """Map a node kind to an access method."""
        if kind in SSH_KINDS:
            return "ssh"
        if kind in DOCKER_EXEC_KINDS:
            return "docker_exec"
        if kind:
            # Any other kind uses clab_connect (serial/console)
            return "clab_connect"
        # Unknown kind with no info defaults to docker_exec
        return "docker_exec"

    def _extract_credentials(
        self,
        topology_data: dict[str, Any],
        node_name: str,
        kind: str,
    ) -> tuple[str | None, str | None]:
        """Extract credentials with precedence: node-level > topology defaults > well-known.

        Returns:
            Tuple of (username, password) or (None, None) if not found.
        """
        topology_section = topology_data.get("topology", {})
        if not isinstance(topology_section, dict):
            return self._get_well_known_credentials(kind)

        # 1. Check node-level credentials
        nodes = topology_section.get("nodes", {})
        if isinstance(nodes, dict):
            node_config = nodes.get(node_name, {})
            if isinstance(node_config, dict):
                node_env = node_config.get("env", {})
                if isinstance(node_env, dict):
                    username = node_env.get("USERNAME") or node_env.get("USER")
                    password = node_env.get("PASSWORD") or node_env.get("PASS")
                    if username and password:
                        return (str(username), str(password))

        # 2. Check topology defaults credentials
        defaults = topology_section.get("defaults", {})
        if isinstance(defaults, dict):
            defaults_env = defaults.get("env", {})
            if isinstance(defaults_env, dict):
                username = defaults_env.get("USERNAME") or defaults_env.get("USER")
                password = defaults_env.get("PASSWORD") or defaults_env.get("PASS")
                if username and password:
                    return (str(username), str(password))

        # 3. Fall back to well-known defaults per kind
        return self._get_well_known_credentials(kind)

    def _get_well_known_credentials(self, kind: str) -> tuple[str | None, str | None]:
        """Get well-known default credentials for a kind."""
        if kind in WELL_KNOWN_CREDENTIALS:
            return WELL_KNOWN_CREDENTIALS[kind]
        return (None, None)

    def _generate_connection_command(
        self,
        access_method: str,
        node_name: str,
        container_id: str,
        mgmt_ipv4: str | None,
        username: str | None,
        lab_name: str | None,
    ) -> str:
        """Generate a shell-ready connection command string."""
        if access_method == "ssh":
            if username and mgmt_ipv4:
                return f"ssh {username}@{mgmt_ipv4}"
            # Fallback if we have SSH method but missing info
            return f"ssh {username or 'admin'}@{mgmt_ipv4 or node_name}"

        if access_method == "docker_exec":
            target = container_id or node_name
            return f"docker exec -it {target} bash"

        if access_method == "clab_connect":
            lab = lab_name or "unknown"
            return f"containerlab connect --lab-name {lab} --node-name {node_name}"

        # Should not reach here, but provide a sensible fallback
        return f"docker exec -it {container_id or node_name} bash"

    def _extract_lab_name(
        self,
        topology_data: dict[str, Any],
        inspect_data: list[dict[str, Any]],
    ) -> str:
        """Extract lab name from topology data or inspect data."""
        # Try topology file first
        lab_name = topology_data.get("name", "")
        if lab_name:
            return str(lab_name)

        # Try from inspect data
        if inspect_data:
            first = inspect_data[0]
            lab = first.get("lab_name", "") or first.get("labname", "")
            if lab:
                return str(lab)

        return "unknown"
