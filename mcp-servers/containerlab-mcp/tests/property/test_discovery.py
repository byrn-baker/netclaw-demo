# Feature: containerlab-mcp, Property 3: Topology Discovery Depth Limit
# Feature: containerlab-mcp, Property 4: Topology Parsing Round-Trip
"""Property-based tests for topology discovery and parsing.

**Validates: Requirements 2.1, 2.2, 2.3**

Property 3: For any directory tree containing `.clab.yml` files at various depths,
the `list_topologies` tool SHALL discover all topology files at depth <= 3 relative
to the search path root AND SHALL NOT discover any topology files at depth > 3.
Every discovered entry SHALL include a valid absolute path, a non-empty lab name,
and a node count >= 0.

Property 4: For any valid topology structure (with valid node definitions, link
definitions, and optional kind), serializing it to YAML and then parsing it with
`get_topology_details` SHALL produce a result where the node names, node kinds,
link endpoints, and topology name match the original structure.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import yaml
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from containerlab_mcp.topology import TopologyParser


# --- Strategies ---


def lab_name_strategy() -> st.SearchStrategy[str]:
    """Generate valid lab names (non-empty, no special chars that break YAML)."""
    return st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_"),
        min_size=1,
        max_size=16,
    ).filter(lambda s: s[0].isalpha())


def node_name_strategy() -> st.SearchStrategy[str]:
    """Generate valid node names."""
    return st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Nd"), whitelist_characters="-_"),
        min_size=1,
        max_size=12,
    ).filter(lambda s: s[0].isalpha())


def kind_strategy() -> st.SearchStrategy[str]:
    """Generate valid node kind strings."""
    return st.sampled_from(["srl", "ceos", "crpd", "linux", "bridge", "vr-sros", "sonic-vs"])


def endpoint_strategy(node_names: list[str]) -> st.SearchStrategy[list[str]]:
    """Generate a valid link endpoint pair referencing existing nodes."""
    return st.tuples(
        st.sampled_from(node_names),
        st.sampled_from(node_names),
    ).filter(lambda t: t[0] != t[1]).map(
        lambda t: [f"{t[0]}:eth1", f"{t[1]}:eth1"]
    )


def depth_positions_strategy(max_depth: int = 5) -> st.SearchStrategy[list[int]]:
    """Generate a list of depth values (0 to max_depth) for placing topology files."""
    return st.lists(
        st.integers(min_value=0, max_value=max_depth),
        min_size=1,
        max_size=8,
    )


# --- Helpers ---


def create_topology_yaml(lab_name: str, nodes: dict[str, str], links: list[list[str]] | None = None) -> str:
    """Create a minimal valid topology YAML string."""
    topology: dict = {
        "name": lab_name,
        "topology": {
            "nodes": {name: {"kind": kind} for name, kind in nodes.items()},
        },
    }
    if links:
        topology["topology"]["links"] = [{"endpoints": ep} for ep in links]
    return yaml.dump(topology, default_flow_style=False)


def create_dir_at_depth(root: Path, depth: int, name: str) -> Path:
    """Create a nested directory at a given depth from root."""
    current = root
    for i in range(depth):
        current = current / f"level{i}"
    current = current / name
    current.mkdir(parents=True, exist_ok=True)
    return current


# --- Property 3: Topology Discovery Depth Limit ---


@settings(max_examples=100)
@given(
    depths=depth_positions_strategy(max_depth=5),
    lab_name=lab_name_strategy(),
)
def test_discovery_respects_depth_limit(depths, lab_name):
    """For any directory tree with .clab.yml files at various depths, discover()
    SHALL find all files at depth <= 3 and SHALL NOT find files at depth > 3.

    **Validates: Requirements 2.1, 2.2**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        placed_files: dict[int, Path] = {}

        # Place one topology file at each requested depth
        for idx, depth in enumerate(depths):
            dir_path = root
            for level in range(depth):
                dir_path = dir_path / f"d{idx}_l{level}"
            dir_path.mkdir(parents=True, exist_ok=True)

            file_name = f"topo{idx}.clab.yml"
            file_path = dir_path / file_name
            nodes = {f"node{idx}": "linux"}
            content = create_topology_yaml(f"{lab_name}{idx}", nodes)
            file_path.write_text(content)
            placed_files[depth] = file_path

        # Run discovery with max_depth=3
        parser = TopologyParser()
        results = parser.discover([str(root)], max_depth=3)
        discovered_paths = {entry.path for entry in results}

        # Verify: files at depth <= 3 should be found
        for depth, file_path in placed_files.items():
            abs_path = str(file_path.resolve())
            if depth <= 3:
                assert abs_path in discovered_paths, (
                    f"File at depth {depth} should be discovered: {abs_path}"
                )
            else:
                assert abs_path not in discovered_paths, (
                    f"File at depth {depth} should NOT be discovered: {abs_path}"
                )

        # Verify: every discovered entry has valid fields
        for entry in results:
            assert os.path.isabs(entry.path), (
                f"Path should be absolute: {entry.path}"
            )
            assert len(entry.lab_name) > 0, "Lab name should be non-empty"
            assert entry.node_count >= 0, "Node count should be >= 0"


