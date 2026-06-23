from src.project_archive.types import (
    AgentResult,
    ArchiveHall,
    EvidenceCard,
    GraphPath,
    ProjectArchiveDraft,
    ProjectEntity,
    ProjectFile,
    ProjectRelation,
    QueryMode,
)


def test_evidence_card_serializes_source_location():
    card = EvidenceCard(
        id="ev_001",
        source_type="code",
        source_path="src/app.py",
        title="Function entry",
        snippet="def run():",
        line_start=10,
        line_end=12,
        linked_entities=["fn_run"],
        confidence=0.91,
    )

    data = card.to_dict()

    assert data["id"] == "ev_001"
    assert data["source_path"] == "src/app.py"
    assert data["line_start"] == 10
    assert data["line_end"] == 12
    assert data["linked_entities"] == ["fn_run"]


def test_project_entity_relation_and_hall_round_trip():
    entity = ProjectEntity(
        id="fn_run",
        type="Function",
        name="run",
        source_path="src/app.py",
        properties={"language": "python"},
        evidence_ids=["ev_001"],
    )
    relation = ProjectRelation(
        id="rel_001",
        source_id="file_app",
        target_id="fn_run",
        type="DEFINES",
        evidence_ids=["ev_001"],
    )
    hall = ArchiveHall(
        id="hall_architecture",
        name="Architecture Hall",
        description="Project structure and entry points",
        entity_ids=["file_app", "fn_run"],
        risk_ids=[],
    )

    assert ProjectEntity.from_dict(entity.to_dict()) == entity
    assert ProjectRelation.from_dict(relation.to_dict()) == relation
    assert ArchiveHall.from_dict(hall.to_dict()) == hall


def test_agent_result_requires_evidence_for_non_speculative_claims():
    result = AgentResult(
        mode=QueryMode.IMPACT_ANALYSIS,
        question="Add graph support",
        summary="Graph support affects ingestion and query tools.",
        affected_entities=["IngestionPipeline"],
        graph_paths=[GraphPath(nodes=["IngestionPipeline", "KGExtractor"], relations=["AFFECTS"])],
        evidence_card_ids=["ev_001"],
        risks=["Graph extraction should not block ingestion."],
        next_actions=["Add KG extraction after chunking."],
        confidence=0.82,
    )

    data = result.to_dict()

    assert data["mode"] == "impact_analysis"
    assert data["evidence_card_ids"] == ["ev_001"]
    assert data["graph_paths"][0]["nodes"] == ["IngestionPipeline", "KGExtractor"]


def test_project_file_carries_relative_path_and_language():
    file = ProjectFile(
        id="file_src_app_py",
        path="src/app.py",
        language="python",
        text="def run():\n    return 0\n",
        metadata={"size": 24},
    )

    assert file.path == "src/app.py"
    assert file.language == "python"
    assert file.metadata["size"] == 24


def test_project_archive_draft_round_trip():
    draft = ProjectArchiveDraft(
        project_id="sample",
        halls=[
            ArchiveHall(
                id="hall_architecture",
                name="Architecture Hall",
                description="Project structure",
                entity_ids=["file_app"],
            )
        ],
        entities=[
            ProjectEntity(
                id="file_app",
                type="File",
                name="src/app.py",
                source_path="src/app.py",
            )
        ],
        relations=[
            ProjectRelation(
                id="rel_app_run",
                source_id="file_app",
                target_id="fn_run",
                type="DEFINES",
            )
        ],
        evidence_cards=[
            EvidenceCard(
                id="ev_app",
                source_type="code",
                source_path="src/app.py",
                title="Function: run",
                snippet="def run():",
            )
        ],
        confirmation_items=["Please review hall assignments."],
    )

    assert ProjectArchiveDraft.from_dict(draft.to_dict()) == draft
