"""Build draft project archives from scanned source files."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Protocol, TypeVar

from src.project_archive.adapters import (
    BaseLanguageAdapter,
    ConfigAdapter,
    GenericAdapter,
    MarkdownAdapter,
    PythonAdapter,
)
from src.project_archive.graph_store import BaseGraphStore
from src.project_archive.scanner import ProjectScanner
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
            "generic": self.generic_adapter,
        }

    def build(self, project_root: Path | str, project_id: str) -> ProjectArchiveDraft:
        files = ProjectScanner(project_root).scan()
        entities: list[ProjectEntity] = []
        relations: list[ProjectRelation] = []
        evidence_cards: list[EvidenceCard] = []

        for project_file in files:
            adapter = self.adapters.get(project_file.language, self.generic_adapter)
            try:
                extraction = adapter.extract(project_file)
            except Exception:
                extraction = self.generic_adapter.extract(project_file)

            entities.extend(extraction.entities)
            relations.extend(extraction.relations)
            evidence_cards.extend(extraction.evidence_cards)

        entities = _unique_by_id(entities)
        relations = _unique_by_id(relations)
        evidence_cards = _unique_by_id(evidence_cards)
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
            confirmation_items=confirmation_items,
        )


def _build_halls(entities: list[ProjectEntity]) -> list[ArchiveHall]:
    return [
        ArchiveHall(
            id="hall_architecture",
            name="Architecture Hall",
            description="Files, classes, and functions that define project structure.",
            entity_ids=_entity_ids_by_type(entities, {"File", "Class", "Function"}),
        ),
        ArchiveHall(
            id="hall_retrieval",
            name="Retrieval Hall",
            description="Entities related to retrieval behavior and configuration.",
            entity_ids=[
                entity.id for entity in entities if "retriev" in entity.name.lower()
            ],
        ),
        ArchiveHall(
            id="hall_config",
            name="Configuration Hall",
            description="Configuration keys and files extracted from project settings.",
            entity_ids=_entity_ids_by_type(entities, {"Config"}),
        ),
        ArchiveHall(
            id="hall_concepts",
            name="Concept Hall",
            description="Concepts and headings found in project documentation.",
            entity_ids=_entity_ids_by_type(entities, {"Concept"}),
        ),
        ArchiveHall(
            id="hall_dependencies",
            name="Dependency Hall",
            description="Imported dependencies referenced by source files.",
            entity_ids=_entity_ids_by_type(entities, {"Import"}),
        ),
    ]


def _entity_ids_by_type(
    entities: Iterable[ProjectEntity], entity_types: set[str]
) -> list[str]:
    return [entity.id for entity in entities if entity.type in entity_types]


def _unique_by_id(items: Iterable[ArchiveItem]) -> list[ArchiveItem]:
    unique = {}
    for item in items:
        unique.setdefault(item.id, item)
    return list(unique.values())
