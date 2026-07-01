# TwinMind Archive Optimization Roadmap

This roadmap records the next six optimization directions for TwinMind Archive, ordered by implementation priority. The goal is to move the project from "many features exist" to "the workflow is understandable, trustworthy, and demo-ready."

## 1. End-to-End Demo Project Mode

Status: implemented in the first optimization pass.

Build a guided demo flow that helps a first-time user move through the complete product loop:

1. Upload a project ZIP.
2. Generate the archive.
3. Open graph exploration.
4. Run Agent analysis.
5. Open the knowledge universe.
6. Generate a cross-project A/B architecture diff when two or more archives exist.

The UI should show the current recommended next action without turning the app into a marketing page.

## 2. Stronger Agent Work Proof

Status: first implementation pass complete. The UI now shows phase metrics and an inspectable Plan / Action / Observation / Verify / Final timeline derived from explicit Agent metadata.

Make Agent output feel inspectable and serious:

- Show Plan / Action / Observation / Verify / Final phases.
- Show which tools were used.
- Mark evidence-supported findings separately from uncertain claims.
- Preserve task traces per project.
- Avoid pretending the Agent did more than it actually did.

## 3. Large-Project Graph Usability

Status: in progress. The first pass added entity type filters to the Graph Explorer so large neighborhoods can be narrowed before inspection. The second pass added graph lens presets and relation type filters backed by the existing neighborhood API. The third pass added explicit recommendation explanations plus foldable node/relation cluster lists. The fourth pass made search results open a full entity neighborhood and upgraded saved routes into a richer path library.

Improve graph exploration for projects with tens of thousands of entities:

- Add entity type filters.
- Add entry point, config, API, data-flow, and dependency-focused views.
- Support cluster folding and expansion.
- Explain why a node is recommended.
- Let search results open directly into a neighborhood.
- Reopen saved paths.

## 4. Formal A/B Architecture Diff Reports

Status: first implementation pass complete. The backend now persists formal sections, component deltas, risk points, migration notes, and evidence-chain references for A/B architecture reports. The React knowledge-universe view renders these fields as an inspectable report rather than only a short summary.

Upgrade cross-project comparison from a structured summary into a report:

- Shared architecture surfaces.
- Module boundary differences.
- Configuration and dependency differences.
- RAG / Agent / backend / frontend component recognition.
- Risk points.
- Migration or reuse recommendations.
- Evidence chain references.

## 5. Ingestion Quality Diagnostics

Status: first implementation pass complete. Archive generation now persists upload filtering, scanner skip reasons, extraction and Tree-sitter counters, graph output counts, image understanding status, Hybrid RAG status, health warnings, and recommendations. The archive overview renders these diagnostics for the selected project.

Add a diagnostic panel that explains why an archive may look sparse:

- ZIP files discovered, kept, and skipped.
- Ignored directories and file size limits.
- Language counts.
- Tree-sitter extraction success/failure counts.
- Image understanding counts.
- Hybrid RAG index status.
- Step-level failures and fallbacks.

## 6. More Visible Multimodal RAG

Status: first implementation pass complete. The archive overview now highlights image evidence, separates evidence by image/code/config/text, marks Hybrid RAG and vision fallback evidence, and Agent query reports surface Hybrid RAG hit counts plus cited evidence modality counts.

Make multimodal behavior obvious in the product:

- Show image evidence cards prominently.
- Display image captions and linked entities.
- Mark when search hits image-derived content.
- Show whether Agent reports cite image evidence.
- Separate text, code, config, and image evidence in result panels.

## Current Implementation Order

The first implementation pass starts with item 1, then proceeds downward. Each item should add tests or build verification when possible.

## Next Stage

After the first six optimization items, continue with the second-stage roadmap in `docs/twinmind_archive_second_stage_optimization_plan.md`.
