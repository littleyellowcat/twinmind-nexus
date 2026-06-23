# TwinMind Archive MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 1 TwinMind Archive MVP: import a project directory, create a correctable project archive graph, run four agentic work modes, expose MCP tools, and show the archive in the Streamlit dashboard.

**Architecture:** Add a focused `src/project_archive/` package that sits beside the existing ingestion, query, MCP, and dashboard modules. The package owns project scanning, language adapters, archive entities, graph storage, archive building, and deterministic agent workflows. Existing RAG components remain the retrieval foundation; this plan first creates testable local archive and graph behavior, then wires it into MCP and Streamlit.

**Tech Stack:** Python 3.10+, dataclasses, `ast`, `tomllib`, `pyyaml`, SQLite fallback graph store, optional Kuzu adapter, pytest, existing MCP SDK, existing Streamlit dashboard.

---

## Scope Check

This plan implements only Phase 1 from `docs/superpowers/specs/2026-06-23-twinmind-archive-design.md`.

Included:

- Python, Markdown, YAML, TOML project scanning.
- Generic fallback scanning for other source files.
- Evidence cards, archive halls, project entities, project relations, graph paths, and agent results.
- SQLite graph store fallback for the first end-to-end slice.
- Kuzu graph store adapter shell with a dedicated follow-up task to make Kuzu the default backend after the SQLite path is green.
- Draft archive builder with rule-based extraction.
- Deterministic agent workflows for architecture tour, impact analysis, risk audit, and evidence Q&A.
- MCP tools for project archive ingestion and querying.
- Streamlit `TwinMind Archive` dashboard page.
- Unit and integration tests.

Excluded from this plan:

- React workspace.
- Three.js or 2.5D archive rendering.
- Neo4j adapter.
- Fully autonomous ReAct or LangGraph loop.
- GitHub issue, PR, and deep commit timeline ingestion.
- Deep Java/C++/TypeScript Tree-sitter parsing.

## File Structure

Create:

- `src/project_archive/__init__.py`  
  Public package exports.

- `src/project_archive/types.py`  
  Dataclasses and enums for archive entities, evidence cards, halls, relations, graph paths, project files, agent runs, and query modes.

- `src/project_archive/scanner.py`  
  Project directory scanner with ignore rules and extension-based routing.

- `src/project_archive/adapters/__init__.py`  
  Adapter exports.

- `src/project_archive/adapters/base.py`  
  Base language adapter contract.

- `src/project_archive/adapters/python_adapter.py`  
  Python AST extraction for classes, functions, imports, and evidence cards.

- `src/project_archive/adapters/markdown_adapter.py`  
  Heading-aware Markdown extraction.

- `src/project_archive/adapters/config_adapter.py`  
  YAML/TOML config extraction.

- `src/project_archive/adapters/generic_adapter.py`  
  Generic text/code fallback adapter.

- `src/project_archive/graph_store.py`  
  `BaseGraphStore`, `SQLiteGraphStore`, `KuzuGraphStore`, and `GraphStoreFactory`. SQLite is implemented first so the MVP is immediately testable; Kuzu is enabled in Task 9.

- `src/project_archive/archive_builder.py`  
  Builds a draft archive from scanned project files and graph storage.

- `src/project_archive/agents.py`  
  Deterministic agent classes and workflows.

- `src/project_archive/service.py`  
  Service layer used by MCP tools and Streamlit.

- `src/mcp_server/tools/ingest_project_archive.py`  
  MCP tool to ingest a project archive.

- `src/mcp_server/tools/query_project_twin.py`  
  MCP tool to query a project archive.

- `src/observability/dashboard/pages/twinmind_archive.py`  
  Streamlit page for project import, mode selection, graph path summary, evidence cards, and agent timeline.

- `tests/fixtures/project_archive_sample/README.md`

- `tests/fixtures/project_archive_sample/pyproject.toml`

- `tests/fixtures/project_archive_sample/src/sample_app/__init__.py`

- `tests/fixtures/project_archive_sample/src/sample_app/main.py`

- `tests/fixtures/project_archive_sample/config/settings.yaml`

- `tests/unit/test_project_archive_types.py`

- `tests/unit/test_project_archive_scanner.py`

- `tests/unit/test_project_archive_adapters.py`

- `tests/unit/test_project_archive_graph_store.py`

- `tests/unit/test_project_archive_builder.py`

- `tests/unit/test_project_archive_agents.py`

- `tests/integration/test_project_archive_service.py`

Modify:

- `pyproject.toml`  
  Add optional `kuzu` dependency group if desired. Keep MVP functional without Kuzu installed.

- `src/mcp_server/protocol_handler.py`  
  Register new MCP tools.

- `src/observability/dashboard/app.py`  
  Add `TwinMind Archive` navigation page.

## Task 1: Core Archive Types

**Files:**

- Create: `src/project_archive/__init__.py`
- Create: `src/project_archive/types.py`
- Test: `tests/unit/test_project_archive_types.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_project_archive_types.py`:

```python
from src.project_archive.types import (
    AgentResult,
    ArchiveHall,
    EvidenceCard,
    GraphPath,
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/unit/test_project_archive_types.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.project_archive'`.

- [ ] **Step 3: Create package exports**

Create `src/project_archive/__init__.py`:

```python
"""Project knowledge archive package for TwinMind Archive."""

from src.project_archive.types import (
    AgentResult,
    ArchiveHall,
    EvidenceCard,
    GraphPath,
    ProjectEntity,
    ProjectFile,
    ProjectRelation,
    QueryMode,
)

__all__ = [
    "AgentResult",
    "ArchiveHall",
    "EvidenceCard",
    "GraphPath",
    "ProjectEntity",
    "ProjectFile",
    "ProjectRelation",
    "QueryMode",
]
```

- [ ] **Step 4: Implement archive dataclasses**

Create `src/project_archive/types.py`:

```python
"""Core contracts for TwinMind project archives."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class QueryMode(str, Enum):
    """Supported TwinMind Archive query modes."""

    ARCHITECTURE_TOUR = "architecture_tour"
    IMPACT_ANALYSIS = "impact_analysis"
    RISK_AUDIT = "risk_audit"
    EVIDENCE_QA = "evidence_qa"


@dataclass(frozen=True)
class EvidenceCard:
    id: str
    source_type: str
    source_path: str
    title: str
    snippet: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    linked_entities: List[str] = field(default_factory=list)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceCard":
        return cls(**data)


@dataclass(frozen=True)
class ProjectEntity:
    id: str
    type: str
    name: str
    source_path: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    evidence_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectEntity":
        return cls(**data)


@dataclass(frozen=True)
class ProjectRelation:
    id: str
    source_id: str
    target_id: str
    type: str
    evidence_ids: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectRelation":
        return cls(**data)


@dataclass(frozen=True)
class ArchiveHall:
    id: str
    name: str
    description: str
    entity_ids: List[str] = field(default_factory=list)
    risk_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArchiveHall":
        return cls(**data)


@dataclass(frozen=True)
class GraphPath:
    nodes: List[str]
    relations: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphPath":
        return cls(**data)


@dataclass(frozen=True)
class ProjectFile:
    id: str
    path: str
    language: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectFile":
        return cls(**data)


@dataclass(frozen=True)
class AgentResult:
    mode: QueryMode
    question: str
    summary: str
    affected_entities: List[str] = field(default_factory=list)
    graph_paths: List[GraphPath] = field(default_factory=list)
    evidence_card_ids: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    next_actions: List[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["mode"] = self.mode.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentResult":
        payload = dict(data)
        payload["mode"] = QueryMode(payload["mode"])
        payload["graph_paths"] = [
            GraphPath.from_dict(path) if isinstance(path, dict) else path
            for path in payload.get("graph_paths", [])
        ]
        return cls(**payload)
```

- [ ] **Step 5: Run tests**

Run:

```bash
pytest tests/unit/test_project_archive_types.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/project_archive/__init__.py src/project_archive/types.py tests/unit/test_project_archive_types.py
git commit -m "feat: add TwinMind archive core types"
```

## Task 2: Project Scanner and Language Adapters

**Files:**

