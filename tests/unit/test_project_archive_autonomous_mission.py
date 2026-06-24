"""Tests for bounded autonomous GraphRAG missions."""

from __future__ import annotations

from tests.unit.test_project_archive_graph_explorer import _draft

from src.project_archive.autonomous_mission import TASK_SPECS, run_architecture_mission
from src.project_archive.types import ProjectArchiveDraft, ProjectEntity, ProjectRelation


def test_architecture_mission_runs_bounded_task_queue() -> None:
    mission = run_architecture_mission(_draft(), max_steps=4)

    assert mission.project_id == "demo"
    assert mission.goal == "understand_project_architecture"
    assert mission.status == "complete"
    assert len(mission.tasks) <= 4
    assert mission.tasks[0].task_type == "find_entry_points"
    assert mission.tasks[0].evidence_ids
    assert mission.graph_overlay.explored_node_ids


def test_architecture_mission_records_verifier_results() -> None:
    mission = run_architecture_mission(_draft(), max_steps=3)

    assert all(task.verifier_status in {"accepted", "uncertain"} for task in mission.tasks)
    assert all(task.confidence >= 0 for task in mission.tasks)


def test_architecture_mission_respects_max_steps() -> None:
    mission = run_architecture_mission(_draft(), max_steps=2)

    assert len(mission.tasks) == 2
    assert mission.stop_reason == "max_steps_reached"


def test_architecture_mission_records_zero_step_budget() -> None:
    mission = run_architecture_mission(_draft(), max_steps=0)

    assert mission.max_steps == 0
    assert mission.tasks == []
    assert mission.status == "complete"
    assert mission.stop_reason == "invalid_step_budget"
    assert mission.graph_overlay is not None
    assert mission.graph_overlay.explored_node_ids == []
    assert mission.graph_overlay.explored_relation_ids == []
    assert mission.graph_overlay.risk_node_ids == []
    assert mission.graph_overlay.risk_relation_ids == []
    assert mission.graph_overlay.annotations[0]["type"] == "no_tasks_run"


def test_architecture_mission_records_negative_step_budget() -> None:
    mission = run_architecture_mission(_draft(), max_steps=-3)

    assert mission.max_steps == -3
    assert mission.tasks == []
    assert mission.stop_reason == "invalid_step_budget"
    assert mission.graph_overlay is not None
    assert mission.graph_overlay.annotations[0]["max_steps"] == -3


def test_architecture_mission_bounds_large_step_budget_to_task_specs() -> None:
    mission = run_architecture_mission(_draft(), max_steps=99)

    assert mission.max_steps == 99
    assert len(mission.tasks) == len(TASK_SPECS)
    assert len(mission.tasks) == 9
    assert mission.stop_reason == "architecture_tasks_complete"


def test_architecture_mission_keeps_graph_level_risks_in_annotations() -> None:
    mission = run_architecture_mission(_draft(), max_steps=7)

    assert mission.graph_overlay is not None
    assert mission.graph_overlay.risk_node_ids == []
    assert mission.graph_overlay.risk_relation_ids == []
    assert any(
        risk["type"] == "sparse_relation_coverage"
        for annotation in mission.graph_overlay.annotations
        for risk in annotation.get("risks", [])
    )


def test_architecture_mission_caps_recommended_entry_points() -> None:
    draft = ProjectArchiveDraft(
        project_id="demo",
        entities=[
            ProjectEntity(
                id=f"file:entry:{index}",
                type="File",
                name="app.py",
                source_path="app.py",
            )
            for index in range(7)
        ],
    )

    mission = run_architecture_mission(draft, max_steps=1)

    assert len(mission.tasks[0].input_entity_ids) == 6


def test_architecture_mission_caps_configuration_chain_entities() -> None:
    draft = ProjectArchiveDraft(
        project_id="demo",
        entities=[
            ProjectEntity(
                id=f"config:{index}",
                type="Config",
                name=f"config_{index}",
            )
            for index in range(10)
        ],
    )

    mission = run_architecture_mission(draft, max_steps=3)
    config_task = mission.tasks[2]

    assert config_task.task_type == "expand_configuration_chain"
    assert config_task.input_entity_ids == [f"config:{index}" for index in range(8)]


def test_architecture_mission_traces_only_relation_derived_hubs() -> None:
    draft = ProjectArchiveDraft(
        project_id="demo",
        entities=[
            ProjectEntity(id="entity:one", type="File", name="one.py"),
            ProjectEntity(id="entity:two", type="File", name="two.py"),
            ProjectEntity(id="entity:three", type="File", name="three.py"),
            ProjectEntity(id="entity:orphan", type="File", name="orphan.py"),
        ],
        relations=[
            ProjectRelation(
                id="rel:one-two",
                source_id="entity:one",
                target_id="entity:two",
                type="IMPORTS",
            ),
            ProjectRelation(
                id="rel:two-three",
                source_id="entity:two",
                target_id="entity:three",
                type="IMPORTS",
            ),
        ],
    )

    mission = run_architecture_mission(draft, max_steps=4)
    hub_task = mission.tasks[3]

    assert hub_task.task_type == "trace_dependency_hubs"
    assert hub_task.input_entity_ids == [
        "entity:two",
        "entity:one",
        "entity:three",
    ]
