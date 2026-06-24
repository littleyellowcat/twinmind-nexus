"""Pure graph explorer projections for TwinMind project archives."""

from __future__ import annotations

from collections import deque

from src.project_archive.types import (
    GraphExplorerNode,
    GraphExplorerRelation,
    GraphNeighborhood,
    GraphSummary,
    ProjectArchiveDraft,
    ProjectEntity,
    ProjectRelation,
    RecommendedGraphStart,
)


ENTRY_FILE_NAMES = {"main.py", "app.py", "server.py", "cli.py", "index.js", "index.ts"}
CONFIG_NAMES = {"llm", "retrieval", "vector_store", "embedding", "database", "agent"}
DOCUMENT_TYPE_NAMES = {"doc", "document", "markdown", "readme", "md", "rst"}


def build_graph_summary(draft: ProjectArchiveDraft) -> GraphSummary:
    """Build deterministic graph metrics and recommended starting points."""

    entity_by_id = {entity.id: entity for entity in draft.entities}
    hall_ids_by_entity = _hall_ids_by_entity(draft)
    degrees = _degrees(draft.relations, entity_by_id)
    starts: list[RecommendedGraphStart] = []

    for entity in draft.entities:
        degree = degrees.get(entity.id, 0)
        hall_ids = hall_ids_by_entity.get(entity.id, [])
        basename = _basename(entity.source_path or entity.name).lower()
        stem = _stem(basename)
        name = entity.name.lower()
        entity_type = entity.type.lower()

        if basename in ENTRY_FILE_NAMES:
            starts.append(
                RecommendedGraphStart(
                    entity_id=entity.id,
                    label=entity.name,
                    group="entry_file",
                    reason="Likely application entry point.",
                    score=100.0 + float(degree),
                    hall_ids=hall_ids,
                )
            )

        if degree > 0:
            starts.append(
                RecommendedGraphStart(
                    entity_id=entity.id,
                    label=entity.name,
                    group="high_degree",
                    reason=f"Connects to {degree} graph relation(s).",
                    score=90.0 + float(degree),
                    hall_ids=hall_ids,
                )
            )

        if (
            name in CONFIG_NAMES
            or stem in CONFIG_NAMES
            or "config" in entity_type
            or "setting" in entity_type
        ):
            starts.append(
                RecommendedGraphStart(
                    entity_id=entity.id,
                    label=entity.name,
                    group="config_hotspot",
                    reason="Configuration-like node that may explain runtime behavior.",
                    score=80.0 + float(degree),
                    hall_ids=hall_ids,
                )
            )

        if _is_document_entity(entity):
            starts.append(
                RecommendedGraphStart(
                    entity_id=entity.id,
                    label=entity.name,
                    group="document_center",
                    reason="Documentation node that may summarize project intent.",
                    score=70.0 + float(degree),
                    hall_ids=hall_ids,
                )
            )

    return GraphSummary(
        project_id=draft.project_id,
        metrics={
            "entities": len(draft.entities),
            "relations": len(draft.relations),
            "evidence": len(draft.evidence_cards),
        },
        recommended_starts=sorted(
            starts,
            key=lambda start: (
                -start.score,
                _start_group_order(start.group),
                start.label.lower(),
                start.entity_id,
            ),
        ),
    )