- Create: `src/project_archive/scanner.py`
- Create: `src/project_archive/adapters/__init__.py`
- Create: `src/project_archive/adapters/base.py`
- Create: `src/project_archive/adapters/python_adapter.py`
- Create: `src/project_archive/adapters/markdown_adapter.py`
- Create: `src/project_archive/adapters/config_adapter.py`
- Create: `src/project_archive/adapters/generic_adapter.py`
- Create: `tests/fixtures/project_archive_sample/README.md`
- Create: `tests/fixtures/project_archive_sample/pyproject.toml`
- Create: `tests/fixtures/project_archive_sample/src/sample_app/__init__.py`
- Create: `tests/fixtures/project_archive_sample/src/sample_app/main.py`
- Create: `tests/fixtures/project_archive_sample/config/settings.yaml`
- Test: `tests/unit/test_project_archive_scanner.py`
- Test: `tests/unit/test_project_archive_adapters.py`

- [ ] **Step 1: Create fixture project files**

Create `tests/fixtures/project_archive_sample/README.md`:

```markdown
# Sample Archive Project

This project demonstrates a query service.

## Architecture

The service exposes a command-line entry point and reads YAML configuration.
```

Create `tests/fixtures/project_archive_sample/pyproject.toml`:

```toml
[project]
name = "sample-archive-project"
version = "0.1.0"
```

Create `tests/fixtures/project_archive_sample/src/sample_app/__init__.py`:

```python
"""Sample app package."""
```

Create `tests/fixtures/project_archive_sample/src/sample_app/main.py`:

```python
import yaml


class QueryService:
    def __init__(self, config_path: str):
        self.config_path = config_path

    def run(self) -> str:
        return load_config(self.config_path)["mode"]


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)
```

Create `tests/fixtures/project_archive_sample/config/settings.yaml`:

```yaml
mode: demo
retrieval:
  top_k: 5
```

- [ ] **Step 2: Write failing scanner tests**

Create `tests/unit/test_project_archive_scanner.py`:

```python
from pathlib import Path

from src.project_archive.scanner import ProjectScanner


FIXTURE = Path("tests/fixtures/project_archive_sample")


def test_scanner_discovers_supported_project_files():
    scanner = ProjectScanner(root=FIXTURE)

    files = scanner.scan()
    paths = {file.path for file in files}

    assert "README.md" in paths
    assert "pyproject.toml" in paths
    assert "src/sample_app/main.py" in paths
    assert "config/settings.yaml" in paths


def test_scanner_assigns_languages_from_extensions():
    scanner = ProjectScanner(root=FIXTURE)

    files = {file.path: file for file in scanner.scan()}

    assert files["src/sample_app/main.py"].language == "python"
    assert files["README.md"].language == "markdown"
    assert files["pyproject.toml"].language == "toml"
    assert files["config/settings.yaml"].language == "yaml"
```

- [ ] **Step 3: Write failing adapter tests**

Create `tests/unit/test_project_archive_adapters.py`:

```python
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

    assert {entity.name for entity in result.entities} == {"Project", "Architecture"}
    assert result.evidence_cards[0].source_type == "markdown"


def test_config_adapter_extracts_top_level_config_keys():
    project_file = ProjectFile(
        id="file_settings",
        path="config/settings.yaml",
        language="yaml",
        text="mode: demo\nretrieval:\n  top_k: 5\n",
    )

    result = ConfigAdapter().extract(project_file)

    assert {entity.name for entity in result.entities} >= {"mode", "retrieval"}
    assert all(entity.type == "Config" for entity in result.entities)
```

- [ ] **Step 4: Run tests to verify they fail**

Run:

```bash
pytest tests/unit/test_project_archive_scanner.py tests/unit/test_project_archive_adapters.py -v
```

Expected: FAIL because scanner and adapter modules do not exist.

- [ ] **Step 5: Implement adapter contracts**

Create `src/project_archive/adapters/base.py`:

```python
"""Language adapter contracts for project archive extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from src.project_archive.types import EvidenceCard, ProjectEntity, ProjectFile, ProjectRelation


@dataclass
class AdapterExtraction:
    entities: List[ProjectEntity] = field(default_factory=list)
    relations: List[ProjectRelation] = field(default_factory=list)
    evidence_cards: List[EvidenceCard] = field(default_factory=list)


class BaseLanguageAdapter:
    language: str = "generic"

    def extract(self, project_file: ProjectFile) -> AdapterExtraction:
        raise NotImplementedError
```

Create `src/project_archive/adapters/__init__.py`:

```python
"""Language adapters for TwinMind project archives."""

from src.project_archive.adapters.base import AdapterExtraction, BaseLanguageAdapter
from src.project_archive.adapters.config_adapter import ConfigAdapter
from src.project_archive.adapters.generic_adapter import GenericAdapter
from src.project_archive.adapters.markdown_adapter import MarkdownAdapter
from src.project_archive.adapters.python_adapter import PythonAdapter

__all__ = [
    "AdapterExtraction",
    "BaseLanguageAdapter",
    "ConfigAdapter",
    "GenericAdapter",
    "MarkdownAdapter",
    "PythonAdapter",
]
```

- [ ] **Step 6: Implement scanner**

Create `src/project_archive/scanner.py`:

```python
"""Project directory scanner for TwinMind Archive."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, List, Set

from src.project_archive.types import ProjectFile


DEFAULT_IGNORE_DIRS: Set[str] = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".superpowers",
    "__pycache__",
    "data",
    "dist",
    "build",
    "venv",
    ".venv",
}

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".java": "java",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
}


class ProjectScanner:
    def __init__(self, root: Path | str, ignore_dirs: Iterable[str] = DEFAULT_IGNORE_DIRS):
        self.root = Path(root).resolve()
        self.ignore_dirs = set(ignore_dirs)

    def scan(self) -> List[ProjectFile]:
        if not self.root.exists():
            raise FileNotFoundError(f"Project root does not exist: {self.root}")
        if not self.root.is_dir():
            raise ValueError(f"Project root must be a directory: {self.root}")

        files: List[ProjectFile] = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            if any(part in self.ignore_dirs for part in path.relative_to(self.root).parts):
                continue
            language = LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "generic")
            if language == "generic" and path.stat().st_size > 200_000:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            rel_path = path.relative_to(self.root).as_posix()
            files.append(
                ProjectFile(
                    id=self._file_id(rel_path),
                    path=rel_path,
                    language=language,
                    text=text,
                    metadata={"size": path.stat().st_size},
                )
            )
        return files

    @staticmethod
    def _file_id(rel_path: str) -> str:
        digest = hashlib.sha1(rel_path.encode("utf-8")).hexdigest()[:12]
        safe = rel_path.replace("/", "_").replace(".", "_")
        return f"file_{safe}_{digest}"
```

- [ ] **Step 7: Implement adapters**

Create `src/project_archive/adapters/generic_adapter.py`:

```python
"""Generic fallback adapter for unsupported project files."""

from __future__ import annotations

from src.project_archive.adapters.base import AdapterExtraction, BaseLanguageAdapter
from src.project_archive.types import EvidenceCard, ProjectEntity, ProjectFile


class GenericAdapter(BaseLanguageAdapter):
    language = "generic"

    def extract(self, project_file: ProjectFile) -> AdapterExtraction:
        entity = ProjectEntity(
            id=project_file.id,
            type="File",
            name=project_file.path,
            source_path=project_file.path,
            properties={"language": project_file.language},
        )
        evidence = EvidenceCard(
            id=f"ev_{project_file.id}",
            source_type=project_file.language,
            source_path=project_file.path,
            title=project_file.path,
            snippet=project_file.text[:500],
            linked_entities=[entity.id],
            confidence=0.7,
        )
        return AdapterExtraction(entities=[entity], evidence_cards=[evidence])
```

Create `src/project_archive/adapters/python_adapter.py`:

