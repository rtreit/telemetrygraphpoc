from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Optional
import json
import random as stdlib_random

from generator.generate import TelemetryGenerator
from pipeline.build import load_raw, build_nodes, build_edges

app = FastAPI(title="Malware IOC Telemetry Graph API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

GRAPH_DATA: dict = {"nodes": [], "edges": []}
nodes_by_id: dict = {}
edges_by_source: dict[str, list] = {}
edges_by_target: dict[str, list] = {}



def _load_json(path: Path) -> list:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _build_indexes():
    nodes_by_id.clear()
    edges_by_source.clear()
    edges_by_target.clear()
    for node in GRAPH_DATA["nodes"]:
        nodes_by_id[node["id"]] = node
    for edge in GRAPH_DATA["edges"]:
        edges_by_source.setdefault(edge["source"], []).append(edge)
        edges_by_target.setdefault(edge["target"], []).append(edge)


@app.on_event("startup")
def load_graph():
    graph_dir = DATA_DIR / "graph"
    sample_dir = DATA_DIR / "sample"

    chosen = graph_dir if (graph_dir / "nodes.json").exists() else sample_dir

    GRAPH_DATA["nodes"] = _load_json(chosen / "nodes.json")
    GRAPH_DATA["edges"] = _load_json(chosen / "edges.json")
    _build_indexes()

    n_nodes = len(GRAPH_DATA["nodes"])
    n_edges = len(GRAPH_DATA["edges"])
    print(f"Loaded {n_nodes} nodes and {n_edges} edges from {chosen}")


@app.post("/api/generate")
def generate_campaign(
    seed: Optional[int] = Query(None, description="Random seed (default: random)"),
    nodes: int = Query(150, description="Target node count"),
):
    actual_seed = seed if seed is not None else stdlib_random.randint(1, 999999)
    actual_nodes = max(1, min(10000, nodes))

    # Generate raw telemetry
    gen = TelemetryGenerator(seed=actual_seed, nodes=actual_nodes)
    counts = gen.generate_all()
    gen.write(output_dir=DATA_DIR / "raw")

    # Build graph
    raw = load_raw(DATA_DIR / "raw")
    node_dict, sha_to_file_nodes = build_nodes(raw)
    edge_list = build_edges(raw, node_dict, sha_to_file_nodes)

    # Write graph files
    graph_dir = DATA_DIR / "graph"
    graph_dir.mkdir(parents=True, exist_ok=True)
    with open(graph_dir / "nodes.json", "w", encoding="utf-8") as f:
        json.dump(list(node_dict.values()), f, indent=2, default=str)
    with open(graph_dir / "edges.json", "w", encoding="utf-8") as f:
        json.dump(edge_list, f, indent=2, default=str)

    # Reload into memory
    GRAPH_DATA["nodes"] = list(node_dict.values())
    GRAPH_DATA["edges"] = edge_list
    _build_indexes()

    return {
        "seed": actual_seed,
        "requested_nodes": actual_nodes,
        "total_nodes": len(GRAPH_DATA["nodes"]),
        "total_edges": len(GRAPH_DATA["edges"]),
        "raw_counts": counts,
    }


@app.get("/api/graph")
def get_graph(
    type: Optional[str] = Query(None, description="Filter nodes by type"),
    country: Optional[str] = Query(None, description="Filter by country code"),
    campaign: Optional[str] = Query(None, description="Filter by campaign cluster_id"),
    time_start: Optional[str] = Query(None, description="ISO datetime start"),
    time_end: Optional[str] = Query(None, description="ISO datetime end"),
):
    """Return filtered graph (nodes + edges). Only edges where both endpoints are in filtered set."""
    nodes = GRAPH_DATA["nodes"]

    if type:
        types = set(t.strip() for t in type.split(","))
        nodes = [n for n in nodes if n.get("type") in types]

    if country:
        codes = set(c.strip().upper() for c in country.split(","))
        nodes = [
            n for n in nodes
            if n.get("properties", {}).get("country_code", "").upper() in codes
            or n.get("properties", {}).get("country", "").upper() in codes
            or (n.get("type") == "country" and n.get("id", "").upper() in codes)
        ]

    if campaign:
        campaigns = set(c.strip() for c in campaign.split(","))
        nodes = [
            n for n in nodes
            if n.get("properties", {}).get("cluster_id") in campaigns
            or (n.get("type") == "campaign" and n.get("id") in campaigns)
        ]

    if time_start or time_end:
        filtered = []
        for n in nodes:
            props = n.get("properties", {})
            ts = props.get("timestamp") or props.get("delivery_time") or props.get("first_seen")
            if ts is None:
                filtered.append(n)
                continue
            if time_start and ts < time_start:
                continue
            if time_end and ts > time_end:
                continue
            filtered.append(n)
        nodes = filtered

    node_ids = {n["id"] for n in nodes}

    edges = [
        e for e in GRAPH_DATA["edges"]
        if e["source"] in node_ids and e["target"] in node_ids
    ]

    return {"nodes": nodes, "edges": edges}


@app.get("/api/graph/summary")
def get_summary():
    """Return counts by node type, edge type, countries, campaigns, tenants."""
    node_type_counts: dict[str, int] = {}
    edge_type_counts: dict[str, int] = {}
    countries: set[str] = set()
    campaigns: set[str] = set()
    tenants: set[str] = set()

    for n in GRAPH_DATA["nodes"]:
        ntype = n.get("type", "unknown")
        node_type_counts[ntype] = node_type_counts.get(ntype, 0) + 1

        props = n.get("properties", {})
        if cc := props.get("country_code"):
            countries.add(cc)
        if ntype == "country":
            countries.add(n["id"])
        if cid := props.get("cluster_id"):
            campaigns.add(cid)
        if ntype == "campaign":
            campaigns.add(n["id"])
        if tid := props.get("tenant_id"):
            tenants.add(tid)
        if ntype == "tenant":
            tenants.add(n["id"])

    for e in GRAPH_DATA["edges"]:
        etype = e.get("type", "unknown")
        edge_type_counts[etype] = edge_type_counts.get(etype, 0) + 1

    return {
        "total_nodes": len(GRAPH_DATA["nodes"]),
        "total_edges": len(GRAPH_DATA["edges"]),
        "node_types": node_type_counts,
        "edge_types": edge_type_counts,
        "countries": sorted(countries),
        "campaigns": sorted(campaigns),
        "tenants": sorted(tenants),
    }


@app.get("/api/nodes/{node_id:path}/neighbors")
def get_neighbors(node_id: str):
    """Return 1-hop neighborhood: the node + all directly connected nodes + connecting edges."""
    node = nodes_by_id.get(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

    connected_edges = edges_by_source.get(node_id, []) + edges_by_target.get(node_id, [])

    neighbor_ids: set[str] = set()
    for e in connected_edges:
        neighbor_ids.add(e["source"])
        neighbor_ids.add(e["target"])
    neighbor_ids.discard(node_id)

    neighbor_nodes = [nodes_by_id[nid] for nid in neighbor_ids if nid in nodes_by_id]

    return {
        "nodes": [node] + neighbor_nodes,
        "edges": connected_edges,
    }


@app.get("/api/nodes/{node_id:path}")
def get_node(node_id: str):
    """Return a single node with all properties + its connected edges."""
    node = nodes_by_id.get(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

    connected_edges = edges_by_source.get(node_id, []) + edges_by_target.get(node_id, [])

    return {"node": node, "edges": connected_edges}


@app.get("/api/search")
def search_nodes(q: str = Query(..., min_length=1)):
    """Search nodes by label or property values. Case-insensitive substring match."""
    query = q.lower()
    results: list[dict] = []

    for node in GRAPH_DATA["nodes"]:
        if len(results) >= 50:
            break

        # Match against label
        if query in node.get("label", "").lower():
            results.append(node)
            continue

        # Match against id
        if query in node.get("id", "").lower():
            results.append(node)
            continue

        # Match against all string/list properties
        props = node.get("properties", {})
        matched = False
        for val in props.values():
            if isinstance(val, str) and query in val.lower():
                matched = True
                break
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and query in item.lower():
                        matched = True
                        break
            if matched:
                break
        if matched:
            results.append(node)
            continue

    return {"results": results, "total": len(results), "query": q}
