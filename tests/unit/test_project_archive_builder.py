from pathlib import Path

from src.project_archive.archive_builder import ArchiveBuilder
from src.project_archive.graph_store import SQLiteGraphStore


FIXTURE = Path("tests/fixtures/project_archive_sample")


def test_archive_builder_creates_halls_entities_relations_and_evidence(tmp_path):
    graph_store = SQLiteGraphStore(tmp_path / "graph.db")
    builder = ArchiveBuilder(graph_store=graph_store)

    draft = builder.build(project_root=FIXTURE, project_id="sample")

    hall_names = {hall.name for hall in draft.halls}
    entity_names = {entity.name for entity in draft.entities}
    relation_types = {relation.type for relation in draft.relations}

    assert "Architecture Hall" in hall_names
    assert "Retrieval Hall" in hall_names
    assert "QueryService" in entity_names
    assert "load_config" in entity_names
    assert "DEFINES" in relation_types
    assert draft.evidence_cards
    assert graph_store.list_entities()


def test_archive_builder_marks_low_confidence_items_for_confirmation(tmp_path):
    graph_store = SQLiteGraphStore(tmp_path / "graph.db")
    builder = ArchiveBuilder(graph_store=graph_store)

    draft = builder.build(project_root=FIXTURE, project_id="sample")

    assert draft.confirmation_items
    assert any("review" in item.lower() for item in draft.confirmation_items)
