"""Build draft project archives from scanned source files."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol, TypeVar

from src.project_archive.adapters import (
    BaseLanguageAdapter,
    ConfigAdapter,
    GenericAdapter,
    MarkdownAdapter,
    PythonAdapter,
    TreeSitterCodeAdapter,
)
from src.project_archive.graph_store import BaseGraphStore
from src.project_archive.scanner import SCAN_PROFILE_ARCHITECTURE, scanner_for_profile
from src.project_archive.semantic_enhancer import enhance_semantic_graph
from src.project_archive.types import (
    ArchiveHall,
    EvidenceCard,
    ProjectArchiveDraft,
    ProjectEntity,
    ProjectRelation,
)


class _HasId(Protocol):
    id: str


ArchiveItem = TypeVar("ArchiveItem", bound=_HasId)


class ArchiveBuilder:
    """Create a draft archive and persist extracted graph objects."""

    def __init__(self, graph_store: BaseGraphStore) -> None:
        self.graph_store = graph_store
        self.generic_adapter = GenericAdapter()
        self.adapters: dict[str, BaseLanguageAdapter] = {
            "python": PythonAdapter(),
            "markdown": MarkdownAdapter(),
            "yaml": ConfigAdapter(),
            "toml": ConfigAdapter(),
            "json": ConfigAdapter(),
            "java": TreeSitterCodeAdapter("java"),
            "cpp": TreeSitterCodeAdapter("cpp"),
            "typescript": TreeSitterCodeAdapter("typescript"),
            "javascript": TreeSitterCodeAdapter("javascript"),
            "go": TreeSitterCodeAdapter("go"),
            "rust": TreeSitterCodeAdapter("rust"),
            "generic": self.generic_adapter,
        }

    def build(
        self,
        project_root: Path | str,
        project_id: str,
        scan_profile: str = SCAN_PROFILE_ARCHITECTURE,
    ) -> ProjectArchiveDraft:
        project_root_path = Path(project_root)
        scanner = scanner_for_profile(project_root_path, scan_profile)
        files = scanner.scan()
        extraction_diagnostics = _empty_extraction_diagnostics()
        entities: list[ProjectEntity] = []
        relations: list[ProjectRelation] = []
        evidence_cards: list[EvidenceCard] = []

        for project_file in files:
            adapter = self.adapters.get(project_file.language, self.generic_adapter)
            before_entities = len(entities)
            before_relations = len(relations)
            before_evidence = len(evidence_cards)
            language_stats = extraction_diagnostics["languages"][project_file.language]
            language_stats["files"] += 1
            used_fallback = False
            if isinstance(adapter, TreeSitterCodeAdapter):
                extraction_diagnostics["tree_sitter"]["files"] += 1
                if getattr(adapter, "_parser", None) is None:
                    extraction_diagnostics["tree_sitter"]["unavailable"] += 1
            try:
                extraction = adapter.extract(project_file)
            except Exception as exc:
                used_fallback = True
                language_stats["fallbacks"] += 1
                extraction_diagnostics["fallbacks"] += 1
                if isinstance(adapter, TreeSitterCodeAdapter):
                    extraction_diagnostics["tree_sitter"]["fallbacks"] += 1
                if len(extraction_diagnostics["errors"]) < 20:
                    extraction_diagnostics["errors"].append(
                        {
                            "path": project_file.path,
                            "language": project_file.language,
                            "error": str(exc),
                        }
                    )
                extraction = self.generic_adapter.extract(project_file)

            entities.extend(extraction.entities)
            relations.extend(extraction.relations)
            evidence_cards.extend(extraction.evidence_cards)
            extracted_entities = len(entities) - before_entities
            extracted_relations = len(relations) - before_relations
            extracted_evidence = len(evidence_cards) - before_evidence
            language_stats["entities"] += extracted_entities
            language_stats["relations"] += extracted_relations
            language_stats["evidence"] += extracted_evidence
            if (
                isinstance(adapter, TreeSitterCodeAdapter)
                and getattr(adapter, "_parser", None) is not None
                and not used_fallback
            ):
                extraction_diagnostics["tree_sitter"]["parsed"] += 1

        entities = _unique_by_id(entities)
        relations = _unique_by_id(relations)
        evidence_cards = _unique_by_id(evidence_cards)
        entities, relations = enhance_semantic_graph(entities, relations, evidence_cards)
        entities = _unique_by_id(entities)
        relations = _unique_by_id(relations)
        halls = _build_halls(entities)
        confirmation_items = [
            f"Please review {len(entities)} extracted entities for duplicates.",
            f"Please review {len(relations)} extracted relations for false positives.",
            "Please review hall assignments before using the archive for risk audit.",
        ]

        self.graph_store.upsert_entities(entities)
        self.graph_store.upsert_relations(relations)
        self.graph_store.upsert_evidence(evidence_cards)

        return ProjectArchiveDraft(
            project_id=project_id,
            halls=halls,
            entities=entities,
            relations=relations,
            evidence_cards=evidence_cards,
            confirmation_items=[
                f"Scan profile: {scan_profile}.",
                *confirmation_items,
            ],
            metadata={
                "ingestion": {
                    "scan_profile": scan_profile,
                    "upload": _load_upload_diagnostics(project_root_path),
                    "scan": scanner.diagnostics(),
                    "extraction": _finalize_extraction_diagnostics(extraction_diagnostics),
                    "graph": {
                        "entities": len(entities),
                        "relations": len(relations),
                        "evidence": len(evidence_cards),
                        "halls": len(halls),
                    },
                }
            },
        )


def _build_halls(entities: list[ProjectEntity]) -> list[ArchiveHall]:
    return [
        ArchiveHall(
            id="hall_architecture",
            name="Architecture Hall",
            description="Files, classes, and functions that define project structure.",
            entity_ids=_matching_entity_ids(
                entities,
                lambda entity: entity.type
                in {
                    "Class",
                    "EntryPoint",
                    "Enum",
                    "File",
                    "Function",
                    "Implementation",
                    "Interface",
                    "Method",
                    "Module",
                    "Namespace",
                    "ServiceBoundary",
                    "Struct",
                    "Trait",
                    "Type",
                    "TypeAlias",
                },
            ),
        ),
        ArchiveHall(
            id="hall_retrieval",
            name="Retrieval Hall",
            description="Entities related to retrieval behavior and configuration.",
            entity_ids=_matching_entity_ids(entities, _is_retrieval_entity),
        ),
        ArchiveHall(
            id="hall_config",
            name="Configuration Hall",
            description="Configuration keys and files extracted from project settings.",
            entity_ids=_matching_entity_ids(entities, _is_config_entity),
        ),
        ArchiveHall(
            id="hall_concepts",
            name="Concept Hall",
            description="Concepts and headings found in project documentation.",
            entity_ids=_matching_entity_ids(
                entities,
                lambda entity: entity.type in {"Concept", "Heading", "Document"},
            ),
        ),
        ArchiveHall(
            id="hall_dependencies",
            name="Dependency Hall",
            description="Imported dependencies referenced by source files.",
            entity_ids=_matching_entity_ids(entities, _is_dependency_entity),
        ),
    ]


def _matching_entity_ids(
    entities: Iterable[ProjectEntity], predicate: Callable[[ProjectEntity], bool]
) -> list[str]:
    return [entity.id for entity in entities if predicate(entity)]


def _entity_search_text(entity: ProjectEntity) -> str:
    parts = [entity.type, entity.name, entity.source_path or ""]
    parts.extend(str(value) for value in entity.properties.values())
    return " ".join(parts).lower()


def _is_retrieval_entity(entity: ProjectEntity) -> bool:
    keywords = {
        "rag",
        "retriev",
        "search",
        "query",
        "vector",
        "embedding",
        "embed",
        "bm25",
        "rank",
        "rerank",
        "index",
        "chroma",
        "milvus",
        "faiss",
        "llm",
    }
    text = _entity_search_text(entity)
    return any(keyword in text for keyword in keywords)


def _is_config_entity(entity: ProjectEntity) -> bool:
    if entity.type == "Config":
        return True
    path = (entity.source_path or entity.name).lower()
    config_names = {
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "pom.xml",
        "build.gradle",
        "settings.gradle",
        "cargo.toml",
        "go.mod",
        "dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
    }
    config_suffixes = (
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".ini",
        ".env",
        ".properties",
        ".xml",
    )
    return (
        Path(path).name in config_names
        or path.endswith(config_suffixes)
        or "/config/" in path
        or "settings" in Path(path).name
    )


def _is_dependency_entity(entity: ProjectEntity) -> bool:
    if entity.type in {"Import", "Dependency"}:
        return True
    path = (entity.source_path or entity.name).lower()
    dependency_files = {
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "requirements.txt",
        "poetry.lock",
        "pyproject.toml",
        "pom.xml",
        "build.gradle",
        "cargo.toml",
        "cargo.lock",
        "go.mod",
        "go.sum",
        "composer.json",
        "gemfile",
    }
    return Path(path).name in dependency_files


def _unique_by_id(items: Iterable[ArchiveItem]) -> list[ArchiveItem]:
    unique = {}
    for item in items:
        unique.setdefault(item.id, item)
    return list(unique.values())


def _empty_extraction_diagnostics() -> dict:
    return {
        "languages": defaultdict(Counter),
        "tree_sitter": {
            "files": 0,
            "parsed": 0,
            "unavailable": 0,
            "fallbacks": 0,
        },
        "fallbacks": 0,
        "errors": [],
    }


def _finalize_extraction_diagnostics(diagnostics: dict) -> dict:
    languages = diagnostics.get("languages", {})
    return {
        "languages": {
            language: dict(stats)
            for language, stats in sorted(languages.items())
        },
        "tree_sitter": dict(diagnostics.get("tree_sitter", {})),
        "fallbacks": int(diagnostics.get("fallbacks", 0)),
        "errors": list(diagnostics.get("errors", [])),
    }


def _load_upload_diagnostics(project_root: Path) -> dict:
    path = project_root / ".twinmind" / "upload_diagnostics.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}
