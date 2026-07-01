"""Unit tests for the TwinMind Archive dashboard helpers."""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from src.project_archive.types import (
    AgentResult,
    ArchiveHall,
    EvidenceCard,
    ProjectArchiveDraft,
    ProjectEntity,
    ProjectRelation,
    QueryMode,
)


class _FakeUpload:
    def __init__(self, name: str, payload: bytes) -> None:
        self.name = name
        self._payload = payload

    def getvalue(self) -> bytes:
        return self._payload


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


def test_upload_project_id_defaults_to_uploaded_name() -> None:
    from src.observability.dashboard.pages import twinmind_archive as page

    assert page._slugify_project_id(" My Cool 项目! ") == "My-Cool"
    assert page._project_id_from_upload("", zip_name="modular-rag.zip") == "modular-rag"
    assert (
        page._project_id_from_upload(
            "",
            folder_files=[_FakeUpload("TwinMind Archive/src/app.py", b"")],
        )
        == "TwinMind-Archive"
    )


def test_safe_upload_path_blocks_traversal() -> None:
    from src.observability.dashboard.pages import twinmind_archive as page

    assert page._safe_upload_path("project/src/app.py").parts == (
        "project",
        "src",
        "app.py",
    )
    with pytest.raises(ValueError):
        page._safe_upload_path("../secrets.env")
    with pytest.raises(ValueError):
        page._safe_upload_path("/tmp/project.py")


def test_extract_project_zip_selects_wrapped_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.observability.dashboard.pages import twinmind_archive as page

    monkeypatch.setattr(page, "PROJECT_UPLOAD_DIR", tmp_path)
    archive_bytes = _build_zip(
        {
            "DemoProject/README.md": b"# Demo",
            "DemoProject/src/app.py": b"print('hi')",
        }
    )

    project_root = page._extract_project_zip(
        _FakeUpload("DemoProject.zip", archive_bytes),
        "demo-project",
    )

    assert project_root == tmp_path / "demo-project" / "source" / "DemoProject"
    assert (project_root / "README.md").read_text(encoding="utf-8") == "# Demo"


def test_extract_project_zip_skips_heavy_ignored_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.observability.dashboard.pages import twinmind_archive as page

    monkeypatch.setattr(page, "PROJECT_UPLOAD_DIR", tmp_path)
    archive_bytes = _build_zip(
        {
            "DemoProject/README.md": b"# Demo",
            "DemoProject/.venv/lib/site-packages/pkg.py": b"ignored",
            "DemoProject/node_modules/pkg/index.js": b"ignored",
            "DemoProject/data/chroma.sqlite": b"ignored",
            "DemoProject/tests/test_app.py": b"ignored",
            "DemoProject/.claude/skills/SKILL.md": b"# ignored",
        }
    )

    project_root = page._extract_project_zip(
        _FakeUpload("DemoProject.zip", archive_bytes),
        "demo-project",
    )

    assert (project_root / "README.md").exists()
    assert not (project_root / ".venv").exists()
    assert not (project_root / "node_modules").exists()
    assert not (project_root / "data").exists()
    assert not (project_root / "tests").exists()
    assert not (project_root / ".claude").exists()


def test_save_project_folder_upload_preserves_relative_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.observability.dashboard.pages import twinmind_archive as page

    monkeypatch.setattr(page, "PROJECT_UPLOAD_DIR", tmp_path)
    project_root = page._save_project_folder_upload(
        [
            _FakeUpload("DemoProject/README.md", b"# Demo"),
            _FakeUpload("DemoProject/src/app.py", b"print('hi')"),
        ],
        "demo-project",
    )

    assert project_root == tmp_path / "demo-project" / "source" / "DemoProject"
    assert (project_root / "src" / "app.py").read_text(encoding="utf-8") == "print('hi')"


def test_save_project_folder_upload_rejects_too_many_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.observability.dashboard.pages import twinmind_archive as page

    monkeypatch.setattr(page, "PROJECT_UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(page, "MAX_FOLDER_UPLOAD_FILES", 2)

    with pytest.raises(ValueError, match="Please upload a ZIP"):
        page._save_project_folder_upload(
            [
                _FakeUpload("DemoProject/a.py", b""),
                _FakeUpload("DemoProject/b.py", b""),
                _FakeUpload("DemoProject/c.py", b""),
            ],
            "demo-project",
        )


def test_entity_display_name_uses_human_readable_context() -> None:
    from src.observability.dashboard.pages import twinmind_archive as page

    assert (
        page._entity_display_name("func:run", _sample_draft())
        == "Function: run"
    )
    assert (
        page._entity_display_name("file:app.py", _sample_draft())
        == "File: app.py"
    )


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


def test_format_agent_result_can_expand_archive_ids() -> None:
    from src.observability.dashboard.pages import twinmind_archive as page

    result = AgentResult(
        mode=QueryMode.IMPACT_ANALYSIS,
        question="What changes?",
        summary="Impact analysis traced deterministic archive relationships.",
        affected_entities=["func:run"],
        evidence_card_ids=["ev:1"],
        confidence=0.8,
    )

    formatted = page._format_agent_result(result, draft=_sample_draft())

    assert "- Function: run" in formatted
    assert "- run (app.py)" in formatted


def test_format_agent_result_supports_chinese_labels() -> None:
    from src.observability.dashboard.pages import twinmind_archive as page

    result = AgentResult(
        mode=QueryMode.RISK_AUDIT,
        question="有哪些风险？",
        summary="Risk audit found no placeholder evidence.",
        risks=["Review stale docs."],
        next_actions=["Open evidence."],
        confidence=0.5,
    )

    formatted = page._format_agent_result(result, language="zh")

    assert "模式: 风险审计" in formatted
    assert "置信度: 0.50" in formatted
    assert "风险:" in formatted
    assert "下一步行动:" in formatted


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


def _build_zip(files: dict[str, bytes]) -> bytes:
    import io

    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        for filename, payload in files.items():
            archive.writestr(filename, payload)
    return buffer.getvalue()