def build_graph_neighborhood(
    draft: ProjectArchiveDraft,
    hall_id: str | None,
    focus_entity_id: str | None,
    depth: int,
    relation_types: list[str],
    node_limit: int,
    relation_limit: int,
) -> GraphNeighborhood:
    """Build a hall-scoped or focus-scoped graph neighborhood."""

    safe_depth = max(1, min(3, int(depth)))
    safe_node_limit = max(0, int(node_limit))
    safe_relation_limit = max(0, int(relation_limit))
    entity_by_id = {entity.id: entity for entity in draft.entities}
    hall_by_id = {hall.id: hall for hall in draft.halls}
    hall_ids_by_entity = _hall_ids_by_entity(draft)
    relation_types_filter = {item.upper() for item in relation_types}
    candidate_relations = [
        relation
        for relation in draft.relations
        if relation.source_id in entity_by_id
        and relation.target_id in entity_by_id
        and (
            not relation_types_filter
            or relation.type.upper() in relation_types_filter
        )
    ]

    if hall_id is not None:
        hall = hall_by_id.get(hall_id)
        hall_entity_ids = set(hall.entity_ids) if hall else set()
        candidate_relations = [
            relation
            for relation in candidate_relations
            if (
                relation.source_id in hall_entity_ids
                or relation.target_id in hall_entity_ids
            )
        ]
        if not candidate_relations:
            return _sparse_neighborhood(
                draft=draft,
                hall_id=hall_id,
                focus_entity_id=focus_entity_id,
                depth=safe_depth,
                reason="No relations are visible for this hall.",
            )

    if focus_entity_id:
        selected_relation_ids, visible_node_ids = _focus_projection(
            candidate_relations=candidate_relations,
            focus_entity_id=focus_entity_id,
            depth=safe_depth,
        )
        selected_relations = [
            relation
            for relation in candidate_relations
            if relation.id in selected_relation_ids
        ]
        if focus_entity_id in entity_by_id:
            visible_node_ids.add(focus_entity_id)
    else:
        selected_relations = list(candidate_relations)
        visible_node_ids = {
            entity_id
            for relation in selected_relations
            for entity_id in (relation.source_id, relation.target_id)
        }

    if not selected_relations:
        nodes = []
        if focus_entity_id and focus_entity_id in entity_by_id:
            nodes = [
                _graph_node(
                    entity_by_id[focus_entity_id],
                    hall_ids_by_entity,
                    degree=0,
                )
            ]
        return GraphNeighborhood(
            project_id=draft.project_id,
            hall_id=hall_id,
            focus_entity_id=focus_entity_id,
            depth=safe_depth,
            nodes=nodes,
            relations=[],
            evidence_ids=_evidence_ids(nodes=nodes, relations=[]),
            is_sparse=True,
            sparse_reason=(
                "No relations are visible for this focus entity."
                if focus_entity_id
                else "No relations are visible for this graph."
            ),
        )

    visible_node_ids = _trim_nodes(
        node_ids=visible_node_ids,
        relations=selected_relations,
        entity_by_id=entity_by_id,
        node_limit=safe_node_limit,
    )
    selected_relations = [
        relation
        for relation in selected_relations
        if relation.source_id in visible_node_ids and relation.target_id in visible_node_ids
    ][:safe_relation_limit]
    final_degrees = _degrees(selected_relations, entity_by_id)
    nodes = [
        _graph_node(
            entity_by_id[entity_id],
            hall_ids_by_entity,
            degree=final_degrees.get(entity_id, 0),
        )
        for entity_id in sorted(
            visible_node_ids,
            key=lambda item: (
                -final_degrees.get(item, 0),
                entity_by_id[item].name.lower(),
                item,
            ),
        )
        if entity_id in entity_by_id and final_degrees.get(entity_id, 0) > 0
    ]
    relations = [
        _graph_relation(relation, draft)
        for relation in selected_relations
        if relation.source_id in {node.id for node in nodes}
        and relation.target_id in {node.id for node in nodes}
    ]

    return GraphNeighborhood(
        project_id=draft.project_id,
        hall_id=hall_id,
        focus_entity_id=focus_entity_id,
        depth=safe_depth,
        nodes=nodes,
        relations=relations,
        evidence_ids=_evidence_ids(nodes=nodes, relations=relations),
        is_sparse=not relations,
        sparse_reason=None if relations else "No relations are visible for this graph.",
    )


def _focus_projection(
    candidate_relations: list[ProjectRelation],
    focus_entity_id: str,
    depth: int,
) -> tuple[set[str], set[str]]:
    adjacency: dict[str, list[ProjectRelation]] = {}
    for relation in candidate_relations:
        adjacency.setdefault(relation.source_id, []).append(relation)
        adjacency.setdefault(relation.target_id, []).append(relation)

    distances = {focus_entity_id: 0}
    queue: deque[str] = deque([focus_entity_id])
    while queue:
        entity_id = queue.popleft()
        if distances[entity_id] >= depth:
            continue
        for relation in adjacency.get(entity_id, []):
            neighbor_id = (
                relation.target_id
                if relation.source_id == entity_id
                else relation.source_id
            )
            if neighbor_id not in distances:
                distances[neighbor_id] = distances[entity_id] + 1
                queue.append(neighbor_id)

    visible_node_ids = set(distances)
    selected_relation_ids = {
        relation.id
        for relation in candidate_relations
        if relation.source_id in visible_node_ids
        and relation.target_id in visible_node_ids
        and max(distances[relation.source_id], distances[relation.target_id]) <= depth
    }
    return selected_relation_ids, visible_node_ids


