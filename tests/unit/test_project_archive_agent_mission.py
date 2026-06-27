from src.project_archive.types import (
    AgentMission,
    AgentMissionBudget,
    AgentMissionFinalReport,
    AgentMissionTask,
    AgentMissionVerifierResult,
    AgentTraceEvent,
)


def test_agent_mission_round_trips_trace_and_verifier_result():
    mission = AgentMission(
        id="mission-1",
        project_id="demo",
        goal="Understand architecture",
        status="complete",
        created_at="2026-06-27T00:00:00+00:00",
        completed_at="2026-06-27T00:00:10+00:00",
        budget=AgentMissionBudget(max_tasks=3, max_steps_per_task=4, max_tool_calls=10),
        tasks=[
            AgentMissionTask(
                id="task-1",
                mission_id="mission-1",
                task_type="find_entry_points",
                objective="Find likely entry points.",
                status="complete",
                allowed_tools=["graph_summary", "inspect_entity"],
                max_steps=3,
                steps_used=2,
                evidence_ids=["ev_1"],
                findings=[
                    {
                        "summary": "main.py is an entry point.",
                        "evidence_ids": ["ev_1"],
                    }
                ],
                confidence=0.82,
            )
        ],
        trace_events=[
            AgentTraceEvent(
                id="trace-1",
                mission_id="mission-1",
                task_id="task-1",
                sequence=1,
                event_type="action",
                tool_name="graph_summary",
                tool_input={"project_id": "demo"},
                observation_summary="Found one entry point.",
                evidence_ids=["ev_1"],
                entity_ids=["file_main"],
            )
        ],
        verifier_result=AgentMissionVerifierResult(
            status="accepted",
            supported_finding_count=1,
            uncertain_finding_count=0,
            warnings=[],
        ),
        final_report=AgentMissionFinalReport(
            summary="Architecture understood with cited evidence.",
            evidence_ids=["ev_1"],
            confidence=0.82,
        ),
    )

    restored = AgentMission.from_dict(mission.to_dict())

    assert restored == mission
    assert restored.tasks[0].allowed_tools == ["graph_summary", "inspect_entity"]
    assert restored.trace_events[0].tool_input == {"project_id": "demo"}
    assert restored.verifier_result.status == "accepted"
