"""
Graph construction pipeline: transforms raw telemetry JSON into nodes + edges.

Usage:
    python -m pipeline.build [--input data/raw] [--output data/graph]
"""

import json
import argparse
from collections import defaultdict
from pathlib import Path


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

_RAW_FILES = [
    "seed_ioc", "campaigns", "tenants", "hosts",
    "emails", "files", "executions", "network",
]


def load_raw(data_dir: Path) -> dict:
    """Load all raw JSON files from *data_dir* and return keyed by name."""
    raw: dict = {}
    for name in _RAW_FILES:
        p = data_dir / f"{name}.json"
        if not p.exists():
            raise FileNotFoundError(f"Missing required file: {p}")
        with open(p, encoding="utf-8") as f:
            raw[name] = json.load(f)
    return raw


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node(nid: str, ntype: str, label: str, properties: dict) -> dict:
    return {"id": nid, "type": ntype, "label": label, "properties": properties}


def _edge(source: str, target: str, etype: str, properties: dict | None = None) -> dict:
    return {"source": source, "target": target, "type": etype, "properties": properties or {}}


def _trunc(s: str, maxlen: int) -> str:
    return s if len(s) <= maxlen else s[: maxlen - 1] + "…"


# ---------------------------------------------------------------------------
# Node construction
# ---------------------------------------------------------------------------

