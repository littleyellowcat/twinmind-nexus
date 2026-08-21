"""Configurable TwinMind agent role profiles."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.project_archive.harness_policy import FORBIDDEN_CODING_AGENT_TOOLS


DEFAULT_AGENT_PROFILES = {
    "roles": {
        "archivist": {
            "purpose": "Select and organize project evidence.",
            "allowed_tools": ["list_halls", "get_evidence", "inspect_entity"],
            "disallowed_actions": ["final_risk_verdict", "archive_mutation"],
            "risk_level": "low",
        },
        "cartographer": {
            "purpose": "Map entities, halls, neighborhoods, and graph paths.",
            "allowed_tools": ["graph_summary", "graph_neighborhood", "graph_search"],
            "disallowed_actions": ["unsupported_architecture_claim", "archive_mutation"],
            "risk_level": "low",
        },
        "detective": {
            "purpose": "Perform architecture and impact reasoning over graph/RAG evidence.",
            "allowed_tools": ["hybrid_search", "inspect_entity", "graph_neighborhood", "get_evidence"],
            "disallowed_actions": ["uncited_summary", "external_api_call"],
            "risk_level": "medium",
        },
        "skeptic": {
            "purpose": "Challenge weak evidence, contradictions, and overclaims.",
            "allowed_tools": ["get_evidence", "graph_search", "graph_summary"],
            "disallowed_actions": ["archive_mutation", "final_report_without_citations"],
            "risk_level": "low",
        },
        "curator": {
            "purpose": "Compose final reports from prior cited Agent outputs.",
            "allowed_tools": ["get_evidence", "graph_summary"],
            "disallowed_actions": ["introduce_uncited_facts", "live_model_call_without_policy"],
            "risk_level": "medium",
        },
    }
}


@dataclass(frozen=True)
class AgentProfile:
    role: str
    purpose: str
    allowed_tools: list[str]
    disallowed_actions: list[str]
    risk_level: str
    evidence_requirements: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_agent_profiles(source: dict[str, Any] | str | Path | None = None) -> list[AgentProfile]:
    if source is None:
        payload = DEFAULT_AGENT_PROFILES
    elif isinstance(source, dict):
        payload = source
    else:
        path = Path(source)
        payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else DEFAULT_AGENT_PROFILES
    profiles = [
        _profile_from_dict(role, data)
        for role, data in dict(payload.get("roles", {})).items()
        if isinstance(data, dict)
    ]
    if not profiles:
        raise ValueError("At least one agent profile is required.")
    return profiles


def profiles_to_capability_matrix(profiles: list[AgentProfile]) -> dict[str, Any]:
    return {
        "roles": [profile.to_dict() for profile in profiles],
    }


def _profile_from_dict(role: str, data: dict[str, Any]) -> AgentProfile:
    allowed_tools = [str(item) for item in data.get("allowed_tools", [])]
    forbidden = sorted(set(allowed_tools) & FORBIDDEN_CODING_AGENT_TOOLS)
    if forbidden:
        raise ValueError(f"Forbidden tool in agent profile {role}: {', '.join(forbidden)}")
    return AgentProfile(
        role=str(role),
        purpose=str(data.get("purpose", "")),
        allowed_tools=allowed_tools,
        disallowed_actions=[str(item) for item in data.get("disallowed_actions", [])],
        risk_level=str(data.get("risk_level", "medium")),
        evidence_requirements=dict(data.get("evidence_requirements", {})),
    )
