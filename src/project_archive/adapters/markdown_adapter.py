"""Markdown heading extraction for project archives."""

from __future__ import annotations

import hashlib
import re

from src.project_archive.adapters.base import AdapterExtraction, BaseLanguageAdapter
from src.project_archive.types import EvidenceCard, ProjectEntity, ProjectFile, ProjectRelation

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


class MarkdownAdapter(BaseLanguageAdapter):
    language = "markdown"

    def extract(self, project_file: ProjectFile) -> AdapterExtraction:
        file_entity = ProjectEntity(
            id=project_file.id,
            type="File",
            name=project_file.path,
            source_path=project_file.path,
            properties={"language": project_file.language},
        )
        extraction = AdapterExtraction(entities=[file_entity])

        for line_number, line in enumerate(project_file.text.splitlines(), start=1):
            match = HEADING_RE.match(line)
            if not match:
                continue

            level = len(match.group(1))
            name = match.group(2).strip()
            entity_id = _stable_id("concept", project_file.path, name, str(line_number))
            evidence_id = _stable_id("ev", project_file.path, name, str(line_number))
            entity = ProjectEntity(
                id=entity_id,
                type="Concept",
                name=name,
                source_path=project_file.path,
                properties={"heading_level": level},
                evidence_ids=[evidence_id],
            )
            extraction.entities.append(entity)
            extraction.relations.append(
                ProjectRelation(
                    id=_stable_id("rel", project_file.id, entity.id, "MENTIONS"),
                    source_id=project_file.id,
                    target_id=entity.id,
                    type="MENTIONS",
                    evidence_ids=[evidence_id],
                )
            )
            extraction.evidence_cards.append(
                EvidenceCard(
                    id=evidence_id,
                    source_type="markdown",
                    source_path=project_file.path,
                    title=f"Heading: {name}",
                    snippet=line,
                    line_start=line_number,
                    line_end=line_number,
                    linked_entities=[project_file.id, entity.id],
                )
            )

        return extraction


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1(":".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"