def build_nodes(raw: dict) -> dict[str, dict]:
    """Build a deduplicated node dict keyed by node id."""
    nodes: dict[str, dict] = {}

    # --- seed IOC (ensure it exists as a file node even if files.json is empty) ---
    seed = raw["seed_ioc"]
    # Will be overwritten / merged by the files loop below.

    # --- file nodes (deduplicate by sha256, merge names/paths) ---
    file_agg: dict[str, dict] = defaultdict(lambda: {
        "file_names": [], "file_paths": [], "file_type": None,
        "file_sizes": [], "signature_statuses": [],
        "first_seen": None, "last_seen": None,
        "parent_processes": [], "dropped_by": set(),
    })
    for f in raw["files"]:
        sha = f["sha256"]
        agg = file_agg[sha]
        if f["file_name"] not in agg["file_names"]:
            agg["file_names"].append(f["file_name"])
        if f["file_path"] not in agg["file_paths"]:
            agg["file_paths"].append(f["file_path"])
        agg["file_type"] = agg["file_type"] or f.get("file_type")
        agg["file_sizes"].append(f.get("file_size"))
        agg["signature_statuses"].append(f.get("signature_status"))
        if f.get("parent_process") and f["parent_process"] not in agg["parent_processes"]:
            agg["parent_processes"].append(f["parent_process"])
        if f.get("dropped_by"):
            agg["dropped_by"].add(f["dropped_by"])
        fs = f.get("first_seen")
        ls = f.get("last_seen")
        if fs and (agg["first_seen"] is None or fs < agg["first_seen"]):
            agg["first_seen"] = fs
        if ls and (agg["last_seen"] is None or ls > agg["last_seen"]):
            agg["last_seen"] = ls

    for sha, agg in file_agg.items():
        label = agg["file_names"][0] if agg["file_names"] else sha[:16]
        nodes[sha] = _node(sha, "file", label, {
            "sha256": sha,
            "file_names": agg["file_names"],
            "file_paths": agg["file_paths"],
            "file_type": agg["file_type"],
            "file_sizes": sorted(set(agg["file_sizes"])),
            "signature_statuses": sorted(set(agg["signature_statuses"])),
            "first_seen": agg["first_seen"],
            "last_seen": agg["last_seen"],
            "parent_processes": agg["parent_processes"],
            "dropped_by": sorted(agg["dropped_by"]),
        })

    # Ensure seed IOC is present even if not in files.json
    if seed["sha256"] not in nodes:
        nodes[seed["sha256"]] = _node(
            seed["sha256"], "file", seed["sha256"][:16],
            {"sha256": seed["sha256"], "description": seed["description"]},
        )

    # --- host nodes ---
    for h in raw["hosts"]:
        nid = h["device_id"]
        nodes[nid] = _node(nid, "host", h["hostname"], {
            "device_id": nid,
            "hostname": h["hostname"],
            "os_family": h.get("os_family"),
            "device_type": h.get("device_type"),
            "environment": h.get("environment"),
            "country": h.get("country"),
            "tenant_id": h.get("tenant_id"),
            "user": h.get("user"),
            "security_posture": h.get("security_posture"),
        })

    # --- email nodes ---
    for e in raw["emails"]:
        nid = e["message_id"]
        nodes[nid] = _node(nid, "email", _trunc(e["subject"], 50), {
            "message_id": nid,
            "sender": e.get("sender"),
            "sender_domain": e.get("sender_domain"),
            "reply_to": e.get("reply_to"),
            "subject": e.get("subject"),
            "attachment_name": e.get("attachment_name"),
            "attachment_type": e.get("attachment_type"),
            "delivery_time": e.get("delivery_time"),
            "recipient_user": e.get("recipient_user"),
            "recipient_tenant": e.get("recipient_tenant"),
            "spf": e.get("spf"),
            "dkim": e.get("dkim"),
            "dmarc": e.get("dmarc"),
            "campaign_id": e.get("campaign_id"),
        })

    # --- domain nodes (from network data) ---
    domain_first_seen: dict[str, str | None] = {}
    for n in raw["network"]:
        d = n.get("domain")
        if not d:
            continue
        fs = n.get("first_seen")  # may not exist in data
        if d not in domain_first_seen or (fs and (domain_first_seen[d] is None or fs < domain_first_seen[d])):
            domain_first_seen[d] = fs
        if d not in nodes:
            nodes[d] = _node(d, "domain", d, {"first_seen": fs})

    # Also create domain nodes from email sender_domains and campaign sender_domains
    for e in raw["emails"]:
        sd = e.get("sender_domain")
        if sd and sd not in nodes:
            nodes[sd] = _node(sd, "domain", sd, {})
    for c in raw["campaigns"]:
        for sd in c.get("sender_domains", []):
            if sd not in nodes:
                nodes[sd] = _node(sd, "domain", sd, {})

    # domains from execution external_connection
    for ex in raw["executions"]:
        ec = ex.get("external_connection")
        if ec and ec not in nodes:
            nodes[ec] = _node(ec, "domain", ec, {})

    # --- ip nodes ---
    seen_ips: dict[str, dict] = {}
    for n in raw["network"]:
        ip = n.get("ip")
        if not ip:
            continue
        if ip not in seen_ips:
            seen_ips[ip] = {
                "asn": n.get("asn"),
                "hosting_provider": n.get("hosting_provider"),
                "ip_country": n.get("ip_country"),
                "ports": set(),
            }
        if n.get("port"):
            seen_ips[ip]["ports"].add(n["port"])
    for ip, props in seen_ips.items():
        nodes[ip] = _node(ip, "ip", ip, {
            "asn": props["asn"],
            "hosting_provider": props["hosting_provider"],
            "ip_country": props["ip_country"],
            "ports": sorted(props["ports"]),
        })

    # --- user nodes (from hosts + emails) ---
    for h in raw["hosts"]:
        user = h.get("user")
        tid = h.get("tenant_id")
        if user and tid:
            uid = f"{tid}/{user}"
            if uid not in nodes:
                nodes[uid] = _node(uid, "user", user, {"tenant_id": tid})

    for e in raw["emails"]:
        user = e.get("recipient_user")
        tid = e.get("recipient_tenant")
        if user and tid:
            uid = f"{tid}/{user}"
            if uid not in nodes:
                nodes[uid] = _node(uid, "user", user, {"tenant_id": tid})

    # --- country nodes ---
    country_sources: set[str] = set()
    for h in raw["hosts"]:
        if h.get("country"):
            country_sources.add(h["country"])
    for n in raw["network"]:
        if n.get("ip_country"):
            country_sources.add(n["ip_country"])
    for c in raw["campaigns"]:
        for cc in c.get("target_countries", []):
            country_sources.add(cc)
    for t in raw["tenants"]:
        for cc in t.get("countries", []):
            country_sources.add(cc)
    for cc in country_sources:
        if cc not in nodes:
            nodes[cc] = _node(cc, "country", cc, {})

    # --- tenant nodes ---
    for t in raw["tenants"]:
        nid = t["tenant_id"]
        nodes[nid] = _node(nid, "tenant", t["name"], {
            "tenant_id": nid,
            "name": t["name"],
            "countries": t.get("countries", []),
        })

    # --- campaign nodes ---
    for c in raw["campaigns"]:
        nid = c["cluster_id"]
        label = f"{c['lure_family']} ({c['region_variant']})"
        nodes[nid] = _node(nid, "campaign", label, {
            "cluster_id": nid,
            "region_variant": c.get("region_variant"),
            "lure_family": c.get("lure_family"),
            "time_window_start": c.get("time_window_start"),
            "time_window_end": c.get("time_window_end"),
            "infra_reuse_cluster": c.get("infra_reuse_cluster"),
            "sender_domains": c.get("sender_domains", []),
            "target_countries": c.get("target_countries", []),
        })

    # --- url nodes ---
    for n in raw["network"]:
        url = n.get("url")
        if not url:
            continue
        if url not in nodes:
            nodes[url] = _node(url, "url", _trunc(url, 80), {
                "domain": n.get("domain"),
                "ip": n.get("ip"),
                "protocol": n.get("protocol"),
                "port": n.get("port"),
                "uri_path": n.get("uri_path"),
            })

    # --- process nodes (from executions) ---
    for ex in raw["executions"]:
        nid = f"{ex['host_device_id']}/{ex['process_name']}/{ex['event_id']}"
        nodes[nid] = _node(nid, "process", ex["process_name"], {
            "event_id": ex["event_id"],
            "host_device_id": ex["host_device_id"],
            "file_sha256": ex.get("file_sha256"),
            "persistence_type": ex.get("persistence_type"),
            "script_interpreter": ex.get("script_interpreter"),
            "behavior_flags": ex.get("behavior_flags", []),
            "timestamp": ex.get("timestamp"),
        })

    return nodes


