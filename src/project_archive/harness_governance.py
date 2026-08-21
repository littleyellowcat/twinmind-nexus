"""Governance rules and role capabilities for TwinMind harness runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.project_archive.agent_profiles import load_agent_profiles, profiles_to_capability_matrix
from src.project_archive.harness_policy import (
    FORBIDDEN_CODING_AGENT_TOOLS,
    HarnessPolicyContext,
    evaluate_policy,
)


DEFAULT_OPERATION_RULES = {
    "read_only": "allow",
    "local_artifact_write": "allow",
    "live_model_call": "ask",
    "external_api_call": "ask",
    "paid_operation": "ask",
    "production_operation": "deny",
}

PROVIDER_POLICY = {
    "live_model_call": {
        "default_effect": "ask",
        "reason": "Live provider calls can spend tokens, depend on credentials, or cross a local/runtime boundary.",
    },
    "external_api_call": {
        "default_effect": "ask",
        "reason": "External API calls depend on network reachability and may pull untrusted or rate-limited data.",
    },
    "paid_operation": {
        "default_effect": "ask",
        "reason": "Paid operations require explicit confirmation before use.",
    },
    "tests": {
        "real_external_calls_disabled_by_default": True,
        "credential_values_are_never_returned": True,
    },
}

@dataclass(frozen=True)
class HarnessGovernanceDecision:
    action: str
    resource: str
    effect: str
    reason: str
    rule_source: str = "default_harness_policy"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def evaluate_harness_operation(action: str, resource: str) -> HarnessGovernanceDecision:
    normalized_action = action.strip() or "read_only"
    effect = DEFAULT_OPERATION_RULES.get(normalized_action, "ask")
    reasons = {
        "allow": "Operation is inside TwinMind's local, evidence-preserving harness boundary.",
        "ask": "Operation may call live providers, external services, or paid infrastructure.",
        "deny": "Operation is outside TwinMind's analysis boundary and must not run automatically.",
    }
    return HarnessGovernanceDecision(
        action=normalized_action,
        resource=resource,
        effect=effect,
        reason=reasons[effect],
    )


def build_harness_policy_check(
    *,
    action: str,
    resource: str,
    provider_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return an opencode-style dry-run policy decision without secrets."""

    context = HarnessPolicyContext(
        role=str((provider_status or {}).get("role") or "system"),
        action=action,
        tool=str((provider_status or {}).get("tool") or action),
        resource=resource,
    )
    policy_decision = evaluate_policy(context)
    legacy_decision = evaluate_harness_operation(action, resource)
    effect = policy_decision.effect
    next_actions = {
        "allow": "Proceed without additional confirmation inside the local harness boundary.",
        "ask": "Request explicit confirmation before calling live providers or paid/external services.",
        "deny": "Do not execute this operation from TwinMind harness automation.",
    }
    return {
        "dry_run": True,
        "action": legacy_decision.action,
        "resource": resource,
        "decision": {
            **legacy_decision.to_dict(),
            "effect": effect,
            "reason": policy_decision.reason,
            "rule_source": policy_decision.rule_id,
        },
        "policy_decision": policy_decision.to_dict(),
        "allowed_without_confirmation": effect == "allow",
        "requires_confirmation": effect == "ask",
        "denied": effect == "deny",
        "provider": _safe_provider_status(provider_status or {}),
        "policy": dict(PROVIDER_POLICY),
        "next_required_action": next_actions[effect],
    }


def harness_capability_matrix() -> dict[str, object]:
    matrix = profiles_to_capability_matrix(load_agent_profiles())
    return {
        "roles": matrix["roles"],
        "governance": {
            "default_rules": dict(DEFAULT_OPERATION_RULES),
            "provider_policy": dict(PROVIDER_POLICY),
            "forbidden_coding_agent_tools": sorted(FORBIDDEN_CODING_AGENT_TOOLS),
            "policy": "TwinMind agents analyze archives and evidence; they do not execute shell, edit files, deploy, or push code.",
        },
    }


def _safe_provider_status(provider_status: dict[str, Any]) -> dict[str, Any]:
    provider = str(provider_status.get("provider") or "unknown")
    model = provider_status.get("model")
    mode = str(provider_status.get("mode") or "")
    configured = bool(
        provider_status.get("configured")
        or provider_status.get("working")
        or provider_status.get("llm_enabled")
    )
    return {
        "provider": provider,
        "mode": mode,
        "model": str(model) if model else None,
        "configured": configured,
        "llm_enabled": bool(provider_status.get("llm_enabled", configured)),
        "working": bool(provider_status.get("working", configured)),
        "external_reachability_checked": bool(provider_status.get("external_reachability_checked", False)),
    }
