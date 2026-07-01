from pathlib import Path

from src.project_archive.archive_builder import ArchiveBuilder, _build_halls
from src.project_archive.graph_store import SQLiteGraphStore
from src.project_archive.types import ProjectEntity

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


def test_archive_builder_assigns_manifest_and_retrieval_files_to_halls():
    entities = [
        ProjectEntity(id="file:pom", type="File", name="pom.xml", source_path="pom.xml"),
        ProjectEntity(id="file:go", type="File", name="go.mod", source_path="go.mod"),
        ProjectEntity(
            id="file:search",
            type="File",
            name="src/search/vector_index.cpp",
            source_path="src/search/vector_index.cpp",
        ),
        ProjectEntity(
            id="config:settings",
            type="Config",
            name="embedding.provider",
            source_path="config/settings.yaml",
        ),
    ]

    halls_by_id = {hall.id: hall for hall in _build_halls(entities)}

    assert "file:search" in halls_by_id["hall_retrieval"].entity_ids
    assert "config:settings" in halls_by_id["hall_config"].entity_ids
    assert "file:pom" in halls_by_id["hall_config"].entity_ids
    assert "file:pom" in halls_by_id["hall_dependencies"].entity_ids
    assert "file:go" in halls_by_id["hall_dependencies"].entity_ids


def test_archive_builder_extracts_multilanguage_code_and_semantic_edges(tmp_path):
    project_root = tmp_path / "mixed"
    java_dir = project_root / "src" / "main" / "java" / "demo"
    ts_dir = project_root / "frontend" / "src"
    go_dir = project_root / "cmd" / "server"
    rust_dir = project_root / "src"
    cpp_dir = project_root / "src" / "native"
    for directory in [java_dir, ts_dir, go_dir, rust_dir, cpp_dir]:
        directory.mkdir(parents=True, exist_ok=True)
    (java_dir / "UserService.java").write_text(
        "package demo;\n"
        "import java.util.List;\n"
        "class UserService { User getUser(String id) { return repo.findById(id); } }\n",
        encoding="utf-8",
    )
    (ts_dir / "App.ts").write_text(
        'import React from "react";\n'
        "export interface Props { id: string }\n"
        "export function SearchPanel(){ return fetchData(); }\n",
        encoding="utf-8",
    )
    (go_dir / "main.go").write_text(
        'package main\nimport "fmt"\nfunc main(){ fmt.Println("hi") }\n',
        encoding="utf-8",
    )
    (rust_dir / "main.rs").write_text(
        "use std::fmt;\nstruct User {}\nfn main() {}\n",
        encoding="utf-8",
    )
    (cpp_dir / "vector_index.cpp").write_text(
        "#include <vector>\nnamespace native { struct SearchResult {}; }\n",
        encoding="utf-8",
    )

    graph_store = SQLiteGraphStore(tmp_path / "graph.db")
    draft = ArchiveBuilder(graph_store=graph_store).build(
        project_root=project_root,
        project_id="mixed",
        scan_profile="full",
    )

    names = {entity.name for entity in draft.entities}
    types = {entity.type for entity in draft.entities}
    relation_types = {relation.type for relation in draft.relations}

    assert {"UserService", "Props", "SearchPanel", "main", "User", "SearchResult"} <= names
    assert {"Class", "Interface", "Function", "Struct", "EntryPoint", "ServiceBoundary"} <= types
    assert {"IMPORTS", "DEPENDS_ON", "CALLS", "DECLARES_ENTRYPOINT", "BELONGS_TO_MODULE", "BELONGS_TO_BOUNDARY"} <= relation_types
