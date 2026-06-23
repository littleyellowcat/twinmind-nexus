"""Configuration file extraction for project archives."""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass
from typing import Any

import yaml

from src.project_archive.adapters.base import AdapterExtraction, BaseLanguageAdapter
from src.project_archive.types import EvidenceCard, ProjectEntity, ProjectFile, ProjectRelation


class ConfigAdapter(BaseLanguageAdapter):
    language = "config"

    def extract(self, project_file: ProjectFile) -> AdapterExtraction:
        file_entity = ProjectEntity(
            id=project_file.id,
            type="File",
            name=project_file.path,
            source_path=project_file.path,
            properties={"language": project_file.language},
        )
        extraction = AdapterExtraction(entities=[file_entity])
        parsed = _parse_config(project_file)

        if isinstance(parsed, ParseError):
            extraction.evidence_cards.append(
                EvidenceCard(
                    id=_stable_id("ev", project_file.path, "parse_error"),
                    source_type="config",
                    source_path=project_file.path,
                    title="Config parse error",
                    snippet=project_file.text[:500],
                    linked_entities=[project_file.id],
                    confidence=0.0,
                    metadata={"error": parsed.message},
                )
            )
            return extraction

        if not isinstance(parsed, dict):
            entity_id = _stable_id("config", project_file.path, "value")
            evidence_id = _stable_id("ev", project_file.path, "value")
            entity = ProjectEntity(
                id=entity_id,
                type="Config",
                name="value",
                source_path=project_file.path,
                properties={"language": project_file.language},
                evidence_ids=[evidence_id],
            )
            extraction.entities.append(entity)
            extraction.relations.append(
                ProjectRelation(
                    id=_stable_id("rel", project_file.id, entity.id, "CONFIGURES"),
                    source_id=project_file.id,
                    target_id=entity.id,
                    type="CONFIGURES",
                    evidence_ids=[evidence_id],
                )
            )
            extraction.evidence_cards.append(
                EvidenceCard(
                    id=evidence_id,
                    source_type="config",
                    source_path=project_file.path,
                    title="Config: value",
                    snippet=project_file.text[:500],
                    linked_entities=[project_file.id, entity.id],
                )
            )
            return extraction

        for key in parsed:
            name = str(key)
            entity_id = _stable_id("config", project_file.path, name)
            evidence_id = _stable_id("ev", project_file.path, name)
            entity = ProjectEntity(
                id=entity_id,
                type="Config",
                name=name,
                source_path=project_file.path,
                properties={"language": project_file.language},
                evidence_ids=[evidence_id],
            )
            extraction.entities.append(entity)
            extraction.relations.append(
                ProjectRelation(
                    id=_stable_id("rel", project_file.id, entity.id, "CONFIGURES"),
                    source_id=project_file.id,
                    target_id=entity.id,
                    type="CONFIGURES",
                    evidence_ids=[evidence_id],
                )
            )
            extraction.evidence_cards.append(
                EvidenceCard(
                    id=evidence_id,
                    source_type="config",
                    source_path=project_file.path,
                    title=f"Config: {name}",
                    snippet=_config_snippet(project_file.text, name),
                    linked_entities=[project_file.id, entity.id],
                )
            )

        return extraction


@dataclass(frozen=True)
class ParseError:
    message: str


def _parse_config(project_file: ProjectFile) -> Any:
    try:
        if project_file.language == "toml":
            return tomllib.loads(project_file.text)
        if project_file.language == "json":
            return json.loads(project_file.text)
        if project_file.language == "yaml":
            return yaml.safe_load(project_file.text)
    except (json.JSONDecodeError, tomllib.TOMLDecodeError, yaml.YAMLError) as error:
        return ParseError(message=str(error))
    return {}


def _config_snippet(text: str, key: str) -> str:
    for line in text.splitlines():
        if line.startswith(f"{key}:") or line.startswith(f"{key} ="):
            return line
    return text[:500]


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1(":".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"
