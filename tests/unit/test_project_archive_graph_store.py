import sys
import types
from importlib.util import find_spec

import pytest

from types import SimpleNamespace

from src.project_archive.service import ProjectArchiveService
from src.project_archive.graph_store import (
    GraphStoreFactory,
    KuzuGraphStore,
    Neo4jGraphStore,
    SQLiteGraphStore,
    create_graph_store,
)
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


def test_create_graph_store_uses_preferred_provider(tmp_path):
    store = create_graph_store(
        path=tmp_path / "graph.db",
        preferred_provider="sqlite",
    )

    assert isinstance(store, SQLiteGraphStore)


def test_graph_store_factory_can_create_neo4j_provider(monkeypatch, tmp_path):
    run_calls = []

    class FakeResult:
        def consume(self):
            return None

        def __iter__(self):
            return iter([])

    class FakeTx:
        def run(self, query, **params):
            run_calls.append((query, params))
            return FakeResult()

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute_write(self, callback):
            return callback(FakeTx())

        def execute_read(self, callback):
            return callback(FakeTx())

    class FakeDriver:
        def session(self, database=None):
            assert database == "neo4j"
            return FakeSession()

        def close(self):
            return None

    class FakeGraphDatabase:
        @staticmethod
        def driver(uri, auth):
            assert uri == "bolt://neo4j.local:7687"
            assert auth == ("neo4j", "secret")
            return FakeDriver()

    fake_module = types.ModuleType("neo4j")
    fake_module.GraphDatabase = FakeGraphDatabase
    monkeypatch.setitem(sys.modules, "neo4j", fake_module)

    store = GraphStoreFactory.create(
        provider="neo4j",
        path=tmp_path / "ignored",
        project_id="sample",
        config={
            "uri": "bolt://neo4j.local:7687",
            "username": "neo4j",
            "password": "secret",
            "database": "neo4j",
        },
    )

    assert isinstance(store, Neo4jGraphStore)
    assert any("ProjectEntity" in query for query, _ in run_calls)


def test_neo4j_graph_store_requires_project_id(monkeypatch):
    fake_module = types.ModuleType("neo4j")
    fake_module.GraphDatabase = object()
    monkeypatch.setitem(sys.modules, "neo4j", fake_module)

    with pytest.raises(ValueError, match="project_id"):
        Neo4jGraphStore(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="secret",
            project_id="",
        )


def test_project_archive_service_reads_configured_graph_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.project_archive.service.load_settings",
        lambda: SimpleNamespace(
            project_archive=SimpleNamespace(
                graph_store=SimpleNamespace(
                    provider="neo4j",
                    uri="bolt://localhost:7687",
                    username="neo4j",
                    password="secret",
                    database="neo4j",
                )
            )
        ),
    )

    service = ProjectArchiveService(storage_dir=tmp_path)

    assert service.graph_provider == "neo4j"
    assert service.graph_config["uri"] == "bolt://localhost:7687"


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


def test_sqlite_graph_store_persists_between_instances(tmp_path):
    db_path = tmp_path / "archive_graph.db"
    first_store = SQLiteGraphStore(db_path)
    entity = ProjectEntity(id="fn_run", type="Function", name="run", source_path="src/app.py")
    relation = ProjectRelation(id="rel_1", source_id="file_app", target_id="fn_run", type="DEFINES")
    evidence = EvidenceCard(
        id="ev_1",
        source_type="code",
        source_path="src/app.py",
        title="run",
        snippet="def run():",
    )

    first_store.upsert_entities([entity])
    first_store.upsert_relations([relation])
    first_store.upsert_evidence([evidence])

    second_store = SQLiteGraphStore(db_path)

    assert second_store.get_entity("fn_run") == entity
    assert second_store.list_relations(source_id="file_app") == [relation]
    assert second_store.list_evidence() == [evidence]


def test_graph_store_find_paths_matches_names_case_insensitively(tmp_path):
    store = SQLiteGraphStore(tmp_path / "archive_graph.db")
    source = ProjectEntity(id="module_ingestion", type="Module", name="Ingestion")
    target = ProjectEntity(id="module_query", type="Module", name="Query")
    relation = ProjectRelation(
        id="rel_affects",
        source_id="module_ingestion",
        target_id="module_query",
        type="AFFECTS",
        evidence_ids=["ev_1"],
    )

    store.upsert_entities([source, target])
    store.upsert_relations([relation])

    paths = store.find_paths("ingestion", "qUeRy")

    assert len(paths) == 1
    assert paths[0].nodes == ["module_ingestion", "module_query"]
    assert paths[0].relations == ["AFFECTS"]
    assert paths[0].evidence_ids == ["ev_1"]


@pytest.mark.skipif(
    find_spec("kuzu") is None,
    reason="Kuzu optional dependency is not installed",
)
def test_kuzu_graph_store_round_trip(tmp_path):
    store = KuzuGraphStore(tmp_path / "archive_graph.kuzu")
    source = ProjectEntity(
        id="file_app",
        type="File",
        name="app.py",
        source_path="src/app.py",
    )
    target = ProjectEntity(
        id="fn_run",
        type="Function",
        name="run",
        source_path="src/app.py",
        evidence_ids=["ev_1"],
    )
    relation = ProjectRelation(
        id="rel_1",
        source_id="file_app",
        target_id="fn_run",
        type="DEFINES",
        evidence_ids=["ev_1"],
    )
    evidence = EvidenceCard(
        id="ev_1",
        source_type="code",
        source_path="src/app.py",
        title="run",
        snippet="def run():",
    )

    store.upsert_entities([source, target])
    store.upsert_relations([relation])
    store.upsert_evidence([evidence])

    assert store.get_entity("fn_run") == target
    assert store.list_entities(type="Function") == [target]
    assert store.list_relations(source_id="file_app") == [relation]
    assert store.list_evidence() == [evidence]
    assert store.find_paths("app.py", "run")[0].nodes == ["file_app", "fn_run"]
