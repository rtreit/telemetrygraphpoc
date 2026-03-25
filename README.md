# Global Malware IOC Telemetry Graph

A proof of concept that simulates global cross-tenant telemetry for a known malware IOC, constructs a rich entity graph, and visualizes it in an interactive 3D web application.

## What It Does

Starting from a single SHA-256 dropper hash observed across many customer tenants worldwide, this POC:

1. **Generates synthetic telemetry** — realistic data modeling a global email-based malware campaign across 25+ countries, multiple tenants, and thousands of hosts
2. **Builds an entity graph** — transforms raw telemetry into interconnected nodes (files, hosts, emails, domains, IPs, users, campaigns) and edges (relationships between them)
3. **Visualizes the graph in 3D** — a browser-based interactive graph where analysts can rotate, zoom, filter, search, and inspect entities to understand how the malware spreads

## Architecture

```
generator/      Synthetic telemetry generator (Python, seeded for reproducibility)
pipeline/       Graph construction pipeline (Python, transforms telemetry → nodes + edges)
api/            Backend API (Python / FastAPI, serves graph data)
frontend/       Web application (React / TypeScript, 3D force-directed graph)
```

## Quick Start

```bash
# Generate synthetic data
python -m generator.generate --seed 42 --nodes 5000

# Build the graph
python -m pipeline.build

# Start the API
uvicorn api.main:app --reload --port 8000

# Start the frontend (in another terminal)
cd frontend && npm install && npm run dev
```

## Entity Types

| Type | Examples |
|------|----------|
| File / Malware | SHA-256 hashes, file names, paths, dropped files, process trees |
| Host / Device | Hostname, OS, device type, country, tenant, security posture |
| Email | Sender, subject, attachment, delivery time, auth results |
| Network / Infra | URLs, domains, IPs, ASN, ports, SSL certs |
| Execution | Process events, persistence, C2 connections, follow-on payloads |
| Campaign | Cluster ID, region variant, lure family, time window |

## Analyst Questions This Answers

- Which countries saw this dropper most often?
- What file paths were most commonly used?
- Which domains and IPs were reused across tenants?
- Were there regional campaign variants?
- What follow-on payloads were associated with this hash?

## License

See [LICENSE](LICENSE) for details.