# ---------------------------------------------------------------------------
# Edge construction
# ---------------------------------------------------------------------------

def build_edges(raw: dict, nodes: dict[str, dict]) -> list[dict]:
    """Build edge list from all defined relationships."""
    edges: list[dict] = []
    seen_edges: set[tuple[str, str, str]] = set()

    def _add(source: str, target: str, etype: str, props: dict | None = None):
        if source not in nodes or target not in nodes:
            return
        key = (source, target, etype)
        if key not in seen_edges:
            seen_edges.add(key)
            edges.append(_edge(source, target, etype, props))

    # Build lookup: file_name → set of sha256 (for attachment matching)
    fname_to_sha: dict[str, set[str]] = defaultdict(set)
    for f in raw["files"]:
        fname_to_sha[f["file_name"]].add(f["sha256"])

    # Build lookup: user → list of host device_ids
    user_to_hosts: dict[str, list[str]] = defaultdict(list)
    for h in raw["hosts"]:
        if h.get("user") and h.get("tenant_id"):
            uid = f"{h['tenant_id']}/{h['user']}"
            user_to_hosts[uid].append(h["device_id"])

    # 1. email --delivered_to--> user
    for e in raw["emails"]:
        user = e.get("recipient_user")
        tid = e.get("recipient_tenant")
        if user and tid:
            _add(e["message_id"], f"{tid}/{user}", "delivered_to")

    # 2. email --contains_attachment--> file
    for e in raw["emails"]:
        att = e.get("attachment_name")
        if att and att in fname_to_sha:
            for sha in fname_to_sha[att]:
                _add(e["message_id"], sha, "contains_attachment")

    # 3. file --dropped_on--> host (via executions)
    for ex in raw["executions"]:
        sha = ex.get("file_sha256")
        hid = ex.get("host_device_id")
        if sha and hid:
            _add(sha, hid, "dropped_on")

    # Also: file dropped_on host via email→user→host chain
    for e in raw["emails"]:
        att = e.get("attachment_name")
        user = e.get("recipient_user")
        tid = e.get("recipient_tenant")
        if att and user and tid:
            uid = f"{tid}/{user}"
            for sha in fname_to_sha.get(att, set()):
                for hid in user_to_hosts.get(uid, []):
                    _add(sha, hid, "dropped_on")

    # 4. file --drops--> file (child.dropped_by → parent sha256)
    for f in raw["files"]:
        if f.get("dropped_by"):
            _add(f["dropped_by"], f["sha256"], "drops")

    # 5. process --executes--> file
    for ex in raw["executions"]:
        pid = f"{ex['host_device_id']}/{ex['process_name']}/{ex['event_id']}"
        sha = ex.get("file_sha256")
        if sha:
            _add(pid, sha, "executes")

    # 6. process --connects_to--> domain
    for ex in raw["executions"]:
        pid = f"{ex['host_device_id']}/{ex['process_name']}/{ex['event_id']}"
        ec = ex.get("external_connection")
        if ec:
            _add(pid, ec, "connects_to")

    # 7. domain --resolves_to--> ip
    for n in raw["network"]:
        d = n.get("domain")
        ip = n.get("ip")
        if d and ip:
            _add(d, ip, "resolves_to")

    # 8. host --located_in--> country
    for h in raw["hosts"]:
        if h.get("country"):
            _add(h["device_id"], h["country"], "located_in")

    # 9. host --belongs_to--> tenant
    for h in raw["hosts"]:
        if h.get("tenant_id"):
            _add(h["device_id"], h["tenant_id"], "belongs_to")

    # 10. campaign --includes--> email
    campaign_ids = {c["cluster_id"] for c in raw["campaigns"]}
    for e in raw["emails"]:
        cid = e.get("campaign_id")
        if cid and cid in campaign_ids:
            _add(cid, e["message_id"], "includes")

    # 11. campaign --uses--> domain
    for c in raw["campaigns"]:
        for sd in c.get("sender_domains", []):
            _add(c["cluster_id"], sd, "uses")

    # 12. campaign --targets--> country
    for c in raw["campaigns"]:
        for cc in c.get("target_countries", []):
            _add(c["cluster_id"], cc, "targets")

    # 14. user --uses--> host
    for h in raw["hosts"]:
        user = h.get("user")
        tid = h.get("tenant_id")
        if user and tid:
            uid = f"{tid}/{user}"
            _add(uid, h["device_id"], "uses")

    # 15. process --runs_on--> host
    for ex in raw["executions"]:
        pid = f"{ex['host_device_id']}/{ex['process_name']}/{ex['event_id']}"
        hid = ex.get("host_device_id")
        if hid:
            _add(pid, hid, "runs_on")

    # 17. url --hosted_on--> domain
    for n in raw["network"]:
        url = n.get("url")
        d = n.get("domain")
        if url and d:
            _add(url, d, "hosted_on")

    # 18. url --resolves_to--> ip
    for n in raw["network"]:
        url = n.get("url")
        ip = n.get("ip")
        if url and ip:
            _add(url, ip, "resolves_to")

    return edges


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build graph from raw telemetry")
    parser.add_argument("--input", default="data/raw", help="Input directory")
    parser.add_argument("--output", default="data/graph", help="Output directory")
    args = parser.parse_args()

    raw = load_raw(Path(args.input))
    nodes = build_nodes(raw)
    edges = build_edges(raw, nodes)

    # Write output
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "nodes.json", "w", encoding="utf-8") as f:
        json.dump(list(nodes.values()), f, indent=2, default=str)
    with open(out / "edges.json", "w", encoding="utf-8") as f:
        json.dump(edges, f, indent=2, default=str)

    # Print summary
    from collections import Counter
    node_types = Counter(n["type"] for n in nodes.values())
    edge_types = Counter(e["type"] for e in edges)

    print(f"\n{'='*50}")
    print(f"Graph built: {len(nodes):,} nodes, {len(edges):,} edges")
    print(f"{'='*50}")

    print("\nNode counts by type:")
    for t, c in sorted(node_types.items(), key=lambda x: -x[1]):
        print(f"  {t:12s}  {c:>6,}")

    print("\nEdge counts by type:")
    for t, c in sorted(edge_types.items(), key=lambda x: -x[1]):
        print(f"  {t:20s}  {c:>6,}")

    # Validate: no orphan edges
    node_ids = set(nodes.keys())
    orphan_sources = {e["source"] for e in edges if e["source"] not in node_ids}
    orphan_targets = {e["target"] for e in edges if e["target"] not in node_ids}
    if orphan_sources or orphan_targets:
        print(f"\n⚠️  Orphan edge sources: {len(orphan_sources)}")
        print(f"⚠️  Orphan edge targets: {len(orphan_targets)}")
    else:
        print("\n✅ No orphan edges — all sources and targets exist in nodes")

    # Verify seed IOC
    seed_sha = raw["seed_ioc"]["sha256"]
    if seed_sha in nodes:
        print(f"✅ Seed IOC present: {seed_sha[:24]}…")
    else:
        print(f"⚠️  Seed IOC missing: {seed_sha[:24]}…")

    print(f"\nOutput written to: {out.resolve()}")


if __name__ == "__main__":
    main()
