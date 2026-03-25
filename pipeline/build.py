"""
Attack-campaign-oriented graph construction pipeline.

Transforms raw telemetry JSON into an attack-story graph where edges show
the flow: email → user → host → file → process → domain → ip, etc.

File nodes are per-instance (not deduplicated by SHA-256) to avoid creating
a dense star pattern around the seed IOC.  Follow-on payload files are the
exception — they are deduplicated since only a handful of unique hashes exist.

Usage:
    python -m pipeline.build [--input data/raw] [--output data/graph]
"""

import hashlib
import json
import argparse
from collections import Counter, defaultdict
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


def _path_hash(path: str) -> str:
    """Short deterministic hash of a file path for use in node IDs."""
    return hashlib.sha256(path.encode("utf-8")).hexdigest()[:8]


def _stable_index(items_len: int, key: str) -> int:
    """Deterministic index into a list of *items_len* based on *key*."""
    if items_len <= 0:
        return 0
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16) % items_len


# ---------------------------------------------------------------------------
# Node construction
# ---------------------------------------------------------------------------

def build_nodes(raw: dict) -> tuple[dict[str, dict], dict[str, list[str]]]:
    """Build nodes and return ``(nodes_by_id, sha_to_file_node_ids)``.

    ``sha_to_file_node_ids`` maps each SHA-256 to the list of per-instance
    file node IDs created for that hash — needed by the edge builder to
    distribute edges across file instances instead of funnelling them all
    through a single node.
    """
    nodes: dict[str, dict] = {}
    seed_sha = raw["seed_ioc"]["sha256"]

    # --- Identify follow-on payload SHA-256s (these get deduplicated) ---
    payload_sha256s: set[str] = set()
    for ex in raw["executions"]:
        p = ex.get("follow_on_payload")
        if p:
            payload_sha256s.add(p)

    # --- Country lookup tables ---
    host_by_id = {h["device_id"]: h for h in raw["hosts"]}

    file_host_countries: dict[str, list[str]] = defaultdict(list)
    for ex in raw["executions"]:
        sha = ex.get("file_sha256")
        hid = ex.get("host_device_id")
        if sha and hid:
            host = host_by_id.get(hid)
            country = ex.get("country") or (host.get("country") if host else None)
            if country:
                file_host_countries[sha].append(country)

    domain_countries: dict[str, list[str]] = defaultdict(list)
    for n in raw["network"]:
        d = n.get("domain")
        c = n.get("ip_country")
        if d and c:
            domain_countries[d].append(c)

    user_countries: dict[str, list[str]] = defaultdict(list)
    for h in raw["hosts"]:
        user = h.get("user")
        tid = h.get("tenant_id")
        c = h.get("country")
        if user and tid and c:
            user_countries[f"{tid}/{user}"].append(c)

    # --- File nodes ---
    sha_to_file_nodes: dict[str, list[str]] = defaultdict(list)

    # 1. Follow-on payloads — deduplicate by sha256
    payload_agg: dict[str, dict] = {}
    for f in raw["files"]:
        sha = f["sha256"]
        if sha not in payload_sha256s:
            continue
        if sha not in payload_agg:
            payload_agg[sha] = {
                "file_names": [], "file_paths": [], "file_type": None,
                "file_sizes": [], "signature_statuses": [],
                "first_seen": None, "last_seen": None,
            }
        agg = payload_agg[sha]
        if f["file_name"] not in agg["file_names"]:
            agg["file_names"].append(f["file_name"])
        if f["file_path"] not in agg["file_paths"]:
            agg["file_paths"].append(f["file_path"])
        agg["file_type"] = agg["file_type"] or f.get("file_type")
        if f.get("file_size") is not None:
            agg["file_sizes"].append(f["file_size"])
        if f.get("signature_status"):
            agg["signature_statuses"].append(f["signature_status"])
        fs, ls = f.get("first_seen"), f.get("last_seen")
        if fs and (agg["first_seen"] is None or fs < agg["first_seen"]):
            agg["first_seen"] = fs
        if ls and (agg["last_seen"] is None or ls > agg["last_seen"]):
            agg["last_seen"] = ls

    for sha, agg in payload_agg.items():
        label = agg["file_names"][0] if agg["file_names"] else sha[:16]
        _fc = file_host_countries.get(sha, [])
        cc = Counter(_fc).most_common(1)[0][0] if _fc else "unknown"
        nodes[sha] = _node(sha, "file", label, {
            "sha256": sha,
            "file_names": agg["file_names"],
            "file_paths": agg["file_paths"],
            "file_type": agg["file_type"],
            "file_sizes": sorted(set(agg["file_sizes"])),
            "signature_statuses": sorted(set(agg["signature_statuses"])),
            "first_seen": agg["first_seen"],
            "last_seen": agg["last_seen"],
            "is_payload": True,
            "country_code": cc,
        })
        sha_to_file_nodes[sha].append(sha)

    # Ensure every payload sha256 has a node even if absent from files.json
    for sha in payload_sha256s:
        if sha not in nodes:
            nodes[sha] = _node(sha, "file", sha[:16], {
                "sha256": sha,
                "is_payload": True,
                "country_code": "unknown",
            })
            sha_to_file_nodes[sha].append(sha)

    # 2. All other files — one node per unique (sha256, file_path)
    seen_file_combos: set[tuple[str, str]] = set()
    for f in raw["files"]:
        sha = f["sha256"]
        if sha in payload_sha256s:
            continue
        fpath = f.get("file_path", "")
        combo = (sha, fpath)
        if combo in seen_file_combos:
            continue
        seen_file_combos.add(combo)

        nid = f"file:{sha[:12]}:{_path_hash(fpath)}"
        sha_to_file_nodes[sha].append(nid)

        _fc = file_host_countries.get(sha, [])
        cc = Counter(_fc).most_common(1)[0][0] if _fc else "unknown"
        nodes[nid] = _node(nid, "file", f.get("file_name") or sha[:16], {
            "sha256": sha,
            "file_name": f.get("file_name"),
            "file_path": fpath,
            "file_type": f.get("file_type"),
            "file_size": f.get("file_size"),
            "signature_status": f.get("signature_status"),
            "first_seen": f.get("first_seen"),
            "last_seen": f.get("last_seen"),
            "is_seed_ioc": sha == seed_sha,
            "country_code": cc,
        })

    # Ensure seed IOC has at least one file node
    if not sha_to_file_nodes.get(seed_sha):
        nid = f"file:{seed_sha[:12]}:seed"
        sha_to_file_nodes[seed_sha].append(nid)
        nodes[nid] = _node(nid, "file", seed_sha[:16], {
            "sha256": seed_sha,
            "description": raw["seed_ioc"].get("description", ""),
            "is_seed_ioc": True,
            "country_code": "unknown",
        })

    # --- Host nodes ---
    for h in raw["hosts"]:
        nid = h["device_id"]
        nodes[nid] = _node(nid, "host", h["hostname"], {
            "device_id": nid,
            "hostname": h["hostname"],
            "os_family": h.get("os_family"),
            "device_type": h.get("device_type"),
            "environment": h.get("environment"),
            "country": h.get("country"),
            "country_code": h.get("country"),
            "tenant_id": h.get("tenant_id"),
            "user": h.get("user"),
            "security_posture": h.get("security_posture"),
            "machine_guid": h.get("machine_guid"),
        })

    # --- Email nodes ---
    campaign_lookup = {c["cluster_id"]: c for c in raw.get("campaigns", [])}
    for e in raw["emails"]:
        nid = e["message_id"]
        ci = campaign_lookup.get(e.get("campaign_id", ""), {})
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
            "campaign_lure": ci.get("lure_family"),
            "campaign_region": ci.get("region_variant"),
            "country_code": e.get("country", "unknown"),
        })

    # --- Domain nodes ---
    for n in raw["network"]:
        d = n.get("domain")
        if not d or d in nodes:
            continue
        _dc = domain_countries.get(d, [])
        cc = Counter(_dc).most_common(1)[0][0] if _dc else "unknown"
        nodes[d] = _node(d, "domain", d, {
            "first_seen": n.get("first_seen"),
            "countries": sorted(set(_dc)),
            "country_code": cc,
        })

    for e in raw["emails"]:
        sd = e.get("sender_domain")
        if sd and sd not in nodes:
            _dc = domain_countries.get(sd, [])
            cc = Counter(_dc).most_common(1)[0][0] if _dc else "unknown"
            nodes[sd] = _node(sd, "domain", sd, {
                "countries": sorted(set(_dc)),
                "country_code": cc,
            })

    for c in raw["campaigns"]:
        for sd in c.get("sender_domains", []):
            if sd not in nodes:
                _dc = domain_countries.get(sd, [])
                cc = Counter(_dc).most_common(1)[0][0] if _dc else "unknown"
                nodes[sd] = _node(sd, "domain", sd, {
                    "countries": sorted(set(_dc)),
                    "country_code": cc,
                })

    for ex in raw["executions"]:
        ec = ex.get("external_connection")
        if ec and ec not in nodes:
            _dc = domain_countries.get(ec, [])
            cc = Counter(_dc).most_common(1)[0][0] if _dc else "unknown"
            nodes[ec] = _node(ec, "domain", ec, {
                "countries": sorted(set(_dc)),
                "country_code": cc,
            })

    # --- IP nodes ---
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
            "country_code": props.get("ip_country") or "unknown",
            "ports": sorted(props["ports"]),
        })

    # --- User nodes ---
    for h in raw["hosts"]:
        user = h.get("user")
        tid = h.get("tenant_id")
        if user and tid:
            uid = f"{tid}/{user}"
            if uid not in nodes:
                _uc = user_countries.get(uid, [])
                cc = Counter(_uc).most_common(1)[0][0] if _uc else "unknown"
                nodes[uid] = _node(uid, "user", user, {
                    "tenant_id": tid,
                    "country_code": cc,
                })

    for e in raw["emails"]:
        user = e.get("recipient_user")
        tid = e.get("recipient_tenant")
        if user and tid:
            uid = f"{tid}/{user}"
            if uid not in nodes:
                _uc = user_countries.get(uid, [])
                cc = Counter(_uc).most_common(1)[0][0] if _uc else "unknown"
                nodes[uid] = _node(uid, "user", user, {
                    "tenant_id": tid,
                    "country_code": cc,
                })

    # --- Tenant nodes ---
    for t in raw["tenants"]:
        nid = t["tenant_id"]
        _tc = t.get("countries", [])
        nodes[nid] = _node(nid, "tenant", t["name"], {
            "tenant_id": nid,
            "name": t["name"],
            "countries": _tc,
            "country_code": _tc[0] if _tc else "unknown",
        })

    # --- URL nodes ---
    for n in raw["network"]:
        url = n.get("url")
        if not url or url in nodes:
            continue
        nodes[url] = _node(url, "url", _trunc(url, 80), {
            "domain": n.get("domain"),
            "ip": n.get("ip"),
            "protocol": n.get("protocol"),
            "port": n.get("port"),
            "uri_path": n.get("uri_path"),
            "country_code": n.get("ip_country", "unknown"),
        })

    # --- Process nodes ---
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
            "country_code": ex.get("country", "unknown"),
        })

    return nodes, sha_to_file_nodes