```python
"""Python AST adapter for project archive extraction."""

from __future__ import annotations

import ast
import hashlib
from typing import List

from src.project_archive.adapters.base import AdapterExtraction, BaseLanguageAdapter
from src.project_archive.types import EvidenceCard, ProjectEntity, ProjectFile, ProjectRelation


class PythonAdapter(BaseLanguageAdapter):
    language = "python"

    def extract(self, project_file: ProjectFile) -> AdapterExtraction:
        tree = ast.parse(project_file.text)
        lines = project_file.text.splitlines()
        entities: List[ProjectEntity] = [
            ProjectEntity(
                id=project_file.id,
                type="File",
                name=project_file.path,
                source_path=project_file.path,
                properties={"language": "python"},
            )
        ]
        relations: List[ProjectRelation] = []
        evidence_cards: List[EvidenceCard] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                entity_type = "Class" if isinstance(node, ast.ClassDef) else "Function"
                entity_id = self._entity_id(project_file.path, entity_type, node.name)
                evidence_id = f"ev_{entity_id}"
                entities.append(
                    ProjectEntity(
                        id=entity_id,
                        type=entity_type,
                        name=node.name,
                        source_path=project_file.path,
                        properties={
                            "language": "python",
                            "line_start": node.lineno,
                            "line_end": getattr(node, "end_lineno", node.lineno),
                        },
                        evidence_ids=[evidence_id],
                    )
                )
                relations.append(
                    ProjectRelation(
                        id=f"rel_{project_file.id}_defines_{entity_id}",
                        source_id=project_file.id,
                        target_id=entity_id,
                        type="DEFINES",
                        evidence_ids=[evidence_id],
                    )
                )
                evidence_cards.append(
                    EvidenceCard(
                        id=evidence_id,
                        source_type="code",
                        source_path=project_file.path,
                        title=f"{entity_type}: {node.name}",
                        snippet=self._snippet(lines, node.lineno, getattr(node, "end_lineno", node.lineno)),
                        line_start=node.lineno,
                        line_end=getattr(node, "end_lineno", node.lineno),
                        linked_entities=[entity_id],
                        confidence=0.95,
                    )
                )
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names]
                for name in names:
                    import_id = self._entity_id(project_file.path, "Import", name)
                    entities.append(
                        ProjectEntity(
                            id=import_id,
                            type="Import",
                            name=name,
                            source_path=project_file.path,
                            properties={"language": "python"},
                        )
                    )
                    relations.append(
                        ProjectRelation(
                            id=f"rel_{project_file.id}_imports_{import_id}",
                            source_id=project_file.id,
                            target_id=import_id,
                            type="IMPORTS",
                        )
                    )

        return AdapterExtraction(entities=entities, relations=relations, evidence_cards=evidence_cards)

    @staticmethod
    def _entity_id(path: str, entity_type: str, name: str) -> str:
        raw = f"{path}:{entity_type}:{name}"
        return f"{entity_type.lower()}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"

    @staticmethod
    def _snippet(lines: List[str], start: int, end: int) -> str:
        selected = lines[max(start - 1, 0):end]
        return "\n".join(selected)[:1000]
```

Create `src/project_archive/adapters/markdown_adapter.py`:

```python
"""Markdown adapter for heading and concept extraction."""

from __future__ import annotations

import hashlib

from src.project_archive.adapters.base import AdapterExtraction, BaseLanguageAdapter
from src.project_archive.types import EvidenceCard, ProjectEntity, ProjectFile, ProjectRelation


class MarkdownAdapter(BaseLanguageAdapter):
    language = "markdown"

    def extract(self, project_file: ProjectFile) -> AdapterExtraction:
        entities = [
            ProjectEntity(
                id=project_file.id,
                type="File",
                name=project_file.path,
                source_path=project_file.path,
                properties={"language": "markdown"},
            )
        ]
        relations = []
        evidence_cards = []

        for line_number, line in enumerate(project_file.text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith("#"):
                continue
            title = stripped.lstrip("#").strip()
            if not title:
                continue
            entity_id = self._heading_id(project_file.path, title, line_number)
            evidence_id = f"ev_{entity_id}"
            entities.append(
                ProjectEntity(
                    id=entity_id,
                    type="Concept",
                    name=title,
                    source_path=project_file.path,
                    properties={"line_start": line_number},
                    evidence_ids=[evidence_id],
                )
            )
            relations.append(
                ProjectRelation(
                    id=f"rel_{project_file.id}_mentions_{entity_id}",
                    source_id=project_file.id,
                    target_id=entity_id,
                    type="MENTIONS",
                    evidence_ids=[evidence_id],
                )
            )
            evidence_cards.append(
                EvidenceCard(
                    id=evidence_id,
                    source_type="markdown",
                    source_path=project_file.path,
                    title=title,
                    snippet=line,
                    line_start=line_number,
                    line_end=line_number,
                    linked_entities=[entity_id],
                    confidence=0.9,
                )
            )

        return AdapterExtraction(entities=entities, relations=relations, evidence_cards=evidence_cards)

    @staticmethod
    def _heading_id(path: str, title: str, line_number: int) -> str:
        raw = f"{path}:heading:{title}:{line_number}"
        return f"concept_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"
```

Create `src/project_archive/adapters/config_adapter.py`:

```python
"""Configuration adapter for YAML, TOML, and JSON-like files."""

from __future__ import annotations

import hashlib
import json
import tomllib
from typing import Any, Dict

import yaml

from src.project_archive.adapters.base import AdapterExtraction, BaseLanguageAdapter
from src.project_archive.types import EvidenceCard, ProjectEntity, ProjectFile, ProjectRelation


class ConfigAdapter(BaseLanguageAdapter):
    language = "config"

    def extract(self, project_file: ProjectFile) -> AdapterExtraction:
        data = self._parse(project_file)
        entities = [
            ProjectEntity(
                id=project_file.id,
                type="File",
                name=project_file.path,
                source_path=project_file.path,
                properties={"language": project_file.language},
            )
        ]
        relations = []
        evidence_cards = []

        for key in sorted(data.keys()):
            entity_id = self._config_id(project_file.path, key)
            evidence_id = f"ev_{entity_id}"
            entities.append(
                ProjectEntity(
                    id=entity_id,
                    type="Config",
                    name=key,
                    source_path=project_file.path,
                    properties={"value_type": type(data[key]).__name__},
                    evidence_ids=[evidence_id],
                )
            )
            relations.append(
                ProjectRelation(
                    id=f"rel_{project_file.id}_configures_{entity_id}",
                    source_id=project_file.id,
                    target_id=entity_id,
                    type="CONFIGURES",
                    evidence_ids=[evidence_id],
                )
            )
            evidence_cards.append(
                EvidenceCard(
                    id=evidence_id,
                    source_type="config",
                    source_path=project_file.path,
                    title=f"Config: {key}",
                    snippet=f"{key}: {data[key]!r}",
                    linked_entities=[entity_id],
                    confidence=0.9,
                )
            )

        return AdapterExtraction(entities=entities, relations=relations, evidence_cards=evidence_cards)

    @staticmethod
    def _parse(project_file: ProjectFile) -> Dict[str, Any]:
        if project_file.language == "toml":
            parsed = tomllib.loads(project_file.text)
        elif project_file.language == "json":
            parsed = json.loads(project_file.text)
        else:
            parsed = yaml.safe_load(project_file.text) or {}
        if not isinstance(parsed, dict):
            return {"value": parsed}
        return parsed

    @staticmethod
    def _config_id(path: str, key: str) -> str:
        raw = f"{path}:config:{key}"
        return f"config_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"
```

- [ ] **Step 8: Run scanner and adapter tests**

Run:

```bash
pytest tests/unit/test_project_archive_scanner.py tests/unit/test_project_archive_adapters.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/project_archive/scanner.py src/project_archive/adapters tests/fixtures/project_archive_sample tests/unit/test_project_archive_scanner.py tests/unit/test_project_archive_adapters.py
git commit -m "feat: add project archive scanner and adapters"
```

## Task 3: Graph Store Abstraction with SQLite Fallback

**Files:**

- Create: `src/project_archive/graph_store.py`
- Test: `tests/unit/test_project_archive_graph_store.py`

- [ ] **Step 1: Write failing graph store tests**

Create `tests/unit/test_project_archive_graph_store.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/unit/test_project_archive_graph_store.py -v
```

Expected: FAIL because `src.project_archive.graph_store` does not exist.

- [ ] **Step 3: Implement graph store**

Create `src/project_archive/graph_store.py`:

```python
"""Graph storage backends for TwinMind project archives."""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, List, Optional

from src.project_archive.types import EvidenceCard, GraphPath, ProjectEntity, ProjectRelation


class BaseGraphStore(ABC):
    @abstractmethod
    def upsert_entities(self, entities: Iterable[ProjectEntity]) -> None:
        raise NotImplementedError

    @abstractmethod
    def upsert_relations(self, relations: Iterable[ProjectRelation]) -> None:
        raise NotImplementedError

    @abstractmethod
    def upsert_evidence(self, evidence_cards: Iterable[EvidenceCard]) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_entity(self, entity_id: str) -> Optional[ProjectEntity]:
        raise NotImplementedError

    @abstractmethod
    def list_entities(self, type: Optional[str] = None) -> List[ProjectEntity]:
        raise NotImplementedError

    @abstractmethod
    def list_relations(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        type: Optional[str] = None,
    ) -> List[ProjectRelation]:
        raise NotImplementedError

    @abstractmethod
    def list_evidence(self) -> List[EvidenceCard]:
        raise NotImplementedError

    @abstractmethod
    def find_paths(self, source_name: str, target_name: str) -> List[GraphPath]:
        raise NotImplementedError


class SQLiteGraphStore(BaseGraphStore):
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def upsert_entities(self, entities: Iterable[ProjectEntity]) -> None:
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO entities(id, type, name, source_path, properties_json, evidence_ids_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    type=excluded.type,
                    name=excluded.name,
                    source_path=excluded.source_path,
                    properties_json=excluded.properties_json,
                    evidence_ids_json=excluded.evidence_ids_json
                """,
                [
                    (
                        entity.id,
                        entity.type,
                        entity.name,
                        entity.source_path,
                        json.dumps(entity.properties, ensure_ascii=False),
                        json.dumps(entity.evidence_ids, ensure_ascii=False),
                    )
                    for entity in entities
                ],
            )

    def upsert_relations(self, relations: Iterable[ProjectRelation]) -> None:
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO relations(id, source_id, target_id, type, evidence_ids_json, properties_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_id=excluded.source_id,
                    target_id=excluded.target_id,
                    type=excluded.type,
                    evidence_ids_json=excluded.evidence_ids_json,
                    properties_json=excluded.properties_json
                """,
                [
                    (
                        relation.id,
                        relation.source_id,
                        relation.target_id,
                        relation.type,
                        json.dumps(relation.evidence_ids, ensure_ascii=False),
                        json.dumps(relation.properties, ensure_ascii=False),
                    )
                    for relation in relations
                ],
            )

    def upsert_evidence(self, evidence_cards: Iterable[EvidenceCard]) -> None:
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO evidence(id, payload_json)
                VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET payload_json=excluded.payload_json
                """,
                [
                    (card.id, json.dumps(card.to_dict(), ensure_ascii=False))
                    for card in evidence_cards
                ],
            )

    def get_entity(self, entity_id: str) -> Optional[ProjectEntity]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, type, name, source_path, properties_json, evidence_ids_json FROM entities WHERE id = ?",
                (entity_id,),
            ).fetchone()
        return self._entity_from_row(row) if row else None

    def list_entities(self, type: Optional[str] = None) -> List[ProjectEntity]:
        with self._connect() as conn:
            if type is None:
                rows = conn.execute(
                    "SELECT id, type, name, source_path, properties_json, evidence_ids_json FROM entities ORDER BY id"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, type, name, source_path, properties_json, evidence_ids_json FROM entities WHERE type = ? ORDER BY id",
                    (type,),
                ).fetchall()
        return [self._entity_from_row(row) for row in rows]

    def list_relations(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        type: Optional[str] = None,
    ) -> List[ProjectRelation]:
        clauses = []
        params = []
        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)
        if target_id is not None:
            clauses.append("target_id = ?")
            params.append(target_id)
        if type is not None:
            clauses.append("type = ?")
            params.append(type)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT id, source_id, target_id, type, evidence_ids_json, properties_json FROM relations{where} ORDER BY id",
                params,
            ).fetchall()
        return [self._relation_from_row(row) for row in rows]

    def list_evidence(self) -> List[EvidenceCard]:
        with self._connect() as conn:
            rows = conn.execute("SELECT payload_json FROM evidence ORDER BY id").fetchall()
        return [EvidenceCard.from_dict(json.loads(row[0])) for row in rows]

    def find_paths(self, source_name: str, target_name: str) -> List[GraphPath]:
        entities = self.list_entities()
        by_name = {entity.name.lower(): entity for entity in entities}
        source = by_name.get(source_name.lower())
        target = by_name.get(target_name.lower())
        if source is None or target is None:
            return []
        paths = []
        for relation in self.list_relations(source_id=source.id, target_id=target.id):
            paths.append(
                GraphPath(
                    nodes=[relation.source_id, relation.target_id],
                    relations=[relation.type],
                    evidence_ids=relation.evidence_ids,
                )
            )
        return paths

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    source_path TEXT,
                    properties_json TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS relations (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    properties_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    @staticmethod
    def _entity_from_row(row: tuple) -> ProjectEntity:
        return ProjectEntity(
            id=row[0],
            type=row[1],
            name=row[2],
            source_path=row[3],
            properties=json.loads(row[4]),
            evidence_ids=json.loads(row[5]),
        )

    @staticmethod
    def _relation_from_row(row: tuple) -> ProjectRelation:
        return ProjectRelation(
            id=row[0],
            source_id=row[1],
            target_id=row[2],
            type=row[3],
            evidence_ids=json.loads(row[4]),
            properties=json.loads(row[5]),
        )


class KuzuGraphStore(BaseGraphStore):
    def __init__(self, path: Path | str):
        try:
            import kuzu  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("KuzuGraphStore requires the optional 'kuzu' package") from exc
        raise RuntimeError("KuzuGraphStore schema implementation is not enabled in Phase 1 execution")


class GraphStoreFactory:
    @staticmethod
    def create(provider: str, path: Path | str) -> BaseGraphStore:
        normalized = provider.lower()
        if normalized == "sqlite":
            return SQLiteGraphStore(path)
        if normalized == "kuzu":
            return KuzuGraphStore(path)
        raise ValueError(f"Unsupported graph store provider: {provider}")
```

- [ ] **Step 4: Run graph store tests**

Run:

```bash
pytest tests/unit/test_project_archive_graph_store.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/project_archive/graph_store.py tests/unit/test_project_archive_graph_store.py
git commit -m "feat: add project archive graph store"
```

## Task 4: Draft Archive Builder

**Files:**

- Create: `src/project_archive/archive_builder.py`
- Test: `tests/unit/test_project_archive_builder.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_project_archive_builder.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/unit/test_project_archive_builder.py -v
```

Expected: FAIL because `archive_builder.py` does not exist and `ProjectArchiveDraft` is not defined.

- [ ] **Step 3: Extend types with `ProjectArchiveDraft`**

Modify `src/project_archive/types.py` by adding this dataclass after `ProjectFile`:

```python
@dataclass(frozen=True)
class ProjectArchiveDraft:
    project_id: str
    halls: List[ArchiveHall] = field(default_factory=list)
    entities: List[ProjectEntity] = field(default_factory=list)
    relations: List[ProjectRelation] = field(default_factory=list)
    evidence_cards: List[EvidenceCard] = field(default_factory=list)
    confirmation_items: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectArchiveDraft":
        return cls(
            project_id=data["project_id"],
            halls=[ArchiveHall.from_dict(item) for item in data.get("halls", [])],
            entities=[ProjectEntity.from_dict(item) for item in data.get("entities", [])],
            relations=[ProjectRelation.from_dict(item) for item in data.get("relations", [])],
            evidence_cards=[
                EvidenceCard.from_dict(item) for item in data.get("evidence_cards", [])
            ],
            confirmation_items=list(data.get("confirmation_items", [])),
        )
```

Also update `src/project_archive/__init__.py` exports to include `ProjectArchiveDraft`.

- [ ] **Step 4: Implement archive builder**

Create `src/project_archive/archive_builder.py`:

