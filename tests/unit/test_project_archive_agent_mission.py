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


from pathlib import Path

from src.project_archive.agent_mission import (
    AgentMissionRuntime,
    EvidenceVerifier,
    MissionStore,
    plan_agent_mission,
)
from src.project_archive.agent_tools import AgentToolRegistry
from src.project_archive.types import (
    ArchiveHall,
    EvidenceCard,
    ProjectArchiveDraft,
    ProjectEntity,
    ProjectRelation,
)


class RuntimeFakeService:
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.draft = ProjectArchiveDraft(
            project_id="demo",
            halls=[
                ArchiveHall(
                    id="hall_architecture",
                    name="Architecture Hall",
                    description="Architecture",
                    entity_ids=["file_main", "class_service"],
                )
            ],
            entities=[
                ProjectEntity(
                    id="file_main",
                    type="File",
                    name="main.py",
                    source_path="main.py",
                    evidence_ids=["ev_main"],
                ),
                ProjectEntity(
                    id="class_service",
                    type="Class",
                    name="QueryService",
                    source_path="main.py",
                    evidence_ids=["ev_service"],
                ),
            ],
            relations=[
                ProjectRelation(
                    id="rel_defines",
                    source_id="file_main",
                    target_id="class_service",
                    type="DEFINES",
                    evidence_ids=["ev_service"],
                )
            ],
            evidence_cards=[
                EvidenceCard(
                    id="ev_main",
                    source_type="code",
                    source_path="main.py",
                    title="main.py",
                    snippet="from service import QueryService",
                    linked_entities=["file_main"],
                ),
                EvidenceCard(
                    id="ev_service",
                    source_type="code",
                    source_path="main.py",
                    title="QueryService",
                    snippet="class QueryService: pass",
                    linked_entities=["class_service"],
                ),
            ],
        )

    def load_draft(self, project_id):
        assert project_id == "demo"
        return self.draft

    def graph_summary(self, project_id):
        return type(
            "Summary",
            (),
            {
                "to_dict": lambda self: {
                    "project_id": project_id,
                    "metrics": {"entities": 2, "relations": 1, "evidence": 2},
                    "recommended_starts": [],
                }
            },
        )()

    def search_graph_entities(self, project_id, *, query, limit=20):
        return []

    def graph_neighborhood(self, project_id, **kwargs):
        return type(
            "Neighborhood",
            (),
            {
                "to_dict": lambda self: {
                    "project_id": project_id,
                    "nodes": [],
                    "relations": [],
                    "evidence_ids": ["ev_service"],
                    "is_sparse": False,
                }
            },
        )()


def test_plan_agent_mission_creates_bounded_tasks():
    draft = RuntimeFakeService(Path(".")).draft

    mission = plan_agent_mission(
        draft=draft,
        goal="Understand architecture",
        max_tasks=3,
        max_steps_per_task=4,
    )

    assert mission.status == "planned"
    assert len(mission.tasks) == 3
    assert mission.tasks[0].task_type == "find_entry_points"
    assert mission.tasks[0].allowed_tools
    assert mission.budget.max_tasks == 3


def test_evidence_verifier_marks_missing_evidence_uncertain():
    draft = RuntimeFakeService(Path(".")).draft
    verifier = EvidenceVerifier()
    mission = plan_agent_mission(draft=draft, goal="Understand architecture")
    unsupported = mission.tasks[0].to_dict()
    unsupported["findings"] = [{"summary": "This claim has no citations."}]
    task = mission.tasks[0].from_dict(unsupported)

    result = verifier.verify_task(task=task, draft=draft)

    assert result.status == "uncertain"
    assert result.uncertain_finding_count == 1
    assert result.warnings


def test_runtime_runs_tools_and_persists_trace(tmp_path):
    service = RuntimeFakeService(tmp_path)
    runtime = AgentMissionRuntime(
        service=service,
        store=MissionStore(tmp_path),
        tool_registry=AgentToolRegistry(service),
        llm=None,
    )

    mission = runtime.start(
        project_id="demo",
        goal="Understand architecture",
        max_tasks=2,
        max_steps_per_task=2,
    )
    restored = runtime.load(mission.id)

    assert restored.status == "complete"
    assert restored.trace_events
    assert restored.final_report is not None
    assert restored.verifier_result is not None
    assert runtime.trace(mission.id) == restored.trace_events
