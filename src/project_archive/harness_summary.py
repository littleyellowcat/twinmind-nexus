"""Read-only run summary and resume guidance for TwinMind harness events."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


TERMINAL_EVENT_TYPES = {
    "run.completed",
    "run.failed",
    "run.cancelled",
    "run.stage.failed",
}


def build_harness_summary(
    *,
    project_id: str,
    events: list[dict[str, Any]],
    agent_eval_report: dict[str, Any] | None = None,
    version_events: list[dict[str, Any]] | None = None,
    mission_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_events = sorted(
        [_event_dict(event) for event in events],
        key=lambda event: int(event.get("sequence", 0) or 0),
    )
    agent_eval_report = agent_eval_report or {}
    version_events = [dict(item) for item in (version_events or []) if isinstance(item, dict)]
    mission_records = [dict(item) for item in (mission_records or []) if isinstance(item, dict)]
    latest_sequence = int(normalized_events[-1].get("sequence", 0) or 0) if normalized_events else 0
    events_by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in normalized_events:
        events_by_run[str(event.get("run_id") or "")].append(event)

    last_run_events = _last_run_events(events_by_run)
    last_run = _summarize_run(last_run_events, agent_eval_report)
    status = str(last_run.get("status") or "idle")
    phase = str(last_run.get("kind") or "none")
    last_failure = _latest_failure(normalized_events)
    artifacts = _collect_artifacts(normalized_events, agent_eval_report)
    warnings = _collect_warnings(agent_eval_report, mission_records)
    errors = _collect_errors(normalized_events, agent_eval_report)
    guidance = _resume_guidance(status, bool(normalized_events))

    return {
        "project_id": project_id,
        "status": status,
        "phase": phase,
        "last_event_sequence": latest_sequence,
        "latest_sequence": latest_sequence,
        "last_run": last_run,
        "last_failure": last_failure,
        "artifacts": artifacts,
        "warnings": warnings,
        "errors": errors,
        "resume_available": guidance["resume_available"],
        "resume_action": guidance["resume_action"],
        "next_best_action": guidance["next_best_action"],
        "metrics": {
            "events": len(normalized_events),
            "runs": len([run_id for run_id in events_by_run if run_id]),
            "artifacts": len(artifacts),
            "warnings": len(warnings),
            "errors": len(errors),
            "version_events": len(version_events),
            "mission_records": len(mission_records),
            "event_types": dict(Counter(str(event.get("type", "")) for event in normalized_events)),
        },
    }


def _event_dict(event: Any) -> dict[str, Any]:
    if hasattr(event, "to_dict"):
        return dict(event.to_dict())
    return dict(event)


def _last_run_events(events_by_run: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    if not events_by_run:
        return []
    return max(
        events_by_run.values(),
        key=lambda run_events: max(int(event.get("sequence", 0) or 0) for event in run_events),
    )


def _summarize_run(
    run_events: list[dict[str, Any]],
    agent_eval_report: dict[str, Any],
) -> dict[str, Any]:
    if not run_events:
        return {
            "run_id": "",
            "kind": "none",
            "status": "idle",
            "started_at": "",
            "completed_at": "",
            "duration_seconds": None,
            "event_count": 0,
        }
    run_id = str(run_events[-1].get("run_id") or "")
    started = next((event for event in run_events if event.get("type") == "run.started"), None)
    terminal = next(
        (
            event
            for event in reversed(run_events)
            if str(event.get("type")) in TERMINAL_EVENT_TYPES
        ),
        None,
    )
    status = _status_from_terminal_event(terminal)
    kind = _run_kind(started, terminal, agent_eval_report)
    return {
        "run_id": run_id,
        "kind": kind,
        "status": status,
        "started_at": str(started.get("created_at", "")) if started else "",
        "completed_at": str(terminal.get("created_at", "")) if terminal else "",
        "duration_seconds": _event_data(terminal).get("duration_seconds") if terminal else None,
        "event_count": len(run_events),
    }


def _status_from_terminal_event(event: dict[str, Any] | None) -> str:
    if event is None:
        return "running"
    event_type = str(event.get("type") or "")
    if event_type in {"run.failed", "run.stage.failed"}:
        return "failed"
    if event_type == "run.cancelled":
        return "cancelled"
    data_status = str(_event_data(event).get("status") or "complete")
    return _normalize_status(data_status)


def _normalize_status(status: str) -> str:
    lowered = status.lower()
    if lowered in {"pass", "passed", "ok", "success"}:
        return "complete"
    if lowered in {"fail", "error"}:
        return "failed"
    if lowered in {"complete", "warn", "failed", "cancelled", "running", "queued", "idle", "stopped"}:
        return lowered
    return "warn" if "warn" in lowered else lowered or "idle"


def _run_kind(
    started: dict[str, Any] | None,
    terminal: dict[str, Any] | None,
    agent_eval_report: dict[str, Any],
) -> str:
    for event in (started, terminal):
        data = _event_data(event)
        if data.get("kind"):
            return str(data["kind"])
    if agent_eval_report.get("id"):
        return "agent_eval_harness"
    return "unknown"


def _latest_failure(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in reversed(events):
        if str(event.get("type")) not in {"run.failed", "run.stage.failed"}:
            continue
        data = _event_data(event)
        return {
            "run_id": str(event.get("run_id") or ""),
            "sequence": int(event.get("sequence", 0) or 0),
            "created_at": str(event.get("created_at") or ""),
            "kind": str(data.get("kind") or data.get("phase") or "unknown"),
            "error": str(data.get("error") or "Run failed."),
        }
    return None


def _collect_artifacts(
    events: list[dict[str, Any]],
    agent_eval_report: dict[str, Any],
) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") != "artifact.persisted":
            continue
        data = _event_data(event)
        artifacts.append(
            {
                "run_id": str(event.get("run_id") or ""),
                "kind": str(data.get("kind") or "artifact"),
                "artifact_id": str(data.get("artifact_id") or ""),
                "sha256": str(data.get("sha256") or ""),
                "bytes": int(data.get("bytes", 0) or 0),
                "path": str(data.get("path") or ""),
            }
        )
    report_artifacts = agent_eval_report.get("artifacts", {})
    if isinstance(report_artifacts, dict):
        for value in report_artifacts.values():
            if isinstance(value, dict) and value.get("artifact_id"):
                artifacts.append(dict(value))
    return _dedupe_artifacts(artifacts)


def _dedupe_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for artifact in artifacts:
        key = str(artifact.get("artifact_id") or artifact.get("path") or artifact)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(artifact)
    return deduped


def _collect_warnings(
    agent_eval_report: dict[str, Any],
    mission_records: list[dict[str, Any]],
) -> list[str]:
    warnings: list[str] = []
    if _normalize_status(str(agent_eval_report.get("status", ""))) == "warn":
        warnings.append("Latest AgentEval run completed with warnings.")
    warnings.extend(_string_values(agent_eval_report.get("recommendations", [])))
    for mission in mission_records:
        if str(mission.get("status")) in {"stopped", "cancelled", "partial"}:
            warnings.append(f"Agent mission {mission.get('id')} is {mission.get('status')}.")
    return _unique(warnings)


def _collect_errors(
    events: list[dict[str, Any]],
    agent_eval_report: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    for event in events:
        if str(event.get("type")) in {"run.failed", "run.stage.failed"}:
            error = _event_data(event).get("error")
            if error:
                errors.append(str(error))
    metadata = agent_eval_report.get("metadata", {})
    if isinstance(metadata, dict):
        errors.extend(
            str(metadata[key])
            for key in ("agent_error", "evaluation_error")
            if metadata.get(key)
        )
    return _unique(errors)


def _resume_guidance(status: str, has_events: bool) -> dict[str, Any]:
    normalized = _normalize_status(status)
    if normalized == "failed":
        return {
            "resume_available": True,
            "resume_action": "rerun_agent_eval_harness",
            "next_best_action": "Inspect the last failure, then rerun AgentEval with deterministic settings.",
        }
    if normalized == "running":
        return {
            "resume_available": False,
            "resume_action": "wait_or_check_active_job",
            "next_best_action": "Check the active job or mission before starting another harness run.",
        }
    if normalized == "cancelled":
        return {
            "resume_available": True,
            "resume_action": "start_new_harness_run",
            "next_best_action": "Start a fresh harness run after confirming the cancellation was intentional.",
        }
    if has_events:
        return {
            "resume_available": True,
            "resume_action": "rerun_agent_eval_harness",
            "next_best_action": "Review artifacts and rerun AgentEval when archive inputs change.",
        }
    return {
        "resume_available": False,
        "resume_action": "run_agent_eval_harness",
        "next_best_action": "Run AgentEval to create the first harness event stream.",
    }


def _event_data(event: dict[str, Any] | None) -> dict[str, Any]:
    if not event:
        return {}
    data = event.get("data", {})
    return dict(data) if isinstance(data, dict) else {}


def _string_values(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value)]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values
