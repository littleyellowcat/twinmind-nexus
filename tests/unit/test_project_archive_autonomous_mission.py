"""Tests for bounded autonomous GraphRAG missions."""

from __future__ import annotations

from tests.unit.test_project_archive_graph_explorer import _draft

from src.project_archive.autonomous_mission import run_architecture_mission


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
