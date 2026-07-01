"""Graph-grounded Agent mission runtime."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

from src.libs.llm import BaseLLM, Message
from src.project_archive.agent_tools import SPECIALIST_ROLES, AgentToolRegistry
from src.project_archive.types import (
    AgentMission,
    AgentMissionBudget,
    AgentMissionFinalReport,
    AgentMissionTask,
    AgentMissionVerifierResult,
    AgentTraceEvent,
    ProjectArchiveDraft,
)

DEFAULT_AGENT_GOAL = "Understand project architecture"
MISSION_ID_GLOB_CHARS = {"*", "?", "[", "]", "{", "}"}
MAX_THOUGHT_SUMMARY_CHARS = 240
TERMINAL_MISSION_STATUSES = {"complete", "partial", "failed", "stopped", "cancelled"}
INTERRUPTED_MISSION_STATUSES = {"stopped", "cancelled"}
JSON_OBJECT_RESPONSE_FORMAT = {"type": "json_object"}
ACTION_SELECTION_MAX_TOKENS = 700


@dataclass(frozen=True)
class _TaskTemplate:
    task_type: str
    objective: str
    allowed_tools: list[str]


TASK_TEMPLATES = [
    _TaskTemplate(
        task_type="find_entry_points",
        objective="Find likely entry points and high-signal graph starts.",
        allowed_tools=["graph_summary", "list_halls", "graph_search", "hybrid_search"],
    ),
    _TaskTemplate(
        task_type="map_archive_halls",
        objective="Map archive halls and their surrounding graph neighborhoods.",
        allowed_tools=["list_halls", "graph_neighborhood"],
    ),
    _TaskTemplate(
        task_type="inspect_core_entities",
        objective="Inspect core entities related to the mission goal.",
        allowed_tools=["graph_search", "hybrid_search", "inspect_entity", "graph_neighborhood"],
    ),
    _TaskTemplate(
        task_type="collect_architecture_evidence",
        objective="Collect evidence cards for architecture claims.",
        allowed_tools=["graph_neighborhood", "hybrid_search", "get_evidence"],
    ),
    _TaskTemplate(
        task_type="summarize_architecture",
        objective="Summarize graph-grounded architecture findings.",
        allowed_tools=["graph_summary", "hybrid_search", "get_evidence"],
    ),
]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def plan_agent_mission(
    draft: ProjectArchiveDraft,
    goal: str,
    max_tasks: int = 5,
    max_steps_per_task: int = 4,
    max_tool_calls: int = 16,
) -> AgentMission:
    mission_id = str(uuid4())
    effective_max_tasks = max(0, int(max_tasks))
    effective_max_steps = max(1, int(max_steps_per_task))
    requested_tool_calls = max(1, int(max_tool_calls))
    planned_tool_calls = effective_max_tasks * min(effective_max_steps, 3)
    effective_max_tool_calls = max(requested_tool_calls, planned_tool_calls + effective_max_tasks)
    selected_templates = TASK_TEMPLATES[:effective_max_tasks]
    created_at = utc_now()
    seed_entity_ids = _seed_entity_ids(draft)

    tasks = [
        AgentMissionTask(
            id=f"{mission_id}:task:{index}",
            mission_id=mission_id,
            task_type=template.task_type,
            objective=template.objective,
            status="pending",
            allowed_tools=list(template.allowed_tools),
            max_steps=effective_max_steps,
            input_entity_ids=_task_seed_entity_ids(
                seed_entity_ids,
                task_type=template.task_type,
                order=index,
            ),
            created_at=created_at,
            metadata={
                "planner": {
                    "order": index,
                    "strategy": "architecture_graph_react",
                    "allowed_tools": list(template.allowed_tools),
                }
            },
        )
        for index, template in enumerate(selected_templates, start=1)
    ]

    return AgentMission(
        id=mission_id,
        project_id=draft.project_id,
        goal=goal.strip() or DEFAULT_AGENT_GOAL,
        status="planned",
        created_at=created_at,
        budget=AgentMissionBudget(
            max_tasks=effective_max_tasks,
            max_steps_per_task=effective_max_steps,
            max_tool_calls=effective_max_tool_calls,
            timeout_seconds=max(180, effective_max_tool_calls * 18),
        ),
        tasks=tasks,
        metadata={
            "agent_loop": {
                "pattern": "planner_react_critic_retry",
                "planner": "deterministic_task_templates",
                "tool_selection": "llm_or_deterministic_fallback",
                "critic": "evidence_verifier",
                "memory": "mission_scoped_entity_evidence_relation_ids",
            },
            "task_queue": [
                {
                    "id": task.id,
                    "task_type": task.task_type,
                    "objective": task.objective,
                    "allowed_tools": list(task.allowed_tools),
                    "status": task.status,
                }
                for task in tasks
            ],
            "draft_metrics": {
                "halls": len(draft.halls),
                "entities": len(draft.entities),
                "relations": len(draft.relations),
                "evidence": len(draft.evidence_cards),
            }
        },
    )


def _parse_action_response(content: str) -> tuple[str, str, dict[str, object], bool]:
    payload = json.loads(_repair_json_content(content), parse_constant=_reject_json_constant)
    if not isinstance(payload, dict):
        raise ValueError("LLM action response must be a JSON object.")

    thought_summary = payload.get("thought_summary", "")
    if thought_summary is None:
        thought_summary = ""
    if not isinstance(thought_summary, str):
        raise ValueError("LLM thought_summary must be a string.")

    action = payload.get("action")
    if not isinstance(action, dict):
        raise ValueError("LLM action must be a JSON object.")

    tool = action.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        raise ValueError("LLM action.tool must be a non-empty string.")

    tool_input = action.get("input", {})
    if not isinstance(tool_input, dict):
        raise ValueError("LLM action.input must be a JSON object.")

    stop = payload.get("stop", False)
    if not isinstance(stop, bool):
        raise ValueError("LLM stop must be a boolean.")

    return (
        thought_summary.strip()[:MAX_THOUGHT_SUMMARY_CHARS],
        tool.strip(),
        dict(tool_input),
        stop,
    )


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON constant: {value}")


def _repair_json_content(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]
    return text


def _validate_llm_tool_input(
    tool_name: str,
    tool_input: dict[str, Any],
    project_id: str,
) -> str | None:
    project_id_error = _validate_required_str(tool_input, "project_id")
    if project_id_error:
        return project_id_error
    if tool_input["project_id"].strip() != project_id:
        return "invalid_project_id"

    if tool_name in {"graph_summary", "list_halls"}:
        return None
    if tool_name == "graph_search":
        query_error = _validate_required_str(tool_input, "query")
        if query_error:
            return query_error
        if "limit" in tool_input and not _is_positive_int_like(tool_input["limit"]):
            return "invalid_limit"
        return None
    if tool_name == "hybrid_search":
        query_error = _validate_required_str(tool_input, "query")
        if query_error:
            return query_error
        if "top_k" in tool_input and not _is_positive_int_like(tool_input["top_k"]):
            return "invalid_top_k"
        if "hall_id" in tool_input and not isinstance(tool_input["hall_id"], str):
            return "invalid_hall_id"
        return None
    if tool_name == "graph_neighborhood":
        for key in ("hall_id", "focus_entity_id"):
            if key in tool_input and not isinstance(tool_input[key], str):
                return f"invalid_{key}"
        for key in ("depth", "node_limit", "relation_limit"):
            if key in tool_input and not _is_positive_int_like(tool_input[key]):
                return f"invalid_{key}"
        if "relation_types" in tool_input and not _is_string_list(
            tool_input["relation_types"],
            allow_empty=True,
        ):
            return "invalid_relation_types"
        return None
    if tool_name == "get_evidence":
        if "evidence_ids" in tool_input and not _is_string_list(
            tool_input["evidence_ids"],
            allow_empty=True,
        ):
            return "invalid_evidence_ids"
        return None
    if tool_name == "inspect_entity":
        return _validate_required_str(tool_input, "entity_id")
    if tool_name == "run_specialist_agent":
        role_error = _validate_required_str(tool_input, "role")
        if role_error:
            return role_error
        if tool_input["role"].strip() not in SPECIALIST_ROLES:
            return "invalid_role"
        if "prior_agents" in tool_input and not isinstance(
            tool_input["prior_agents"],
            dict,
        ):
            return "invalid_prior_agents"
        return None
    return "unknown_tool"


def _validate_required_str(tool_input: dict[str, Any], key: str) -> str | None:
    value = tool_input.get(key)
    if not isinstance(value, str) or not value.strip():
        return f"missing_{key}"
    return None


def _is_positive_int_like(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value >= 1
    if isinstance(value, float):
        return value.is_integer() and value >= 1
    if isinstance(value, str):
        return value.strip().isdigit() and int(value.strip()) >= 1
    return False


def _is_string_list(value: Any, *, allow_empty: bool) -> bool:
    if value is None:
        return allow_empty
    if not isinstance(value, list):
        return False
    if not allow_empty and not value:
        return False
    return all(isinstance(item, str) and item.strip() for item in value)


def _llm_fallback_metadata(
    fallback_reason: str,
    *,
    error_type: str | None = None,
    model: str | None = None,
    thought_summary: str | None = None,
    llm_stop_requested: bool = False,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "selection": "deterministic",
        "llm_fallback": True,
        "fallback_reason": fallback_reason,
        "llm_selection_attempts": 1,
    }
    if error_type:
        metadata["error_type"] = error_type[:80]
    if model:
        metadata["model"] = model[:120]
    if thought_summary:
        metadata["thought_summary"] = thought_summary[:MAX_THOUGHT_SUMMARY_CHARS]
    if llm_stop_requested:
        metadata["llm_stop_requested"] = True
    return metadata


def _action_messages(
    mission: AgentMission,
    task: AgentMissionTask,
    allowed_tools: list[str],
    trace_events: list[AgentTraceEvent],
) -> list[Message]:
    recent_observations = [
        {
            "event_type": event.event_type,
            "tool_name": event.tool_name,
            "observation_summary": event.observation_summary,
            "evidence_ids": list(event.evidence_ids),
            "entity_ids": list(event.entity_ids),
            "relation_ids": list(event.relation_ids),
        }
        for event in trace_events[-5:]
    ]
    request = {
        "mission": {
            "id": mission.id,
            "project_id": mission.project_id,
            "goal": mission.goal,
        },
        "task": {
            "id": task.id,
            "task_type": task.task_type,
            "objective": task.objective,
            "allowed_tools": list(allowed_tools),
            "input_entity_ids": list(task.input_entity_ids),
            "steps_used": task.steps_used,
            "max_steps": task.max_steps,
        },
        "recent_observations": recent_observations,
        "response_schema": {
            "thought_summary": "brief rationale summary only; no hidden reasoning",
            "action": {
                "tool": "one allowed tool name",
                "input": {"project_id": mission.project_id},
            },
            "stop": False,
        },
        "strict_output_rules": [
            "Return one json object only.",
            "Do not wrap the JSON object in Markdown or a string.",
            "Choose a tool from allowed_tools.",
            "Use project_id exactly as provided.",
            'Example json output: {"thought_summary":"Use graph summary","action":{"tool":"graph_summary","input":{"project_id":"PROJECT_ID"}},"stop":false}.',
        ],
    }
    return [
        Message(
            role="system",
            content=(
                "Select the next graph-grounded tool call for the mission. "
                "Return json only, with no Markdown fences. Do not include "
                "hidden reasoning or chain-of-thought; at most include a short "
                "thought_summary."
            ),
        ),
        Message(
            role="user",
            content=json.dumps(request, ensure_ascii=False),
        ),
    ]


class MissionStore:
    def __init__(self, storage_dir: str | Path) -> None:
        self.storage_dir = Path(storage_dir)

    def save(self, mission: AgentMission) -> AgentMission:
        path = self._mission_path(mission.project_id, mission.id)
        tmp_path = path.with_name(f"{path.name}.tmp")
        payload = json.dumps(mission.to_dict(), ensure_ascii=False, indent=2)
        try:
            tmp_path.write_text(payload, encoding="utf-8")
            tmp_path.replace(path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
        return mission

    def save_if_not_interrupted(
        self,
        mission: AgentMission,
        interrupted_statuses: set[str],
    ) -> AgentMission:
        stored = self.load(mission.id)
        if stored.status in interrupted_statuses:
            return stored
        return self.save(mission)

    def load(self, mission_id: str) -> AgentMission:
        self._validate_mission_id(mission_id)
        if not self.storage_dir.exists():
            raise ValueError(f"Agent mission not found: {mission_id}")
        for project_dir in self.storage_dir.iterdir():
            if not project_dir.is_dir():
                continue
            path = project_dir / "agent_missions" / f"{mission_id}.json"
            if not path.is_file():
                continue
            return AgentMission.from_dict(json.loads(path.read_text(encoding="utf-8")))
        raise ValueError(f"Agent mission not found: {mission_id}")

    def update_status(self, mission_id: str, status: str) -> AgentMission:
        mission = self.load(mission_id)
        completed_at = mission.completed_at
        if status in TERMINAL_MISSION_STATUSES and not completed_at:
            completed_at = utc_now()
        updated = replace(mission, status=status, completed_at=completed_at)
        return self.save(updated)

    def _mission_path(self, project_id: str, mission_id: str) -> Path:
        self._validate_mission_id(mission_id)
        mission_dir = (
            self.storage_dir / _safe_project_id(project_id) / "agent_missions"
        )
        mission_dir.mkdir(parents=True, exist_ok=True)
        return mission_dir / f"{mission_id}.json"

    def _validate_mission_id(self, mission_id: str) -> None:
        if not isinstance(mission_id, str) or not mission_id:
            raise ValueError("Agent mission id must be a non-empty string.")
        if any(char in mission_id for char in ("/", "\\")):
            raise ValueError(f"Invalid agent mission id: {mission_id}")
        if any(char in mission_id for char in MISSION_ID_GLOB_CHARS):
            raise ValueError(f"Invalid agent mission id: {mission_id}")


class EvidenceVerifier:
    def verify_task(
        self,
        task: AgentMissionTask,
        draft: ProjectArchiveDraft,
    ) -> AgentMissionVerifierResult:
        result, _findings = self._verify_task_findings(task=task, draft=draft)
        return result

    def _verify_task_findings(
        self,
        task: AgentMissionTask,
        draft: ProjectArchiveDraft,
    ) -> tuple[AgentMissionVerifierResult, list[dict[str, Any]]]:
        valid_evidence_ids = {card.id for card in draft.evidence_cards}
        supported_count = 0
        uncertain_count = 0
        warnings: list[str] = []
        verified_findings: list[dict[str, Any]] = []

        if not task.findings:
            warnings.append(f"Task {task.id} produced no findings.")

        for index, finding in enumerate(task.findings, start=1):
            verified_finding = deepcopy(finding)
            evidence_ids = _string_values(finding.get("evidence_ids", []))
            supported_evidence_ids = [
                evidence_id
                for evidence_id in evidence_ids
                if evidence_id in valid_evidence_ids
            ]
            invalid_evidence_ids = [
                evidence_id
                for evidence_id in evidence_ids
                if evidence_id not in valid_evidence_ids
            ]
            verified_finding["evidence_ids"] = supported_evidence_ids
            verified_finding["supported_evidence_ids"] = supported_evidence_ids
            if invalid_evidence_ids:
                verified_finding["invalid_evidence_ids"] = invalid_evidence_ids
                warnings.append(
                    f"Task {task.id} finding {index} cites unknown evidence."
                )
            if supported_evidence_ids:
                supported_count += 1
                verified_finding["verification_status"] = "supported"
            else:
                uncertain_count += 1
                verified_finding["verification_status"] = "uncertain"
                if not evidence_ids:
                    warnings.append(
                        f"Task {task.id} finding {index} has no evidence citations."
                    )
            verified_findings.append(verified_finding)

        status = "accepted"
        if uncertain_count and supported_count:
            status = "partial"
        elif uncertain_count or not supported_count:
            status = "uncertain"

        return (
            AgentMissionVerifierResult(
                status=status,
                supported_finding_count=supported_count,
                uncertain_finding_count=uncertain_count,
                warnings=warnings,
            ),
            verified_findings,
        )


class AgentMissionRuntime:
    def __init__(
        self,
        service: Any,
        store: MissionStore,
        tool_registry: AgentToolRegistry,
        llm: BaseLLM | None = None,
    ) -> None:
        self.service = service
        self.store = store
        self.tool_registry = tool_registry
        self.llm = llm
        self.verifier = EvidenceVerifier()

    def create(
        self,
        draft: ProjectArchiveDraft,
        goal: str,
        max_tasks: int = 5,
        max_steps_per_task: int = 4,
    ) -> AgentMission:
        mission = plan_agent_mission(
            draft=draft,
            goal=goal,
            max_tasks=max_tasks,
            max_steps_per_task=max_steps_per_task,
        )
        return self.store.save(mission)

    def start(
        self,
        project_id: str,
        goal: str,
        max_tasks: int = 5,
        max_steps_per_task: int = 4,
    ) -> AgentMission:
        draft = self.service.load_draft(project_id)
        mission = self.create(
            draft=draft,
            goal=goal,
            max_tasks=max_tasks,
            max_steps_per_task=max_steps_per_task,
        )
        return self._run_to_completion(mission, draft)

    def run(self, mission_id: str) -> AgentMission:
        mission = self.load(mission_id)
        if mission.status in TERMINAL_MISSION_STATUSES:
            return mission
        draft = self.service.load_draft(mission.project_id)
        return self._run_to_completion(mission, draft)

    def load(self, mission_id: str) -> AgentMission:
        return self.store.load(mission_id)

    def trace(self, mission_id: str) -> list[AgentTraceEvent]:
        return self.load(mission_id).trace_events

    def update_status(self, mission_id: str, status: str) -> AgentMission:
        return self.store.update_status(mission_id, status)

    def _run_to_completion(
        self,
        mission: AgentMission,
        draft: ProjectArchiveDraft,
    ) -> AgentMission:
        if mission.status in TERMINAL_MISSION_STATUSES:
            return mission
        interrupted = self._interrupted_mission(mission.id)
        if interrupted is not None:
            return interrupted

        running = replace(mission, status="running")
        self.store.save(running)

        completed_tasks: list[AgentMissionTask] = []
        trace_events = list(running.trace_events)
        sequence = len(trace_events) + 1
        tool_calls_used = 0
        agent_memory: dict[str, list[str]] = {
            "entity_ids": [],
            "evidence_ids": [],
            "relation_ids": [],
            "tool_names": [],
        }
        critic_reviews: list[dict[str, Any]] = []
        started_monotonic = monotonic()
        timeout_seconds = max(0, int(running.budget.timeout_seconds))

        selected_tasks = running.tasks[: running.budget.max_tasks]
        skipped_budget_tasks = running.tasks[running.budget.max_tasks :]

        for task in selected_tasks:
            interrupted = self._interrupted_mission(running.id)
            if interrupted is not None:
                return interrupted
            if tool_calls_used >= running.budget.max_tool_calls:
                completed_tasks.append(replace(task, status="skipped", steps_used=0))
                continue

            started_at = utc_now()
            findings: list[dict[str, Any]] = []
            task_evidence_ids: list[str] = []
            task_entity_ids: list[str] = []
            task_relation_ids: list[str] = []
            errors: list[str] = []
            calls = self._default_tool_calls(task, running, draft)[: task.max_steps]
            task_trace_count = 0
            timed_out = False

            for default_tool_name, default_tool_input in calls:
                interrupted = self._interrupted_mission(running.id)
                if interrupted is not None:
                    return interrupted
                if tool_calls_used >= running.budget.max_tool_calls:
                    break
                if monotonic() - started_monotonic >= timeout_seconds:
                    timed_out = True
                    now = utc_now()
                    trace_events.append(
                        AgentTraceEvent(
                            id=str(uuid4()),
                            mission_id=running.id,
                            task_id=task.id,
                            sequence=sequence,
                            event_type="error",
                            tool_name=default_tool_name,
                            tool_input=dict(default_tool_input),
                            observation_summary="Mission timeout expired before tool execution.",
                            started_at=now,
                            completed_at=now,
                            error="Mission timeout expired.",
                            metadata={"selection": "deterministic"},
                        )
                    )
                    sequence += 1
                    task_trace_count += 1
                    break

                tool_name, tool_input, selection_metadata = self._select_tool_call(
                    mission=running,
                    task=task,
                    default_tool_name=default_tool_name,
                    default_tool_input=default_tool_input,
                    trace_events=trace_events,
                )
                selection_metadata = {
                    **selection_metadata,
                    "budget": {
                        "tool_calls_used_before": tool_calls_used,
                        "max_tool_calls": running.budget.max_tool_calls,
                        "task_steps_used_before": task_trace_count,
                        "task_max_steps": task.max_steps,
                    },
                    "memory": _memory_summary(agent_memory),
                }
                interrupted = self._interrupted_mission(running.id)
                if interrupted is not None:
                    return interrupted
                if tool_name not in task.allowed_tools:
                    now = utc_now()
                    trace_events.append(
                        AgentTraceEvent(
                            id=str(uuid4()),
                            mission_id=running.id,
                            task_id=task.id,
                            sequence=sequence,
                            event_type="skipped",
                            tool_name=tool_name,
                            tool_input=dict(tool_input),
                            observation_summary="Tool is not allowed for this task.",
                            started_at=now,
                            completed_at=now,
                            metadata=selection_metadata,
                        )
                    )
                    sequence += 1
                    task_trace_count += 1
                    continue
                event_started_at = utc_now()
                tool_calls_used += 1
                try:
                    result = self.tool_registry.execute(tool_name, tool_input)
                    trace_events.append(
                        AgentTraceEvent(
                            id=str(uuid4()),
                            mission_id=running.id,
                            task_id=task.id,
                            sequence=sequence,
                            event_type="action",
                            tool_name=tool_name,
                            tool_input=dict(tool_input),
                            observation_summary=result.summary,
                            evidence_ids=list(result.evidence_ids),
                            entity_ids=list(result.entity_ids),
                            relation_ids=list(result.relation_ids),
                            started_at=event_started_at,
                            completed_at=utc_now(),
                            metadata=selection_metadata,
                        )
                    )
                    findings.append(
                        {
                            "summary": result.summary,
                            "tool_name": tool_name,
                            "evidence_ids": list(result.evidence_ids),
                            "entity_ids": list(result.entity_ids),
                            "relation_ids": list(result.relation_ids),
                        }
                    )
                    task_evidence_ids.extend(result.evidence_ids)
                    task_entity_ids.extend(result.entity_ids)
                    task_relation_ids.extend(result.relation_ids)
                    _remember(agent_memory, result)
                except Exception as exc:  # pragma: no cover - defensive trace path.
                    errors.append(str(exc))
                    trace_events.append(
                        AgentTraceEvent(
                            id=str(uuid4()),
                            mission_id=running.id,
                            task_id=task.id,
                            sequence=sequence,
                            event_type="error",
                            tool_name=tool_name,
                            tool_input=dict(tool_input),
                            observation_summary="Tool execution failed.",
                            started_at=event_started_at,
                            completed_at=utc_now(),
                            error=str(exc),
                            metadata=selection_metadata,
                        )
                    )
                sequence += 1
                task_trace_count += 1

            status = "complete" if findings else "failed"
            if timed_out:
                status = "timeout"
            if errors and findings:
                status = "partial"
            findings = _backfill_finding_evidence(findings, task_evidence_ids)
            provisional_task = replace(
                task,
                status=status,
                steps_used=task_trace_count,
                output_entity_ids=_unique(task_entity_ids),
                evidence_ids=_unique(task_evidence_ids),
                findings=findings,
                confidence=0.8 if task_evidence_ids else 0.45,
                completed_at=utc_now(),
                created_at=task.created_at or started_at,
            )
            critic_result = self.verifier.verify_task(provisional_task, draft)
            retry_performed = False
            retry_reason = ""
            if (
                critic_result.status == "uncertain"
                and not timed_out
                and tool_calls_used < running.budget.max_tool_calls
                and task_trace_count < task.max_steps
            ):
                retry_call = self._critic_retry_call(
                    task=task,
                    mission=running,
                    agent_memory=agent_memory,
                )
                if retry_call is not None:
                    retry_tool_name, retry_tool_input = retry_call
                    retry_reason = "critic_uncertain"
                    event_started_at = utc_now()
                    tool_calls_used += 1
                    try:
                        retry_result = self.tool_registry.execute(
                            retry_tool_name,
                            retry_tool_input,
                        )
                        retry_metadata = {
                            "selection": "critic_retry",
                            "retry_reason": retry_reason,
                            "budget": {
                                "tool_calls_used_before": tool_calls_used - 1,
                                "max_tool_calls": running.budget.max_tool_calls,
                                "task_steps_used_before": task_trace_count,
                                "task_max_steps": task.max_steps,
                            },
                            "memory": _memory_summary(agent_memory),
                        }
                        trace_events.append(
                            AgentTraceEvent(
                                id=str(uuid4()),
                                mission_id=running.id,
                                task_id=task.id,
                                sequence=sequence,
                                event_type="action",
                                tool_name=retry_tool_name,
                                tool_input=dict(retry_tool_input),
                                observation_summary=retry_result.summary,
                                evidence_ids=list(retry_result.evidence_ids),
                                entity_ids=list(retry_result.entity_ids),
                                relation_ids=list(retry_result.relation_ids),
                                started_at=event_started_at,
                                completed_at=utc_now(),
                                metadata=retry_metadata,
                            )
                        )
                        findings.append(
                            {
                                "summary": retry_result.summary,
                                "tool_name": retry_tool_name,
                                "evidence_ids": list(retry_result.evidence_ids),
                                "entity_ids": list(retry_result.entity_ids),
                                "relation_ids": list(retry_result.relation_ids),
                                "retry_reason": retry_reason,
                            }
                        )
                        task_evidence_ids.extend(retry_result.evidence_ids)
                        task_entity_ids.extend(retry_result.entity_ids)
                        task_relation_ids.extend(retry_result.relation_ids)
                        _remember(agent_memory, retry_result)
                        task_trace_count += 1
                        sequence += 1
                        retry_performed = True
                    except Exception as exc:  # pragma: no cover - defensive trace path.
                        errors.append(str(exc))
                        trace_events.append(
                            AgentTraceEvent(
                                id=str(uuid4()),
                                mission_id=running.id,
                                task_id=task.id,
                                sequence=sequence,
                                event_type="error",
                                tool_name=retry_tool_name,
                                tool_input=dict(retry_tool_input),
                                observation_summary="Critic retry failed.",
                                started_at=event_started_at,
                                completed_at=utc_now(),
                                error=str(exc),
                                metadata={
                                    "selection": "critic_retry",
                                    "retry_reason": retry_reason,
                                },
                            )
                        )
                        task_trace_count += 1
                        sequence += 1
            findings = _backfill_finding_evidence(findings, task_evidence_ids)
            critic_result = self.verifier.verify_task(
                replace(
                    provisional_task,
                    findings=findings,
                    evidence_ids=_unique(task_evidence_ids),
                    output_entity_ids=_unique(task_entity_ids),
                ),
                draft,
            )
            status = "complete" if findings else "failed"
            if timed_out:
                status = "partial" if findings else "timeout"
            if errors and findings:
                status = "partial"
            provisional_task = replace(
                provisional_task,
                status=status,
                steps_used=task_trace_count,
                output_entity_ids=_unique(task_entity_ids),
                evidence_ids=_unique(task_evidence_ids),
                findings=findings,
                confidence=0.8 if task_evidence_ids else 0.45,
                metadata={
                    **dict(provisional_task.metadata),
                    "critic": {
                        "status": critic_result.status,
                        "supported_finding_count": critic_result.supported_finding_count,
                        "uncertain_finding_count": critic_result.uncertain_finding_count,
                        "warnings": list(critic_result.warnings),
                        "retry_performed": retry_performed,
                        "retry_reason": retry_reason,
                    },
                    "memory_after": _memory_summary(agent_memory),
                },
            )
            critic_reviews.append(
                {
                    "task_id": task.id,
                    "status": critic_result.status,
                    "supported_finding_count": critic_result.supported_finding_count,
                    "uncertain_finding_count": critic_result.uncertain_finding_count,
                    "retry_performed": retry_performed,
                }
            )
            completed_tasks.append(
                provisional_task
            )
            if timed_out:
                break

        completed_task_ids = {task.id for task in completed_tasks}
        for task in selected_tasks:
            if task.id not in completed_task_ids:
                completed_tasks.append(replace(task, status="skipped", steps_used=0))
        completed_tasks.extend(
            replace(task, status="skipped", steps_used=0)
            for task in skipped_budget_tasks
        )
        final_status = _mission_status(completed_tasks)

        completed = replace(
            running,
            status=final_status,
            completed_at=utc_now(),
            tasks=completed_tasks,
            trace_events=trace_events,
            metadata={
                **dict(running.metadata),
                "task_queue": [
                    {
                        "id": task.id,
                        "task_type": task.task_type,
                        "objective": task.objective,
                        "allowed_tools": list(task.allowed_tools),
                        "status": task.status,
                    }
                    for task in completed_tasks
                ],
                "agent_memory": _memory_summary(agent_memory),
                "budget_usage": {
                    "tool_calls_used": tool_calls_used,
                    "max_tool_calls": running.budget.max_tool_calls,
                    "completed_tasks": sum(
                        1 for task in completed_tasks if task.status == "complete"
                    ),
                    "max_tasks": running.budget.max_tasks,
                    "trace_events": len(trace_events),
                },
                "critic_reviews": critic_reviews,
            },
        )
        verified = self._verify_mission(completed, draft)
        final = replace(verified, final_report=self._final_report(verified))
        return self.store.save_if_not_interrupted(final, INTERRUPTED_MISSION_STATUSES)

    def _interrupted_mission(self, mission_id: str) -> AgentMission | None:
        stored = self.store.load(mission_id)
        if stored.status in INTERRUPTED_MISSION_STATUSES:
            return stored
        return None

    def _default_tool_calls(
        self,
        task: AgentMissionTask,
        mission: AgentMission,
        draft: ProjectArchiveDraft,
    ) -> list[tuple[str, dict[str, Any]]]:
        project_id = mission.project_id
        goal_query = mission.goal or DEFAULT_AGENT_GOAL
        evidence_ids = _unique(
            evidence_id
            for entity in draft.entities[:4]
            for evidence_id in entity.evidence_ids
        )
        focus_entity_id = (
            task.input_entity_ids[0]
            if task.input_entity_ids
            else draft.entities[0].id
            if draft.entities
            else None
        )
        inspect_core_calls = [
            (
                "graph_search",
                {"project_id": project_id, "query": goal_query, "limit": 5},
            )
        ]
        if focus_entity_id:
            inspect_core_calls.append(
                (
                    "inspect_entity",
                    {"project_id": project_id, "entity_id": focus_entity_id},
                )
            )
        else:
            inspect_core_calls.append(
                (
                    "graph_neighborhood",
                    {
                        "project_id": project_id,
                        "depth": 1,
                        "node_limit": 20,
                        "relation_limit": 40,
                    },
                )
            )

        calls_by_type: dict[str, list[tuple[str, dict[str, Any]]]] = {
            "find_entry_points": [
                ("graph_summary", {"project_id": project_id}),
                ("list_halls", {"project_id": project_id}),
                (
                    "graph_search",
                    {"project_id": project_id, "query": goal_query, "limit": 5},
                ),
                (
                    "hybrid_search",
                    {"project_id": project_id, "query": goal_query, "top_k": 6},
                ),
            ],
            "map_archive_halls": [
                ("list_halls", {"project_id": project_id}),
                (
                    "graph_neighborhood",
                    {
                        "project_id": project_id,
                        "depth": 1,
                        "node_limit": 20,
                        "relation_limit": 40,
                    },
                ),
            ],
            "inspect_core_entities": inspect_core_calls,
            "collect_architecture_evidence": [
                (
                    "graph_neighborhood",
                    {
                        "project_id": project_id,
                        **({"focus_entity_id": focus_entity_id} if focus_entity_id else {}),
                        "depth": 1,
                        "node_limit": 20,
                        "relation_limit": 40,
                    },
                ),
                (
                    "hybrid_search",
                    {"project_id": project_id, "query": goal_query, "top_k": 8},
                ),
                (
                    "get_evidence",
                    {"project_id": project_id, "evidence_ids": evidence_ids[:10]},
                ),
            ],
            "summarize_architecture": [
                ("graph_summary", {"project_id": project_id}),
                (
                    "hybrid_search",
                    {"project_id": project_id, "query": goal_query, "top_k": 8},
                ),
                (
                    "get_evidence",
                    {"project_id": project_id, "evidence_ids": evidence_ids[:10]},
                ),
            ],
        }
        return calls_by_type.get(
            task.task_type,
            [("graph_summary", {"project_id": project_id})],
        )

    def _select_tool_call(
        self,
        mission: AgentMission,
        task: AgentMissionTask,
        default_tool_name: str,
        default_tool_input: dict[str, Any],
        trace_events: list[AgentTraceEvent],
    ) -> tuple[str, dict[str, Any], dict[str, Any]]:
        fallback_input = dict(default_tool_input)
        fallback_input.setdefault("project_id", mission.project_id)
        deterministic_metadata: dict[str, Any] = {"selection": "deterministic"}
        if self.llm is None:
            return default_tool_name, fallback_input, deterministic_metadata
        if _task_trace_count(trace_events, task.id) > 0:
            return (
                default_tool_name,
                fallback_input,
                {"selection": "deterministic_after_first_llm_selection"},
            )

        try:
            response = self.llm.chat(
                _action_messages(
                    mission=mission,
                    task=task,
                    allowed_tools=task.allowed_tools,
                    trace_events=trace_events,
                ),
                temperature=0.0,
                max_tokens=ACTION_SELECTION_MAX_TOKENS,
                response_format=JSON_OBJECT_RESPONSE_FORMAT,
            )
        except Exception as exc:
            return (
                default_tool_name,
                fallback_input,
                _llm_fallback_metadata(
                    "llm_exception",
                    error_type=exc.__class__.__name__,
                ),
            )

        model = getattr(response, "model", None)
        try:
            thought_summary, tool_name, tool_input, stop_requested = (
                _parse_action_response(response.content)
            )
        except Exception as exc:
            return (
                default_tool_name,
                fallback_input,
                _llm_fallback_metadata(
                    "invalid_llm_response",
                    error_type=exc.__class__.__name__,
                    model=model,
                ),
            )

        metadata: dict[str, Any] = {
            "selection": "llm",
            "model": model,
            "llm_selection_attempts": 1,
        }
        if thought_summary:
            metadata["thought_summary"] = thought_summary

        if stop_requested:
            return (
                default_tool_name,
                fallback_input,
                _llm_fallback_metadata(
                    "stop_requested",
                    model=model,
                    thought_summary=thought_summary,
                    llm_stop_requested=True,
                ),
            )
        if tool_name not in task.allowed_tools:
            return (
                default_tool_name,
                fallback_input,
                _llm_fallback_metadata(
                    "disallowed_tool",
                    model=model,
                    thought_summary=thought_summary,
                ),
            )

        selected_input = dict(tool_input)
        selected_input.setdefault("project_id", mission.project_id)
        input_error = _validate_llm_tool_input(
            tool_name,
            selected_input,
            mission.project_id,
        )
        if input_error:
            return (
                default_tool_name,
                fallback_input,
                _llm_fallback_metadata(
                    "invalid_tool_input",
                    error_type=input_error,
                    model=model,
                    thought_summary=thought_summary,
                ),
            )
        return tool_name, selected_input, metadata

    def _critic_retry_call(
        self,
        task: AgentMissionTask,
        mission: AgentMission,
        agent_memory: dict[str, list[str]],
    ) -> tuple[str, dict[str, Any]] | None:
        project_id = mission.project_id
        if "hybrid_search" in task.allowed_tools:
            return (
                "hybrid_search",
                {"project_id": project_id, "query": mission.goal, "top_k": 8},
            )
        if "get_evidence" in task.allowed_tools and agent_memory["evidence_ids"]:
            return (
                "get_evidence",
                {
                    "project_id": project_id,
                    "evidence_ids": agent_memory["evidence_ids"][:10],
                },
            )
        if "graph_neighborhood" in task.allowed_tools:
            tool_input: dict[str, Any] = {
                "project_id": project_id,
                "depth": 1,
                "node_limit": 30,
                "relation_limit": 60,
            }
            focus_entity_id = (
                agent_memory["entity_ids"][0]
                if agent_memory["entity_ids"]
                else task.input_entity_ids[0]
                if task.input_entity_ids
                else None
            )
            if focus_entity_id:
                tool_input["focus_entity_id"] = focus_entity_id
            return ("graph_neighborhood", tool_input)
        if "graph_search" in task.allowed_tools:
            return (
                "graph_search",
                {"project_id": project_id, "query": mission.goal, "limit": 5},
            )
        return None

    def _verify_mission(
        self,
        mission: AgentMission,
        draft: ProjectArchiveDraft,
    ) -> AgentMission:
        supported = 0
        uncertain = 0
        warnings: list[str] = []
        verified_tasks: list[AgentMissionTask] = []

        for task in mission.tasks:
            result, findings = self.verifier._verify_task_findings(
                task=task,
                draft=draft,
            )
            supported += result.supported_finding_count
            uncertain += result.uncertain_finding_count
            warnings.extend(result.warnings)
            verified_tasks.append(replace(task, findings=findings))

        status = "accepted"
        if uncertain and supported:
            status = "partial"
        elif uncertain or not supported:
            status = "uncertain"

        return replace(
            mission,
            tasks=verified_tasks,
            verifier_result=AgentMissionVerifierResult(
                status=status,
                supported_finding_count=supported,
                uncertain_finding_count=uncertain,
                warnings=warnings,
            ),
        )

    def _final_report(self, mission: AgentMission) -> AgentMissionFinalReport:
        findings = [
            finding
            for task in mission.tasks
            for finding in task.findings
            if finding.get("verification_status") == "supported"
        ]
        evidence_ids = _unique(
            evidence_id
            for finding in findings
            for evidence_id in _string_values(
                finding.get("supported_evidence_ids", [])
            )
        )
        completed_count = sum(1 for task in mission.tasks if task.status == "complete")
        failed_count = sum(
            1
            for task in mission.tasks
            if task.status in {"failed", "partial", "timeout"}
        )
        skipped_count = sum(1 for task in mission.tasks if task.status == "skipped")
        if findings:
            summary = (
                f"Mission {mission.status}: completed {completed_count}, failed "
                f"{failed_count}, skipped {skipped_count} task(s) for {mission.goal}; "
                f"{len(findings)} supported finding(s)."
            )
        else:
            summary = (
                f"Mission {mission.status}: completed {completed_count}, failed "
                f"{failed_count}, skipped {skipped_count} task(s) for {mission.goal}; "
                "findings need additional evidence."
            )
        confidence = 0.8 if findings else 0.35
        if mission.verifier_result and mission.verifier_result.status == "partial":
            confidence = 0.6
        return AgentMissionFinalReport(
            summary=summary,
            findings=findings,
            evidence_ids=evidence_ids,
            confidence=confidence,
        )


def _unique(values: Any) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        if not isinstance(value, str) or not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _remember(agent_memory: dict[str, list[str]], result: Any) -> None:
    agent_memory["entity_ids"] = _unique(
        [*agent_memory["entity_ids"], *list(result.entity_ids)]
    )[:80]
    agent_memory["evidence_ids"] = _unique(
        [*agent_memory["evidence_ids"], *list(result.evidence_ids)]
    )[:80]
    agent_memory["relation_ids"] = _unique(
        [*agent_memory["relation_ids"], *list(result.relation_ids)]
    )[:80]
    agent_memory["tool_names"] = _unique(
        [*agent_memory["tool_names"], str(result.tool_name)]
    )[:40]


def _memory_summary(agent_memory: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "entity_ids": list(agent_memory.get("entity_ids", []))[:20],
        "evidence_ids": list(agent_memory.get("evidence_ids", []))[:20],
        "relation_ids": list(agent_memory.get("relation_ids", []))[:20],
        "tool_names": list(agent_memory.get("tool_names", []))[:20],
        "counts": {
            "entities": len(agent_memory.get("entity_ids", [])),
            "evidence": len(agent_memory.get("evidence_ids", [])),
            "relations": len(agent_memory.get("relation_ids", [])),
            "tools": len(agent_memory.get("tool_names", [])),
        },
    }


def _backfill_finding_evidence(
    findings: list[dict[str, Any]],
    task_evidence_ids: list[str],
) -> list[dict[str, Any]]:
    evidence_pool = _unique(task_evidence_ids)
    if not evidence_pool:
        return findings

    backfilled: list[dict[str, Any]] = []
    for finding in findings:
        evidence_ids = _string_values(finding.get("evidence_ids", []))
        if evidence_ids:
            backfilled.append(finding)
            continue

        updated = dict(finding)
        updated["evidence_ids"] = evidence_pool[:3]
        updated["citation_backfilled"] = True
        updated["citation_backfill_source"] = "task_evidence_pool"
        backfilled.append(updated)
    return backfilled


def _mission_status(tasks: list[AgentMissionTask]) -> str:
    if not tasks:
        return "failed"
    completed_count = sum(1 for task in tasks if task.status == "complete")
    if completed_count == len(tasks):
        return "complete"
    partial_count = sum(1 for task in tasks if task.status == "partial")
    if completed_count or partial_count:
        return "partial"
    return "failed"


def _task_trace_count(trace_events: list[AgentTraceEvent], task_id: str) -> int:
    return sum(1 for event in trace_events if event.task_id == task_id)


def _task_seed_entity_ids(
    seed_entity_ids: list[str],
    *,
    task_type: str,
    order: int,
) -> list[str]:
    if not seed_entity_ids:
        return []
    if task_type in {"find_entry_points", "map_archive_halls"}:
        return seed_entity_ids[:4]
    window_size = 4
    offset = max(0, (order - 2) * 2)
    window = seed_entity_ids[offset: offset + window_size]
    return window or seed_entity_ids[:window_size]


def _seed_entity_ids(draft: ProjectArchiveDraft) -> list[str]:
    hall_entity_ids = [
        entity_id for hall in draft.halls for entity_id in hall.entity_ids
    ]
    entity_ids = [entity.id for entity in draft.entities]
    return _unique([*hall_entity_ids, *entity_ids])


def _safe_project_id(project_id: str) -> str:
    safe = [
        char if char.isalnum() or char in {"-", "_", "."} else "_"
        for char in project_id
    ]
    return "".join(safe).strip("._") or "project"


def _string_values(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str) and value]
