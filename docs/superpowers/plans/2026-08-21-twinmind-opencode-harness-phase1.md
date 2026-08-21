# TwinMind opencode Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the opencode-inspired harness engineering layer to TwinMind Nexus: durable events, bounded artifacts, governance, role capabilities, run summary/resume guidance, trace artifactization, provider/cost policy dry-run, and developer debugging tools.

**Architecture:** Keep the implementation project-local and deterministic. Add small harness modules under `src/project_archive/`, integrate them into AgentEval/mission APIs and developer scripts, and avoid real external services in tests.

**Tech Stack:** Python dataclasses, JSON/JSONL files, FastAPI, pytest.

---

## File Structure

- Create `src/project_archive/harness_events.py`: append-only project event stream with monotonic sequence numbers and list/filter helpers.
- Create `src/project_archive/harness_artifacts.py`: bounded artifact store that writes full content, returns preview/hash/size metadata.
- Create `src/project_archive/harness_governance.py`: operation rules, allow/ask/deny evaluator, role capability matrix.
- Modify `src/project_archive/service.py`: initialize harness helpers, expose events/capabilities/summary/policy, wrap AgentEval runs with events and artifacts, artifactize mission trace.
- Modify `src/project_archive/api.py`: add harness capability, policy, project event/summary, and trace artifact endpoints.
- Create `scripts/harness_doctor.py`: local storage diagnostics for harness state.
- Create `scripts/harness_events.py`: local JSONL event browser for project harness streams.
- Create `tests/unit/test_project_archive_harness.py`: unit tests for events, artifacts, governance.
- Modify `tests/unit/test_project_archive_api.py`: API tests for harness endpoints and AgentEval artifact metadata.
- Modify `docs/twinmind_archive_quickstart.md`: add harness debugging commands and API notes.

## Task 1: Harness Event Stream

**Files:**
- Create: `src/project_archive/harness_events.py`
- Test: `tests/unit/test_project_archive_harness.py`

- [x] Step 1: Write failing tests for event append/list ordering.
- [x] Step 2: Run `python -m pytest tests/unit/test_project_archive_harness.py -q` and confirm import failure.
- [x] Step 3: Implement `HarnessEventStore.append()` and `HarnessEventStore.list_events()`.
- [x] Step 4: Run the focused test and confirm event tests pass.

## Task 2: Bounded Artifact Store

**Files:**
- Modify: `src/project_archive/harness_artifacts.py`
- Test: `tests/unit/test_project_archive_harness.py`

- [x] Step 1: Add failing tests for long output preview, sha256, bytes, and full content retention.
- [x] Step 2: Run focused tests and confirm failure.
- [x] Step 3: Implement `HarnessArtifactStore.persist_text()`.
- [x] Step 4: Run focused tests and confirm artifact tests pass.

## Task 3: Governance and Capability Matrix

**Files:**
- Create: `src/project_archive/harness_governance.py`
- Test: `tests/unit/test_project_archive_harness.py`

- [x] Step 1: Add failing tests for allow/ask/deny and role capabilities.
- [x] Step 2: Run focused tests and confirm failure.
- [x] Step 3: Implement operation rules and role matrix.
- [x] Step 4: Run focused tests and confirm governance tests pass.

## Task 4: Service Integration

**Files:**
- Modify: `src/project_archive/service.py`
- Test: `tests/unit/test_project_archive_api.py`

- [x] Step 1: Add failing API/service tests asserting AgentEval writes harness events and artifact metadata.
- [x] Step 2: Run focused API tests and confirm failure.
- [x] Step 3: Integrate event/artifact stores into `ProjectArchiveService.run_agent_eval_harness()`.
- [x] Step 4: Expose `list_harness_events()` and `harness_capabilities()`.
- [ ] Step 5: Run focused tests and confirm service integration passes.
  - Current environment note: API/service pytest collection is blocked before assertions by missing runtime dependency `jieba` under the available Python 3.9 interpreter. Python 3.12 is present but lacks pytest/project dependencies. Syntax compilation for service/API passes.

## Task 5: API Endpoints

**Files:**
- Modify: `src/project_archive/api.py`
- Test: `tests/unit/test_project_archive_api.py`

