"""Tests for the TwinMind Archive FastAPI integration."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from fastapi.testclient import TestClient

from src.project_archive import api
from src.project_archive.service import ProjectArchiveService
from src.project_archive.types import (
    ArchiveHall,
    EvidenceCard,
    ProjectArchiveDraft,
    ProjectEntity,
    ProjectRelation,
)


def _sample_draft() -> ProjectArchiveDraft:
    return ProjectArchiveDraft(
        project_id="sample",
        halls=[
            ArchiveHall(
                id="hall_architecture",
                name="Architecture Hall",
                description="Files and modules.",
                entity_ids=["file:app.py"],
            )
        ],
        entities=[
            ProjectEntity(id="file:app.py", type="File", name="app.py"),
            ProjectEntity(id="func:run", type="Function", name="run"),
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


def _client(tmp_path: Path) -> TestClient:
    draft = _sample_draft()
    archive_dir = tmp_path / draft.project_id
    archive_dir.mkdir()
    (archive_dir / "draft_archive.json").write_text(
        json.dumps(draft.to_dict()),
        encoding="utf-8",
    )

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


def test_list_archives_returns_persisted_project_ids(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/archives")

    assert response.status_code == 200
    assert response.json() == {"archives": ["sample"]}


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
    assert payload["metrics"]["entities"] == 2
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
    stopped = client.post(f"/api/agent-missions/{mission['id']}/stop")

    assert loaded.status_code == 200
    assert loaded.json()["status"] in {"planned", "running", "complete"}
    assert trace.status_code == 200
    assert "trace_events" in trace.json()
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"


def test_upload_archive_ingests_project_zip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TWINMIND_AGENT_LLM_ENABLED", "false")
    client = _client(tmp_path)
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w") as archive:
        archive.writestr("demo-project/README.md", "# Demo Project\n")
        archive.writestr("demo-project/src/app.py", "def run():\n    return 'ok'\n")
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
    assert "agent_report" not in payload
    assert (tmp_path / "demo-project" / "draft_archive.json").exists()
    assert not (tmp_path / "demo-project" / "agent_report.json").exists()

    report_response = client.get("/api/archives/demo-project/agent-report")

    assert report_response.status_code == 404


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
    assert payload["result"]["archive"]["project_id"] == "job-project"
    assert "agent_report" not in payload["result"]


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
