"""Unit tests for topology file discovery and parsing."""

import os
from pathlib import Path

import pytest
import yaml

from containerlab_mcp.models import LinkDefinition, NodeDefinition, TopologyDetails
from containerlab_mcp.topology import TopologyParser


@pytest.fixture
def parser() -> TopologyParser:
    return TopologyParser()


@pytest.fixture
def topology_tree(tmp_path: Path) -> Path:
    """Create a directory tree with topology files at various depths."""
    # Depth 0: root
    _write_topo(tmp_path / "root.clab.yml", "root-lab", 2)

    # Depth 1
    sub1 = tmp_path / "level1"
    sub1.mkdir()
    _write_topo(sub1 / "spine.clab.yml", "spine-lab", 4)

    # Depth 2
    sub2 = sub1 / "level2"
    sub2.mkdir()
    _write_topo(sub2 / "leaf.clab.yml", "leaf-lab", 1)

    # Depth 3 (max)
    sub3 = sub2 / "level3"
    sub3.mkdir()
    _write_topo(sub3 / "deep.clab.yml", "deep-lab", 3)

    # Depth 4 (beyond max — should NOT be discovered)
    sub4 = sub3 / "level4"
    sub4.mkdir()
    _write_topo(sub4 / "too-deep.clab.yml", "too-deep-lab", 1)

    return tmp_path


def _write_topo(path: Path, name: str, node_count: int) -> None:
    """Helper to write a minimal topology YAML file."""
    nodes = {f"node{i}": {"kind": "linux", "image": "alpine:latest"} for i in range(node_count)}
    data = {"name": name, "topology": {"nodes": nodes}}
    with open(path, "w") as f:
        yaml.dump(data, f)


class TestDiscover:
    def test_discovers_files_up_to_max_depth(
        self, parser: TopologyParser, topology_tree: Path
    ) -> None:
        results = parser.discover([str(topology_tree)])
        names = {r.lab_name for r in results}

        assert "root-lab" in names
        assert "spine-lab" in names
        assert "leaf-lab" in names
        assert "deep-lab" in names
        assert "too-deep-lab" not in names

    def test_returns_correct_node_counts(
        self, parser: TopologyParser, topology_tree: Path
    ) -> None:
        results = parser.discover([str(topology_tree)])
        by_name = {r.lab_name: r for r in results}

        assert by_name["root-lab"].node_count == 2
        assert by_name["spine-lab"].node_count == 4
        assert by_name["leaf-lab"].node_count == 1
        assert by_name["deep-lab"].node_count == 3

    def test_returns_absolute_paths(
        self, parser: TopologyParser, topology_tree: Path
    ) -> None:
        results = parser.discover([str(topology_tree)])
        for entry in results:
            assert os.path.isabs(entry.path)
            assert entry.path.endswith(".clab.yml")

    def test_skips_unreadable_directory(
        self, parser: TopologyParser, tmp_path: Path
    ) -> None:
        # Create a readable topology
        _write_topo(tmp_path / "visible.clab.yml", "visible", 1)

        # Create an unreadable subdirectory
        restricted = tmp_path / "restricted"
        restricted.mkdir()
        _write_topo(restricted / "hidden.clab.yml", "hidden", 1)
        os.chmod(restricted, 0o000)

        try:
            results = parser.discover([str(tmp_path)])
            names = {r.lab_name for r in results}
            assert "visible" in names
            assert "hidden" not in names
        finally:
            os.chmod(restricted, 0o755)

    def test_skips_invalid_yaml(
        self, parser: TopologyParser, tmp_path: Path
    ) -> None:
        _write_topo(tmp_path / "good.clab.yml", "good-lab", 1)
        (tmp_path / "bad.clab.yml").write_text(": : invalid [[[")

        results = parser.discover([str(tmp_path)])
        names = {r.lab_name for r in results}
        assert "good-lab" in names
        assert len(results) == 1

    def test_non_existent_search_path(self, parser: TopologyParser) -> None:
        results = parser.discover(["/nonexistent/xyz/abc"])
        assert results == []

    def test_multiple_search_paths(
        self, parser: TopologyParser, tmp_path: Path
    ) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()

        _write_topo(dir_a / "lab-a.clab.yml", "lab-a", 2)
        _write_topo(dir_b / "lab-b.clab.yml", "lab-b", 3)

        results = parser.discover([str(dir_a), str(dir_b)])
        names = {r.lab_name for r in results}
        assert names == {"lab-a", "lab-b"}

    def test_fallback_name_when_name_field_missing(
        self, parser: TopologyParser, tmp_path: Path
    ) -> None:
        data = {"topology": {"nodes": {"n1": {"kind": "linux"}}}}
        with open(tmp_path / "mylab.clab.yml", "w") as f:
            yaml.dump(data, f)

        results = parser.discover([str(tmp_path)])
        assert len(results) == 1
        assert results[0].lab_name == "mylab"

    def test_custom_max_depth(
        self, parser: TopologyParser, tmp_path: Path
    ) -> None:
        # Create file at depth 1
        sub = tmp_path / "sub"
        sub.mkdir()
        _write_topo(sub / "d1.clab.yml", "depth1", 1)

        # With max_depth=0, only root files should be found
        _write_topo(tmp_path / "root.clab.yml", "root", 1)
        results = parser.discover([str(tmp_path)], max_depth=0)
        names = {r.lab_name for r in results}
        assert "root" in names
        assert "depth1" not in names

    def test_zero_nodes_topology(
        self, parser: TopologyParser, tmp_path: Path
    ) -> None:
        data = {"name": "empty-lab", "topology": {"nodes": {}}}
        with open(tmp_path / "empty.clab.yml", "w") as f:
            yaml.dump(data, f)

        results = parser.discover([str(tmp_path)])
        assert len(results) == 1
        assert results[0].node_count == 0
        assert results[0].lab_name == "empty-lab"