def _trim_nodes(
    node_ids: set[str],
    relations: list[ProjectRelation],
    entity_by_id: dict[str, ProjectEntity],
    node_limit: int,
) -> set[str]:
    if node_limit <= 0:
        return set()
    degrees = _degrees(relations, entity_by_id)
    return set(
        sorted(
            node_ids,
            key=lambda item: (
                -degrees.get(item, 0),
                entity_by_id[item].name.lower(),
                item,
            ),
        )[:node_limit]
    )


def _graph_node(
    entity: ProjectEntity,
    hall_ids_by_entity: dict[str, list[str]],
    degree: int,
) -> GraphExplorerNode:
    return GraphExplorerNode(
        id=entity.id,
        label=entity.name,
        type=entity.type,
        hall_ids=hall_ids_by_entity.get(entity.id, []),
        source_path=entity.source_path,
        evidence_ids=list(entity.evidence_ids),
        degree=degree,
        importance=float(degree),
        tags=[],
    )


def _graph_relation(
    relation: ProjectRelation,
    draft: ProjectArchiveDraft,
) -> GraphExplorerRelation:
    return GraphExplorerRelation(
        id=relation.id,
        source_id=relation.source_id,
        target_id=relation.target_id,
        type=relation.type,
        evidence_ids=list(relation.evidence_ids),
        hall_ids=_relation_hall_ids(relation, draft),
        weight=max(1.0, float(len(relation.evidence_ids))),
    )


def _sparse_neighborhood(
    draft: ProjectArchiveDraft,
    hall_id: str | None,
    focus_entity_id: str | None,
    depth: int,
    reason: str,
) -> GraphNeighborhood:
    return GraphNeighborhood(
        project_id=draft.project_id,
        hall_id=hall_id,
        focus_entity_id=focus_entity_id,
        depth=depth,
        nodes=[],
        relations=[],
        evidence_ids=[],
        is_sparse=True,
        sparse_reason=reason,
    )


def _degrees(
    relations: list[ProjectRelation],
    entity_by_id: dict[str, ProjectEntity],
) -> dict[str, int]:
    degrees = {entity_id: 0 for entity_id in entity_by_id}
    for relation in relations:
        if relation.source_id in degrees:
            degrees[relation.source_id] += 1
        if relation.target_id in degrees:
            degrees[relation.target_id] += 1
    return degrees


def _hall_ids_by_entity(draft: ProjectArchiveDraft) -> dict[str, list[str]]:
    hall_ids_by_entity: dict[str, list[str]] = {}
    for hall in draft.halls:
        for entity_id in hall.entity_ids:
            hall_ids_by_entity.setdefault(entity_id, []).append(hall.id)
    return {
        entity_id: sorted(hall_ids)
        for entity_id, hall_ids in hall_ids_by_entity.items()
    }


def _relation_hall_ids(
    relation: ProjectRelation,
    draft: ProjectArchiveDraft,
) -> list[str]:
    hall_ids = [
        hall.id
        for hall in draft.halls
        if relation.source_id in hall.entity_ids or relation.target_id in hall.entity_ids
    ]
    return sorted(hall_ids)


def _evidence_ids(
    nodes: list[GraphExplorerNode],
    relations: list[GraphExplorerRelation],
) -> list[str]:
    evidence_ids: list[str] = []
    for node in nodes:
        evidence_ids.extend(node.evidence_ids)
    for relation in relations:
        evidence_ids.extend(relation.evidence_ids)
    return _ordered_unique(evidence_ids)


def _ordered_unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _start_group_order(group: str) -> int:
    return {
        "entry_file": 0,
        "high_degree": 1,
        "config_hotspot": 2,
        "document_center": 3,
    }.get(group, 99)


def _is_document_entity(entity: ProjectEntity) -> bool:
    entity_type = entity.type.lower()
    basename = _basename(entity.source_path or entity.name).lower()
    stem = _stem(basename)
    return (
        any(document_type in entity_type for document_type in DOCUMENT_TYPE_NAMES)
        or basename.endswith((".md", ".rst", ".txt"))
        or stem in DOCUMENT_TYPE_NAMES
    )


def _basename(path: str) -> str:
    return path.replace("\\", "/").rstrip("/").split("/")[-1]


def _stem(filename: str) -> str:
    return filename.rsplit(".", 1)[0] if "." in filename else filename