# ---------------------------------------------------------------------------
# Edge construction
# ---------------------------------------------------------------------------

def build_edges(raw: dict, nodes: dict[str, dict],
                sha_to_file_nodes: dict[str, list[str]]) -> list[dict]:
    """Build attack-campaign-oriented edge list.

    Edge types (attack story flow):
        delivered_to   email → user
        contains       email → file  (seed IOC attachment)
        uses           user → host
        dropped_on     file → host
        executes       process → file
        runs_on        process → host
        connects_to    process → domain  (C2)
        downloads      process → file    (follow-on payload)
        resolves_to    domain → ip
        belongs_to     host → tenant
        hosted_on      url → domain
    """
    edges: list[dict] = []
    seen_edges: set[tuple[str, str, str]] = set()
    seed_sha = raw["seed_ioc"]["sha256"]

    payload_sha256s: set[str] = set()
    for ex in raw["executions"]:
        p = ex.get("follow_on_payload")
        if p:
            payload_sha256s.add(p)

    def _add(source: str, target: str, etype: str, props: dict | None = None):
        if source not in nodes or target not in nodes:
            return
        key = (source, target, etype)
        if key not in seen_edges:
            seen_edges.add(key)
            edges.append(_edge(source, target, etype, props))

    def _pick_file_node(sha: str, distribution_key: str) -> str | None:
        """Pick one file node for *sha*, distributed by *distribution_key*."""
        fnodes = sha_to_file_nodes.get(sha)
        if not fnodes:
            return None
        idx = _stable_index(len(fnodes), distribution_key)
        return fnodes[idx]

    # 1. email → delivered_to → user
    for e in raw["emails"]:
        user = e.get("recipient_user")
        tid = e.get("recipient_tenant")
        if user and tid:
            _add(e["message_id"], f"{tid}/{user}", "delivered_to")

    # 2. email → contains → file (seed IOC instance, distributed across nodes)
    for e in raw["emails"]:
        mid = e["message_id"]
        fnode = _pick_file_node(seed_sha, mid)
        if fnode:
            _add(mid, fnode, "contains")

    # 3. user → uses → host
    for h in raw["hosts"]:
        user = h.get("user")
        tid = h.get("tenant_id")
        if user and tid:
            _add(f"{tid}/{user}", h["device_id"], "uses")

    # 4. file → dropped_on → host (from executions)
    for ex in raw["executions"]:
        sha = ex.get("file_sha256")
        hid = ex.get("host_device_id")
        if not sha or not hid:
            continue
        fnode = _pick_file_node(sha, hid)
        if fnode:
            _add(fnode, hid, "dropped_on")

    # 5. process → executes → file
    for ex in raw["executions"]:
        pid = f"{ex['host_device_id']}/{ex['process_name']}/{ex['event_id']}"
        sha = ex.get("file_sha256")
        hid = ex.get("host_device_id")
        if sha:
            fnode = _pick_file_node(sha, hid or ex["event_id"])
            if fnode:
                _add(pid, fnode, "executes")

    # 6. process → runs_on → host
    for ex in raw["executions"]:
        pid = f"{ex['host_device_id']}/{ex['process_name']}/{ex['event_id']}"
        hid = ex.get("host_device_id")
        if hid:
            _add(pid, hid, "runs_on")

    # 7. process → connects_to → domain (C2 callback)
    for ex in raw["executions"]:
        pid = f"{ex['host_device_id']}/{ex['process_name']}/{ex['event_id']}"
        ec = ex.get("external_connection")
        if ec:
            _add(pid, ec, "connects_to")

    # 8. process → downloads → file (follow-on payload)
    for ex in raw["executions"]:
        payload = ex.get("follow_on_payload")
        if not payload:
            continue
        pid = f"{ex['host_device_id']}/{ex['process_name']}/{ex['event_id']}"
        _add(pid, payload, "downloads")

    # 9. domain → resolves_to → ip
    for n in raw["network"]:
        d = n.get("domain")
        ip = n.get("ip")
        if d and ip:
            _add(d, ip, "resolves_to")

    # 10. host → belongs_to → tenant
    for h in raw["hosts"]:
        if h.get("tenant_id"):
            _add(h["device_id"], h["tenant_id"], "belongs_to")

    # 11. url → hosted_on → domain
    for n in raw["network"]:
        url = n.get("url")
        d = n.get("domain")
        if url and d:
            _add(url, d, "hosted_on")

    return edges


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Build attack-campaign graph from raw telemetry",
    )
    parser.add_argument("--input", default="data/raw", help="Input directory")
    parser.add_argument("--output", default="data/graph", help="Output directory")
    args = parser.parse_args()

    raw = load_raw(Path(args.input))
    nodes, sha_to_file_nodes = build_nodes(raw)
    edges = build_edges(raw, nodes, sha_to_file_nodes)

    # Write output
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "nodes.json", "w", encoding="utf-8") as f:
        json.dump(list(nodes.values()), f, indent=2, default=str)
    with open(out / "edges.json", "w", encoding="utf-8") as f:
        json.dump(edges, f, indent=2, default=str)

    # Print summary
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
        print(f"\n[WARN] Orphan edge sources: {len(orphan_sources)}")
        print(f"[WARN] Orphan edge targets: {len(orphan_targets)}")
    else:
        print("\n[OK] No orphan edges -- all sources and targets exist in nodes")

    # Verify seed IOC
    seed_sha = raw["seed_ioc"]["sha256"]
    seed_nodes = sha_to_file_nodes.get(seed_sha, [])
    if seed_nodes:
        print(f"[OK] Seed IOC present as {len(seed_nodes)} per-instance file node(s)")
    else:
        print(f"[WARN] Seed IOC missing: {seed_sha[:24]}")

    print(f"\nOutput written to: {out.resolve()}")


if __name__ == "__main__":
    main()
