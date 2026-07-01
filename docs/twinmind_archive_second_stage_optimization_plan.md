# TwinMind Archive Second-Stage Optimization Plan

This document records the next seven optimization directions after the first roadmap pass. The goal of this stage is to move TwinMind Archive from "feature-complete MVP" toward a trustworthy, scalable, and inspectable project-intelligence workspace.

## 1. Large-Project Ingestion Performance And Stability

Status: implementation pass complete. Upload and Agent report jobs now expose list/cancel state, step history, cancellation markers, and ingestion stage callbacks. Ingestion metadata preserves partial graph output, stage timing, Hybrid RAG/vision failure details, and diagnostics for retry decisions.

Why it matters:

- Large ZIP uploads and 10k-100k entity archives need reliable background execution.
- Users need to know whether ingestion is running, paused, failed, or recoverable.
- Current diagnostics explain what happened after ingestion; this step should make ingestion itself more robust.

Target improvements:

- Add resumable or restartable ingestion jobs.
- Add cancel support for long-running archive generation.
- Persist stage timing for upload, extraction, graph build, Hybrid RAG, vision, and Agent preparation.
- Add retry metadata for recoverable failures.
- Add incremental ingestion for unchanged project files.
- Preserve partial archive artifacts when a late stage fails.

Acceptance signals:

- A large project can fail in Hybrid RAG or vision without losing all scan/extraction output.
- The frontend can show stage-by-stage timing and failure location.
- Users can safely retry the failed stage or regenerate the archive.

## 2. More Professional Graph Workspace

Status: implementation pass complete. The backend exposes a graph workspace report with module clusters, module boundary candidates, relation confidence, weak relations, saved curation state, and graph snapshot diffs. The React graph page now surfaces those signals above the large-project graph workbench.

Why it matters:

- The graph is the central way users understand unfamiliar projects.
- Large projects need graph operations that explain architecture rather than just display nodes.

Target improvements:

- Add a richer entity detail page or drawer.
- Add path explanations that summarize why two entities are connected.
- Add relation confidence and evidence strength.
- Add automatic community or module clustering.
- Add module boundary detection.
- Add graph snapshot comparison for the same project across regenerations.

Acceptance signals:

- Users can start from an unknown project and discover major modules without knowing search keywords.
- Clicking a relation or path explains its evidence and confidence.
- Large graphs can be explored through clusters and saved viewpoints.

## 3. Stronger Agent Trust And Verification

Status: implementation pass complete. The backend exposes an Agent trust report that separates supported, partial, unsupported, and low-confidence claims across multi-agent reports and ReAct missions. The Agent page now shows this trust check beside model status, reports, and task history.

Why it matters:

- Agent reports must feel inspectable, not magical.
- Users need to distinguish evidence-backed conclusions from guesses.

Target improvements:

- Expand every Agent step with tool input and output summaries.
- Add clear failure reasons and retry records.
- Add Agent self-correction history.
- Enforce report citation checks before final output.
- Add low-confidence and unsupported-claim warnings.
- Separate deterministic, Hybrid RAG, LLM, and tool-derived claims.

Acceptance signals:

- Every major Agent conclusion can be traced to evidence, graph nodes, retrieval hits, or an explicit fallback.
- Unsupported claims are marked for review instead of presented as final truth.
- Agent failures are understandable and actionable.

## 4. Deeper Multimodal RAG

Status: implementation pass complete. Multimodal insights are exposed through a dedicated archive API and UI panel, including image count, vision/OCR support, image quality, understanding method, and image-derived graph candidate counts.

Why it matters:

- The product now shows image evidence, but architecture diagrams should become first-class graph inputs.
- Images can contain module boundaries, service flows, screenshots, UI states, and deployment diagrams.

Target improvements:

- Add OCR for image text.
- Extract architecture diagram nodes and edges where possible.
- Link image-derived entities to code/config/document entities.
- Support image-aware questions in Agent reports.
- Mark which answers are supported by image evidence.
- Add image evidence quality scoring.