class TestParse:
    def test_parses_full_topology(
        self, parser: TopologyParser, tmp_path: Path
    ) -> None:
        data = {
            "name": "my-lab",
            "topology": {
                "defaults": {"kind": "linux"},
                "nodes": {
                    "node1": {"kind": "srl", "image": "ghcr.io/srl:latest", "startup-config": "/cfg.cfg"},
                    "node2": {},
                },
                "links": [
                    {"endpoints": ["node1:eth1", "node2:eth1"]},
                    {"endpoints": ["node1:eth2", "node2:eth2"]},
                ],
            },
        }
        topo_file = tmp_path / "lab.clab.yml"
        with open(topo_file, "w") as f:
            yaml.dump(data, f)

        result = parser.parse(str(topo_file))

        assert result.name == "my-lab"
        assert result.kind == "linux"
        assert len(result.nodes) == 2
        assert len(result.links) == 2

        node1 = next(n for n in result.nodes if n.name == "node1")
        assert node1.kind == "srl"
        assert node1.image == "ghcr.io/srl:latest"
        assert node1.startup_config == "/cfg.cfg"

        node2 = next(n for n in result.nodes if n.name == "node2")
        assert node2.kind == "linux"  # Falls back to default kind
        assert node2.image is None
        assert node2.startup_config is None

        assert result.links[0].endpoints == ["node1:eth1", "node2:eth1"]
        assert result.links[1].endpoints == ["node1:eth2", "node2:eth2"]

    def test_raises_file_not_found(self, parser: TopologyParser) -> None:
        with pytest.raises(FileNotFoundError, match="Topology file not found"):
            parser.parse("/nonexistent/path/topo.clab.yml")

    def test_raises_value_error_on_invalid_yaml(
        self, parser: TopologyParser, tmp_path: Path
    ) -> None:
        bad_file = tmp_path / "bad.clab.yml"
        bad_file.write_text(": : invalid [[[")

        with pytest.raises(ValueError, match="Failed to parse YAML"):
            parser.parse(str(bad_file))

    def test_raises_value_error_when_not_a_mapping(
        self, parser: TopologyParser, tmp_path: Path
    ) -> None:
        bad_file = tmp_path / "list.clab.yml"
        bad_file.write_text("- item1\n- item2\n")

        with pytest.raises(ValueError, match="does not contain a YAML mapping"):
            parser.parse(str(bad_file))

    def test_raises_value_error_when_topology_section_missing(
        self, parser: TopologyParser, tmp_path: Path
    ) -> None:
        bad_file = tmp_path / "no-topo.clab.yml"
        with open(bad_file, "w") as f:
            yaml.dump({"name": "lab", "other": "stuff"}, f)

        with pytest.raises(ValueError, match="missing or invalid 'topology' section"):
            parser.parse(str(bad_file))

    def test_topology_without_links(
        self, parser: TopologyParser, tmp_path: Path
    ) -> None:
        data = {
            "name": "no-links",
            "topology": {
                "nodes": {"node1": {"kind": "linux"}},
            },
        }
        topo_file = tmp_path / "lab.clab.yml"
        with open(topo_file, "w") as f:
            yaml.dump(data, f)

        result = parser.parse(str(topo_file))
        assert result.name == "no-links"
        assert len(result.nodes) == 1
        assert result.links == []
        assert result.kind is None

    def test_fallback_name_from_filename(
        self, parser: TopologyParser, tmp_path: Path
    ) -> None:
        data = {"topology": {"nodes": {"n1": {"kind": "linux"}}}}
        topo_file = tmp_path / "mylab.clab.yml"
        with open(topo_file, "w") as f:
            yaml.dump(data, f)

        result = parser.parse(str(topo_file))
        assert result.name == "mylab"

    def test_node_with_null_config(
        self, parser: TopologyParser, tmp_path: Path
    ) -> None:
        """Nodes with None/null config should be handled gracefully."""
        data = {
            "name": "null-node-lab",
            "topology": {
                "defaults": {"kind": "linux"},
                "nodes": {"node1": None},
            },
        }
        topo_file = tmp_path / "lab.clab.yml"
        with open(topo_file, "w") as f:
            yaml.dump(data, f)

        result = parser.parse(str(topo_file))
        assert len(result.nodes) == 1
        assert result.nodes[0].name == "node1"
        assert result.nodes[0].kind == "linux"


