"""Fine-grained role/tool/resource policy evaluation for TwinMind harness."""

from __future__ import annotations

import fnmatch
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

FORBIDDEN_CODING_AGENT_TOOLS = {
    "bash",
    "shell",
    "file_write",
    "file_edit",
    "apply_patch",
    "patch",
    "git_push",
    "deploy",
}

DEFAULT_POLICY_CONFIG = {
    "rules": [
        {
            "id": "deny-coding-agent-tools",
            "effect": "deny",
            "tool": sorted(FORBIDDEN_CODING_AGENT_TOOLS),
            "action": "*",
            "resource": "*",
            "reason": "Forbidden coding-agent tool is outside TwinMind's analysis boundary.",
        },
        {
            "id": "ask-live-model",
            "effect": "ask",
            "action": "live_model_call",
            "resource": "provider:*",
            "reason": "Live model calls may use credentials, network, or paid infrastructure.",
        },
        {
            "id": "ask-external-api",
            "effect": "ask",
            "action": "external_api_call",
            "resource": "*",
            "reason": "External API calls require explicit confirmation.",
        },
        {
            "id": "deny-production",
            "effect": "deny",
            "action": "production_operation",
            "resource": "*",
            "reason": "Production mutation is denied from TwinMind harness automation.",
        },
        {
            "id": "allow-local-read-write",
            "effect": "allow",
            "action": ["read_only", "local_artifact_write"],
            "resource": "*",
            "reason": "Local archive reads and harness artifact writes are inside the evidence boundary.",
        },
    ]
}


@dataclass(frozen=True)
class HarnessPolicyContext:
    role: str
    action: str
    tool: str
    resource: str
    project_id: str = ""
    run_id: str = ""
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["metadata"] = dict(self.metadata or {})
        return payload


@dataclass(frozen=True)
class HarnessPolicyRule:
    id: str
    effect: str
    reason: str
    role: list[str]
    action: list[str]
    tool: list[str]
    resource: list[str]
    priority: int = 100

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HarnessPolicyRule":
        return cls(
            id=str(data.get("id", "rule")),
            effect=str(data.get("effect", "ask")),
            reason=str(data.get("reason", "")),
            role=_patterns(data.get("role", "*")),
            action=_patterns(data.get("action", "*")),
            tool=_patterns(data.get("tool", "*")),
            resource=_patterns(data.get("resource", "*")),
            priority=int(data.get("priority", 100) or 100),
        )

    def matches(self, context: HarnessPolicyContext) -> bool:
        return (
            _matches_any(context.role, self.role)
            and _matches_any(context.action, self.action)
            and _matches_any(context.tool, self.tool)
            and _matches_any(context.resource, self.resource)
        )


@dataclass(frozen=True)
class HarnessPolicyDecision:
    effect: str
    reason: str
    rule_id: str
    context: HarnessPolicyContext

    def to_dict(self) -> dict[str, Any]:
        return {
            "effect": self.effect,
            "reason": self.reason,
            "rule_id": self.rule_id,
            "context": self.context.to_dict(),
        }


def load_default_policy_rules(config_path: str | Path | None = None) -> list[HarnessPolicyRule]:
    config = DEFAULT_POLICY_CONFIG
    if config_path:
        path = Path(config_path)
        if path.exists():
            config = json.loads(path.read_text(encoding="utf-8"))
    return [
        HarnessPolicyRule.from_dict(item)
        for item in config.get("rules", [])
        if isinstance(item, dict)
    ]


def evaluate_policy(
    context: HarnessPolicyContext,
    rules: list[HarnessPolicyRule] | None = None,
) -> HarnessPolicyDecision:
    if context.tool in FORBIDDEN_CODING_AGENT_TOOLS:
        return HarnessPolicyDecision(
            effect="deny",
            reason="Forbidden coding-agent tool is outside TwinMind's analysis boundary.",
            rule_id="deny-coding-agent-tools",
            context=context,
        )
    sorted_rules = sorted(rules or load_default_policy_rules(), key=lambda rule: rule.priority)
    for rule in sorted_rules:
        if rule.matches(context):
            return HarnessPolicyDecision(
                effect=rule.effect,
                reason=rule.reason,
                rule_id=rule.id,
                context=context,
            )
    return HarnessPolicyDecision(
        effect="ask",
        reason="No explicit policy rule matched this operation.",
        rule_id="default-ask",
        context=context,
    )


def _patterns(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _matches_any(value: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(value or "", pattern) for pattern in patterns)
