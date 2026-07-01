"""Semantic graph enrichment for project archives."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

from src.project_archive.types import EvidenceCard, ProjectEntity, ProjectRelation

ENTRY_FILE_NAMES = {
    "main.py",
    "main.java",
    "main.cpp",
    "main.cc",
    "main.go",
    "main.rs",
    "app.py",
    "server.py",
    "index.js",
    "index.ts",
    "index.tsx",
}
ENTRY_ENTITY_NAMES = {"main", "app", "server", "cli"}
SERVICE_BOUNDARY_KEYWORDS = {
    "service": "Service Boundary",
    "controller": "API Boundary",
    "handler": "API Boundary",
    "router": "Routing Boundary",
    "endpoint": "API Boundary",
    "repository": "Data Boundary",
    "dao": "Data Boundary",
    "store": "Data Boundary",
    "storage": "Data Boundary",
    "client": "Integration Boundary",
}
RAG_COMPONENT_KEYWORDS = {
    "rag": "RAG System",
    "retriev": "Retriever",
    "search": "Retriever",
    "vector": "Vector Store",
    "embedding": "Embedding",
    "embed": "Embedding",
    "bm25": "Sparse Retriever",
    "rerank": "Reranker",
    "llm": "LLM",
    "agent": "Agent",
    "chroma": "Vector Store",
    "faiss": "Vector Store",
    "milvus": "Vector Store",
}
CONFIG_DEPENDENCY_FILES = {
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


def enhance_semantic_graph(
    entities: list[ProjectEntity],
    relations: list[ProjectRelation],
    evidence_cards: list[EvidenceCard],
) -> tuple[list[ProjectEntity], list[ProjectRelation]]:
    """Add deterministic semantic entities and relations to a code graph."""

    entity_by_id = {entity.id: entity for entity in entities}
    extra_entities: dict[str, ProjectEntity] = {}
    extra_relations: dict[str, ProjectRelation] = {}
    evidence_by_path = _evidence_by_path(evidence_cards)

    for entity in entities:
        source_path = entity.source_path or entity.name
        if not source_path:
            continue

        if entity.type == "File":
            module_name = _module_name(source_path)
            if module_name:
                module = _module_entity(module_name)
                extra_entities.setdefault(module.id, module)
                _add_relation(
                    extra_relations,
                    entity.id,
                    module.id,
                    "BELONGS_TO_MODULE",
                    _evidence_ids_for_path(evidence_by_path, source_path),
                    {"source": "semantic_enhancer"},
                )

            if _is_config_dependency_file(source_path):
                manifest = _manifest_entity(Path(source_path).name)
                extra_entities.setdefault(manifest.id, manifest)
                _add_relation(
                    extra_relations,
                    entity.id,
                    manifest.id,
                    "CONFIGURES_DEPENDENCIES",
                    _evidence_ids_for_path(evidence_by_path, source_path),
                    {"source": "semantic_enhancer"},
                )

        if _is_entry_point(entity):
            entry = _entry_point_entity(entity)
            extra_entities.setdefault(entry.id, entry)
            _add_relation(
                extra_relations,
                entity.id,
                entry.id,
                "DECLARES_ENTRYPOINT",
                list(entity.evidence_ids),
                {"source": "semantic_enhancer"},
            )

        boundary_name = _service_boundary_name(entity)
        if boundary_name:
            boundary = _boundary_entity(boundary_name)
            extra_entities.setdefault(boundary.id, boundary)
            _add_relation(
                extra_relations,
                entity.id,
                boundary.id,
                "BELONGS_TO_BOUNDARY",
                list(entity.evidence_ids),
                {"source": "semantic_enhancer"},
            )

        rag_component = _rag_component_name(entity)
        if rag_component:
            component = _rag_component_entity(rag_component)
            extra_entities.setdefault(component.id, component)
            _add_relation(
                extra_relations,
                entity.id,
                component.id,
                "PARTICIPATES_IN_RAG",
                list(entity.evidence_ids),
                {"source": "semantic_enhancer"},
            )

    existing_relation_keys = {
        (relation.source_id, relation.target_id, relation.type) for relation in relations
    }
    valid_entity_ids = set(entity_by_id) | set(extra_entities)
    filtered_relations = [
        relation
        for relation in extra_relations.values()
        if (relation.source_id, relation.target_id, relation.type) not in existing_relation_keys
        and relation.source_id in valid_entity_ids
        and relation.target_id in valid_entity_ids
    ]
    return [*entities, *extra_entities.values()], [*relations, *filtered_relations]


def _module_name(source_path: str) -> str:
    parts = Path(source_path).parts
    if not parts:
        return ""
    if parts[0] in {"src", "app", "lib", "cmd", "internal", "pkg"} and len(parts) > 1:
        return "/".join(parts[:2]) if Path(parts[1]).suffix == "" else parts[0]
    return parts[0] if len(parts) > 1 else ""


def _is_entry_point(entity: ProjectEntity) -> bool:
    source_name = Path(entity.source_path or entity.name).name.lower()
    name = entity.name.lower()
    roles = entity.properties.get("semantic_roles", [])
    return (
        source_name in ENTRY_FILE_NAMES
        or name in ENTRY_ENTITY_NAMES
        or "entry_point" in roles
    )


def _service_boundary_name(entity: ProjectEntity) -> str:
    text = _entity_text(entity)
    for keyword, boundary_name in SERVICE_BOUNDARY_KEYWORDS.items():
        if keyword in text:
            return boundary_name
    roles = entity.properties.get("semantic_roles", [])
    if "service_boundary" in roles:
        return "Service Boundary"
    if "data_boundary" in roles:
        return "Data Boundary"
    return ""


def _rag_component_name(entity: ProjectEntity) -> str:
    text = _entity_text(entity)
    for keyword, component_name in RAG_COMPONENT_KEYWORDS.items():
        if keyword in text:
            return component_name
    roles = entity.properties.get("semantic_roles", [])
    if "rag_component" in roles:
        return "RAG System"
    return ""


def _entity_text(entity: ProjectEntity) -> str:
    values = [entity.type, entity.name, entity.source_path or ""]
    values.extend(str(value) for value in entity.properties.values())
    return " ".join(values).lower()


def _is_config_dependency_file(source_path: str) -> bool:
    return Path(source_path).name.lower() in CONFIG_DEPENDENCY_FILES


def _module_entity(module_name: str) -> ProjectEntity:
    return ProjectEntity(
        id=_stable_id("module", module_name),
        type="Module",
        name=module_name,
        properties={"source": "semantic_enhancer"},
    )


def _manifest_entity(name: str) -> ProjectEntity:
    return ProjectEntity(
        id=_stable_id("dependency_manifest", name.lower()),
        type="DependencyManifest",
        name=name,
        properties={"source": "semantic_enhancer"},
    )


def _entry_point_entity(entity: ProjectEntity) -> ProjectEntity:
    name = entity.source_path or entity.name
    return ProjectEntity(
        id=_stable_id("entry_point", entity.id),
        type="EntryPoint",
        name=name,
        source_path=entity.source_path,
        properties={"source": "semantic_enhancer"},
        evidence_ids=list(entity.evidence_ids),
    )


def _boundary_entity(name: str) -> ProjectEntity:
    return ProjectEntity(
        id=_stable_id("boundary", name),
        type="ServiceBoundary",
        name=name,
        properties={"source": "semantic_enhancer"},
    )


def _rag_component_entity(name: str) -> ProjectEntity:
    return ProjectEntity(
        id=_stable_id("rag_component", name),
        type="RAGComponent",
        name=name,
        properties={"source": "semantic_enhancer"},
    )


def _add_relation(
    relations: dict[str, ProjectRelation],
    source_id: str,
    target_id: str,
    relation_type: str,
    evidence_ids: list[str],
    properties: dict[str, str],
) -> None:
    relation_id = _stable_id("rel", source_id, target_id, relation_type)
    relations.setdefault(
        relation_id,
        ProjectRelation(
            id=relation_id,
            source_id=source_id,
            target_id=target_id,
            type=relation_type,
            evidence_ids=evidence_ids,
            properties=properties,
        ),
    )


def _evidence_by_path(evidence_cards: Iterable[EvidenceCard]) -> dict[str, list[str]]:
    by_path: dict[str, list[str]] = {}
    for card in evidence_cards:
        by_path.setdefault(card.source_path, []).append(card.id)
    return by_path


def _evidence_ids_for_path(evidence_by_path: dict[str, list[str]], source_path: str) -> list[str]:
    return evidence_by_path.get(source_path, [])[:3]


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1(":".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"