```python
"""Draft archive builder for TwinMind Archive."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from src.project_archive.adapters import ConfigAdapter, GenericAdapter, MarkdownAdapter, PythonAdapter
from src.project_archive.adapters.base import AdapterExtraction, BaseLanguageAdapter
from src.project_archive.graph_store import BaseGraphStore
from src.project_archive.scanner import ProjectScanner
from src.project_archive.types import (
    ArchiveHall,
    EvidenceCard,
    ProjectArchiveDraft,
    ProjectEntity,
    ProjectRelation,
)


class ArchiveBuilder:
    def __init__(self, graph_store: BaseGraphStore):
        self.graph_store = graph_store
        self.adapters: Dict[str, BaseLanguageAdapter] = {
            "python": PythonAdapter(),
            "markdown": MarkdownAdapter(),
            "yaml": ConfigAdapter(),
            "toml": ConfigAdapter(),
            "json": ConfigAdapter(),
        }
        self.generic_adapter = GenericAdapter()

    def build(self, project_root: Path | str, project_id: str) -> ProjectArchiveDraft:
        files = ProjectScanner(project_root).scan()
        entities: List[ProjectEntity] = []
        relations: List[ProjectRelation] = []
        evidence_cards: List[EvidenceCard] = []

        for project_file in files:
            extraction = self._extract(project_file.language, project_file)
            entities.extend(extraction.entities)
            relations.extend(extraction.relations)
            evidence_cards.extend(extraction.evidence_cards)

        halls = self._build_halls(entities)
        confirmation_items = self._confirmation_items(entities, relations)

        self.graph_store.upsert_entities(entities)
        self.graph_store.upsert_relations(relations)
        self.graph_store.upsert_evidence(evidence_cards)

        return ProjectArchiveDraft(
            project_id=project_id,
            halls=halls,
            entities=entities,
            relations=relations,
            evidence_cards=evidence_cards,
            confirmation_items=confirmation_items,
        )

    def _extract(self, language: str, project_file) -> AdapterExtraction:
        adapter = self.adapters.get(language, self.generic_adapter)
        try:
            return adapter.extract(project_file)
        except Exception:
            return self.generic_adapter.extract(project_file)

    @staticmethod
    def _build_halls(entities: List[ProjectEntity]) -> List[ArchiveHall]:
        code_ids = [entity.id for entity in entities if entity.type in {"File", "Class", "Function"}]
        config_ids = [entity.id for entity in entities if entity.type == "Config"]
        concept_ids = [entity.id for entity in entities if entity.type == "Concept"]
        import_ids = [entity.id for entity in entities if entity.type == "Import"]
        return [
            ArchiveHall(
                id="hall_architecture",
                name="Architecture Hall",
                description="Files, classes, functions, and entry points.",
                entity_ids=code_ids,
            ),
            ArchiveHall(
                id="hall_retrieval",
                name="Retrieval Hall",
                description="Search and retrieval concepts discovered from docs and code.",
                entity_ids=[entity.id for entity in entities if "retriev" in entity.name.lower()],
            ),
            ArchiveHall(
                id="hall_config",
                name="Configuration Hall",
                description="Project configuration keys and provider settings.",
                entity_ids=config_ids,
            ),
            ArchiveHall(
                id="hall_concepts",
                name="Concept Hall",
                description="Documentation headings and project concepts.",
                entity_ids=concept_ids,
            ),
            ArchiveHall(
                id="hall_dependencies",
                name="Dependency Hall",
                description="Imports and external package touchpoints.",
                entity_ids=import_ids,
            ),
        ]

    @staticmethod
    def _confirmation_items(
        entities: List[ProjectEntity], relations: List[ProjectRelation]
    ) -> List[str]:
        return [
            f"Please review {len(entities)} extracted entities for duplicates.",
            f"Please review {len(relations)} extracted relations for false positives.",
            "Please review hall assignments before using the archive for risk audit.",
        ]
```

- [ ] **Step 5: Run builder and type tests**

Run:

```bash
pytest tests/unit/test_project_archive_types.py tests/unit/test_project_archive_builder.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/project_archive/types.py src/project_archive/__init__.py src/project_archive/archive_builder.py tests/unit/test_project_archive_types.py tests/unit/test_project_archive_builder.py
git commit -m "feat: build draft project archives"
```

## Task 5: Deterministic Agent Workflows

**Files:**

- Create: `src/project_archive/agents.py`
- Test: `tests/unit/test_project_archive_agents.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_project_archive_agents.py`:

```python
from src.project_archive.agents import AgentWorkflow
from src.project_archive.types import EvidenceCard, ProjectEntity, ProjectRelation, QueryMode


def _fixture_archive_parts():
    entities = [
        ProjectEntity(id="module_ingestion", type="Module", name="IngestionPipeline"),
        ProjectEntity(id="module_query", type="Module", name="QueryKnowledgeHubTool"),
        ProjectEntity(id="risk_main", type="Risk", name="main.py placeholder entry"),
    ]
    relations = [
        ProjectRelation(
            id="rel_impact",
            source_id="module_ingestion",
            target_id="module_query",
            type="AFFECTS",
            evidence_ids=["ev_pipeline"],
        )
    ]
    evidence = [
        EvidenceCard(
            id="ev_pipeline",
            source_type="code",
            source_path="src/ingestion/pipeline.py",
            title="Ingestion pipeline",
            snippet="class IngestionPipeline:",
        ),
        EvidenceCard(
            id="ev_main",
            source_type="code",
            source_path="main.py",
            title="Placeholder main",
            snippet="MCP Server will be implemented in Phase E.",
        ),
    ]
    return entities, relations, evidence


def test_impact_analysis_returns_affected_entities_and_evidence():
    entities, relations, evidence = _fixture_archive_parts()
    workflow = AgentWorkflow(entities=entities, relations=relations, evidence_cards=evidence)

    result = workflow.run(
        question="If I add a knowledge graph layer, which modules are affected?",
        mode=QueryMode.IMPACT_ANALYSIS,
    )

    assert result.mode == QueryMode.IMPACT_ANALYSIS
    assert "module_ingestion" in result.affected_entities
    assert "module_query" in result.affected_entities
    assert "ev_pipeline" in result.evidence_card_ids
    assert result.next_actions


def test_risk_audit_mentions_placeholder_entry_risk():
    entities, relations, evidence = _fixture_archive_parts()
    workflow = AgentWorkflow(entities=entities, relations=relations, evidence_cards=evidence)

    result = workflow.run(question="Does README match implementation?", mode=QueryMode.RISK_AUDIT)

    assert result.mode == QueryMode.RISK_AUDIT
    assert result.risks
    assert "ev_main" in result.evidence_card_ids
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/unit/test_project_archive_agents.py -v
```

Expected: FAIL because `agents.py` does not exist.

- [ ] **Step 3: Implement deterministic agents**

Create `src/project_archive/agents.py`:

```python
"""Deterministic agent workflows for TwinMind Archive MVP."""

from __future__ import annotations

from typing import List

from src.project_archive.types import AgentResult, EvidenceCard, GraphPath, ProjectEntity, ProjectRelation, QueryMode


class AgentWorkflow:
    def __init__(
        self,
        entities: List[ProjectEntity],
        relations: List[ProjectRelation],
        evidence_cards: List[EvidenceCard],
    ):
        self.entities = entities
        self.relations = relations
        self.evidence_cards = evidence_cards

    def run(self, question: str, mode: QueryMode) -> AgentResult:
        if mode == QueryMode.ARCHITECTURE_TOUR:
            return self._architecture_tour(question)
        if mode == QueryMode.IMPACT_ANALYSIS:
            return self._impact_analysis(question)
        if mode == QueryMode.RISK_AUDIT:
            return self._risk_audit(question)
        return self._evidence_qa(question)

    def _architecture_tour(self, question: str) -> AgentResult:
        file_and_module_ids = [
            entity.id for entity in self.entities if entity.type in {"File", "Module", "Class", "Function"}
        ][:12]
        evidence_ids = self._first_evidence_ids(limit=5)
        return AgentResult(
            mode=QueryMode.ARCHITECTURE_TOUR,
            question=question,
            summary="Architecture tour generated from files, classes, functions, and documentation evidence.",
            affected_entities=file_and_module_ids,
            evidence_card_ids=evidence_ids,
            next_actions=["Review the Architecture Hall and confirm core entry points."],
            confidence=0.75,
        )

    def _impact_analysis(self, question: str) -> AgentResult:
        related_relations = [
            relation for relation in self.relations if relation.type in {"AFFECTS", "DEFINES", "CONFIGURES"}
        ]
        affected = []
        paths = []
        evidence_ids = []
        for relation in related_relations[:8]:
            affected.extend([relation.source_id, relation.target_id])
            paths.append(
                GraphPath(
                    nodes=[relation.source_id, relation.target_id],
                    relations=[relation.type],
                    evidence_ids=relation.evidence_ids,
                )
            )
            evidence_ids.extend(relation.evidence_ids)
        if not evidence_ids:
            evidence_ids = self._first_evidence_ids(limit=3)
        return AgentResult(
            mode=QueryMode.IMPACT_ANALYSIS,
            question=question,
            summary="Impact analysis found the most relevant entities through graph relations and evidence cards.",
            affected_entities=sorted(set(affected)),
            graph_paths=paths,
            evidence_card_ids=sorted(set(evidence_ids)),
            risks=["Review graph extraction placement so it does not block existing ingestion or query paths."],
            next_actions=[
                "Add project archive extraction after file scanning.",
                "Expose graph paths in query responses.",
                "Add risk audit tests before changing MCP tool contracts.",
            ],
            confidence=0.78,
        )

    def _risk_audit(self, question: str) -> AgentResult:
        risky_evidence = [
            card for card in self.evidence_cards
            if "placeholder" in card.snippet.lower()
            or "will be implemented" in card.snippet.lower()
            or "phase" in card.snippet.lower()
        ]
        evidence_ids = [card.id for card in risky_evidence] or self._first_evidence_ids(limit=3)
        return AgentResult(
            mode=QueryMode.RISK_AUDIT,
            question=question,
            summary="Risk audit checked evidence for implementation gaps and documentation drift.",
            evidence_card_ids=evidence_ids,
            risks=["Some evidence suggests documentation or entry-point behavior may need review."],
            next_actions=["Compare documentation claims with actual executable entry points."],
            confidence=0.72,
        )

    def _evidence_qa(self, question: str) -> AgentResult:
        evidence_ids = self._first_evidence_ids(limit=5)
        return AgentResult(
            mode=QueryMode.EVIDENCE_QA,
            question=question,
            summary="Evidence Q&A response generated from the highest-priority evidence cards.",
            evidence_card_ids=evidence_ids,
            next_actions=["Open the linked evidence cards for source details."],
            confidence=0.7,
        )

    def _first_evidence_ids(self, limit: int) -> List[str]:
        return [card.id for card in self.evidence_cards[:limit]]
```

