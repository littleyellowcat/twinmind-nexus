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
    assert payload["agent_report"]["project_id"] == "demo-project"
    assert payload["agent_report"]["agents"]["archivist"]["status"] == "complete"
    assert payload["agent_report"]["agents"]["curator"]["status"] == "complete"
    assert (tmp_path / "demo-project" / "draft_archive.json").exists()
    assert (tmp_path / "demo-project" / "agent_report.json").exists()

    report_response = client.get("/api/archives/demo-project/agent-report")

    assert report_response.status_code == 200
    assert report_response.json()["agents"]["skeptic"]["agent"] == "skeptic"


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
    assert payload["result"]["agent_report"]["agents"]["curator"]["agent"] == "curator"


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
