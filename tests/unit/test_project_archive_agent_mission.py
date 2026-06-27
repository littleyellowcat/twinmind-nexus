from dataclasses import replace

import pytest

from src.libs.llm import ChatResponse, Message
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


class FakeActionLLM:
    model = "fake-action-model"

    def __init__(self, content: str):
        self.content = content
        self.messages: list[list[Message]] = []

    def chat(self, messages, trace=None, **kwargs):
        self.messages.append(messages)
        return ChatResponse(
            content=self.content,
            model=self.model,
            usage={"total_tokens": 12},
        )


class RaisingActionLLM:
    model = "raising-action-model"

    def __init__(self, message: str):
        self.message = message
        self.messages: list[list[Message]] = []

    def chat(self, messages, trace=None, **kwargs):
        self.messages.append(messages)
        raise RuntimeError(self.message)


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


def test_mission_store_rejects_glob_like_ids_without_matching_saved_mission(tmp_path):
    draft = RuntimeFakeService(tmp_path).draft
    store = MissionStore(tmp_path)
    mission = plan_agent_mission(draft=draft, goal="Understand architecture")
    store.save(mission)

    for unsafe_id in ["*", "?", "[abc]", "{abc}", f"{mission.id}*"]:
        with pytest.raises(ValueError):
            store.load(unsafe_id)

    assert store.load(mission.id).id == mission.id


def test_runtime_timeout_marks_mission_failed_without_tool_execution(tmp_path):
    service = RuntimeFakeService(tmp_path)
    store = MissionStore(tmp_path)
    runtime = AgentMissionRuntime(
        service=service,
        store=store,
        tool_registry=AgentToolRegistry(service),
        llm=None,
    )
    mission = plan_agent_mission(
        draft=service.draft,
        goal="Understand architecture",
        max_tasks=2,
        max_steps_per_task=2,
    )
    mission = replace(
        mission,
        budget=replace(mission.budget, timeout_seconds=0),
    )
    store.save(mission)

    result = runtime.run(mission.id)

    assert result.status == "failed"
    assert result.tasks[0].status == "timeout"
    assert result.tasks[0].steps_used == 1
    assert result.tasks[1].status == "skipped"
    assert len(result.trace_events) == 1
    assert result.trace_events[0].event_type == "error"
    assert result.trace_events[0].error == "Mission timeout expired."


def test_runtime_max_tool_calls_exhaustion_marks_remaining_tasks_partial(tmp_path):
    service = RuntimeFakeService(tmp_path)
    store = MissionStore(tmp_path)
    runtime = AgentMissionRuntime(
        service=service,
        store=store,
        tool_registry=AgentToolRegistry(service),
        llm=None,
    )
    mission = plan_agent_mission(
        draft=service.draft,
        goal="Understand architecture",
        max_tasks=2,
        max_steps_per_task=2,
    )
    mission = replace(mission, budget=replace(mission.budget, max_tool_calls=1))
    store.save(mission)

    result = runtime.run(mission.id)

    assert result.status == "partial"
    assert result.tasks[0].status == "complete"
    assert result.tasks[0].steps_used == 1
    assert result.tasks[1].status == "skipped"
    assert len(result.trace_events) == 1


def test_runtime_all_tool_errors_mark_mission_failed_and_report_counts(tmp_path):
    class ErrorService(RuntimeFakeService):
        def graph_summary(self, project_id):
            raise ValueError("graph summary unavailable")

    service = ErrorService(tmp_path)
    store = MissionStore(tmp_path)
    runtime = AgentMissionRuntime(
        service=service,
        store=store,
        tool_registry=AgentToolRegistry(service),
        llm=None,
    )
    mission = plan_agent_mission(
        draft=service.draft,
        goal="Understand architecture",
        max_tasks=1,
        max_steps_per_task=1,
    )
    store.save(mission)

    result = runtime.run(mission.id)

    assert result.status == "failed"
    assert result.tasks[0].status == "failed"
    assert result.tasks[0].steps_used == 1
    assert result.final_report is not None
    assert "completed 0, failed 1, skipped 0" in result.final_report.summary


