import json
import sys
from pathlib import Path

from generator.generate import TelemetryGenerator
from pipeline.build import main as build_main


def _generate_raw(output_dir: Path, seed: int = 42, nodes: int = 200) -> None:
    gen = TelemetryGenerator(seed=seed, nodes=nodes)
    gen.generate_all()
    gen.write(output_dir)


def test_pipeline_builds_graph(tmp_path, monkeypatch):
    """Pipeline produces valid nodes and edges."""
    raw_dir = tmp_path / "raw"
    graph_dir = tmp_path / "graph"

    _generate_raw(raw_dir, seed=42, nodes=200)

    monkeypatch.setattr(
        sys, "argv", ["build", "--input", str(raw_dir), "--output", str(graph_dir)]
    )
    build_main()

    nodes = json.loads((graph_dir / "nodes.json").read_text())
    edges = json.loads((graph_dir / "edges.json").read_text())

    assert len(nodes) > 0
    assert len(edges) > 0

    # Validate node structure
    for node in nodes:
        assert "id" in node
        assert "type" in node
        assert "label" in node
        assert "properties" in node

    # Validate edge structure — no orphan edges
    node_ids = {n["id"] for n in nodes}
    for edge in edges:
        assert "source" in edge
        assert "target" in edge
        assert "type" in edge
        assert edge["source"] in node_ids, f"Orphan edge source: {edge['source']}"
        assert edge["target"] in node_ids, f"Orphan edge target: {edge['target']}"

    # Check expected node types
    node_types = {n["type"] for n in nodes}
    assert "file" in node_types
    assert "host" in node_types
    assert "email" in node_types
    assert "tenant" in node_types
    # country and campaign are metadata, not separate node types
    assert "country" not in node_types
    assert "campaign" not in node_types


def test_pipeline_no_duplicate_nodes(tmp_path, monkeypatch):
    """Node IDs should be unique."""
    raw_dir = tmp_path / "raw"
    graph_dir = tmp_path / "graph"

    _generate_raw(raw_dir, seed=42, nodes=300)

    monkeypatch.setattr(
        sys, "argv", ["build", "--input", str(raw_dir), "--output", str(graph_dir)]
    )
    build_main()

    nodes = json.loads((graph_dir / "nodes.json").read_text())
    ids = [n["id"] for n in nodes]
    assert len(ids) == len(set(ids)), "Duplicate node IDs found"
