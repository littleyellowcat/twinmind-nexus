"""Tests for the TwinMind Archive FastAPI integration."""

from __future__ import annotations

import json
import base64
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from fastapi.testclient import TestClient

from src.project_archive import api
from src.project_archive import service as service_module
from src.project_archive.service import ProjectArchiveService
from src.project_archive.types import (
    AgentMission,
    AgentMissionBudget,
    AgentMissionTask,
    AgentMissionVerifierResult,
    ArchiveHall,
    EvidenceCard,
    ProjectArchiveDraft,
    ProjectEntity,
    ProjectRelation,
)

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _sample_draft() -> ProjectArchiveDraft:
    return ProjectArchiveDraft(
        project_id="sample",
        halls=[
            ArchiveHall(
                id="hall_architecture",
                name="Architecture Hall",
                description="Files and modules.",
                entity_ids=["file:app.py", "func:run", "class:ArchiveService"],
            )
        ],
        entities=[
            ProjectEntity(id="file:app.py", type="File", name="app.py", evidence_ids=["ev:1"]),
            ProjectEntity(id="func:run", type="Function", name="run", evidence_ids=["ev:1"]),
            ProjectEntity(
                id="class:ArchiveService",
                type="Class",
                name="ArchiveService",
                evidence_ids=["ev:1"],
            ),
        ],
        relations=[
            ProjectRelation(
                id="rel:defines",
                source_id="file:app.py",
                target_id="func:run",
                type="DEFINES",
                evidence_ids=["ev:1"],
            )
        ],
        evidence_cards=[
            EvidenceCard(
                id="ev:1",
                source_type="code",
                source_path="app.py",
                title="run",
                snippet="def run(): pass",
            )
        ],
    )


def _sample_peer_draft() -> ProjectArchiveDraft:
    return ProjectArchiveDraft(
        project_id="peer",
        halls=[
            ArchiveHall(
                id="hall_architecture",
                name="Architecture Hall",
                description="Peer files and modules.",
                entity_ids=["file:main.py", "func:run"],
            )
        ],
        entities=[
            ProjectEntity(id="file:main.py", type="File", name="main.py", evidence_ids=["ev:peer"]),
            ProjectEntity(id="func:run", type="Function", name="run", evidence_ids=["ev:peer"]),
            ProjectEntity(id="class:ArchiveService", type="Class", name="ArchiveService", evidence_ids=["ev:peer"]),
        ],
        relations=[
            ProjectRelation(
                id="rel:peer-defines",
                source_id="file:main.py",
                target_id="func:run",
                type="DEFINES",
                evidence_ids=["ev:peer"],
            )
        ],
        evidence_cards=[
            EvidenceCard(
                id="ev:peer",
                source_type="code",
                source_path="main.py",
                title="run",
                snippet="def run(): return 'peer'",
            )
        ],
    )


def _write_draft(tmp_path: Path, draft: ProjectArchiveDraft) -> None:
    archive_dir = tmp_path / draft.project_id
    archive_dir.mkdir(exist_ok=True)
    (archive_dir / "draft_archive.json").write_text(
        json.dumps(draft.to_dict()),
        encoding="utf-8",
    )


def _client(tmp_path: Path) -> TestClient:
    draft = _sample_draft()
    _write_draft(tmp_path, draft)

    app = api.create_app()
    app.dependency_overrides[api.get_project_archive_service] = lambda: ProjectArchiveService(
        storage_dir=tmp_path
    )
    return TestClient(app)


