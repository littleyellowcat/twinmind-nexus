"""Unit tests for the TwinMind Archive dashboard helpers."""

from __future__ import annotations

import json
from pathlib import Path

from src.project_archive.types import (
    AgentResult,
    ArchiveHall,
    EvidenceCard,
    ProjectArchiveDraft,
    ProjectEntity,
    ProjectRelation,
    QueryMode,
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


def test_list_archived_project_ids(tmp_path: Path) -> None:
    from src.observability.dashboard.pages import twinmind_archive as page

    archive_dir = tmp_path / "sample"
    archive_dir.mkdir()
    (archive_dir / "draft_archive.json").write_text("{}", encoding="utf-8")
    (tmp_path / "empty").mkdir()

    assert page._list_archived_project_ids(tmp_path) == ["sample"]


def test_archive_metrics_counts_draft_items() -> None:
    from src.observability.dashboard.pages import twinmind_archive as page

    assert page._archive_metrics(_sample_draft()) == {
        "halls": 1,
        "entities": 2,
        "relations": 1,
        "evidence": 1,
    }


def test_relation_rows_use_entity_names() -> None:
    from src.observability.dashboard.pages import twinmind_archive as page

    assert page._relation_rows(_sample_draft()) == [
        {"source": "app.py", "relation": "DEFINES", "target": "run"}
    ]


def test_format_agent_result_includes_sections() -> None:
    from src.observability.dashboard.pages import twinmind_archive as page

    result = AgentResult(
        mode=QueryMode.IMPACT_ANALYSIS,
        question="What changes?",
        summary="Impact analysis traced deterministic archive relationships.",
        affected_entities=["file:app.py"],
        evidence_card_ids=["ev:1"],
        risks=["Check affected callers."],
        next_actions=["Open evidence."],
        confidence=0.8,
    )

    formatted = page._format_agent_result(result)

    assert "Mode: Impact Analysis" in formatted
    assert "Confidence: 0.80" in formatted
    assert "- file:app.py" in formatted
    assert "- ev:1" in formatted
    assert "- Check affected callers." in formatted


def test_draft_fixture_round_trip_matches_dashboard_expectation(tmp_path: Path) -> None:
    draft = _sample_draft()
    archive_dir = tmp_path / draft.project_id
    archive_dir.mkdir()
    (archive_dir / "draft_archive.json").write_text(
        json.dumps(draft.to_dict()),
        encoding="utf-8",
    )

    from src.project_archive.service import ProjectArchiveService

    loaded = ProjectArchiveService(storage_dir=tmp_path).load_draft("sample")

    assert loaded.project_id == "sample"
    assert loaded.entities[0].name == "app.py"
