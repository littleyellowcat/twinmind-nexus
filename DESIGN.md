# Design

## Product Name

TwinMind Archive

## Design Direction

Archive Observatory.

TwinMind Archive should feel like a dark research observatory for code knowledge: a precise engineering workspace where a project becomes an archive, its modules become halls, and its relationships become a navigable star map.

The target is not a flashy sci-fi control room. It is a focused product UI with a memorable spatial metaphor.

## Physical Scene

A developer is working at night or in a quiet study session, trying to understand a large unfamiliar repository. The ambient light is low, the task is cognitive, and the interface should reduce noise while making relationships visible. This supports a dark, restrained, high-contrast product theme.

## Visual Principles

- The graph is the main stage, not a decorative widget.
- Halls organize knowledge; evidence cards prove claims.
- Internal IDs are secondary metadata, never the primary reading surface.
- Metrics summarize archive health, but they should not dominate the page.
- Dense views are allowed when they improve engineering comprehension.
- Tables are fallbacks and detail views, not the hero experience.

## Color System

Use a restrained dark palette with a precise cyan/green archive accent.

```css
:root {
  --tm-bg: #080d14;
  --tm-bg-elevated: #0d141f;
  --tm-panel: #111a27;
  --tm-panel-2: #162233;
  --tm-border: #263445;
  --tm-border-strong: #3b4d63;

  --tm-text: #eef6ff;
  --tm-text-muted: #9aa9ba;
  --tm-text-subtle: #6f8093;

  --tm-accent: #35d0ba;
  --tm-accent-2: #6aa8ff;
  --tm-risk: #f3b65f;
  --tm-danger: #ef6b7a;
  --tm-success: #6fdc8c;

  --tm-file: #6aa8ff;
  --tm-function: #35d0ba;
  --tm-class: #b894ff;
  --tm-config: #f3b65f;
  --tm-doc: #d4e157;
  --tm-import: #9aa9ba;
}
```

Color use:

- Accent: primary action, active selection, current graph path.
- Blue: files and architecture structure.
- Green/cyan: functions, successful ingestion, live graph focus.
- Amber: risk, configuration, caution.
- Rose: errors, destructive states.
- Muted slate: inactive relations and background scaffolding.

Avoid:

- Purple-blue gradients as the main identity.
- Full neon cyberpunk saturation.
- Glassmorphism as the default surface.
- Low-contrast gray text on dark panels.

## Typography

Primary UI font: system sans or a clean product font.

Recommended stack:

```css
font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
```

Monospace for code paths, entity IDs, relation labels, and compact technical data:

```css
font-family: "SF Mono", "JetBrains Mono", "Cascadia Code", monospace;
```

Scale:

- Page title: 32px / 40px, 700
- Section title: 20px / 28px, 650
- Panel title: 15px / 22px, 650
- Body: 14px / 22px, 400
- Label: 12px / 16px, 600
- Metadata: 12px / 16px, 400
- Code/path: 12px / 18px, 500

Do not use display fonts for buttons, labels, data tables, or graph labels.

## App Shell

The future primary UI should be a three-zone product shell.

```text
┌────────────────────────────────────────────────────────────────────┐
│ Top Bar: project switcher, scope, ingest status, command button     │
├───────────────┬──────────────────────────────────────┬─────────────┤
│ Archive Halls │ Star Map / Current Work Surface       │ Evidence    │
│ Navigation    │ graph, passport, reports, tables      │ Drawer      │
├───────────────┴──────────────────────────────────────┴─────────────┤
│ Agent Command Bar / Trace Timeline                                  │
└────────────────────────────────────────────────────────────────────┘
```

Desktop default:

- Left rail: 260px
- Main work surface: flexible
- Right evidence drawer: 360-440px
- Bottom Agent bar: collapsible, 72px collapsed / 280px expanded

Tablet:

- Left rail collapses to icons.
- Evidence drawer becomes overlay sheet.

Mobile:

- Primary tabs: Archive, Star Map, Evidence, Agent.
- Graph view uses clustered list plus simplified node view.

## First Screen States

### 1. Empty Archive

Goal: make the user understand the product in one action.

Layout:

- Top title: TwinMind Archive
- Subtitle: Project archive observatory for GraphRAG and Agent analysis.
- Central upload dock: project ZIP, ingestion scope, build archive.
- Secondary actions: sample project, local path, recent archives.
- Right side preview: ghosted mini star map and evidence card skeleton.

Copy style:

- Use verbs like "Create Archive", "Build Star Map", "Inspect Evidence".
- Avoid "ingest" as the primary button label for non-technical users.

### 2. Ingestion In Progress

Goal: show progress without blocking trust.

Stages:

1. Unpack project
2. Filter scope
3. Detect languages
4. Extract entities
5. Build relations
6. Write evidence cards
7. Prepare archive

Each stage has:

- Status icon
- Current file or phase label
- Count when available
- Error recovery if failed

Motion:

- 150-250ms state transitions.
- Use subtle progress shimmer or line sweep.
- Respect reduced motion.

### 3. Project Passport

Goal: summarize the project as an archive object.

Content:

- Project name
- Ingestion scope
- Main language distribution
- Files scanned
- Entities
- Relations
- Evidence cards
- Last built time
- Risk hints

Visual:

