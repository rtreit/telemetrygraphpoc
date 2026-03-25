# Copilot Instructions

## Project Overview

**Global Malware IOC Telemetry Graph** — a proof of concept that simulates global cross-tenant telemetry for a known malware IOC (a SHA-256 dropper hash seen in a large-scale email campaign). It generates realistic synthetic data, constructs a rich entity graph, and exposes it through a web application with an interactive 3D graph visualization.

## Architecture

The project has four clearly separated layers:

```
generator/      — Synthetic telemetry generator (Python)
pipeline/       — Graph construction pipeline: transforms raw telemetry into nodes + edges (Python)
api/            — Backend API serving graph data and node details (Python / FastAPI)
frontend/       — Single-page React app with 3D force-directed graph (TypeScript / React)
```

### Entity types
- **File/Malware**: SHA-256 hashes, file names, paths, dropped files, process trees, signatures
- **Host/Device**: device ID, hostname, OS, device type, environment, country, tenant, security posture
- **Email**: message ID, sender, subject, attachment, delivery time, SPF/DKIM/DMARC, campaign traits
- **Network/Infrastructure**: URLs, domains, IPs, ASN, ports, SSL certs, geo
- **Execution/Behavior**: process events, persistence, scheduled tasks, C2 connections, follow-on payloads
- **Campaign**: cluster ID, region variant, lure family, time window, infrastructure reuse

### Key relationships
The graph supports pivoting from the seed IOC outward through: email → user → host → file → process → domain → IP → country → tenant → campaign and back.

## Build and Run

```bash
# Backend — install dependencies
cd api
uv pip install -r requirements.txt

# Backend — generate synthetic data
python -m generator.generate --seed 42 --nodes 5000

# Backend — build graph from telemetry
python -m pipeline.build

# Backend — start API server
uvicorn api.main:app --reload --port 8000

# Frontend — install dependencies
cd frontend
npm install

# Frontend — start dev server
npm run dev
```

## Conventions

- **Python packaging**: Use `uv` instead of `pip` for installing Python packages.
- **Deterministic generation**: The telemetry generator must accept a `--seed` parameter for reproducible output.
- **Data format**: Raw telemetry is stored as JSON. Graph nodes and edges are serialized as JSON for the API.
- **Graph structure**: Nodes have `id`, `type`, `label`, and a `properties` dict. Edges have `source`, `target`, `type`, and optional `properties`.
- **Frontend**: React with TypeScript. 3D rendering via `3d-force-graph` or equivalent Three.js-based library.
- **Styling**: Dark theme, Tailwind CSS. Country-based color coding. Node shapes/icons by entity type.
- **Target scale**: Minimum 5,000 nodes, 25+ countries, multiple tenants and campaign variants.
- **Testing**: pytest for Python, vitest or jest for frontend.
- **PR workflow**: When creating or editing GitHub PRs with `gh` on PowerShell, always use `--body-file` instead of `--body` to avoid backtick escape corruption.
- **File search**: Use `es` (Everything Search CLI) to find files on disk by name — it's instant and searches the entire filesystem.

## Data Generation Guidelines

The synthetic data should feel plausible:
- Uneven geographic distribution (not uniform across countries)
- Infrastructure and campaign reuse patterns across tenants
- Some benign-adjacent artifacts to add noise
- Time-based campaign progression by region
- OS-appropriate file paths (Windows: AppData/Temp/Downloads, Linux: /tmp, /var/tmp, home dirs)
- Varied host behavior: some only receive email, some execute, some download follow-on payloads
- Campaign variants that differ by subject line, sender domain, or target geography

## Visualization Requirements

The 3D graph must support:
- Rotate, pan, zoom
- Node selection with property inspection
- Highlight connected entities
- Neighborhood expansion
- Filtering by entity type, country/region, time window, campaign cluster
- Search by hash, hostname, domain, user, subject, or IP
- Country-based color coding
- Different shapes/icons for major node types
- Edge labels on demand
- Collapse/hide noisy categories
- Dark background, smooth camera controls, tooltips and side panel