class TestGetNodeKinds:
    def test_returns_node_kind_mapping(
        self, parser: TopologyParser, tmp_path: Path
    ) -> None:
        data = {
            "name": "kind-lab",
            "topology": {
                "defaults": {"kind": "linux"},
                "nodes": {
                    "router1": {"kind": "srl"},
                    "router2": {"kind": "ceos"},
                    "host1": {},
                },
            },
        }
        topo_file = tmp_path / "lab.clab.yml"
        with open(topo_file, "w") as f:
            yaml.dump(data, f)

        kinds = parser.get_node_kinds(str(topo_file))

        assert kinds == {
            "router1": "srl",
            "router2": "ceos",
            "host1": "linux",
        }

    def test_uses_default_kind_when_node_has_no_kind(
        self, parser: TopologyParser, tmp_path: Path
    ) -> None:
        data = {
            "name": "default-kind-lab",
            "topology": {
                "defaults": {"kind": "nokia_srlinux"},
                "nodes": {
                    "spine1": {},
                    "leaf1": {},
                },
            },
        }
        topo_file = tmp_path / "lab.clab.yml"
        with open(topo_file, "w") as f:
            yaml.dump(data, f)

        kinds = parser.get_node_kinds(str(topo_file))
        assert kinds == {"spine1": "nokia_srlinux", "leaf1": "nokia_srlinux"}

    def test_raises_file_not_found(self, parser: TopologyParser) -> None:
        with pytest.raises(FileNotFoundError):
            parser.get_node_kinds("/nonexistent/path.clab.yml")

    def test_empty_kind_when_no_default(
        self, parser: TopologyParser, tmp_path: Path
    ) -> None:
        data = {
            "name": "no-default",
            "topology": {
                "nodes": {"host1": {}},
            },
        }
        topo_file = tmp_path / "lab.clab.yml"
        with open(topo_file, "w") as f:
            yaml.dump(data, f)

        kinds = parser.get_node_kinds(str(topo_file))
        assert kinds == {"host1": ""}
