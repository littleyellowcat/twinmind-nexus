from src.project_archive.graph_store import GraphStoreFactory, SQLiteGraphStore
from src.project_archive.types import EvidenceCard, ProjectEntity, ProjectRelation


def test_sqlite_graph_store_round_trip(tmp_path):
    store = SQLiteGraphStore(tmp_path / "archive_graph.db")
    entity = ProjectEntity(id="fn_run", type="Function", name="run", source_path="src/app.py")
    relation = ProjectRelation(id="rel_1", source_id="file_app", target_id="fn_run", type="DEFINES")
    evidence = EvidenceCard(
        id="ev_1",
        source_type="code",
        source_path="src/app.py",
        title="run",
        snippet="def run():",
    )

    store.upsert_entities([entity])
    store.upsert_relations([relation])
    store.upsert_evidence([evidence])

    assert store.get_entity("fn_run") == entity
    assert store.list_entities(type="Function") == [entity]
    assert store.list_relations(source_id="file_app") == [relation]
    assert store.list_evidence() == [evidence]


def test_graph_store_factory_uses_sqlite_fallback(tmp_path):
    store = GraphStoreFactory.create(provider="sqlite", path=tmp_path / "graph.db")

    assert isinstance(store, SQLiteGraphStore)


def test_graph_store_finds_paths_by_entity_names(tmp_path):
    store = SQLiteGraphStore(tmp_path / "archive_graph.db")
    source = ProjectEntity(id="module_ingestion", type="Module", name="Ingestion")
    target = ProjectEntity(id="module_query", type="Module", name="Query")
    relation = ProjectRelation(
        id="rel_affects",
        source_id="module_ingestion",
        target_id="module_query",
        type="AFFECTS",
    )

    store.upsert_entities([source, target])
    store.upsert_relations([relation])

    paths = store.find_paths("Ingestion", "Query")

    assert len(paths) == 1
    assert paths[0].nodes == ["module_ingestion", "module_query"]
    assert paths[0].relations == ["AFFECTS"]