- Compact header band, not oversized metric cards.
- Counts grouped with labels and small semantic icons.
- Show "architecture-first" badge when using default scope.

### 4. Archive Observatory

Goal: explore the graph.

Main composition:

- Left: archive hall list with counts and filters.
- Center: graph canvas with cluster controls.
- Right: evidence drawer.
- Bottom: Agent command and trace.

Default graph:

- Show clustered modules first, not thousands of nodes.
- Highlight the selected hall.
- Provide search/filter for entity type and path.
- Provide table/list fallback.

## Components

### Archive Hall Item

Fields:

- Hall name
- Count
- Short description
- Dominant entity types
- Active/focused state

States:

- Default
- Hover
- Focus
- Active
- Empty

### Project Passport

Fields:

- Project name
- Scope badge
- Language badges
- Count strip
- Archive health state

Avoid raw metric blocks. Use compact summary rows and small semantic indicators.

### Star Map

Graph rules:

- Node color by entity type.
- Node size by connection count or importance.
- Edge color muted by default.
- Selected path uses accent color.
- Hover reveals readable label.
- Click opens evidence drawer.
- Double-click or action button focuses neighborhood.

Scale rules:

- Under 100 nodes: SVG or Canvas graph.
- 100-500 nodes: Canvas with clustering.
- Over 500 nodes: show clusters by default; drill down by hall/module.

Accessibility:

- Always provide relation table fallback.
- Keyboard users can navigate entity list and open evidence drawer.

### Evidence Drawer

Sections:

- Header: entity name, type, source path.
- Evidence cards: title, snippet, line range, confidence.
- Relations: incoming/outgoing grouped by type.
- Agent actions: explain this node, trace impact, audit risk.

No modal needed. Use inline drawer.

### Agent Command Bar

Commands:

- Explain this project
- Find key modules
- Trace impact
- Audit risks
- Summarize evidence
- Generate architecture report

Behavior:

- Command palette opens with keyboard shortcut later.
- Results show in a report panel with citations.
- Trace timeline shows retrieval, graph traversal, evidence selection, answer composition.

## Motion System

Use motion to communicate state and focus only.

Recommended:

- Drawer open/close: transform x + opacity, 180ms, ease-out.
- Node focus: scale + edge opacity transition, 160ms.
- Ingestion stage update: crossfade and progress line, 200ms.
- Command result reveal: vertical translate 8px + opacity, 180ms.

Avoid:

- Decorative page-load choreography.
- Infinite ambient particles in the product surface.
- Animating width, height, top, or left.
- Scroll-driven spectacle.

If React is used later, GSAP is appropriate for graph focus transitions, staged ingestion animations, and command palette micro-interactions. Use `gsap.context()` or `useGSAP()` with cleanup, and respect `prefers-reduced-motion`.

## Streamlit MVP Redesign

The current Streamlit dashboard should become a cleaner bridge, not the final form.

Immediate improvements:

- Add scoped CSS theme for TwinMind Archive page.
- Replace raw page sections with an app-shell layout.
- Hide backend-like fields in advanced sections.
- Use readable entity names everywhere.
- Make upload dock and project passport the first visible sections.
- Convert star map table into a graph preview or clustered relation browser.
- Move type tables into a compact "Archive Stats" panel.

Streamlit constraints:

- Deep interactivity and graph manipulation will remain limited.
- It is acceptable as an internal dashboard and MVP demo.
- The long-term product should move to React for graph canvas, drawers, command palette, and motion.

## React Target Architecture

Recommended frontend stack when moving beyond Streamlit:

- React + Vite
- TypeScript
- React Flow or Cytoscape.js for graph exploration
- TanStack Query for API state
- Zustand or local reducers for UI state
- GSAP for focused motion where CSS is not enough
- Lucide icons

The backend can expose:

- `GET /archives`
- `POST /archives/upload`
- `GET /archives/{id}`
- `GET /archives/{id}/graph?scope=...`
- `GET /archives/{id}/evidence/{evidence_id}`
- `POST /archives/{id}/query`

## Implementation Phases

### Phase 1: Streamlit Visual Repair

- Apply Archive Observatory theme.
- Add ingestion scope UI polish.
- Improve empty, loading, and error states.
- Add project passport.
- Improve hall cards and evidence formatting.

### Phase 2: Knowledge Graph Experience

- Add clustered graph visualization.
- Add node focus and evidence drawer.
- Add table fallback and graph filters.
- Add readable relation labels and path highlighting.

### Phase 3: Agent Workbench

- Replace basic query output with report cards.
- Add Agent trace timeline.
- Add mode-specific outputs: architecture tour, impact analysis, risk audit, evidence Q&A.

### Phase 4: React Frontend

- Build full Archive Observatory app shell.
- Keep Streamlit as admin/debug dashboard.
- Add proper upload progress, graph canvas, command palette, and drawer interactions.

## Quality Bar

Before shipping any redesign:

- Text contrast meets WCAG AA.
- No raw internal IDs as main display labels.
- Buttons, inputs, tabs, drawers, and graph controls have hover/focus/active states.
- Reduced motion is respected.
- Graph has an accessible table/list fallback.
- Mobile and tablet layouts do not overlap.
- Upload errors explain exactly what happened and what to do next.
- Empty states teach the next action.
