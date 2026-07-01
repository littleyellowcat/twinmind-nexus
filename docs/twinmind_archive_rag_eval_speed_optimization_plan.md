# TwinMind Archive RAG, Evaluation, and Speed Optimization Plan

## 1. Hybrid RAG Index Health and Rebuild

Problem: large archives can contain tens of thousands of entities and evidence cards while the persisted Hybrid RAG status may contain only a tiny stale index. This makes evidence retrieval, evaluation, reports, and Agent answers look much worse than the archive actually is.

Implementation direction:

- Add project-level Hybrid RAG health fields: candidate chunks, indexed chunks, coverage ratio, stale status, and indexing policy.
- Add a background rebuild endpoint so users can rebuild RAG without re-uploading the project.
- Use prioritized bounded indexing by default for large projects: important evidence, important entities, relations with evidence, config/docs/entry files first.
- Keep a configurable full-index path through environment variables for deeper offline runs.

## 2. Better Golden Questions and Evaluation Scoring

Problem: existing evaluation can generate overly generic questions such as package names or broad concepts, then grade with exact ID matching. This punishes otherwise useful graph and RAG retrieval.

Implementation direction:

- Prefer concrete classes, functions, interfaces, files, config entries, and module boundaries.
- Filter low-information entities such as package roots, generic concepts, and very short names.
- Generate questions with source-path context.
- Score exact hits highly, but also give partial credit for one-hop neighbors, same-file evidence, and relation-neighbor evidence.
- Keep low scores meaningful: unsupported answers should still fail.

## 3. Fast and Deep Agent Modes

Problem: DeepSeek-backed analysis can be slow on large projects, while users need a fast first answer.

Implementation direction:

- Add `fast` Agent mode that uses deterministic graph/rule analysis and skips per-role LLM enhancement.
- Add `deep` Agent mode that uses configured LLM enhancement.
- Default UI action should run the fast mode first; formal reports and deeper analysis can opt into deep mode later.
- Preserve provider/mode metadata so the UI clearly says whether a report is rule-based or model-enhanced.