- [ ] **Step 4: Run agent tests**

Run:

```bash
pytest tests/unit/test_project_archive_agents.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/project_archive/agents.py tests/unit/test_project_archive_agents.py
git commit -m "feat: add TwinMind archive agent workflows"
```

## Task 6: Project Archive Service

**Files:**

- Create: `src/project_archive/service.py`
- Test: `tests/integration/test_project_archive_service.py`

- [ ] **Step 1: Write failing integration test**

Create `tests/integration/test_project_archive_service.py`:

```python
from pathlib import Path

from src.project_archive.service import ProjectArchiveService
from src.project_archive.types import QueryMode


FIXTURE = Path("tests/fixtures/project_archive_sample")


def test_service_ingests_and_queries_project_archive(tmp_path):
    service = ProjectArchiveService(storage_dir=tmp_path)

    draft = service.ingest_project(project_root=FIXTURE, project_id="sample")
    result = service.query_project(
        project_id="sample",
        question="What is the architecture?",
        mode=QueryMode.ARCHITECTURE_TOUR,
    )

    assert draft.project_id == "sample"
    assert draft.halls
    assert result.mode == QueryMode.ARCHITECTURE_TOUR
    assert result.evidence_card_ids


def test_service_rejects_unknown_project(tmp_path):
    service = ProjectArchiveService(storage_dir=tmp_path)

    try:
        service.query_project(
            project_id="missing",
            question="What is this?",
            mode=QueryMode.EVIDENCE_QA,
        )
    except ValueError as exc:
        assert "Project archive not found" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown project")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/integration/test_project_archive_service.py -v
```

Expected: FAIL because `service.py` does not exist.

- [ ] **Step 3: Implement service**

Create `src/project_archive/service.py`:

```python
"""Service layer for TwinMind Archive ingestion and querying."""

from __future__ import annotations

import json
from pathlib import Path

from src.project_archive.agents import AgentWorkflow
from src.project_archive.archive_builder import ArchiveBuilder
from src.project_archive.graph_store import SQLiteGraphStore
from src.project_archive.types import AgentResult, ProjectArchiveDraft, QueryMode


class ProjectArchiveService:
    def __init__(self, storage_dir: Path | str = "data/project_archive"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def ingest_project(self, project_root: Path | str, project_id: str) -> ProjectArchiveDraft:
        graph_store = SQLiteGraphStore(self._graph_path(project_id))
        builder = ArchiveBuilder(graph_store=graph_store)
        draft = builder.build(project_root=project_root, project_id=project_id)
        self._draft_path(project_id).write_text(
            json.dumps(draft.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return draft

    def query_project(self, project_id: str, question: str, mode: QueryMode) -> AgentResult:
        draft = self.load_draft(project_id)
        workflow = AgentWorkflow(
            entities=draft.entities,
            relations=draft.relations,
            evidence_cards=draft.evidence_cards,
        )
        return workflow.run(question=question, mode=mode)

    def load_draft(self, project_id: str) -> ProjectArchiveDraft:
        path = self._draft_path(project_id)
        if not path.exists():
            raise ValueError(f"Project archive not found: {project_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProjectArchiveDraft.from_dict(data)

    def _project_dir(self, project_id: str) -> Path:
        safe = project_id.replace("/", "_").replace(" ", "_")
        path = self.storage_dir / safe
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _draft_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "draft_archive.json"

    def _graph_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "graph.sqlite"
```

- [ ] **Step 4: Run integration test**

Run:

```bash
pytest tests/integration/test_project_archive_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/project_archive/service.py tests/integration/test_project_archive_service.py
git commit -m "feat: add project archive service"
```

## Task 7: MCP Tools

**Files:**

- Create: `src/mcp_server/tools/ingest_project_archive.py`
- Create: `src/mcp_server/tools/query_project_twin.py`
- Modify: `src/mcp_server/protocol_handler.py`
- Test: `tests/unit/test_ingest_project_archive.py`
- Test: `tests/unit/test_query_project_twin.py`

- [ ] **Step 1: Write failing MCP tool tests**

Create `tests/unit/test_ingest_project_archive.py`:

```python
from pathlib import Path

import pytest

from src.mcp_server.tools.ingest_project_archive import IngestProjectArchiveTool


@pytest.mark.asyncio
async def test_ingest_project_archive_tool_returns_summary(tmp_path):
    project_root = Path("tests/fixtures/project_archive_sample")
    tool = IngestProjectArchiveTool(storage_dir=tmp_path)

    result = await tool.execute(project_path=str(project_root), project_id="sample")

    assert "sample" in result
    assert "halls" in result
    assert "entities" in result
```

Create `tests/unit/test_query_project_twin.py`:

```python
from pathlib import Path

import pytest

from src.mcp_server.tools.ingest_project_archive import IngestProjectArchiveTool
from src.mcp_server.tools.query_project_twin import QueryProjectTwinTool


@pytest.mark.asyncio
async def test_query_project_twin_tool_returns_agent_result(tmp_path):
    project_root = Path("tests/fixtures/project_archive_sample")
    ingest_tool = IngestProjectArchiveTool(storage_dir=tmp_path)
    query_tool = QueryProjectTwinTool(storage_dir=tmp_path)
    await ingest_tool.execute(project_path=str(project_root), project_id="sample")

    result = await query_tool.execute(
        project_id="sample",
        question="What is the architecture?",
        mode="architecture_tour",
    )

    assert "architecture_tour" in result
    assert "evidence" in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/unit/test_ingest_project_archive.py tests/unit/test_query_project_twin.py -v
```

Expected: FAIL because the tool modules do not exist.

- [ ] **Step 3: Implement `ingest_project_archive` tool**

Create `src/mcp_server/tools/ingest_project_archive.py`:

```python
"""MCP tool for ingesting a TwinMind project archive."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict

from src.project_archive.service import ProjectArchiveService


TOOL_NAME = "ingest_project_archive"
TOOL_DESCRIPTION = "Import a local project directory and build a TwinMind draft archive."
TOOL_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "project_path": {"type": "string", "description": "Local project directory path."},
        "project_id": {"type": "string", "description": "Stable project archive identifier."},
    },
    "required": ["project_path", "project_id"],
}


class IngestProjectArchiveTool:
    def __init__(self, storage_dir: str | Path = "data/project_archive"):
        self.service = ProjectArchiveService(storage_dir=storage_dir)

    async def execute(self, project_path: str, project_id: str) -> str:
        draft = await asyncio.to_thread(
            self.service.ingest_project,
            project_root=Path(project_path),
            project_id=project_id,
        )
        return (
            f"Project archive '{draft.project_id}' ingested: "
            f"{len(draft.halls)} halls, {len(draft.entities)} entities, "
            f"{len(draft.relations)} relations, {len(draft.evidence_cards)} evidence cards."
        )


_tool = IngestProjectArchiveTool()


async def handle_tool(project_path: str, project_id: str) -> str:
    return await _tool.execute(project_path=project_path, project_id=project_id)


def register_tool(protocol_handler) -> None:
    protocol_handler.register_tool(
        name=TOOL_NAME,
        description=TOOL_DESCRIPTION,
        input_schema=TOOL_INPUT_SCHEMA,
        handler=handle_tool,
    )
```

- [ ] **Step 4: Implement `query_project_twin` tool**

