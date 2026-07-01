from src.project_archive.adapters.config_adapter import ConfigAdapter
from src.project_archive.adapters.markdown_adapter import MarkdownAdapter
from src.project_archive.adapters.python_adapter import PythonAdapter
from src.project_archive.adapters.tree_sitter_code_adapter import TreeSitterCodeAdapter
from src.project_archive.types import ProjectFile


def test_python_adapter_extracts_classes_functions_and_imports():
    project_file = ProjectFile(
        id="file_main",
        path="src/sample_app/main.py",
        language="python",
        text=(
            "import yaml\n\n"
            "class QueryService:\n"
            "    def run(self):\n"
            "        return load_config()\n\n"
            "def load_config():\n"
            "    return {}\n"
        ),
    )

    result = PythonAdapter().extract(project_file)

    names = {entity.name for entity in result.entities}
    relation_types = {relation.type for relation in result.relations}

    assert "QueryService" in names
    assert "run" in names
    assert "load_config" in names
    assert "IMPORTS" in relation_types
    assert "DEFINES" in relation_types
    assert result.evidence_cards


def test_markdown_adapter_extracts_headings_as_concepts():
    project_file = ProjectFile(
        id="file_readme",
        path="README.md",
        language="markdown",
        text="# Project\n\n## Architecture\n\nDetails",
    )

    result = MarkdownAdapter().extract(project_file)

    assert {entity.name for entity in result.entities if entity.type == "Concept"} == {
        "Project",
        "Architecture",
    }
    assert any(entity.type == "File" and entity.name == "README.md" for entity in result.entities)
    assert result.evidence_cards[0].source_type == "markdown"


def test_config_adapter_extracts_top_level_config_keys():
    project_file = ProjectFile(
        id="file_settings",
        path="config/settings.yaml",
        language="yaml",
        text="mode: demo\nretrieval:\n  top_k: 5\n",
    )

    result = ConfigAdapter().extract(project_file)

    config_entities = [entity for entity in result.entities if entity.type == "Config"]

    assert {entity.name for entity in config_entities} >= {"mode", "retrieval"}
    assert any(
        entity.type == "File" and entity.name == "config/settings.yaml"
        for entity in result.entities
    )


def test_config_adapter_returns_file_entity_for_malformed_config():
    project_file = ProjectFile(
        id="file_settings",
        path="config/settings.yaml",
        language="yaml",
        text="mode: [demo\n",
    )

    result = ConfigAdapter().extract(project_file)

    assert any(
        entity.type == "File" and entity.name == "config/settings.yaml"
        for entity in result.entities
    )
    assert [entity for entity in result.entities if entity.type == "Config"] == []


def test_tree_sitter_adapter_extracts_java_structure_and_semantics():
    project_file = ProjectFile(
        id="file_user_service",
        path="src/main/java/demo/UserService.java",
        language="java",
        text=(
            "package demo;\n"
            "import java.util.List;\n"
            "public class UserService extends BaseService implements UserApi {\n"
            "    public User getUser(String id) { return repository.findById(id); }\n"
            "}\n"
        ),
    )

    result = TreeSitterCodeAdapter("java").extract(project_file)

    names = {entity.name for entity in result.entities}
    types = {entity.type for entity in result.entities}
    relation_types = {relation.type for relation in result.relations}

    assert {"demo", "java.util.List", "UserService", "getUser"} <= names
    assert {"Package", "Import", "Dependency", "Class", "Method", "Call"} <= types
    assert {"DECLARES_PACKAGE", "IMPORTS", "DEPENDS_ON", "DEFINES", "EXTENDS", "IMPLEMENTS", "CALLS"} <= relation_types


def test_tree_sitter_adapter_extracts_cpp_typescript_go_and_rust_structures():
    cases = [
        (
            "cpp",
            "src/service/vector_index.cpp",
            '#include <vector>\nnamespace demo { class VectorIndex { public: int search(){ return score(); } }; struct Result {}; }\n',
            {"vector", "demo", "VectorIndex", "Result", "search"},
            {"Import", "Namespace", "Class", "Struct", "Function"},
        ),
        (
            "typescript",
            "frontend/src/App.ts",
            'import React from "react";\nexport interface Props { id: string }\nexport type User = { id: string }\nexport class App { render(){ return fetchData(); } }\nexport function fetchData(){ return 1 }\nconst useSearch = () => fetchData();\n',
            {"react", "Props", "User", "App", "fetchData", "useSearch"},
            {"Import", "Interface", "TypeAlias", "Class", "Function", "Call"},
        ),
        (
            "go",
            "cmd/server/main.go",
            'package main\nimport "fmt"\ntype User struct { Name string }\ntype Repo interface { Get() }\nfunc main(){ fmt.Println("hi") }\nfunc (s *Service) Run() {}\n',
            {"main", "fmt", "User", "Repo", "Run"},
            {"Package", "Import", "Struct", "Interface", "Function", "Method"},
        ),
        (
            "rust",
            "src/main.rs",
            "use std::fmt;\nmod api;\npub struct User { name: String }\nenum Kind { A }\ntrait Repo { fn get(&self); }\nimpl User { pub fn new() -> Self { User { name: String::new() } } }\nfn main() {}\n",
            {"std::fmt", "api", "User", "Kind", "Repo", "impl User", "new", "main"},
            {"Import", "Module", "Struct", "Enum", "Trait", "Implementation", "Function"},
        ),
    ]

    for language, path, text, expected_names, expected_types in cases:
        result = TreeSitterCodeAdapter(language).extract(
            ProjectFile(id=f"file_{language}", path=path, language=language, text=text)
        )
        names = {entity.name for entity in result.entities}
        types = {entity.type for entity in result.entities}

        assert expected_names <= names
        assert expected_types <= types
