from src.project_archive.adapters.config_adapter import ConfigAdapter
from src.project_archive.adapters.markdown_adapter import MarkdownAdapter
from src.project_archive.adapters.python_adapter import PythonAdapter
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
