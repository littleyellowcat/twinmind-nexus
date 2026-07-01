# TwinMind Archive Frontend

React + Vite product frontend for the TwinMind Archive observatory.

This is the user-facing workspace. The Streamlit dashboard remains useful as an
internal debug/admin surface, but the archive exploration experience belongs here.

```bash
npm install
npm run dev
```

Initial scope:

- Three-zone workbench: Archive Halls, Star Map, Evidence Drawer.
- Top project/upload command surface.
- Bottom Agent command bar.
- Mock archive data derived from `MODULAR-RAG-MCP-SERVER`.

Next integration step:

- Add FastAPI endpoints for archive list, upload, graph, evidence, and Agent query.