def test_runtime_partial_task_makes_mission_partial(tmp_path):
    class LaterErrorService(RuntimeFakeService):
        def __init__(self, storage_dir: Path):
            super().__init__(storage_dir)
            self.load_count = 0

        def load_draft(self, project_id):
            self.load_count += 1
            if self.load_count > 1:
                raise ValueError("draft unavailable during later tool call")
            return super().load_draft(project_id)

    service = LaterErrorService(tmp_path)
    store = MissionStore(tmp_path)
    runtime = AgentMissionRuntime(
        service=service,
        store=store,
        tool_registry=AgentToolRegistry(service),
        llm=None,
    )
    mission = plan_agent_mission(
        draft=service.draft,
        goal="Understand architecture",
        max_tasks=1,
        max_steps_per_task=2,
    )
    store.save(mission)

    result = runtime.run(mission.id)

    assert result.status == "partial"
    assert result.tasks[0].status == "partial"
    assert result.tasks[0].steps_used == 2
    assert [event.event_type for event in result.trace_events] == ["action", "error"]


def test_verifier_copies_findings_and_final_report_keeps_only_valid_evidence(tmp_path):
    service = RuntimeFakeService(tmp_path)
    runtime = AgentMissionRuntime(
        service=service,
        store=MissionStore(tmp_path),
        tool_registry=AgentToolRegistry(service),
        llm=None,
    )
    mission = plan_agent_mission(
        draft=service.draft,
        goal="Understand architecture",
        max_tasks=1,
        max_steps_per_task=1,
    )
    original_finding = {
        "summary": "Mixed evidence claim.",
        "evidence_ids": ["ev_main", "missing_ev"],
    }
    task = replace(mission.tasks[0], status="complete", findings=[original_finding])
    mission = replace(mission, status="complete", tasks=[task])

    verifier = EvidenceVerifier()
    verifier_result = verifier.verify_task(task=task, draft=service.draft)
    verified = runtime._verify_mission(mission, service.draft)
    final_report = runtime._final_report(verified)

    assert verifier_result.status == "accepted"
    assert "verification_status" not in original_finding
    assert verified.tasks[0].findings[0]["evidence_ids"] == ["ev_main"]
    assert verified.tasks[0].findings[0]["supported_evidence_ids"] == ["ev_main"]
    assert verified.tasks[0].findings[0]["invalid_evidence_ids"] == ["missing_ev"]
    assert final_report.evidence_ids == ["ev_main"]
    assert final_report.findings[0]["evidence_ids"] == ["ev_main"]
    assert "missing_ev" not in final_report.findings[0]["evidence_ids"]


def test_runtime_uses_llm_next_action_when_json_is_valid(tmp_path):
    service = RuntimeFakeService(tmp_path)
    llm = FakeActionLLM(
        '{"thought_summary":"Inspect graph first",'
        '"action":{"tool":"graph_summary","input":{"project_id":"demo"}},'
        '"stop":false}'
    )
    runtime = AgentMissionRuntime(
        service=service,
        store=MissionStore(tmp_path),
        tool_registry=AgentToolRegistry(service),
        llm=llm,
    )

    mission = runtime.start(
        project_id="demo",
        goal="Understand architecture",
        max_tasks=1,
        max_steps_per_task=1,
    )

    assert llm.messages
    assert mission.trace_events[0].tool_name == "graph_summary"
    assert mission.trace_events[0].metadata["thought_summary"] == "Inspect graph first"
    assert mission.trace_events[0].metadata["model"] == "fake-action-model"


def test_runtime_falls_back_when_llm_action_is_invalid(tmp_path):
    service = RuntimeFakeService(tmp_path)
    llm = FakeActionLLM("this is not json")
    runtime = AgentMissionRuntime(
        service=service,
        store=MissionStore(tmp_path),
        tool_registry=AgentToolRegistry(service),
        llm=llm,
    )

    mission = runtime.start(
        project_id="demo",
        goal="Understand architecture",
        max_tasks=1,
        max_steps_per_task=1,
    )

    assert mission.trace_events[0].tool_name == "graph_summary"
    assert mission.trace_events[0].metadata["llm_fallback"] is True
    assert mission.trace_events[0].metadata["fallback_reason"] == "invalid_llm_response"
    assert mission.trace_events[0].metadata["error_type"] == "JSONDecodeError"


