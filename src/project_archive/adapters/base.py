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