Acceptance signals:

- A project architecture diagram can contribute entities or relations to the graph.
- Agent answers can cite image-derived evidence and explain what was extracted from the image.
- Users can see whether an image was understood by vision, OCR, fallback metadata, or all three.

## 5. Evaluation And Benchmarking Upgrade

Status: implementation pass complete. Evaluation reports now have a public history endpoint, persisted run summaries, frontend history counts, and API tests covering benchmark run persistence.

Why it matters:

- A benchmark suite helps compare scan profiles, embedding models, vision models, and Agent modes.
- It also makes future changes safer.

Target improvements:

- Create a fixed benchmark project set across Python, Java, TypeScript, Go, Rust, and C++.
- Add golden questions for architecture, dependency, config, image, and risk analysis.
- Compare scan profiles: architecture, full, docs, and tests.
- Track graph coverage, entity hit rate, relation hit rate, evidence hit rate, and answer quality.
- Persist benchmark history by run.
- Add a frontend benchmark dashboard.

Acceptance signals:

- A user can run benchmark evaluation and compare results across model/config choices.
- Regressions in ingestion, retrieval, or Agent reports become visible.
- Benchmark outputs can guide model and configuration choices.

## 6. Transparent System Configuration Check

Status: first implementation pass complete. The backend now exposes a redacted system configuration check, and the React workspace includes a dedicated System Config page showing LLM, embedding, vision, graph store, vector store, Hybrid RAG, and Agent runtime status.

Why it matters:

- Users repeatedly need to know whether DeepSeek, Ollama, embeddings, vision, Neo4j, Chroma, BM25, RRF, and Agent modes are actually active.
- The product should answer this directly in the UI.

Target improvements:

- Add a system configuration page or panel.
- Show LLM provider, model name, API key presence, and last successful call.
- Show embedding provider, dimension, model, and last index status.
- Show vision provider, model, enabled/disabled state, and last error.
- Show graph provider: local or Neo4j.
- Show Hybrid RAG components: Chroma/vector, BM25, RRF, fallback reasons.
- Add configuration warnings and recommended fixes.

Acceptance signals:

- Users can open one page and know exactly which backends are active.
- Misconfiguration is shown before users waste time testing uploads.
- The UI distinguishes "not configured", "configured but failed", and "working".

## 7. Frontend Information Architecture Cleanup

Status: implementation pass complete. The workspace is now organized across Archive Overview, Graph Exploration, Agent Analysis, Knowledge Universe, and System Config, with new focused panels for ingestion diagnostics, graph workspace signals, Agent trust, multimodal evidence, evaluation history, and configuration status.

Why it matters:

- The frontend has grown from a simple MVP into a multi-page workbench.
- Users need clearer navigation as more serious features land.

Target improvements:

- Split the product into clearer workspaces:
  - Archive Overview.
  - Ingestion Diagnostics.
  - Graph Workspace.
  - RAG Search.
  - Agent Tasks.
  - Evaluation Center.
  - Knowledge Universe.
- Move dense secondary panels out of the main overview.
- Make project selection and current project state persistent across pages.
- Add empty states that explain what to do next without feeling like a landing page.
- Review responsive layout for all major pages.

Acceptance signals:

- New users can understand where to upload, inspect graph, run RAG, run Agent, evaluate, and compare projects.
- Existing users can jump directly to the task they care about.
- Pages feel focused instead of crowded.

## Recommended Implementation Order

1. Transparent System Configuration Check.
2. Large-Project Ingestion Performance And Stability.
3. Frontend Information Architecture Cleanup.
4. More Professional Graph Workspace.
5. Stronger Agent Trust And Verification.
6. Deeper Multimodal RAG.
7. Evaluation And Benchmarking Upgrade.

The recommended first item is the system configuration check because it directly answers whether DeepSeek, Ollama, vision, embedding, graph storage, and Hybrid RAG are truly active. That makes every later optimization easier to test and trust.
