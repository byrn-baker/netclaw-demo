"""Topology file discovery and parsing for ContainerLab MCP Server."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml

from containerlab_mcp.models import (
    LinkDefinition,
    NodeDefinition,
    TopologyDetails,
    TopologyEntry,
)

logger = logging.getLogger(__name__)


class TopologyParser:
    """Reads and validates ContainerLab topology YAML files."""

    def discover(
        self, search_paths: list[str], max_depth: int = 3
    ) -> list[TopologyEntry]:
        """Recursively scan directories for .clab.yml files up to max_depth levels.

        Args:
            search_paths: List of directory paths to scan.
            max_depth: Maximum directory depth to recurse (default 3).

        Returns:
            List of TopologyEntry objects with absolute paths, lab names,
            and node counts for each discovered topology file.
        """
        entries: list[TopologyEntry] = []

        for search_path in search_paths:
            root = Path(search_path).resolve()
            if not root.is_dir():
                logger.warning(
                    "Search path is not a directory, skipping: %s", search_path
                )
                continue
            self._scan_directory(root, 0, max_depth, entries)

        return entries

    def _scan_directory(
        self,
        directory: Path,
        current_depth: int,
        max_depth: int,
        entries: list[TopologyEntry],
    ) -> None:
        """Recursively scan a directory for topology files.

        Args:
            directory: The directory to scan.
            current_depth: Current recursion depth (0 = root search path).
            max_depth: Maximum depth to recurse.
            entries: Accumulator list for discovered entries.
        """
        if current_depth > max_depth:
            return

        try:
            dir_entries = list(os.scandir(directory))
        except PermissionError:
            logger.warning("Cannot read directory, skipping: %s", directory)
            return
        except OSError as exc:
            logger.warning("Error reading directory %s: %s", directory, exc)
            return

        for entry in dir_entries:
            if entry.is_file() and entry.name.endswith(".clab.yml"):
                topo_entry = self._parse_topology_entry(Path(entry.path))
                if topo_entry is not None:
                    entries.append(topo_entry)
            elif entry.is_dir(follow_symlinks=False):
                self._scan_directory(
                    Path(entry.path), current_depth + 1, max_depth, entries
                )

    def parse(self, path: str) -> TopologyDetails:
        """Parse a topology YAML file and return structured details.

        Args:
            path: Path to the .clab.yml topology file.

        Returns:
            TopologyDetails with name, nodes, links, and optional kind.

        Raises:
            FileNotFoundError: If the topology file does not exist.
            ValueError: If the file cannot be parsed or has invalid structure.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Topology file not found: {path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise ValueError(f"Failed to parse YAML in {path}: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError(
                f"Topology file does not contain a YAML mapping: {path}"
            )

        # Extract topology name
        name = data.get("name", "")
        if not name:
            name = file_path.stem.replace(".clab", "")

        # Extract topology section
        topology_section = data.get("topology")
        if not isinstance(topology_section, dict):
            raise ValueError(
                f"Topology file missing or invalid 'topology' section: {path}"
            )

        # Extract default kind
        defaults = topology_section.get("defaults", {})
        default_kind: str | None = None
        if isinstance(defaults, dict):
            default_kind = defaults.get("kind")

        # Extract nodes
        nodes_data = topology_section.get("nodes", {})
        if not isinstance(nodes_data, dict):
            raise ValueError(
                f"Topology 'nodes' section is not a mapping: {path}"
            )

        nodes: list[NodeDefinition] = []
        for node_name, node_config in nodes_data.items():
            if not isinstance(node_config, dict):
                node_config = {}

            kind = node_config.get("kind", default_kind or "")
            image = node_config.get("image")
            startup_config = node_config.get("startup-config")

            nodes.append(
                NodeDefinition(
                    name=str(node_name),
                    kind=str(kind),
                    image=image,
                    startup_config=startup_config,
                )
            )

        # Extract links
        links_data = topology_section.get("links", [])
        if not isinstance(links_data, list):
            raise ValueError(
                f"Topology 'links' section is not a list: {path}"
            )

        links: list[LinkDefinition] = []
        for link_entry in links_data:
            if isinstance(link_entry, dict) and "endpoints" in link_entry:
                endpoints = link_entry["endpoints"]
                if isinstance(endpoints, list):
                    links.append(
                        LinkDefinition(endpoints=[str(ep) for ep in endpoints])
                    )

        return TopologyDetails(
            name=str(name),
            nodes=nodes,
            links=links,
            kind=default_kind,
        )

    def get_node_kinds(self, path: str) -> dict[str, str]:
        """Return a mapping of node name to kind for all nodes in a topology.

        If a node does not specify its own kind, the topology default kind is used.

        Args:
            path: Path to the .clab.yml topology file.

        Returns:
            Dictionary mapping node_name → kind string.

        Raises:
            FileNotFoundError: If the topology file does not exist.
            ValueError: If the file cannot be parsed or has invalid structure.
        """
        details = self.parse(path)
        return {node.name: node.kind for node in details.nodes}

    def _parse_topology_entry(self, path: Path) -> TopologyEntry | None:
        """Extract minimal metadata from a topology file.

        Args:
            path: Absolute path to the .clab.yml file.

        Returns:
            TopologyEntry with lab name and node count, or None if parsing fails.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as exc:
            logger.warning("Failed to parse topology file %s: %s", path, exc)
            return None

        if not isinstance(data, dict):
            logger.warning(
                "Topology file does not contain a YAML mapping: %s", path
            )
            return None

        lab_name = data.get("name", "")
        if not lab_name:
            # Fall back to filename without extension
            lab_name = path.stem.replace(".clab", "")

        topology_section = data.get("topology", {})
        nodes = topology_section.get("nodes", {}) if isinstance(topology_section, dict) else {}
        node_count = len(nodes) if isinstance(nodes, dict) else 0

        return TopologyEntry(
            path=str(path),
            lab_name=str(lab_name),
            node_count=node_count,
        )