@settings(max_examples=100)
@given(
    num_files=st.integers(min_value=0, max_value=5),
    lab_name=lab_name_strategy(),
)
def test_discovery_entries_have_valid_metadata(num_files, lab_name):
    """Every discovered entry SHALL include a valid absolute path, a non-empty
    lab name, and a node count >= 0.

    **Validates: Requirements 2.1, 2.2**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        expected_node_counts: dict[str, int] = {}

        for i in range(num_files):
            file_path = root / f"lab{i}.clab.yml"
            node_count = i + 1
            nodes = {f"node{j}": "linux" for j in range(node_count)}
            name = f"{lab_name}{i}"
            content = create_topology_yaml(name, nodes)
            file_path.write_text(content)
            expected_node_counts[str(file_path.resolve())] = node_count

        parser = TopologyParser()
        results = parser.discover([str(root)], max_depth=3)

        assert len(results) == num_files

        for entry in results:
            # Valid absolute path
            assert os.path.isabs(entry.path)
            assert entry.path in expected_node_counts
            # Non-empty lab name
            assert len(entry.lab_name) > 0
            # Node count >= 0 and matches what we wrote
            assert entry.node_count >= 0
            assert entry.node_count == expected_node_counts[entry.path]


# --- Property 4: Topology Parsing Round-Trip ---


@settings(max_examples=100)
@given(
    lab_name=lab_name_strategy(),
    node_entries=st.lists(
        st.tuples(node_name_strategy(), kind_strategy()),
        min_size=1,
        max_size=6,
    ),
    include_kind=st.booleans(),
)
def test_topology_parsing_round_trip(lab_name, node_entries, include_kind):
    """For any valid topology structure, serializing to YAML and parsing with
    get_topology_details SHALL produce matching node names, node kinds, link
    endpoints, and topology name.

    **Validates: Requirements 2.3**
    """
    # Ensure unique node names
    seen_names: set[str] = set()
    unique_nodes: list[tuple[str, str]] = []
    for name, kind in node_entries:
        if name not in seen_names:
            seen_names.add(name)
            unique_nodes.append((name, kind))
    assume(len(unique_nodes) >= 1)

    node_names = [n for n, _ in unique_nodes]
    nodes_dict = {name: kind for name, kind in unique_nodes}

    # Generate links only if we have at least 2 nodes
    links: list[list[str]] = []
    if len(unique_nodes) >= 2:
        # Create one link between first two nodes
        links.append([f"{node_names[0]}:eth1", f"{node_names[1]}:eth2"])

    # Build YAML topology structure
    topology_data: dict = {
        "name": lab_name,
        "topology": {
            "nodes": {name: {"kind": kind} for name, kind in unique_nodes},
        },
    }
    if links:
        topology_data["topology"]["links"] = [{"endpoints": ep} for ep in links]
    if include_kind:
        topology_data["topology"]["defaults"] = {"kind": "linux"}

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.clab.yml"
        file_path.write_text(yaml.dump(topology_data, default_flow_style=False))

        # Parse with TopologyParser
        parser = TopologyParser()
        result = parser.parse(str(file_path))

        # Verify topology name matches
        assert result.name == lab_name, (
            f"Expected name '{lab_name}', got '{result.name}'"
        )

        # Verify node names match
        result_node_names = sorted([n.name for n in result.nodes])
        expected_node_names = sorted(node_names)
        assert result_node_names == expected_node_names, (
            f"Expected nodes {expected_node_names}, got {result_node_names}"
        )

        # Verify node kinds match
        result_kinds = {n.name: n.kind for n in result.nodes}
        for name, kind in unique_nodes:
            assert result_kinds[name] == kind, (
                f"Node '{name}': expected kind '{kind}', got '{result_kinds[name]}'"
            )

        # Verify link endpoints match
        result_links = [sorted(link.endpoints) for link in result.links]
        expected_links = [sorted(ep) for ep in links]
        assert sorted(result_links) == sorted(expected_links), (
            f"Expected links {expected_links}, got {result_links}"
        )

        # Verify optional kind field
        if include_kind:
            assert result.kind == "linux"
        else:
            assert result.kind is None


@settings(max_examples=100)
@given(
    lab_name=lab_name_strategy(),
    node_entries=st.lists(
        st.tuples(node_name_strategy(), kind_strategy()),
        min_size=2,
        max_size=8,
    ),
)
def test_topology_parsing_preserves_all_links(lab_name, node_entries):
    """For any topology with multiple links, parsing SHALL preserve all
    link endpoint pairs exactly.

    **Validates: Requirements 2.3**
    """
    # Ensure unique node names
    seen_names: set[str] = set()
    unique_nodes: list[tuple[str, str]] = []
    for name, kind in node_entries:
        if name not in seen_names:
            seen_names.add(name)
            unique_nodes.append((name, kind))
    assume(len(unique_nodes) >= 2)

    node_names = [n for n, _ in unique_nodes]

    # Create links between consecutive pairs of nodes
    links: list[list[str]] = []
    for i in range(len(node_names) - 1):
        links.append([f"{node_names[i]}:eth{i+1}", f"{node_names[i+1]}:eth{i+1}"])

    # Build YAML
    topology_data: dict = {
        "name": lab_name,
        "topology": {
            "nodes": {name: {"kind": kind} for name, kind in unique_nodes},
            "links": [{"endpoints": ep} for ep in links],
        },
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.clab.yml"
        file_path.write_text(yaml.dump(topology_data, default_flow_style=False))

        parser = TopologyParser()
        result = parser.parse(str(file_path))

        # Verify all links are preserved
        assert len(result.links) == len(links), (
            f"Expected {len(links)} links, got {len(result.links)}"
        )

        result_links_sorted = sorted([sorted(link.endpoints) for link in result.links])
        expected_links_sorted = sorted([sorted(ep) for ep in links])
        assert result_links_sorted == expected_links_sorted, (
            f"Links mismatch: expected {expected_links_sorted}, got {result_links_sorted}"
        )
