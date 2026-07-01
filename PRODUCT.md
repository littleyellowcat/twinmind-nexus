# Product

## Register

product

## Users

TwinMind Archive is for developers, architecture reviewers, technical leads, AI engineers, and learners who need to understand an unfamiliar code project quickly without losing evidence. Users are usually in a work mode: importing a repository, reading architecture, tracing module relationships, auditing risks, or asking evidence-backed questions before changing code.

The primary user context is focused desktop work. The interface should support repeated analysis, scanning, comparison, and drill-down. It should feel trustworthy enough for real engineering decisions, not like a decorative demo.

## Product Purpose

TwinMind Archive turns a project into an explorable, evidence-backed knowledge archive. It ingests code, docs, configuration, and project artifacts; extracts entities, relationships, evidence cards, and archive halls; then supports RAG, knowledge graph exploration, and Agent-assisted project analysis.

Success means a user can drop in a project and quickly answer:

- What is this project?
- What are the important modules and entry points?
- How do modules collaborate?
- Which evidence supports this conclusion?
- What should I inspect before making a change?
- Where are risks, stale docs, or hidden coupling?

## Brand Personality

Research-grade, cinematic, precise.

The product should feel like an archive observatory: part project museum, part knowledge graph telescope, part engineering command desk. It should be imaginative but not theatrical. It should invite exploration while keeping every claim grounded in source evidence.

## Anti-references

TwinMind Archive should not look like:

- A generic Streamlit admin page with large raw metrics and default tables.
- A neon cyberpunk dashboard where decoration competes with the data.
- A SaaS landing page with oversized hero copy, marketing cards, and decorative gradients.
- A bland enterprise BI dashboard where the knowledge graph becomes just another table.
- A toy metaverse interface with unclear controls or non-standard affordances.

Avoid exposing internal IDs as primary display text. Users should see readable module names, file paths, relation labels, evidence titles, and Agent reasoning states.

## Design Principles

1. Evidence First

Every answer, graph path, and Agent conclusion should point back to source evidence. Visual polish must make evidence easier to inspect, not hide it.

2. Archive, Not Admin

The interface should use the metaphor of halls, artifacts, evidence cards, and star maps instead of generic dashboard sections. The metaphor should organize the product, not decorate it.

3. Focused Exploration

Large projects must be clustered and filtered before they are visualized. The default view should show architecture-level signal, with deeper layers available on demand.

4. Product Discipline

This is a working tool. Components should be familiar, accessible, responsive, and consistent. Motion should communicate state, focus, or relationship changes.

5. Progressive Depth

The user should be able to start with a simple project upload, then gradually move into graph exploration, evidence inspection, Agent reports, and future multimodal artifacts.

## Accessibility & Inclusion

Target WCAG 2.2 AA for product UI. Maintain visible focus states, keyboard-accessible navigation, readable contrast, and non-color-only status indicators.

Graph views must have text/table alternatives because network graphs are not accessible as the sole representation. Respect reduced-motion preferences. Avoid long decorative animations, flashing effects, tiny low-contrast labels, and hover-only information.
