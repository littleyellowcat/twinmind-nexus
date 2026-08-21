"""Safe command registry for TwinMind harness operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.project_archive.harness_governance import build_harness_policy_check


@dataclass(frozen=True)
class HarnessCommand:
    id: str
    title: str
    description: str
    action: str
    resource_template: str
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_COMMANDS = [
    HarnessCommand(
        id="doctor",
        title="Harness Doctor",
        description="Inspect local harness storage and dependency readiness.",
        action="read_only",
        resource_template="harness:{project_id}",
    ),
    HarnessCommand(
        id="events",
        title="List Events",
        description="Read the project harness event timeline.",
        action="read_only",
        resource_template="events:{project_id}",
    ),
    HarnessCommand(
        id="export-harness",
        title="Export Harness",
        description="Build a redacted portable harness export.",
        action="local_artifact_write",
        resource_template="harness-export:{project_id}",
    ),
    HarnessCommand(
        id="artifacts",
        title="Validate Artifacts",
        description="Validate artifact manifests and list cleanup candidates.",
        action="read_only",
        resource_template="artifacts:{project_id}",
    ),
    HarnessCommand(
        id="agent-eval-live",
        title="AgentEval Live Provider",
        description="Prepare an AgentEval run that may use a configured model provider.",
        action="live_model_call",
        resource_template="provider:{provider}",
        requires_confirmation=True,
    ),
]


def list_harness_commands() -> list[dict[str, Any]]:
    """Return safe command metadata without process snippets."""

    return [command.to_dict() for command in DEFAULT_COMMANDS]


def run_harness_command(
    command_id: str,
    params: dict[str, Any] | None = None,
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Return a policy-checked command plan; execution is disabled by default."""

    command = _command_by_id(command_id)
    values = dict(params or {})
    project_id = str(values.get("project_id") or "unknown")
    provider = str(values.get("provider") or "configured")
    resource = command.resource_template.format(project_id=project_id, provider=provider)
    policy = build_harness_policy_check(
        action=command.action,
        resource=resource,
        provider_status={
            "role": values.get("role", "curator"),
            "tool": values.get("tool", command.id),
            "provider": provider,
            "model": values.get("model"),
            "llm_enabled": bool(values.get("llm_enabled", command.requires_confirmation)),
        },
    )
    return {
        "id": command.id,
        "dry_run": dry_run,
        "executed": False,
        "command": command.to_dict(),
        "params": values,
        "policy": policy,
        "status": "planned" if dry_run else "not_executed",
        "message": (
            "Dry-run command plan generated."
            if dry_run
            else "Direct execution is intentionally disabled for this registry."
        ),
    }


def _command_by_id(command_id: str) -> HarnessCommand:
    for command in DEFAULT_COMMANDS:
        if command.id == command_id:
            return command
    raise ValueError(f"Unknown harness command: {command_id}")