def test_runtime_falls_back_when_llm_selects_disallowed_tool(tmp_path):
    service = RuntimeFakeService(tmp_path)
    llm = FakeActionLLM(
        '{"thought_summary":"Try evidence first",'
        '"action":{"tool":"get_evidence","input":{"project_id":"demo"}},'
        '"stop":false}'
    )
    runtime = AgentMissionRuntime(
        service=service,
        store=MissionStore(tmp_path),
        tool_registry=AgentToolRegistry(service),
        llm=llm,
    )

    mission = runtime.start(
        project_id="demo",
        goal="Understand architecture",
        max_tasks=1,
        max_steps_per_task=1,
    )

    assert mission.trace_events[0].tool_name == "graph_summary"
    assert mission.trace_events[0].metadata["llm_fallback"] is True
    assert mission.trace_events[0].metadata["fallback_reason"] == "disallowed_tool"
    assert "get_evidence" not in str(mission.trace_events[0].metadata)


def test_runtime_falls_back_when_llm_selected_tool_input_is_invalid(tmp_path):
    service = RuntimeFakeService(tmp_path)
    llm = FakeActionLLM(
        '{"thought_summary":"Search without a query",'
        '"action":{"tool":"graph_search","input":{"project_id":"demo"}},'
        '"stop":false}'
    )
    runtime = AgentMissionRuntime(
        service=service,
        store=MissionStore(tmp_path),
        tool_registry=AgentToolRegistry(service),
        llm=llm,
    )

    mission = runtime.start(
        project_id="demo",
        goal="Understand architecture",
        max_tasks=1,
        max_steps_per_task=1,
    )

    assert mission.status == "complete"
    assert mission.trace_events[0].event_type == "action"
    assert mission.trace_events[0].tool_name == "graph_summary"
    assert mission.trace_events[0].metadata["llm_fallback"] is True
    assert mission.trace_events[0].metadata["fallback_reason"] == "invalid_tool_input"
    assert mission.trace_events[0].metadata["error_type"] == "missing_query"


def test_runtime_falls_back_when_llm_requests_stop(tmp_path):
    service = RuntimeFakeService(tmp_path)
    llm = FakeActionLLM(
        '{"thought_summary":"Enough context",'
        '"action":{"tool":"graph_summary","input":{"project_id":"demo"}},'
        '"stop":true}'
    )
    runtime = AgentMissionRuntime(
        service=service,
        store=MissionStore(tmp_path),
        tool_registry=AgentToolRegistry(service),
        llm=llm,
    )

    mission = runtime.start(
        project_id="demo",
        goal="Understand architecture",
        max_tasks=1,
        max_steps_per_task=1,
    )

    assert mission.trace_events[0].tool_name == "graph_summary"
    assert mission.trace_events[0].metadata["llm_fallback"] is True
    assert mission.trace_events[0].metadata["llm_stop_requested"] is True
    assert mission.trace_events[0].metadata["fallback_reason"] == "stop_requested"


def test_runtime_falls_back_when_llm_raises_without_leaking_message(tmp_path):
    service = RuntimeFakeService(tmp_path)
    llm = RaisingActionLLM("provider failed with secret-token-123")
    runtime = AgentMissionRuntime(
        service=service,
        store=MissionStore(tmp_path),
        tool_registry=AgentToolRegistry(service),
        llm=llm,
    )

    mission = runtime.start(
        project_id="demo",
        goal="Understand architecture",
        max_tasks=1,
        max_steps_per_task=1,
    )

    metadata = mission.trace_events[0].metadata
    assert mission.trace_events[0].tool_name == "graph_summary"
    assert metadata["llm_fallback"] is True
    assert metadata["fallback_reason"] == "llm_exception"
    assert metadata["error_type"] == "RuntimeError"
    assert "secret-token-123" not in str(metadata)
