"""Generic text extraction fallback."""

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
            source_type="generic",
            source_path=project_file.path,
            title=project_file.path,
            snippet=project_file.text[:500],
            linked_entities=[entity.id],
        )
        return AdapterExtraction(entities=[entity], evidence_cards=[evidence])
