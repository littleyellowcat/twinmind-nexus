from pathlib import Path

from src.project_archive.archive_builder import ArchiveBuilder
from src.project_archive.graph_store import SQLiteGraphStore


FIXTURE = Path("tests/fixtures/project_archive_sample")


def test_archive_builder_creates_halls_entities_relations_and_evidence(tmp_path):
    graph_store = SQLiteGraphStore(tmp_path / "graph.db")
    builder = ArchiveBuilder(graph_store=graph_store)

    draft = builder.build(project_root=FIXTURE, project_id="sample")

    halls_by_id = {hall.id: hall for hall in draft.halls}
    entity_names = {entity.name for entity in draft.entities}
    relation_types = {relation.type for relation in draft.relations}

    assert {
        hall_id: hall.name for hall_id, hall in halls_by_id.items()
    } == {
        "hall_architecture": "Architecture Hall",
        "hall_retrieval": "Retrieval Hall",
        "hall_config": "Configuration Hall",
        "hall_concepts": "Concept Hall",
        "hall_dependencies": "Dependency Hall",
    }
    assert "QueryService" in entity_names
    assert "load_config" in entity_names
    assert "DEFINES" in relation_types
    assert draft.evidence_cards
    assert graph_store.list_entities()
    assert graph_store.list_relations()
    assert graph_store.list_evidence()


def test_archive_builder_marks_low_confidence_items_for_confirmation(tmp_path):
    graph_store = SQLiteGraphStore(tmp_path / "graph.db")
    builder = ArchiveBuilder(graph_store=graph_store)

    draft = builder.build(project_root=FIXTURE, project_id="sample")

    confirmation_text = "\n".join(draft.confirmation_items).lower()

    assert "duplicates" in confirmation_text
    assert "false positives" in confirmation_text
    assert "hall assignments" in confirmation_text
    assert "risk audit" in confirmation_text


def test_archive_builder_falls_back_to_generic_adapter_when_adapter_errors(tmp_path):
    class RaisingAdapter:
        def extract(self, project_file):
            raise RuntimeError("boom")

    graph_store = SQLiteGraphStore(tmp_path / "graph.db")
    builder = ArchiveBuilder(graph_store=graph_store)
    builder.adapters["python"] = RaisingAdapter()

    draft = builder.build(project_root=FIXTURE, project_id="sample")

    python_file_entities = [
        entity
        for entity in draft.entities
        if entity.type == "File" and entity.name == "src/sample_app/main.py"
    ]
    fallback_evidence = [
        evidence
        for evidence in draft.evidence_cards
        if evidence.source_path == "src/sample_app/main.py"
        and evidence.source_type == "generic"
    ]

    assert python_file_entities
    assert fallback_evidence