def test_agent_status_reports_rule_mode_without_deepseek_key(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(
        "src.project_archive.llm.load_settings",
        lambda: SimpleNamespace(
            llm=SimpleNamespace(
                provider="deepseek",
                model="deepseek-v4-flash",
                base_url="https://api.deepseek.com",
                api_key="YOUR_DEEPSEEK_API_KEY_HERE",
                temperature=0.2,
                max_tokens=1200,
            )
        ),
    )
    client = _client(tmp_path)

    response = client.get("/api/agent/status")

    assert response.status_code == 200
    assert response.json() == {
        "llm_enabled": False,
        "provider": "rules",
        "mode": "deterministic",
        "model": None,
    }


def test_graph_store_status_reports_configured_provider(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/graph-store/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "sqlite"
    assert payload["mode"] == "local"
    assert payload["project_isolation"] is True


def test_second_stage_reports_are_exposed(tmp_path: Path) -> None:
    client = _client(tmp_path)

    graph_response = client.get("/api/archives/sample/graph/workspace")
    trust_response = client.get("/api/archives/sample/agent-trust")
    multimodal_response = client.get("/api/archives/sample/multimodal")

    assert graph_response.status_code == 200
    graph_payload = graph_response.json()
    assert graph_payload["project_id"] == "sample"
    assert "module_clusters" in graph_payload
    assert "snapshot_diff" in graph_payload
    assert graph_payload["quality"]["grade"]
    assert "component_scores" in graph_payload["quality"]
    assert graph_payload["quality"]["score"] >= 0
    assert "entry_points" in graph_payload
    assert "entity_quality" in graph_payload
    assert "language_structure" in graph_payload
    assert "large_graph_policy" in graph_payload["metadata"]

    assert trust_response.status_code == 200
    trust_payload = trust_response.json()
    assert trust_payload["project_id"] == "sample"
    assert trust_payload["metrics"]["claims"] == 0
    assert trust_payload["warnings"]

    assert multimodal_response.status_code == 200
    multimodal_payload = multimodal_response.json()
    assert multimodal_payload["project_id"] == "sample"
    assert multimodal_payload["image_count"] == 0
    assert multimodal_payload["graph_contributions"]["status"] == "candidate_only"


def test_evaluation_history_endpoint_tracks_runs(tmp_path: Path) -> None:
    client = _client(tmp_path)

    run_response = client.post("/api/archives/sample/evaluation/run")
    history_response = client.get(
        "/api/evaluation/history",
        params={"project_id": "sample"},
    )

    assert run_response.status_code == 200
    assert history_response.status_code == 200
    payload = history_response.json()
    assert payload["project_id"] == "sample"
    assert payload["metrics"]["runs"] >= 1
    assert payload["runs"][0]["project_id"] == "sample"


def test_agent_eval_harness_run_persists_report_and_memory(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/archives/sample/agent-eval/run",
        json={"run_evaluation": True, "evaluation_limit": 3},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == "sample"
    assert payload["metrics"]["evaluation_available"] is True
    assert payload["quality_gates"]
    assert payload["regression"]["status"] == "baseline"
    assert payload["memory_update"]["run_count"] == 1
    assert payload["artifacts"]["agent_eval_report"]["sha256"]
    assert payload["artifacts"]["agent_eval_report"]["bytes"] > 0
    assert "preview" in payload["artifacts"]["agent_eval_report"]
    assert (tmp_path / "sample" / "agent_eval_report.json").exists()
    assert (tmp_path / "sample" / "agent_eval_history.json").exists()
    assert (tmp_path / "sample" / "agent_memory.json").exists()
    assert (tmp_path / "sample" / "harness_events.jsonl").exists()

    reload_response = client.get("/api/archives/sample/agent-eval")
    memory_response = client.get("/api/archives/sample/agent-memory")
    events_response = client.get("/api/archives/sample/harness/events")
    summary_response = client.get("/api/archives/sample/harness/summary")

    assert reload_response.status_code == 200
    assert reload_response.json()["id"] == payload["id"]
    assert memory_response.status_code == 200
    memory = memory_response.json()
    assert memory["project_id"] == "sample"
    assert memory["facts"]
    assert memory["harness_runs"][0]["id"] == payload["id"]
    assert events_response.status_code == 200
    event_types = [event["type"] for event in events_response.json()["events"]]
    assert "run.started" in event_types
    assert "artifact.persisted" in event_types
    assert "run.completed" in event_types
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["project_id"] == "sample"
    assert summary["last_run"]["run_id"] == payload["id"]
    assert summary["latest_sequence"] >= 1
    assert summary["artifacts"]
    assert summary["resume_action"] == "rerun_agent_eval_harness"


def test_harness_capabilities_endpoint_exposes_governance_and_roles(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/harness/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["governance"]["default_rules"]["live_model_call"] == "ask"
    roles = {role["role"] for role in payload["roles"]}
    assert {"archivist", "cartographer", "detective", "skeptic", "curator"} <= roles
    all_tools = {
        tool
        for role in payload["roles"]
        for tool in role["allowed_tools"]
    }
    assert "bash" not in all_tools
    assert "file_write" not in all_tools
    assert payload["governance"]["provider_policy"]["tests"]["real_external_calls_disabled_by_default"] is True


def test_harness_policy_check_endpoint_returns_dry_run_decision(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/harness/policy-check",
        json={"action": "live_model_call", "resource": "provider:deepseek"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dry_run"] is True
    assert payload["decision"]["effect"] == "ask"
    assert payload["requires_confirmation"] is True
    assert payload["provider"]["provider"]
    serialized = json.dumps(payload)
    assert "api_key" not in serialized
    assert "secret" not in serialized


def test_harness_policy_profiles_and_command_endpoints(tmp_path: Path) -> None:
    client = _client(tmp_path)

    policy = client.get("/api/harness/policy")
    profiles = client.get("/api/harness/agent-profiles")
    commands = client.get("/api/harness/commands")
    dry_run = client.post(
        "/api/harness/commands/agent-eval-live/dry-run",
        json={"parameters": {"project_id": "sample"}},
    )

    assert policy.status_code == 200
    assert any(rule["id"] == "ask-live-model" for rule in policy.json()["rules"])
    assert profiles.status_code == 200
    assert "detective" in {role["role"] for role in profiles.json()["roles"]}
    assert commands.status_code == 200
    assert {"doctor", "events", "export-harness"} <= {
        command["id"] for command in commands.json()["commands"]
    }
    assert dry_run.status_code == 200
    assert dry_run.json()["executed"] is False
    assert dry_run.json()["policy"]["decision"]["effect"] == "ask"


def test_harness_export_and_artifact_endpoints_redact_local_paths(tmp_path: Path) -> None:
    from src.project_archive.harness_artifacts import HarnessArtifactStore
    from src.project_archive.harness_events import HarnessEventStore

    client = _client(tmp_path)
    event_store = HarnessEventStore(tmp_path)
    event_store.append(
        project_id="sample",
        run_id="run-1",
        event_type="run.started",
        data={"kind": "query"},
    )
    artifact = HarnessArtifactStore(tmp_path).persist_text(
        project_id="sample",
        run_id="run-1",
        kind="query_trace",
        content="trace",
    )
    event_store.append(
        project_id="sample",
        run_id="run-1",
        event_type="artifact.persisted",
        data=artifact.to_dict(),
    )
    orphan_dir = tmp_path / "sample" / "harness_artifacts" / "orphan"
    orphan_dir.mkdir(parents=True)
    (orphan_dir / "old.txt").write_text("old", encoding="utf-8")

    timeline = client.get("/api/archives/sample/harness/timeline")
    export = client.get("/api/archives/sample/harness/export")
    artifacts = client.get("/api/archives/sample/harness/artifacts")
    validation = client.get("/api/archives/sample/harness/artifacts/validation")
    cleanup = client.post("/api/archives/sample/harness/artifacts/cleanup-dry-run")

    assert timeline.status_code == 200
    assert timeline.json()["timeline"][0]["category"] == "run"
    assert export.status_code == 200
    assert str(tmp_path) not in json.dumps(export.json())
    assert artifacts.status_code == 200
    assert artifacts.json()["artifacts"][0]["artifact_id"] == artifact.artifact_id
    assert validation.status_code == 200
    assert validation.json()["orphans"]
    assert cleanup.status_code == 200
    assert cleanup.json()["dry_run"] is True


def test_agent_eval_harness_second_run_checks_regression(tmp_path: Path) -> None:
    client = _client(tmp_path)

    first_response = client.post(
        "/api/archives/sample/agent-eval/run",
        json={"run_evaluation": True, "evaluation_limit": 3},
    )
    second_response = client.post(
        "/api/archives/sample/agent-eval/run",
        json={"run_evaluation": False},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    payload = second_response.json()
    assert payload["regression"]["status"] in {"pass", "warn", "fail"}
    assert payload["regression"]["previous_run_id"] == first_response.json()["id"]
    history = json.loads((tmp_path / "sample" / "agent_eval_history.json").read_text())
    assert len(history["runs"]) == 2


def test_agent_eval_harness_memory_accepts_react_mission_findings(tmp_path: Path) -> None:
    client = _client(tmp_path)
    mission_dir = tmp_path / "sample" / "agent_missions"
    mission_dir.mkdir()
    mission = AgentMission(
        id="mission-1",
        project_id="sample",
        goal="Inspect architecture",
        status="complete",
        created_at="2026-07-01T00:00:00+00:00",
        completed_at="2026-07-01T00:00:01+00:00",
        budget=AgentMissionBudget(max_tasks=1, max_steps_per_task=1),
        tasks=[
            AgentMissionTask(
                id="mission-1:task:1",
                mission_id="mission-1",
                task_type="inspect_core_entities",
                objective="Inspect core entities",
                status="complete",
                input_entity_ids=["file:app.py"],
                output_entity_ids=["func:run"],
                evidence_ids=["ev:1"],
                findings=[
                    {
                        "summary": "run is defined by app.py",
                        "relation_ids": ["rel:defines"],
                    }
                ],
                confidence=0.8,
            )
        ],
        verifier_result=AgentMissionVerifierResult(status="supported", supported_finding_count=1),
    )
    (mission_dir / "mission-1.json").write_text(
        json.dumps(mission.to_dict()),
        encoding="utf-8",
    )

    response = client.post(
        "/api/archives/sample/agent-eval/run",
        json={"run_evaluation": True, "evaluation_limit": 3},
    )

    assert response.status_code == 200
    memory = json.loads((tmp_path / "sample" / "agent_memory.json").read_text())
    assert "rel:defines" in memory["relations"]
    assert memory["harness_runs"][0]["metrics"]["mission_task_count"] == 1


def test_stress_test_run_persists_health_report(tmp_path: Path) -> None:
    client = _client(tmp_path)

    run_response = client.post(
        "/api/stress-test/run",
        json={"project_ids": ["sample"], "run_evaluation": True, "evaluation_limit": 3},
    )
    latest_response = client.get("/api/stress-test/latest")

    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["summary"]["project_count"] == 1
    assert payload["projects"][0]["project_id"] == "sample"
    assert payload["projects"][0]["evaluation_available"] is True
    assert "quality_score" in payload["projects"][0]
    assert payload["regression_matrix"]
    assert "language_coverage" in payload
    assert "blocking_failures" in payload
    assert payload["recommendations"]
    assert (tmp_path / "stress_test_report.json").exists()

    assert latest_response.status_code == 200
    assert latest_response.json()["id"] == payload["id"]


def test_project_intelligence_report_generates_json_and_markdown(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post("/api/archives/sample/intelligence-report/run")
    markdown_response = client.get("/api/archives/sample/intelligence-report/markdown")
    pdf_response = client.get("/api/archives/sample/intelligence-report/pdf")
    reload_response = client.get("/api/archives/sample/intelligence-report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == "sample"
    assert payload["summary"]
    assert "evidence_chain" in payload
    assert "rag_citations" in payload
    assert "sections" in payload
    assert "risk_index" in payload
    assert "evidence_index" in payload
    assert payload["next_actions"]

    assert markdown_response.status_code == 200
    assert "# Project Intelligence Report: sample" in markdown_response.text
    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(b"%PDF-")
    assert reload_response.status_code == 200
    assert reload_response.json()["project_id"] == "sample"
    assert (tmp_path / "sample" / "project_intelligence_report.json").exists()
    assert (tmp_path / "sample" / "project_intelligence_report.md").exists()

    versions_response = client.get("/api/archives/sample/versions")
    assert versions_response.status_code == 200
    assert any(
        event["kind"] == "intelligence_report"
        for event in versions_response.json()["events"]
    )


def test_agent_task_plan_reports_project_specific_queue(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/archives/sample/agent-task-plan")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == "sample"
    assert payload["tasks"]
    assert payload["tasks"][0]["recommended_tools"]


def test_graph_curation_apply_suggestions_persists_state(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post("/api/archives/sample/graph-curation/apply-suggestions")
    reload_response = client.get("/api/archives/sample/graph-curation")

    assert response.status_code == 200
    assert reload_response.status_code == 200
    payload = reload_response.json()
    assert payload["project_id"] == "sample"
    assert "important_entity_ids" in payload
    versions = client.get("/api/archives/sample/versions").json()
    assert any(event["kind"] == "graph_curation" for event in versions["events"])


def test_system_config_check_reports_components_without_secrets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        service_module,
        "_ollama_model_status",
        lambda *, base_url, model: {
            "endpoint_reachable": True,
            "model_available": True,
            "available_models": [model],
        },
    )
    client = _client(tmp_path)

    response = client.get("/api/system/config-check")

    assert response.status_code == 200
    payload = response.json()
    component_ids = {component["id"] for component in payload["components"]}
    assert {
        "llm",
        "embedding",
        "vision",
        "graph_store",
        "vector_store",
        "hybrid_rag",
        "agent",
    } <= component_ids
    assert "runtime_evidence" in payload["metadata"]
    assert "hybrid_retrieval" in payload["metadata"]["runtime_evidence"]
    vision = next(component for component in payload["components"] if component["id"] == "vision")
    assert vision["configured"] is True
    assert vision["working"] is True
    assert vision["details"]["endpoint_reachable"] is True
    assert vision["details"]["model_available"] is True
    serialized = json.dumps(payload)
    assert "sk-a775" not in serialized


def test_list_archives_returns_persisted_project_ids(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/archives")

    assert response.status_code == 200
    assert response.json() == {"archives": ["sample"]}


def test_knowledge_universe_returns_cross_project_links(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _write_draft(tmp_path, _sample_peer_draft())

    response = client.get("/api/universe")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"]["projects"] == 2
    assert payload["metrics"]["links"] > 0
    assert payload["clusters"]
    assert any(link["shared_key"] == "archiveservice" for link in payload["links"])


def test_knowledge_universe_can_filter_projects(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _write_draft(tmp_path, _sample_peer_draft())

    response = client.get(
        "/api/universe",
        params=[("project_ids", "sample")],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_ids"] == ["sample"]
    assert payload["metrics"]["projects"] == 1
    assert payload["links"] == []


def test_knowledge_universe_skips_corrupt_archives(tmp_path: Path) -> None:
    client = _client(tmp_path)
    corrupt_dir = tmp_path / "corrupt"
    corrupt_dir.mkdir()
    (corrupt_dir / "draft_archive.json").write_text("{bad json", encoding="utf-8")

    response = client.get("/api/universe")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_ids"] == ["sample"]
    assert payload["metrics"]["skipped_projects"] == 1
    assert payload["metadata"]["skipped_projects"][0]["project_id"] == "corrupt"


def test_knowledge_universe_returns_404_for_unknown_archive(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get(
        "/api/universe",
        params=[("project_ids", "missing")],
    )

    assert response.status_code == 404


def test_universe_paths_can_be_saved_and_listed(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _write_draft(tmp_path, _sample_peer_draft())

    save_response = client.post(
        "/api/universe/paths",
        json={
            "name": "ArchiveService comparison",
            "project_ids": ["sample", "peer"],
            "cluster_ids": [],
            "link_ids": [],
            "notes": "Follow the shared service concept.",
        },
    )

    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["name"] == "ArchiveService comparison"
    list_response = client.get("/api/universe/paths")
    assert list_response.status_code == 200
    assert list_response.json()["paths"][0]["id"] == saved["id"]


def test_universe_agent_tasks_run_from_cross_project_links(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _write_draft(tmp_path, _sample_peer_draft())

    response = client.post(
        "/api/universe/agent-tasks/run",
        json={"project_ids": ["sample", "peer"], "max_tasks": 4},
    )

    assert response.status_code == 200
    tasks = response.json()["tasks"]
    assert tasks
    assert tasks[0]["status"] == "complete"
    assert set(tasks[0]["project_ids"]) <= {"sample", "peer"}
    history_response = client.get("/api/universe/agent-tasks")
    assert history_response.status_code == 200
    assert history_response.json()["tasks"]


def test_universe_agent_tasks_accept_many_project_archives(tmp_path: Path) -> None:
    client = _client(tmp_path)
    project_ids = ["sample"]
    for index in range(14):
        draft = replace(_sample_peer_draft(), project_id=f"peer-{index}")
        _write_draft(tmp_path, draft)
        project_ids.append(draft.project_id)

    response = client.post(
        "/api/universe/agent-tasks/run",
        json={"project_ids": project_ids, "max_tasks": 6},
    )

    assert response.status_code == 200
    tasks = response.json()["tasks"]
    assert tasks
    assert len(tasks) <= 6


def test_universe_compare_returns_architecture_diff_report(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _write_draft(tmp_path, _sample_peer_draft())

    response = client.post(
        "/api/universe/compare",
        json={"left_project_id": "sample", "right_project_id": "peer"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["left_project_id"] == "sample"
    assert payload["right_project_id"] == "peer"
    assert payload["summary"]
    assert payload["findings"]
    assert "entities" in payload["metric_delta"]
    assert payload["sections"]
    assert payload["component_delta"]["delta"]
    assert "risk_points" in payload
    assert payload["migration_notes"]
    assert payload["evidence_chain"]
    assert payload["metadata"]["evidence_chain_count"] == len(payload["evidence_chain"])


def test_get_archive_returns_draft_payload(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/archives/sample")

    assert response.status_code == 200
    assert response.json()["project_id"] == "sample"
    assert response.json()["halls"][0]["name"] == "Architecture Hall"


def test_get_archive_returns_404_for_unknown_project(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/archives/missing")

    assert response.status_code == 404


def test_get_graph_summary_returns_recommended_starts(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/archives/sample/graph")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == "sample"
    assert payload["metrics"]["entities"] == 3
    assert payload["recommended_starts"]
    assert payload["recommended_starts"][0]["entity_id"]


def test_get_graph_neighborhood_filters_by_hall(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get(
        "/api/archives/sample/graph/neighborhood",
        params={"hall_id": "hall_architecture", "depth": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == "sample"
    assert payload["hall_id"] == "hall_architecture"
    assert payload["relations"][0]["id"] == "rel:defines"
    assert payload["is_sparse"] is False


def test_get_graph_neighborhood_binds_repeated_relation_types(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    response = client.get(
        "/api/archives/sample/graph/neighborhood",
        params=[
            ("hall_id", "hall_architecture"),
            ("relation_types", "defines"),
            ("relation_types", "configures"),
        ],
    )

    assert response.status_code == 200
    relation_ids = {relation["id"] for relation in response.json()["relations"]}
    assert "rel:defines" in relation_ids


def test_get_graph_neighborhood_returns_404_for_unknown_archive(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    response = client.get("/api/archives/missing/graph/neighborhood")

    assert response.status_code == 404


def test_search_graph_entities_returns_matching_entities(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get(
        "/api/archives/sample/graph/search",
        params={"q": "app", "limit": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]
    assert payload["results"][0]["entity_id"] == "file:app.py"
    assert "name" in payload["results"][0]["matched_fields"]


def test_graph_curation_round_trips_project_archive_file(tmp_path: Path) -> None:
    client = _client(tmp_path)

    default_response = client.get("/api/archives/sample/graph-curation")

    assert default_response.status_code == 200
    assert default_response.json()["project_id"] == "sample"
    assert default_response.json()["important_entity_ids"] == []

    save_response = client.put(
        "/api/archives/sample/graph-curation",
        json={
            "important_entity_ids": ["func:run", "missing"],
            "hidden_relation_ids": ["rel:defines", "rel:missing"],
            "merge_candidates": [
                {
                    "id": "merge:app-run",
                    "label": "app/run",
                    "entity_ids": ["file:app.py", "func:run", "missing"],
                    "created_at": "2026-06-28T00:00:00Z",
                }
            ],
        },
    )

    assert save_response.status_code == 200
    payload = save_response.json()
    assert payload["important_entity_ids"] == ["func:run"]
    assert payload["hidden_relation_ids"] == ["rel:defines"]
    assert payload["merge_candidates"][0]["entity_ids"] == ["file:app.py", "func:run"]
    assert payload["updated_at"]
    assert (tmp_path / "sample" / "graph_curation.json").exists()

    reload_response = client.get("/api/archives/sample/graph-curation")

    assert reload_response.status_code == 200
    assert reload_response.json()["hidden_relation_ids"] == ["rel:defines"]


def test_graph_curation_returns_404_for_unknown_archive(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/archives/missing/graph-curation")

    assert response.status_code == 404


def test_archive_golden_questions_are_generated_from_archive(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    response = client.get("/api/archives/sample/evaluation/golden-questions")

    assert response.status_code == 200
    questions = response.json()["questions"]
    assert questions
    assert questions[0]["expected_entity_ids"]


def test_archive_evaluation_run_persists_report(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post("/api/archives/sample/evaluation/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == "sample"
    assert payload["golden_question_count"] > 0
    assert "entity_hit_rate" in payload["aggregate_metrics"]
    assert payload["case_results"]
    assert (tmp_path / "sample" / "evaluation_report.json").exists()

    reload_response = client.get("/api/archives/sample/evaluation")

    assert reload_response.status_code == 200
    assert reload_response.json()["created_at"] == payload["created_at"]


def test_archive_evaluation_returns_404_for_missing_archive(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    responses = [
        client.get("/api/archives/missing/evaluation"),
        client.get("/api/archives/missing/evaluation/golden-questions"),
        client.post("/api/archives/missing/evaluation/run"),
    ]

    assert [response.status_code for response in responses] == [404, 404, 404]


def test_start_architecture_mission_returns_completed_bounded_mission(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/archives/sample/missions",
        json={"goal": "understand_project_architecture", "max_steps": 3},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["project_id"] == "sample"
    assert payload["goal"] == "understand_project_architecture"
    assert len(payload["tasks"]) == 3
    assert payload["graph_overlay"]["explored_node_ids"]

    mission_id = payload["id"]
    mission_response = client.get(f"/api/missions/{mission_id}")
    assert mission_response.status_code == 200
    assert mission_response.json()["id"] == mission_id


def test_get_mission_tasks_and_overlay(tmp_path: Path) -> None:
    client = _client(tmp_path)

    created = client.post(
        "/api/archives/sample/missions",
        json={"goal": "understand_project_architecture", "max_steps": 2},
    ).json()
    mission_id = created["id"]

    tasks_response = client.get(f"/api/missions/{mission_id}/tasks")
    overlay_response = client.get(f"/api/missions/{mission_id}/graph-overlay")

    assert tasks_response.status_code == 200
    assert len(tasks_response.json()["tasks"]) == 2
    assert overlay_response.status_code == 200
    assert overlay_response.json()["mission_id"] == mission_id


def test_pause_resume_stop_mission_update_status(tmp_path: Path) -> None:
    client = _client(tmp_path)
    mission_id = client.post(
        "/api/archives/sample/missions",
        json={"goal": "understand_project_architecture", "max_steps": 2},
    ).json()["id"]

    pause_response = client.post(f"/api/missions/{mission_id}/pause")
    resume_response = client.post(f"/api/missions/{mission_id}/resume")
    stop_response = client.post(f"/api/missions/{mission_id}/stop")

    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == "paused"
    assert resume_response.status_code == 200
    assert resume_response.json()["status"] == "complete"
    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped"


def test_start_mission_rejects_unsupported_goal(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/archives/sample/missions",
        json={"goal": "map_runtime_logs", "max_steps": 2},
    )

    assert response.status_code == 400
    assert "Unsupported mission goal" in response.json()["detail"]


def test_start_mission_validates_step_budget(tmp_path: Path) -> None:
    client = _client(tmp_path)

    too_small = client.post(
        "/api/archives/sample/missions",
        json={"goal": "understand_project_architecture", "max_steps": 0},
    )
    too_large = client.post(
        "/api/archives/sample/missions",
        json={"goal": "understand_project_architecture", "max_steps": 13},
    )

    assert too_small.status_code == 422
    assert too_large.status_code == 422


def test_start_mission_returns_404_for_missing_archive(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/archives/missing/missions",
        json={"goal": "understand_project_architecture", "max_steps": 2},
    )

    assert response.status_code == 404


def test_unknown_mission_endpoints_return_404(tmp_path: Path) -> None:
    client = _client(tmp_path)
    mission_id = "missing-mission"

    responses = [
        client.get(f"/api/missions/{mission_id}"),
        client.get(f"/api/missions/{mission_id}/tasks"),
        client.get(f"/api/missions/{mission_id}/graph-overlay"),
        client.post(f"/api/missions/{mission_id}/pause"),
        client.post(f"/api/missions/{mission_id}/resume"),
        client.post(f"/api/missions/{mission_id}/stop"),
    ]

    assert [response.status_code for response in responses] == [404] * len(responses)


def test_mission_status_update_preserves_persisted_tasks_and_overlay(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    mission_id = client.post(
        "/api/archives/sample/missions",
        json={"goal": "understand_project_architecture", "max_steps": 2},
    ).json()["id"]

    pause_response = client.post(f"/api/missions/{mission_id}/pause")
    reload_response = client.get(f"/api/missions/{mission_id}")

    assert pause_response.status_code == 200
    assert reload_response.status_code == 200
    payload = reload_response.json()
    assert payload["status"] == "paused"
    assert len(payload["tasks"]) == 2
    assert payload["graph_overlay"]["mission_id"] == mission_id
    assert payload["graph_overlay"]["explored_node_ids"]


def test_agent_mission_endpoints_return_mission_and_trace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TWINMIND_AGENT_LLM_ENABLED", "false")
    client = _client(tmp_path)

    response = client.post(
        "/api/archives/sample/agent-missions",
        json={
            "goal": "Understand project architecture",
            "max_tasks": 2,
            "max_steps_per_task": 2,
        },
    )

    assert response.status_code == 202
    mission = response.json()
    assert mission["project_id"] == "sample"
    assert mission["tasks"]

    loaded = client.get(f"/api/agent-missions/{mission['id']}")
    trace = client.get(f"/api/agent-missions/{mission['id']}/trace")
    trace_artifact = client.get(f"/api/agent-missions/{mission['id']}/trace-artifact")
    visualization = client.get(f"/api/agent-missions/{mission['id']}/visualization")
    stopped = client.post(f"/api/agent-missions/{mission['id']}/stop")

    assert loaded.status_code == 200
    loaded_payload = loaded.json()
    assert loaded_payload["status"] == "complete"
    assert loaded_payload["trace_events"]
    assert trace.status_code == 200
    assert trace.json()["trace_events"]
    assert trace_artifact.status_code == 200
    trace_artifact_payload = trace_artifact.json()
    assert trace_artifact_payload["mission_id"] == mission["id"]
    assert trace_artifact_payload["artifact"]["kind"] == "agent_mission_trace"
    assert trace_artifact_payload["artifact"]["sha256"]
    assert "preview" in trace_artifact_payload["artifact"]
    assert visualization.status_code == 200
    visual_payload = visualization.json()
    assert visual_payload["mission_id"] == mission["id"]
    assert visual_payload["loop_phases"]
    assert "tool_calls" in visual_payload["audit"]
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "complete"


def test_agent_mission_endpoints_return_404_for_unknown_mission(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    mission_id = "missing-mission"

    responses = [
        client.get(f"/api/agent-missions/{mission_id}"),
        client.get(f"/api/agent-missions/{mission_id}/trace"),
        client.get(f"/api/agent-missions/{mission_id}/trace-artifact"),
        client.get(f"/api/agent-missions/{mission_id}/visualization"),
        client.post(f"/api/agent-missions/{mission_id}/stop"),
    ]

    assert [response.status_code for response in responses] == [404] * len(responses)


def test_agent_mission_create_returns_404_for_missing_archive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TWINMIND_AGENT_LLM_ENABLED", "false")
    client = _client(tmp_path)

    response = client.post(
        "/api/archives/missing/agent-missions",
        json={
            "goal": "Understand project architecture",
            "max_tasks": 2,
            "max_steps_per_task": 2,
        },
    )

    assert response.status_code == 404


def test_agent_mission_create_validates_task_budgets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TWINMIND_AGENT_LLM_ENABLED", "false")
    client = _client(tmp_path)

    invalid_max_tasks = client.post(
        "/api/archives/sample/agent-missions",
        json={
            "goal": "Understand project architecture",
            "max_tasks": 0,
            "max_steps_per_task": 2,
        },
    )
    invalid_steps = client.post(
        "/api/archives/sample/agent-missions",
        json={
            "goal": "Understand project architecture",
            "max_tasks": 2,
            "max_steps_per_task": 9,
        },
    )

    assert invalid_max_tasks.status_code == 422
    assert invalid_steps.status_code == 422


def test_agent_mission_pause_resume_are_unsupported_and_do_not_mutate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TWINMIND_AGENT_LLM_ENABLED", "false")
    client = _client(tmp_path)
    mission = client.post(
        "/api/archives/sample/agent-missions",
        json={
            "goal": "Understand project architecture",
            "max_tasks": 2,
            "max_steps_per_task": 2,
        },
    ).json()
    mission_id = mission["id"]
    status_before = client.get(f"/api/agent-missions/{mission_id}").json()["status"]

    pause = client.post(f"/api/agent-missions/{mission_id}/pause")
    resume = client.post(f"/api/agent-missions/{mission_id}/resume")
    status_after = client.get(f"/api/agent-missions/{mission_id}").json()["status"]

    assert pause.status_code == 409
    assert pause.json()["detail"] == "Agent mission pause is not supported yet."
    assert resume.status_code == 409
    assert resume.json()["detail"] == "Agent mission resume is not supported yet."
    assert status_after == status_before


def test_agent_mission_stop_preserves_partial_status(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TWINMIND_AGENT_LLM_ENABLED", "false")
    client = _client(tmp_path)
    service = ProjectArchiveService(storage_dir=tmp_path)
    planned = service.create_agent_mission(
        "sample",
        "Understand project architecture",
        max_tasks=2,
        max_steps_per_task=2,
    )
    partial = service.update_agent_mission_status(planned.id, "partial")

    rerun = service.run_agent_mission(partial.id)
    stopped = client.post(f"/api/agent-missions/{partial.id}/stop")

    assert rerun.status == "partial"
    assert rerun.trace_events == []
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "partial"


def test_upload_archive_ingests_project_zip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TWINMIND_AGENT_LLM_ENABLED", "false")
    client = _client(tmp_path)
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w") as archive:
        archive.writestr("demo-project/README.md", "# Demo Project\n")
        archive.writestr("demo-project/src/app.py", "def run():\n    return 'ok'\n")
        archive.writestr("demo-project/docs/architecture.png", PNG_1X1)
        archive.writestr("demo-project/node_modules/ignored.js", "ignored")

    response = client.post(
        "/api/archives/upload",
        files={"file": ("demo-project.zip", zip_buffer.getvalue(), "application/zip")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == "demo-project"
    assert payload["metrics"]["entities"] > 0
    assert payload["archive"]["project_id"] == "demo-project"
    assert payload["archive"]["metadata"]["ingestion"]["scan"]["kept_files"] >= 2
    assert payload["archive"]["metadata"]["ingestion"]["upload"]["skipped_by_reason"]["ignored_directory"] == 1
    image_cards = [
        card
        for card in payload["archive"]["evidence_cards"]
        if card["source_type"] == "image"
    ]
    assert image_cards
    assert image_cards[0]["metadata"]["modality"] == "image"
    assert image_cards[0]["metadata"]["vision_provider"]
    asset_id = image_cards[0]["metadata"]["asset_id"]
    asset_response = client.get(
        f"/api/archives/demo-project/evidence-assets/{asset_id}"
    )
    assert asset_response.status_code == 200
    assert asset_response.content == PNG_1X1
    assert "agent_report" not in payload
    assert (tmp_path / "demo-project" / "draft_archive.json").exists()
    assert not (tmp_path / "demo-project" / "agent_report.json").exists()

    report_response = client.get("/api/archives/demo-project/agent-report")

    assert report_response.status_code == 404

    diagnostics_response = client.get("/api/archives/demo-project/diagnostics")

    assert diagnostics_response.status_code == 200
    diagnostics = diagnostics_response.json()
    assert diagnostics["project_id"] == "demo-project"
    assert diagnostics["upload"]["kept_files"] >= 3
    assert diagnostics["scan"]["kept_files"] >= 2
    assert diagnostics["extraction"]["languages"]
    assert diagnostics["images"]["evidence_cards"] == 1
    assert "indexed_chunks" in diagnostics["hybrid_rag"]
    assert diagnostics["recommendations"]

    multimodal_response = client.get("/api/archives/demo-project/multimodal")

    assert multimodal_response.status_code == 200
    multimodal_payload = multimodal_response.json()
    assert multimodal_payload["image_count"] == 1
    assert "method_counts" in multimodal_payload
    assert "entity_alignment" in multimodal_payload
    assert "evidence_support" in multimodal_payload

    query_response = client.post(
        "/api/archives/demo-project/query",
        json={"question": "What image or architecture evidence exists?", "mode": "evidence_qa"},
    )

    assert query_response.status_code == 200
    query_payload = query_response.json()
    assert "hybrid_rag" in query_payload["metadata"]
    assert "evidence_modalities" in query_payload["metadata"]
    assert "cited_image_evidence_count" in query_payload["metadata"]
    events_response = client.get("/api/archives/demo-project/harness/events")
    assert events_response.status_code == 200
    assert "query.completed" in {
        event["type"] for event in events_response.json()["events"]
    }


def test_upload_archive_keeps_monorepo_source_layouts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TWINMIND_AGENT_LLM_ENABLED", "false")
    client = _client(tmp_path)
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w") as archive:
        archive.writestr("dubbo-like/README.md", "# Dubbo Like\n")
        archive.writestr(
            "dubbo-like/dubbo-common/src/main/java/demo/UserService.java",
            "package demo;\n"
            "import java.util.List;\n"
            "class UserService { User getUser(String id) { return repo.findById(id); } }\n",
        )
        archive.writestr(
            "dubbo-like/dubbo-rpc/src/main/java/demo/RpcClient.java",
            "package demo;\nclass RpcClient {}\n",
        )
        archive.writestr(
            "dubbo-like/tests/src/test/java/demo/UserServiceTest.java",
            "class UserServiceTest {}\n",
        )

    response = client.post(
        "/api/archives/upload",
        files={"file": ("dubbo-like.zip", zip_buffer.getvalue(), "application/zip")},
    )

    assert response.status_code == 200
    payload = response.json()
    entity_names = {entity["name"] for entity in payload["archive"]["entities"]}
    source_paths = {
        entity["source_path"]
        for entity in payload["archive"]["entities"]
        if entity.get("source_path")
    }
    relation_types = {
        relation["type"] for relation in payload["archive"]["relations"]
    }

    assert "UserService" in entity_names
    assert "RpcClient" in entity_names
    assert any("dubbo-common/src/main/java/demo/UserService.java" in path for path in source_paths)
    assert all("UserServiceTest.java" not in path for path in source_paths)
    assert {"IMPORTS", "DEPENDS_ON", "CALLS"} <= relation_types


def test_upload_archive_job_reports_progress_and_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TWINMIND_AGENT_LLM_ENABLED", "false")
    client = _client(tmp_path)
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w") as archive:
        archive.writestr("job-project/README.md", "# Job Project\n")
        archive.writestr("job-project/src/app.py", "def run():\n    return 'ok'\n")

    response = client.post(
        "/api/archives/upload-job",
        files={"file": ("job-project.zip", zip_buffer.getvalue(), "application/zip")},
    )

    assert response.status_code == 202
    job_id = response.json()["id"]

    job_response = client.get(f"/api/jobs/{job_id}")

    assert job_response.status_code == 200
    payload = job_response.json()
    assert payload["status"] == "complete"
    assert payload["progress"] == 100
    assert payload["project_id"] == "job-project"
    assert payload["result"]["project_id"] == "job-project"
    assert payload["result"]["metrics"]["entities"] > 0
    assert "archive" not in payload["result"]
    assert "agent_report" not in payload["result"]

    archive_response = client.get("/api/archives/job-project")

    assert archive_response.status_code == 200
    assert archive_response.json()["project_id"] == "job-project"

    jobs_response = client.get(
        "/api/jobs",
        params={"project_id": "job-project"},
    )
    cancel_response = client.post(f"/api/jobs/{job_id}/cancel")

    assert jobs_response.status_code == 200
    listed_job = next(job for job in jobs_response.json()["jobs"] if job["id"] == job_id)
    assert "result" not in listed_job
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "complete"


def test_run_agent_report_job_reports_progress_and_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TWINMIND_AGENT_LLM_ENABLED", "false")
    client = _client(tmp_path)

    response = client.post("/api/archives/sample/agent-report/run-job")

    assert response.status_code == 202
    job_id = response.json()["id"]

    job_response = client.get(f"/api/jobs/{job_id}")

    assert job_response.status_code == 200
    payload = job_response.json()
    assert payload["status"] == "complete"
    assert payload["progress"] == 100
    assert payload["project_id"] == "sample"
    assert payload["result"]["agent_report"]["agents"]["archivist"]["agent"] == "archivist"


def test_run_agent_report_job_reuses_active_project_job(tmp_path: Path) -> None:
    client = _client(tmp_path)
    with api._JOBS_LOCK:
        api._JOBS.clear()
    active_job = api._create_job(
        kind="agent_report",
        project_id="sample",
        message="Agent analysis queued.",
    )
    try:
        response = client.post("/api/archives/sample/agent-report/run-job")

        assert response.status_code == 202
        payload = response.json()
        assert payload["id"] == active_job.id
        assert payload["status"] == "queued"
    finally:
        with api._JOBS_LOCK:
            api._JOBS.clear()