Create `src/mcp_server/tools/query_project_twin.py`:

```python
"""MCP tool for querying a TwinMind project archive."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict

from src.project_archive.service import ProjectArchiveService
from src.project_archive.types import QueryMode


TOOL_NAME = "query_project_twin"
TOOL_DESCRIPTION = "Query a TwinMind project archive with an agentic work mode."
TOOL_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "project_id": {"type": "string", "description": "Project archive identifier."},
        "question": {"type": "string", "description": "Question or change intent."},
        "mode": {
            "type": "string",
            "description": "architecture_tour, impact_analysis, risk_audit, or evidence_qa.",
            "default": "evidence_qa",
        },
    },
    "required": ["project_id", "question"],
}


class QueryProjectTwinTool:
    def __init__(self, storage_dir: str | Path = "data/project_archive"):
        self.service = ProjectArchiveService(storage_dir=storage_dir)

    async def execute(self, project_id: str, question: str, mode: str = "evidence_qa") -> str:
        query_mode = QueryMode(mode)
        result = await asyncio.to_thread(
            self.service.query_project,
            project_id=project_id,
            question=question,
            mode=query_mode,
        )
        return (
            f"Mode: {result.mode.value}\n"
            f"Summary: {result.summary}\n"
            f"Affected entities: {', '.join(result.affected_entities) or '(none)'}\n"
            f"Evidence cards: {', '.join(result.evidence_card_ids) or '(none)'}\n"
            f"Risks: {'; '.join(result.risks) or '(none)'}\n"
            f"Next actions: {'; '.join(result.next_actions) or '(none)'}"
        )


_tool = QueryProjectTwinTool()


async def handle_tool(project_id: str, question: str, mode: str = "evidence_qa") -> str:
    return await _tool.execute(project_id=project_id, question=question, mode=mode)


def register_tool(protocol_handler) -> None:
    protocol_handler.register_tool(
        name=TOOL_NAME,
        description=TOOL_DESCRIPTION,
        input_schema=TOOL_INPUT_SCHEMA,
        handler=handle_tool,
    )
```

- [ ] **Step 5: Register MCP tools**

Modify `_register_default_tools()` in `src/mcp_server/protocol_handler.py` by appending:

```python
    # Import and register TwinMind Archive tools
    from src.mcp_server.tools.ingest_project_archive import register_tool as register_ingest_archive_tool
    register_ingest_archive_tool(protocol_handler)

    from src.mcp_server.tools.query_project_twin import register_tool as register_query_project_twin_tool
    register_query_project_twin_tool(protocol_handler)
```

- [ ] **Step 6: Run MCP tests**

Run:

```bash
pytest tests/unit/test_ingest_project_archive.py tests/unit/test_query_project_twin.py tests/unit/test_protocol_handler.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/mcp_server/tools/ingest_project_archive.py src/mcp_server/tools/query_project_twin.py src/mcp_server/protocol_handler.py tests/unit/test_ingest_project_archive.py tests/unit/test_query_project_twin.py
git commit -m "feat: expose TwinMind archive MCP tools"
```

## Task 8: Streamlit Dashboard Page

**Files:**

- Create: `src/observability/dashboard/pages/twinmind_archive.py`
- Modify: `src/observability/dashboard/app.py`
- Test: `tests/unit/test_twinmind_archive_dashboard.py`

- [ ] **Step 1: Write failing import/render test**

Create `tests/unit/test_twinmind_archive_dashboard.py`:

```python
from unittest.mock import MagicMock, patch


def test_twinmind_archive_page_imports_and_renders_without_project():
    import src.observability.dashboard.pages.twinmind_archive as page

    with patch.object(page, "st") as fake_st:
        fake_st.text_input.return_value = ""
        fake_st.selectbox.return_value = "evidence_qa"
        fake_st.button.return_value = False
        fake_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]

        page.render()

    fake_st.title.assert_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/unit/test_twinmind_archive_dashboard.py -v
```

Expected: FAIL because the page module does not exist.

- [ ] **Step 3: Implement Streamlit page**

Create `src/observability/dashboard/pages/twinmind_archive.py`:

```python
"""TwinMind Archive dashboard page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.project_archive.service import ProjectArchiveService
from src.project_archive.types import QueryMode


def render() -> None:
    st.title("TwinMind Archive")
    st.caption("Project knowledge digital twin: archive halls, evidence cards, graph paths, and agent traces.")

    service = ProjectArchiveService()

    st.subheader("Import Project")
    project_id = st.text_input("Project ID", value="modular-rag-mcp-server")
    project_path = st.text_input("Project path", value=str(Path.cwd()))
    if st.button("Build Draft Archive") and project_id and project_path:
        draft = service.ingest_project(project_root=project_path, project_id=project_id)
        st.success(
            f"Built archive with {len(draft.halls)} halls, {len(draft.entities)} entities, "
            f"{len(draft.relations)} relations, and {len(draft.evidence_cards)} evidence cards."
        )
        if draft.confirmation_items:
            st.warning("Review needed before treating this graph as authoritative.")
            for item in draft.confirmation_items:
                st.write(f"- {item}")

    st.subheader("Query Archive")
    mode = st.selectbox(
        "Mode",
        options=[mode.value for mode in QueryMode],
        index=0,
    )
    question = st.text_input("Question", value="What is this project's core architecture?")
    if st.button("Run TwinMind Query") and project_id and question:
        try:
            result = service.query_project(
                project_id=project_id,
                question=question,
                mode=QueryMode(mode),
            )
        except ValueError as exc:
            st.error(str(exc))
            return

        left, center, right = st.columns([1, 1.4, 1])
        with left:
            st.markdown("### Agent Summary")
            st.write(result.summary)
            st.markdown("### Next Actions")
            for action in result.next_actions:
                st.write(f"- {action}")
        with center:
            st.markdown("### Graph Paths")
            if not result.graph_paths:
                st.info("No graph path returned for this query.")
            for path in result.graph_paths:
                st.code(" -> ".join(path.nodes))
        with right:
            st.markdown("### Evidence Cards")
            if not result.evidence_card_ids:
                st.info("No evidence cards returned.")
            for evidence_id in result.evidence_card_ids:
                st.write(f"- `{evidence_id}`")
            st.markdown("### Risks")
            for risk in result.risks:
                st.warning(risk)
```

- [ ] **Step 4: Register dashboard navigation page**

Modify `src/observability/dashboard/app.py` by adding:

```python
def _page_twinmind_archive() -> None:
    from src.observability.dashboard.pages.twinmind_archive import render
    render()
```

Then add this entry to `pages` before Evaluation Panel:

```python
    st.Page(_page_twinmind_archive, title="TwinMind Archive", icon="🗂️"),
```

- [ ] **Step 5: Run dashboard tests**

Run:

```bash
pytest tests/unit/test_twinmind_archive_dashboard.py tests/unit/test_dashboard_config.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/observability/dashboard/pages/twinmind_archive.py src/observability/dashboard/app.py tests/unit/test_twinmind_archive_dashboard.py
git commit -m "feat: add TwinMind archive dashboard page"
```

## Task 9: Enable Kuzu as the Preferred Graph Store

**Files:**

- Modify: `pyproject.toml`
- Modify: `src/project_archive/graph_store.py`
- Test: `tests/unit/test_project_archive_graph_store.py`

- [ ] **Step 1: Add Kuzu optional dependency**

Modify `pyproject.toml` by adding `kuzu` to a new optional dependency group:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "pytest-asyncio>=0.21",
    "pytest-mock>=3.14",
    "ruff>=0.1.0",
    "mypy>=1.0",
    "openai>=1.0",
]
graph = [
    "kuzu>=0.9.0",
]
```

If the existing `[project.optional-dependencies]` table already contains `dev`, preserve it and add only the `graph` key.

- [ ] **Step 2: Add Kuzu factory behavior tests**

Append to `tests/unit/test_project_archive_graph_store.py`:

```python
import importlib.util

import pytest

from src.project_archive.graph_store import KuzuGraphStore


def test_graph_store_factory_can_request_kuzu(tmp_path):
    if importlib.util.find_spec("kuzu") is None:
        pytest.skip("kuzu optional dependency is not installed")

    store = GraphStoreFactory.create(provider="kuzu", path=tmp_path / "graph.kuzu")

    assert isinstance(store, KuzuGraphStore)