- [x] Step 1: Add failing tests for `/api/harness/capabilities` and `/api/archives/{project_id}/harness/events`.
- [x] Step 2: Run focused API tests and confirm failure.
- [x] Step 3: Add endpoints using existing service dependency.
- [ ] Step 4: Run focused API tests and confirm endpoints pass.
  - Current environment note: endpoint tests are written but cannot collect in this checkout without the project test environment dependencies.

## Task 6: Verification

**Files:**
- No new files.

- [ ] Step 1: Run `python -m pytest tests/unit/test_project_archive_harness.py tests/unit/test_project_archive_api.py -q`.
  - Partial verification completed: `tests/unit/test_project_archive_harness.py` passes 4/4. API test collection is blocked by missing `jieba`.
- [x] Step 2: Run `git diff --check`.
- [x] Step 3: Review `docs/superpowers/specs/2026-08-21-twinmind-opencode-harness-engineering-design.md` against implemented Phase 1 scope.

## Task 7: Run Summary and Resume Guidance

**Files:**
- Modify: `src/project_archive/service.py`
- Modify: `src/project_archive/api.py`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/styles.css`
- Test: `tests/unit/test_project_archive_harness.py`
- Test: `tests/unit/test_project_archive_api.py`

- [x] Step 1: Add tests for `harness_run_summary()` using events, artifacts, warnings, errors, latest sequence, and next action.
- [x] Step 2: Run focused harness tests and confirm the summary test fails.
- [x] Step 3: Implement summary generation from harness events, AgentEval report, version history, and mission records.
- [x] Step 4: Add `GET /api/archives/{project_id}/harness/summary`.
- [x] Step 5: Run focused tests and confirm summary behavior.
- [x] Step 6: Expose summary in the AgentEval and System configuration pages.

## Task 8: Provider Policy and Cost Guard

**Files:**
- Modify: `src/project_archive/service.py`
- Modify: `src/project_archive/api.py`
- Test: `tests/unit/test_project_archive_harness.py`
- Test: `tests/unit/test_project_archive_api.py`

- [x] Step 1: Add tests for policy dry-run decisions and sanitized provider/config hints.
- [x] Step 2: Run focused tests and confirm policy tests fail.
- [x] Step 3: Implement `harness_policy_check()` around existing governance rules.
- [x] Step 4: Add `POST /api/harness/policy-check`.
- [x] Step 5: Include provider policy metadata in harness capabilities.

## Task 9: Trace Artifactization

**Files:**
- Modify: `src/project_archive/service.py`
- Modify: `src/project_archive/api.py`
- Test: `tests/unit/test_project_archive_harness.py`
- Test: `tests/unit/test_project_archive_api.py`

- [x] Step 1: Add tests that persist an Agent mission trace as bounded artifact metadata.
- [x] Step 2: Run focused tests and confirm trace artifact tests fail.
- [x] Step 3: Implement `agent_mission_trace_artifact(mission_id)`.
- [x] Step 4: Add `GET /api/agent-missions/{mission_id}/trace-artifact`.
- [x] Step 5: Write `artifact.persisted` event for the mission project.
  - Current environment note: API tests are specified but full API pytest collection remains blocked by missing project runtime dependencies under the available Python interpreters.

## Task 10: Developer Experience

**Files:**
- Create: `scripts/harness_doctor.py`
- Create: `scripts/harness_events.py`
- Modify: `scripts/run_github_zip_regression.py`
- Modify: `docs/twinmind_archive_quickstart.md`
- Test: `tests/unit/test_project_archive_harness.py`

- [x] Step 1: Add CLI tests for stdlib-only doctor/events helpers.
- [x] Step 2: Run focused tests and confirm CLI tests fail.
- [x] Step 3: Implement scripts without importing project-heavy dependencies.
- [x] Step 4: Document harness debugging in quickstart.
- [x] Step 5: Run scripts against an empty temp storage or fixture-style project.
- [x] Step 6: Attach harness status, latest sequence, and artifact counts to GitHub ZIP regression rows.

## Notes

- This phase must not require DeepSeek/OpenAI/Ollama network access.
- This phase must not add Bash/file-edit/patch tools to TwinMind Agent capabilities.
- Full resume/retry orchestration remains read-only guidance unless a future phase adds explicit recovery commands.
