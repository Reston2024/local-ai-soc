---
phase: "01"
plan: "04"
subsystem: "dashboard"
tags: ["svelte5", "vite6", "frontend", "spa", "cytoscape", "dark-theme", "soc-ui"]
dependency_graph:
  requires: ["backend/api/health", "backend/api/events", "backend/api/detections", "backend/api/graph", "backend/api/query", "backend/api/ingest"]
  provides: ["dashboard/dist", "dashboard/src"]
  affects: ["backend/main.py (static file mount)"]
tech_stack:
  added: ["svelte@5.28", "vite@6.2.5", "@sveltejs/vite-plugin-svelte@5.0.3", "cytoscape@3.31", "d3@7.9", "typescript@5.7.3"]
  patterns: ["svelte5-runes", "vite-proxy", "sse-streaming", "css-custom-properties"]
key_files:
  created:
    - dashboard/package.json
    - dashboard/vite.config.ts
    - dashboard/tsconfig.json
    - dashboard/svelte.config.js
    - dashboard/index.html
    - dashboard/src/main.ts
    - dashboard/src/App.svelte
    - dashboard/src/app.css
    - dashboard/src/lib/api.ts
    - dashboard/src/views/DetectionsView.svelte
    - dashboard/src/views/EventsView.svelte
    - dashboard/src/views/GraphView.svelte
    - dashboard/src/views/QueryView.svelte
    - dashboard/src/views/IngestView.svelte
    - dashboard/.gitignore
  modified: []
decisions:
  - "Used standalone tsconfig.json (not @tsconfig/svelte extend) for reliability with moduleResolution: bundler"
  - "Added @tsconfig/svelte to devDependencies as fallback but wrote flat tsconfig for portability"
  - "Cytoscape COSE layout chosen (built-in, no extra plugin needed for basic force-directed)"
  - "SSE streaming collected to full string in api.query.ask() — real-time token display deferred to Phase 3"
metrics:
  duration: "316 seconds (5m 16s)"
  completed_date: "2026-03-15"
  tasks_completed: 10
  tasks_total: 10
  files_created: 15
  files_modified: 0
---

# Phase 1 Plan 4: Svelte 5 Dashboard SPA Summary

**One-liner:** Dark-themed SOC investigation dashboard with Cytoscape.js graph, semantic event search, AI query interface, and drag-drop ingest — built with Svelte 5 runes + Vite 6.

---

## What Was Built

A complete Svelte 5 single-page application serving as the frontend for AI-SOC-Brain. The dashboard connects to the FastAPI backend via a Vite dev proxy and will be served as static files from `dashboard/dist/` in production.

### Views

| View | File | Purpose |
|------|------|---------|
| Detections | DetectionsView.svelte | Severity-filtered detection table |
| Events | EventsView.svelte | Paginated events + semantic search |
| Graph | GraphView.svelte | Cytoscape.js force-directed entity graph |
| AI Query | QueryView.svelte | Chat-style interface with SSE streaming |
| Ingest | IngestView.svelte | Drag-drop file upload with job progress |

### Architecture

- **App shell** (`App.svelte`): Sidebar navigation, health status dot polling backend every 30s, conditional view rendering
- **API client** (`src/lib/api.ts`): Typed fetch wrapper covering all 7 backend router endpoints. SSE handler for `/api/query/ask`
- **Theme** (`app.css`): GitHub dark-inspired CSS custom properties, severity badge classes, scrollbar styling, base component styles (cards, buttons, tables, inputs)

---

## Tasks Completed

| # | Task | Commit |
|---|------|--------|
| 1 | Scaffold Svelte 5 + Vite 6 project | dd72811 |
| 2 | Typed API client with all backend endpoints | 4a86d88 |
| 3 | Dark SOC theme CSS | b8de2f9 |
| 4 | App shell + sidebar navigation | 8f27856 |
| 5 | DetectionsView | 3ad2a1a |
| 6 | EventsView | cf237d2 |
| 7 | GraphView (Cytoscape.js) | 6d5f097 |
| 8 | QueryView (SSE streaming) | 295bd40 |
| 9 | IngestView (drag-drop) | 93b541b |
| 10 | npm install + production build verified | 4a66e0e |

---

## Build Output

```
dist/index.html                  0.46 kB | gzip:   0.30 kB
dist/assets/index-*.css         15.36 kB | gzip:   3.16 kB
dist/assets/index-*.js         504.47 kB | gzip: 164.92 kB
121 modules transformed — built in 1.14s
```

Bundle is ~165 kB gzipped. The 504 kB pre-gzip size is expected: Cytoscape.js (~250 kB) and D3.js (~75 kB) account for most of it. Code splitting can be applied in a future phase if load time becomes an issue.

---

## Decisions Made

1. **Flat tsconfig.json** — Did not extend `@tsconfig/svelte` to avoid potential resolution issues. Used `allowImportingTsExtensions: true` and `noEmit: true` directly.

2. **Cytoscape COSE layout** — Used the built-in COSE algorithm (no plugin required). Adequate for subgraphs up to ~200 nodes. If needed, `cytoscape-fcose` can be added for larger graphs.

3. **SSE collected to string** — `api.query.ask()` reads the full SSE stream and returns the complete string. This is intentional for Phase 1 simplicity. Real-time token-by-token rendering will be implemented when the query API is finalized in Phase 3.

4. **Vite proxy** — All `/api` and `/health` requests proxy to `localhost:8000` during development. In production, Caddy handles the reverse proxy and the dashboard is served as static files mounted at `/app` by FastAPI.

---

## Deviations from Plan

None — plan executed exactly as written.

---

## Self-Check: PASSED

Files verified:
- dashboard/src/App.svelte: FOUND
- dashboard/src/lib/api.ts: FOUND
- dashboard/src/app.css: FOUND
- dashboard/src/views/DetectionsView.svelte: FOUND
- dashboard/src/views/EventsView.svelte: FOUND
- dashboard/src/views/GraphView.svelte: FOUND
- dashboard/src/views/QueryView.svelte: FOUND
- dashboard/src/views/IngestView.svelte: FOUND
- dashboard/dist/index.html: FOUND (build output)

Commits verified (all 10 tasks): dd72811, 4a86d88, b8de2f9, 8f27856, 3ad2a1a, cf237d2, 6d5f097, 295bd40, 93b541b, 4a66e0e