```

- [ ] **Step 3: Implement Kuzu adapter behind the same interface**

Modify `KuzuGraphStore` in `src/project_archive/graph_store.py` so it creates a Kuzu database and stores JSON payloads in node and relation tables:

```python
class KuzuGraphStore(BaseGraphStore):
    def __init__(self, path: Path | str):
        try:
            import kuzu
        except ImportError as exc:
            raise RuntimeError("KuzuGraphStore requires the optional 'kuzu' package") from exc
        self.kuzu = kuzu
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = kuzu.Database(str(self.path))
        self.conn = kuzu.Connection(self.db)
        self._init_schema()

    def upsert_entities(self, entities: Iterable[ProjectEntity]) -> None:
        for entity in entities:
            payload = json.dumps(entity.to_dict(), ensure_ascii=False)
            self.conn.execute(
                "MERGE (e:Entity {id: $id}) SET e.type = $type, e.name = $name, e.payload_json = $payload",
                {"id": entity.id, "type": entity.type, "name": entity.name, "payload": payload},
            )

    def upsert_relations(self, relations: Iterable[ProjectRelation]) -> None:
        for relation in relations:
            payload = json.dumps(relation.to_dict(), ensure_ascii=False)
            self.conn.execute(
                """
                MATCH (s:Entity {id: $source_id})
                MATCH (t:Entity {id: $target_id})
                MERGE (s)-[r:RELATED {id: $id}]->(t)
                SET r.type = $type, r.payload_json = $payload
                """,
                {
                    "id": relation.id,
                    "source_id": relation.source_id,
                    "target_id": relation.target_id,
                    "type": relation.type,
                    "payload": payload,
                },
            )

    def upsert_evidence(self, evidence_cards: Iterable[EvidenceCard]) -> None:
        for card in evidence_cards:
            self.conn.execute(
                "MERGE (e:Evidence {id: $id}) SET e.payload_json = $payload",
                {"id": card.id, "payload": json.dumps(card.to_dict(), ensure_ascii=False)},
            )

    def get_entity(self, entity_id: str) -> Optional[ProjectEntity]:
        rows = self._rows(
            self.conn.execute("MATCH (e:Entity {id: $id}) RETURN e.payload_json", {"id": entity_id})
        )
        if not rows:
            return None
        return ProjectEntity.from_dict(json.loads(rows[0][0]))

    def list_entities(self, type: Optional[str] = None) -> List[ProjectEntity]:
        if type is None:
            result = self.conn.execute("MATCH (e:Entity) RETURN e.payload_json ORDER BY e.id")
        else:
            result = self.conn.execute(
                "MATCH (e:Entity) WHERE e.type = $type RETURN e.payload_json ORDER BY e.id",
                {"type": type},
            )
        return [ProjectEntity.from_dict(json.loads(row[0])) for row in self._rows(result)]

    def list_relations(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        type: Optional[str] = None,
    ) -> List[ProjectRelation]:
        relations = [
            ProjectRelation.from_dict(json.loads(row[0]))
            for row in self._rows(self.conn.execute("MATCH ()-[r:RELATED]->() RETURN r.payload_json ORDER BY r.id"))
        ]
        if source_id is not None:
            relations = [relation for relation in relations if relation.source_id == source_id]
        if target_id is not None:
            relations = [relation for relation in relations if relation.target_id == target_id]
        if type is not None:
            relations = [relation for relation in relations if relation.type == type]
        return relations

    def list_evidence(self) -> List[EvidenceCard]:
        rows = self._rows(self.conn.execute("MATCH (e:Evidence) RETURN e.payload_json ORDER BY e.id"))
        return [EvidenceCard.from_dict(json.loads(row[0])) for row in rows]

    def find_paths(self, source_name: str, target_name: str) -> List[GraphPath]:
        entities = self.list_entities()
        by_name = {entity.name.lower(): entity for entity in entities}
        source = by_name.get(source_name.lower())
        target = by_name.get(target_name.lower())
        if source is None or target is None:
            return []
        return [
            GraphPath(
                nodes=[relation.source_id, relation.target_id],
                relations=[relation.type],
                evidence_ids=relation.evidence_ids,
            )
            for relation in self.list_relations(source_id=source.id, target_id=target.id)
        ]

    def _init_schema(self) -> None:
        self.conn.execute("CREATE NODE TABLE IF NOT EXISTS Entity(id STRING, type STRING, name STRING, payload_json STRING, PRIMARY KEY(id))")
        self.conn.execute("CREATE NODE TABLE IF NOT EXISTS Evidence(id STRING, payload_json STRING, PRIMARY KEY(id))")
        self.conn.execute("CREATE REL TABLE IF NOT EXISTS RELATED(FROM Entity TO Entity, id STRING, type STRING, payload_json STRING)")

    @staticmethod
    def _rows(result) -> list:
        rows = []
        while result.has_next():
            rows.append(result.get_next())
        return rows
```

If the installed Kuzu version does not support parameter dictionaries or `MERGE`, adjust only the query calls while keeping the public `BaseGraphStore` behavior and tests unchanged.

- [ ] **Step 4: Run graph store tests without Kuzu installed**

Run:

```bash
pytest tests/unit/test_project_archive_graph_store.py -v
```

Expected: PASS with the Kuzu-specific test skipped when `kuzu` is not installed.

- [ ] **Step 5: Run graph store tests with Kuzu installed**

Run:

```bash
python -m pip install ".[graph]"
pytest tests/unit/test_project_archive_graph_store.py -v
```

Expected: PASS, including `test_graph_store_factory_can_request_kuzu`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/project_archive/graph_store.py tests/unit/test_project_archive_graph_store.py
git commit -m "feat: add optional Kuzu graph store"
```

## Task 10: End-to-End MVP Validation

**Files:**

- Test: existing tests plus new project archive tests.
- No new production files expected.

- [ ] **Step 1: Run focused project archive test suite**

Run:

```bash
pytest \
  tests/unit/test_project_archive_types.py \
  tests/unit/test_project_archive_scanner.py \
  tests/unit/test_project_archive_adapters.py \
  tests/unit/test_project_archive_graph_store.py \
  tests/unit/test_project_archive_builder.py \
  tests/unit/test_project_archive_agents.py \
  tests/integration/test_project_archive_service.py \
  tests/unit/test_ingest_project_archive.py \
  tests/unit/test_query_project_twin.py \
  tests/unit/test_twinmind_archive_dashboard.py \
  -v
```

Expected: PASS.

- [ ] **Step 2: Run existing smoke and protocol tests**

Run:

```bash
pytest tests/unit/test_smoke_imports.py tests/unit/test_protocol_handler.py tests/unit/test_dashboard_config.py -v
```

Expected: PASS.

- [ ] **Step 3: Manually ingest the cloned project using service code**

Run:

```bash
python - <<'PY'
from pathlib import Path
from src.project_archive.service import ProjectArchiveService
from src.project_archive.types import QueryMode

service = ProjectArchiveService(storage_dir="data/project_archive_manual")
draft = service.ingest_project(Path("."), "modular-rag-mcp-server")
print("halls", len(draft.halls))
print("entities", len(draft.entities))
print("relations", len(draft.relations))
print("evidence", len(draft.evidence_cards))
result = service.query_project(
    project_id="modular-rag-mcp-server",
    question="If I add a knowledge graph layer, which modules are affected?",
    mode=QueryMode.IMPACT_ANALYSIS,
)
print(result.to_dict())
PY
```

Expected:

- Prints non-zero hall, entity, relation, and evidence counts.
- Prints an `impact_analysis` result with evidence card IDs.

- [ ] **Step 4: Commit validation notes if any docs changed**

If no files changed during validation, do not commit. If a small validation note is added to docs, commit it:

```bash
git add docs/superpowers/plans/2026-06-23-twinmind-archive-mvp.md
git commit -m "docs: record TwinMind MVP validation notes"
```

## Self-Review Checklist

- Spec coverage: This plan covers Phase 1 project import, archive generation, graph storage fallback, optional Kuzu graph backend, deterministic agents, MCP tools, dashboard page, and tests.
- Deferred by design: React, Three.js, Neo4j, autonomous agent loops, deep multi-language parsing, and multi-project universe remain in Future Enhancements.
- Type consistency: `EvidenceCard`, `ProjectEntity`, `ProjectRelation`, `ArchiveHall`, `GraphPath`, `ProjectFile`, `ProjectArchiveDraft`, `AgentResult`, and `QueryMode` are introduced before later tasks use them.
- Testability: Every production task has unit or integration tests and an explicit command.
- Commit cadence: Every task ends with a focused commit.
