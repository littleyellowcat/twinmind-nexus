"""Deterministic bounded mission runner for TwinMind project archives."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from src.project_archive.graph_explorer import build_graph_summary
from src.project_archive.types import (
    AutonomousMission,
    MissionGraphOverlay,
    MissionTask,
    ProjectArchiveDraft,
    ProjectEntity,
    ProjectRelation,
)


ARCHITECTURE_GOAL = "understand_project_architecture"
CONFIG_NAMES = {"llm", "retrieval", "vector_store", "embedding"}


@dataclass(frozen=True)
class _TaskSpec:
    task_type: str
    agent: str
    title: str


TASK_SPECS = [
    _TaskSpec("find_entry_points", "cartographer", "Find project entry points"),
    _TaskSpec("identify_top_modules", "cartographer", "Identify top-level modules"),
    _TaskSpec("expand_configuration_chain", "detective", "Expand configuration chain"),
    _TaskSpec("trace_dependency_hubs", "detective", "Trace dependency and import hubs"),
    _TaskSpec(
        "find_model_and_retrieval_modules",
        "detective",
        "Find model and retrieval modules",
    ),
    _TaskSpec(
        "verify_architecture_evidence",
        "librarian",
        "Verify architecture evidence",
    ),
    _TaskSpec("check_architecture_risks", "skeptic", "Check architecture risks"),
    _TaskSpec("summarize_architecture", "curator", "Summarize architecture"),
    _TaskSpec("recommend_next_missions", "curator", "Recommend next missions"),
]


def run_architecture_mission(
    draft: ProjectArchiveDraft, *, max_steps: int = 12
) -> AutonomousMission:
    """Run a bounded architecture understanding mission over a project graph."""

    mission_id = str(uuid4())
    created_at = _utc_now()
    requested_max_steps = int(max_steps)

    if requested_max_steps <= 0:
        completed_at = _utc_now()
        return AutonomousMission(
            id=mission_id,
            project_id=draft.project_id,
            goal=ARCHITECTURE_GOAL,
            status="complete",
            max_steps=requested_max_steps,
            stop_reason="invalid_step_budget",
            created_at=created_at,
            completed_at=completed_at,
            tasks=[],
            graph_overlay=MissionGraphOverlay(
                mission_id=mission_id,
                annotations=[
                    {
                        "type": "no_tasks_run",
                        "reason": "max_steps must be greater than zero.",
                        "max_steps": requested_max_steps,
                    }
                ],
            ),
        )

    selected_specs = TASK_SPECS[:requested_max_steps]

    tasks: list[MissionTask] = []
    explored_node_ids: set[str] = set()
    explored_relation_ids: set[str] = set()
    risk_node_ids: set[str] = set()
    risk_relation_ids: set[str] = set()
    annotations: list[dict[str, object]] = []

    for index, spec in enumerate(selected_specs, start=1):
        task_created_at = _utc_now()
        entities = _entities_for_task(draft, spec.task_type)
        relations = _relations_for_entities(draft, [entity.id for entity in entities])
        entity_ids = [entity.id for entity in entities]
        relation_ids = [relation.id for relation in relations]
        evidence_ids = _evidence_ids(entities, relations)
        risks = _risks_for_task(draft, spec.task_type)
        completed_at = _utc_now()

        task = MissionTask(
            id=f"{mission_id}:task:{index}",
            mission_id=mission_id,
            status="complete",
            agent=spec.agent,
            task_type=spec.task_type,
            title=spec.title,
            input_entity_ids=entity_ids,
            input_relation_ids=relation_ids,
            evidence_ids=evidence_ids,
            findings=[
                {
                    "summary": f"{spec.title} explored {len(entity_ids)} entity node(s).",
                    "entity_ids": entity_ids,
                    "relation_ids": relation_ids,
                }
            ],
            risks=risks,
            confidence=0.78 if evidence_ids else 0.42,
            verifier_status="accepted" if evidence_ids else "uncertain",
            created_at=task_created_at,
            completed_at=completed_at,
        )
        tasks.append(task)

        explored_node_ids.update(entity_ids)
        explored_relation_ids.update(relation_ids)
        risk_node_ids.update(_risk_ids(risks, "node_ids"))
        risk_relation_ids.update(_risk_ids(risks, "relation_ids"))
        annotations.append(
            {
                "task_id": task.id,
                "title": spec.title,
                "entity_ids": entity_ids,
                "relation_ids": relation_ids,
                "risks": risks,
            }
        )

    stop_reason = (
        "max_steps_reached"
        if requested_max_steps < len(TASK_SPECS)
        else "architecture_tasks_complete"
    )
    completed_at = _utc_now()

    return AutonomousMission(
        id=mission_id,
        project_id=draft.project_id,
        goal=ARCHITECTURE_GOAL,
        status="complete",
        max_steps=requested_max_steps,
        stop_reason=stop_reason,
        created_at=created_at,
        completed_at=completed_at,
        tasks=tasks,
        graph_overlay=MissionGraphOverlay(
            mission_id=mission_id,
            explored_node_ids=sorted(explored_node_ids),
            explored_relation_ids=sorted(explored_relation_ids),
            risk_node_ids=sorted(risk_node_ids),
            risk_relation_ids=sorted(risk_relation_ids),
            annotations=annotations,
        ),
    )


def _entities_for_task(
    draft: ProjectArchiveDraft, task_type: str
) -> list[ProjectEntity]:
    entity_by_id = {entity.id: entity for entity in draft.entities}

    if task_type == "find_entry_points":
        summary = build_graph_summary(draft)
        entry_ids = [
            start.entity_id
            for start in summary.recommended_starts
            if start.group == "entry_file" and start.entity_id in entity_by_id
        ][:6]
        if entry_ids:
            return [entity_by_id[entity_id] for entity_id in entry_ids]
        return draft.entities[:3]

    if task_type == "expand_configuration_chain":
        return [
            entity
            for entity in draft.entities
            if entity.type.lower() == "config" or entity.name.lower() in CONFIG_NAMES
        ][:8]

    if task_type == "trace_dependency_hubs":
        relation_counts: Counter[str] = Counter()
        for relation in draft.relations:
            relation_counts[relation.source_id] += 1
            relation_counts[relation.target_id] += 1
        return [
            entity_by_id[entity_id]
            for entity_id, _count in relation_counts.most_common(8)
            if entity_id in entity_by_id
        ]

    return draft.entities[:8]


def _relations_for_entities(
    draft: ProjectArchiveDraft, entity_ids: list[str]
) -> list[ProjectRelation]:
    selected_ids = set(entity_ids)
    return [
        relation
        for relation in draft.relations
        if relation.source_id in selected_ids or relation.target_id in selected_ids
    ][:12]


def _evidence_ids(
    entities: list[ProjectEntity], relations: list[ProjectRelation]
) -> list[str]:
    evidence_ids = {
        evidence_id
        for entity in entities
        for evidence_id in entity.evidence_ids
    }
    evidence_ids.update(
        evidence_id
        for relation in relations
        for evidence_id in relation.evidence_ids
    )
    return sorted(evidence_ids)


def _risks_for_task(
    draft: ProjectArchiveDraft, task_type: str
) -> list[dict[str, object]]:
    if task_type != "check_architecture_risks" or len(draft.relations) >= 10:
        return []

    return [
        {
            "type": "sparse_relation_coverage",
            "severity": "medium",
            "message": "Architecture graph has sparse relation coverage.",
            "relation_count": len(draft.relations),
        }
    ]


def _risk_ids(risks: list[dict[str, object]], key: str) -> list[str]:
    ids: list[str] = []
    for risk in risks:
        values = risk.get(key, [])
        if isinstance(values, list):
            ids.extend(str(value) for value in values)
    return ids


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
