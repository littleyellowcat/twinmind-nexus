"""Upload-triggered multi-agent analysis for TwinMind Archive."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from src.libs.llm import BaseLLM, Message
from src.project_archive.llm import create_archive_llm_enhancer_from_config
from src.project_archive.types import (
    AgentRoleResult,
    EvidenceCard,
    ProjectAgentReport,
    ProjectArchiveDraft,
    ProjectEntity,
    ProjectRelation,
)

AGENT_ORDER = ["archivist", "cartographer", "detective", "skeptic", "curator"]
JSON_OBJECT_RESPONSE_FORMAT = {"type": "json_object"}
STRUCTURED_ROLE_MAX_TOKENS = 2200
STRUCTURED_ROLE_RETRY_MAX_TOKENS = 4200


@dataclass(frozen=True)
class AgentSpec:
    """Runtime contract for one TwinMind archive agent."""

    name: str
    title: str
    mission: str
    depends_on: tuple[str, ...]
    expected_inputs: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    tools: tuple[str, ...]


AGENT_SPECS: dict[str, AgentSpec] = {
    "archivist": AgentSpec(
        name="archivist",
        title="Evidence Archivist",
        mission="Inventory project evidence, entry points, important paths, and source coverage.",
        depends_on=(),
        expected_inputs=("entities", "evidence_cards", "scan_profile"),
        expected_outputs=("evidence_card_ids", "entity_ids", "findings", "next_actions"),
        tools=("evidence_ranker", "entry_entity_detector", "important_path_counter"),
    ),
    "cartographer": AgentSpec(
        name="cartographer",
        title="Graph Cartographer",
        mission="Map entities, relations, halls, and cross-hall neighborhoods.",
        depends_on=("archivist",),
        expected_inputs=("halls", "entities", "relations", "archivist_handoff"),
        expected_outputs=("entity_ids", "relation_ids", "findings", "evidence_card_ids"),
        tools=("hall_mapper", "relation_sampler", "cross_hall_link_detector"),
    ),
    "detective": AgentSpec(
        name="detective",
        title="Architecture Detective",
        mission="Trace collaboration, impact paths, dependency hubs, and architecture behavior.",
        depends_on=("archivist", "cartographer"),
        expected_inputs=("relations", "cartographer_handoff", "archivist_handoff"),
        expected_outputs=("relation_ids", "evidence_card_ids", "findings", "risks"),
        tools=("relation_counter", "impact_path_tracer", "sparse_graph_detector"),
    ),
    "skeptic": AgentSpec(
        name="skeptic",
        title="Evidence Skeptic",
        mission="Challenge weak claims, missing evidence, sparse graphs, and stale implementation notes.",
        depends_on=("archivist", "cartographer", "detective"),
        expected_inputs=("previous_agent_outputs", "evidence_cards", "relations"),
        expected_outputs=("risks", "findings", "next_actions", "evidence_card_ids"),
        tools=("coverage_checker", "placeholder_detector", "handoff_validator"),
    ),
    "curator": AgentSpec(
        name="curator",
        title="Report Curator",
        mission="Synthesize prior agent outputs into one evidence-backed project briefing.",
        depends_on=("archivist", "cartographer", "detective", "skeptic"),
        expected_inputs=("all_agent_outputs", "project_metrics", "evidence_chain"),
        expected_outputs=("summary", "findings", "risks", "next_actions", "evidence_card_ids"),
        tools=("handoff_synthesizer", "risk_merger", "briefing_writer"),
    ),
}


class MultiAgentPipeline:
    """Run the five TwinMind archive agents over a project draft."""

    def __init__(self, llm: BaseLLM | None = None, provider: str = "rules") -> None:
        self.llm = llm
        self.provider = provider
        self.model = getattr(llm, "model", None)

    @classmethod
    def from_config(cls, llm_mode: str = "deep") -> MultiAgentPipeline:
        if llm_mode == "fast":
            return cls()
        enhancer = create_archive_llm_enhancer_from_config()
        if enhancer is None:
            return cls()
        if hasattr(enhancer.llm, "timeout"):
            enhancer.llm.timeout = max(float(getattr(enhancer.llm, "timeout", 60.0)), 120.0)
        return cls(llm=enhancer.llm, provider=enhancer.provider)

    def run(
        self,
        draft: ProjectArchiveDraft,
        scan_profile: str,
    ) -> ProjectAgentReport:
        agents: dict[str, AgentRoleResult] = {}
        errors: list[str] = []

        runners = {
            "archivist": self._run_archivist,
            "cartographer": self._run_cartographer,
            "detective": self._run_detective,
            "skeptic": self._run_skeptic,
            "curator": self._run_curator,
        }

        for agent_name in AGENT_ORDER:
            spec = AGENT_SPECS[agent_name]
            runner = runners[agent_name]
            started_at = datetime.now(UTC).isoformat()
            try:
                result = runner(draft, agents)
                result = _attach_agent_runtime_metadata(
                    result=result,
                    draft=draft,
                    spec=spec,
                    prior_agents=agents,
                    started_at=started_at,
                    completed_at=datetime.now(UTC).isoformat(),
                )
                agents[agent_name] = self._maybe_enhance_role(result, draft, agents)
            except Exception as exc:
                errors.append(f"{agent_name}: {exc}")
                fallback = AgentRoleResult(
                    agent=agent_name,
                    status="fallback",
                    summary=f"{agent_name} failed and produced a fallback result.",
                    confidence=0.1,
                    metadata={"error": str(exc)},
                )
                agents[agent_name] = _attach_agent_runtime_metadata(
                    result=fallback,
                    draft=draft,
                    spec=spec,
                    prior_agents=agents,
                    started_at=started_at,
                    completed_at=datetime.now(UTC).isoformat(),
                )

        status = "complete" if not errors else "partial"
        return ProjectAgentReport(
            project_id=draft.project_id,
            status=status,
            provider=self.provider,
            model=self.model,
            created_at=datetime.now(UTC).isoformat(),
            scan_profile=scan_profile,
            agents=agents,
            errors=errors,
            metrics={
                "halls": len(draft.halls),
                "entities": len(draft.entities),
                "relations": len(draft.relations),
                "evidence": len(draft.evidence_cards),
            },
        )

    def _run_archivist(
        self,
        draft: ProjectArchiveDraft,
        agents: dict[str, AgentRoleResult],
    ) -> AgentRoleResult:
        evidence = _top_evidence(draft.evidence_cards, limit=10)
        entry_entities = _entry_entities(draft.entities)
        important_paths = _important_paths(draft.evidence_cards)
        return AgentRoleResult(
            agent="archivist",
            status="complete",
            summary=(
                f"Archived {len(draft.evidence_cards)} evidence cards across "
                f"{len(important_paths)} important source paths."
            ),
            evidence_card_ids=[card.id for card in evidence],
            entity_ids=[entity.id for entity in entry_entities],
            findings=[
                {
                    "title": "Evidence inventory",
                    "detail": f"{len(draft.evidence_cards)} evidence cards are available.",
                    "evidence_ids": [card.id for card in evidence[:3]],
                },
                {
                    "title": "Important paths",
                    "detail": ", ".join(important_paths[:8]) or "No important paths identified.",
                    "evidence_ids": [],
                },
            ],
            next_actions=["Review high-confidence evidence cards before relying on generated claims."],
            confidence=0.75 if draft.evidence_cards else 0.25,
        )

    def _run_cartographer(
        self,
        draft: ProjectArchiveDraft,
        agents: dict[str, AgentRoleResult],
    ) -> AgentRoleResult:
        archivist = agents.get("archivist")
        archivist_entities = _unique(archivist.entity_ids if archivist else [])
        archivist_evidence = _unique(archivist.evidence_card_ids if archivist else [])
        relation_ids = [relation.id for relation in draft.relations[:20]]
        hall_findings = [
            {
                "title": hall.name,
                "detail": f"{len(hall.entity_ids)} entities mapped to this hall.",
                "entity_ids": hall.entity_ids[:8],
            }
            for hall in draft.halls
        ]
        cross_hall_relations = [
            relation
            for relation in draft.relations
            if _relation_crosses_halls(relation, draft)
        ][:8]
        if cross_hall_relations:
            hall_findings.append(
                {
                    "title": "Cross-hall links",
                    "detail": f"{len(cross_hall_relations)} relation(s) connect entities across halls.",
                    "relation_ids": [relation.id for relation in cross_hall_relations],
                    "evidence_ids": _evidence_ids_from_relations(cross_hall_relations)[:6],
                }
            )
        if archivist_entities or archivist_evidence:
            hall_findings.insert(
                0,
                {
                    "title": "Archivist handoff",
                    "detail": (
                        f"Received {len(archivist_entities)} entry/candidate entities and "
                        f"{len(archivist_evidence)} evidence cards from Archivist."
                    ),
                    "entity_ids": archivist_entities[:8],
                    "evidence_ids": archivist_evidence[:6],
                },
            )
        return AgentRoleResult(
            agent="cartographer",
            status="complete",
            summary=(
                f"Mapped {len(draft.entities)} entities and {len(draft.relations)} relations "
                f"into {len(draft.halls)} archive halls."
            ),
            entity_ids=_unique([*archivist_entities, *[entity.id for entity in draft.entities[:16]]]),
            relation_ids=_unique([*relation_ids, *[relation.id for relation in cross_hall_relations]]),
            evidence_card_ids=_unique(
                [*archivist_evidence, *_evidence_ids_from_relations(draft.relations)]
            )[:12],
            findings=hall_findings,
            next_actions=["Use cross-hall relation paths to inspect module collaboration."],
            confidence=0.72 if draft.relations else 0.35,
        )

    def _run_detective(
        self,
        draft: ProjectArchiveDraft,
        agents: dict[str, AgentRoleResult],
    ) -> AgentRoleResult:
        relation_counts = Counter(relation.type for relation in draft.relations)
        cartographer = agents.get("cartographer")
        relation_by_id = {relation.id: relation for relation in draft.relations}
        handoff_relation_ids = cartographer.relation_ids if cartographer else []
        key_relations = [
            relation_by_id[relation_id]
            for relation_id in handoff_relation_ids
            if relation_id in relation_by_id
        ][:12] or draft.relations[:12]
        findings = [
            {
                "title": f"{relation_type} relationships",
                "detail": f"{count} relation(s) found.",
                "evidence_ids": _evidence_ids_for_type(draft.relations, relation_type)[:4],
            }
            for relation_type, count in relation_counts.most_common(5)
        ]
        if not findings:
            findings = [
                {
                    "title": "Low relation coverage",
                    "detail": "Few graph relations were extracted; use full audit or language adapters.",
                    "evidence_ids": [],
                }
            ]
        if cartographer is not None:
            findings.insert(
                0,
                {
                    "title": "Cartographer handoff",
                    "detail": f"Analyzed {len(key_relations)} relation path(s) prioritized by Cartographer.",
                    "relation_ids": [relation.id for relation in key_relations],
                    "evidence_ids": _evidence_ids_from_relations(key_relations)[:6],
                },
            )
        return AgentRoleResult(
            agent="detective",
            status="complete",
            summary=(
                "Impact reasoning is based on extracted relation paths and file-level evidence."
            ),
            relation_ids=[relation.id for relation in key_relations],
            evidence_card_ids=_evidence_ids_from_relations(key_relations),
            findings=findings,
            risks=[
                {
                    "title": "Sparse graph",
                    "severity": "medium",
                    "detail": "Impact analysis may be shallow when relation extraction is sparse.",
                }
            ]
            if len(draft.relations) < max(5, len(draft.entities) // 5)
            else [],
            next_actions=["Trace top relation paths before changing central modules."],
            confidence=0.7 if draft.relations else 0.3,
        )

    def _run_skeptic(
        self,
        draft: ProjectArchiveDraft,
        agents: dict[str, AgentRoleResult],
    ) -> AgentRoleResult:
        findings: list[dict[str, Any]] = []
        risks: list[dict[str, Any]] = []
        for agent_name, result in agents.items():
            if not result.evidence_card_ids and agent_name != "cartographer":
                risks.append(
                    {
                        "title": f"{agent_name} has weak evidence grounding",
                        "severity": "medium",
                        "detail": "This role produced no direct evidence card references.",
                    }
                )
            if result.confidence < 0.5:
                risks.append(
                    {
                        "title": f"{agent_name} low confidence",
                        "severity": "medium",
                        "detail": f"Confidence is {result.confidence:.2f}; confirm manually.",
                    }
                )
        if agents:
            findings.append(
                {
                    "title": "Agent handoff review",
                    "detail": f"Reviewed {len(agents)} upstream agent output(s) for weak evidence and low confidence.",
                    "evidence_ids": _unique(
                        evidence_id
                        for result in agents.values()
                        for evidence_id in result.evidence_card_ids
                    )[:8],
                }
            )
        if len(draft.entities) < 20:
            risks.append(
                {
                    "title": "Low entity count",
                    "severity": "medium",
                    "detail": "The archive may have scanned only a small subset of the project.",
                }
            )
        if len(draft.relations) < 10:
            risks.append(
                {
                    "title": "Low relation count",
                    "severity": "medium",
                    "detail": "Graph reasoning is limited by sparse extracted relations.",
                }
            )
        placeholder_evidence = [
            card
            for card in draft.evidence_cards
            if any(term in card.snippet.lower() for term in ("todo", "fixme", "placeholder"))
        ][:8]
        risks.extend(
            {
                "title": "Placeholder or TODO evidence",
                "severity": "low",
                "detail": card.source_path,
                "evidence_ids": [card.id],
            }
            for card in placeholder_evidence
        )
        return AgentRoleResult(
            agent="skeptic",
            status="complete",
            summary=f"Found {len(risks)} validation concern(s).",
            evidence_card_ids=[card.id for card in placeholder_evidence],
            findings=findings,
            risks=risks,
            next_actions=[
                "Use full audit when entity or relation coverage looks too low.",
                "Manually confirm claims with weak evidence coverage.",
            ],
            confidence=0.76,
        )

    def _run_curator(
        self,
        draft: ProjectArchiveDraft,
        agents: dict[str, AgentRoleResult],
    ) -> AgentRoleResult:
        risk_count = sum(len(result.risks) for result in agents.values())
        evidence_ids: list[str] = []
        for result in agents.values():
            evidence_ids.extend(result.evidence_card_ids)
        evidence_ids = _unique(evidence_ids)[:12]
        return AgentRoleResult(
            agent="curator",
            status="complete",
            summary=(
                f"{draft.project_id} contains {len(draft.entities)} entities, "
                f"{len(draft.relations)} relations, and {risk_count} flagged review point(s)."
            ),
            evidence_card_ids=evidence_ids,
            findings=[
                {
                    "title": "Project briefing",
                    "detail": "The archive is ready for hall navigation, evidence review, and Agent QA.",
                    "evidence_ids": evidence_ids[:4],
                }
            ],
            risks=[
                risk
                for result in agents.values()
                for risk in result.risks
            ][:8],
            next_actions=[
                "Open the architecture hall first.",
                "Inspect cited evidence cards before trusting high-level conclusions.",
                "Run full audit if coverage is unexpectedly low.",
            ],
            confidence=0.78 if draft.evidence_cards else 0.35,
        )

    def _maybe_enhance_role(
        self,
        result: AgentRoleResult,
        draft: ProjectArchiveDraft,
        agents: dict[str, AgentRoleResult],
    ) -> AgentRoleResult:
        if self.llm is None:
            return result
        try:
            payload = _call_role_llm(self.llm, result, draft, agents)
            used_plain_text_fallback = bool(payload.pop("__llm_fallback", False))
            used_json_repair = bool(payload.pop("__json_repaired", False))
            used_json_regeneration = bool(payload.pop("__json_regenerated", False))
            return AgentRoleResult(
                agent=result.agent,
                status="complete",
                summary=_string_value(payload.get("summary"), result.summary),
                evidence_card_ids=_validated_ids(
                    payload.get("evidence_card_ids"),
                    {card.id for card in draft.evidence_cards},
                    result.evidence_card_ids,
                ),
                entity_ids=result.entity_ids,
                relation_ids=result.relation_ids,
                findings=_dict_list(payload.get("findings"), result.findings),
                risks=_dict_list(payload.get("risks"), result.risks),
                next_actions=_string_list(payload.get("next_actions"), result.next_actions),
                confidence=_confidence(payload.get("confidence"), result.confidence),
                metadata={
                    **result.metadata,
                    "llm": {
                        "enabled": True,
                        "provider": self.provider,
                        "model": self.model,
                        **({"fallback": True} if used_plain_text_fallback else {}),
                        **({"json_repaired": True} if used_json_repair else {}),
                        **({"json_regenerated": True} if used_json_regeneration else {}),
                    },
                },
            )
        except Exception as exc:
            return AgentRoleResult(
                **{
                    **result.to_dict(),
                    "status": "fallback",
                    "metadata": {
                        **result.metadata,
                        "llm": {
                            "enabled": True,
                            "provider": self.provider,
                            "model": self.model,
                            "fallback": True,
                            "error": str(exc),
                        },
                    },
                }
            )


def _call_role_llm(
    llm: BaseLLM,
    result: AgentRoleResult,
    draft: ProjectArchiveDraft,
    agents: dict[str, AgentRoleResult],
) -> dict[str, Any]:
    evidence = _top_evidence(draft.evidence_cards, limit=4)
    prompt = {
        "role": result.agent,
        "project_id": draft.project_id,
        "metrics": {
            "entities": len(draft.entities),
            "relations": len(draft.relations),
            "evidence": len(draft.evidence_cards),
        },
        "current_result": result.to_dict(),
        "previous_agent_summaries": {
            name: agent.summary for name, agent in agents.items()
        },
        "evidence_cards": [
            {
                "id": card.id,
                "path": card.source_path,
                "title": card.title,
                "snippet": card.snippet[:360],
            }
            for card in evidence
        ],
        "instructions": (
            "Improve the current role result using only provided evidence. "
            "Return JSON with summary, findings, risks, next_actions, "
            "evidence_card_ids, confidence. Return one json object only, without "
            "Markdown fences, prose, or comments. Do not wrap the JSON in a string. "
            "Use this exact top-level schema: "
            "{summary:string, findings:array, risks:array, next_actions:array, "
            "evidence_card_ids:array, confidence:number}. "
            'Example json output: {"summary":"...","findings":[],"risks":[],"next_actions":[],"evidence_card_ids":[],"confidence":0.8}. '
            "Answer Chinese user-facing text in Chinese."
        ),
    }
    messages = [
        Message(
            role="system",
            content=(
                "You are one role in TwinMind Archive's project analysis pipeline. "
                "Return one json object only. Do not include Markdown fences, prose, or comments."
            ),
        ),
        Message(role="user", content=json.dumps(prompt, ensure_ascii=False)),
    ]
    response = llm.chat(
        messages,
        temperature=0.0,
        max_tokens=STRUCTURED_ROLE_MAX_TOKENS,
        response_format=JSON_OBJECT_RESPONSE_FORMAT,
    )
    try:
        return _normalize_role_llm_payload(_parse_json_object(response.content))
    except ValueError as first_error:
        try:
            payload = _regenerate_role_json_response(
                llm=llm,
                original_prompt=prompt,
                raw_content=response.content,
                error=str(first_error),
            )
            payload["__json_regenerated"] = True
            return _normalize_role_llm_payload(payload)
        except ValueError:
            pass
        try:
            payload = _repair_role_json_response(
                llm=llm,
                raw_content=response.content,
                result=result,
            )
            payload["__json_repaired"] = True
            return _normalize_role_llm_payload(payload)
        except ValueError:
            pass
        summary = _strip_fences(response.content).strip()
        if not summary:
            raise
        return {
            "summary": summary[:1200],
            "findings": result.findings,
            "risks": result.risks,
            "next_actions": result.next_actions,
            "evidence_card_ids": result.evidence_card_ids,
            "confidence": min(0.72, result.confidence),
            "__llm_fallback": True,
        }


def _regenerate_role_json_response(
    *,
    llm: BaseLLM,
    original_prompt: dict[str, Any],
    raw_content: str,
    error: str,
) -> dict[str, Any]:
    retry_payload = {
        "task": "Regenerate the Agent role result as one valid json object.",
        "error": error[:300],
        "previous_invalid_response": raw_content[:1200],
        "required_schema": {
            "summary": "string",
            "findings": [{"title": "string", "detail": "string", "evidence_ids": ["string"]}],
            "risks": [{"title": "string", "detail": "string", "severity": "low|medium|high"}],
            "next_actions": ["string"],
            "evidence_card_ids": ["string"],
            "confidence": "number between 0 and 1",
        },
        "original_prompt": original_prompt,
        "rules": [
            "Return one json object only.",
            "Do not include Markdown fences, analysis, or prose outside the json object.",
            "Use only evidence_card_ids present in original_prompt.evidence_cards.",
            "If uncertain, keep deterministic current_result values and lower confidence.",
        ],
    }
    retry_response = llm.chat(
        [
            Message(
                role="system",
                content=(
                    "The previous structured Agent response was invalid. "
                    "Regenerate it as strict json only. No prose. No Markdown fences."
                ),
            ),
            Message(role="user", content=json.dumps(retry_payload, ensure_ascii=False)),
        ],
        temperature=0.0,
        max_tokens=STRUCTURED_ROLE_RETRY_MAX_TOKENS,
        response_format=JSON_OBJECT_RESPONSE_FORMAT,
    )
    return _parse_json_object(retry_response.content)


def _normalize_role_llm_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle models that return a JSON object string inside the summary field."""
    summary = payload.get("summary")
    if not isinstance(summary, str):
        return payload
    try:
        nested = _parse_json_object(summary)
    except ValueError:
        return payload
    normalized = dict(payload)
    for key in (
        "summary",
        "findings",
        "risks",
        "next_actions",
        "evidence_card_ids",
        "confidence",
    ):
        if key in nested and (key == "summary" or not normalized.get(key)):
            normalized[key] = nested[key]
    normalized["__json_repaired"] = bool(normalized.get("__json_repaired", False))
    return normalized


def _attach_agent_runtime_metadata(
    *,
    result: AgentRoleResult,
    draft: ProjectArchiveDraft,
    spec: AgentSpec,
    prior_agents: dict[str, AgentRoleResult],
    started_at: str,
    completed_at: str,
) -> AgentRoleResult:
    validation = _validate_agent_result(result, draft, spec, prior_agents)
    runtime_metadata = {
        "spec_version": "twinmind-agent-spec-v1",
        "name": spec.name,
        "title": spec.title,
        "mission": spec.mission,
        "depends_on": list(spec.depends_on),
        "expected_inputs": list(spec.expected_inputs),
        "expected_outputs": list(spec.expected_outputs),
        "tools": list(spec.tools),
        "started_at": started_at,
        "completed_at": completed_at,
        "input_counts": {
            "halls": len(draft.halls),
            "entities": len(draft.entities),
            "relations": len(draft.relations),
            "evidence_cards": len(draft.evidence_cards),
            "prior_agents": len(prior_agents),
        },
        "handoffs": {
            name: {
                "status": agent.status,
                "confidence": agent.confidence,
                "summary": agent.summary[:300],
                "evidence_card_ids": agent.evidence_card_ids[:8],
                "entity_ids": agent.entity_ids[:8],
                "relation_ids": agent.relation_ids[:8],
            }
            for name, agent in prior_agents.items()
        },
        "work_log": _agent_work_log(result, spec, validation),
        "validation": validation,
    }
    return AgentRoleResult(
        **{
            **result.to_dict(),
            "metadata": {
                **result.metadata,
                "agent_sdk": runtime_metadata,
            },
        }
    )


def _validate_agent_result(
    result: AgentRoleResult,
    draft: ProjectArchiveDraft,
    spec: AgentSpec,
    prior_agents: dict[str, AgentRoleResult],
) -> dict[str, Any]:
    evidence_ids = {card.id for card in draft.evidence_cards}
    entity_ids = {entity.id for entity in draft.entities}
    relation_ids = {relation.id for relation in draft.relations}
    missing_dependencies = [
        dependency for dependency in spec.depends_on if dependency not in prior_agents
    ]
    invalid_evidence_ids = [
        evidence_id for evidence_id in result.evidence_card_ids if evidence_id not in evidence_ids
    ]
    invalid_entity_ids = [
        entity_id for entity_id in result.entity_ids if entity_id not in entity_ids
    ]
    invalid_relation_ids = [
        relation_id for relation_id in result.relation_ids if relation_id not in relation_ids
    ]
    missing_outputs = [
        output
        for output in spec.expected_outputs
        if output != "summary" and not getattr(result, output, None)
    ]
    notes: list[str] = []
    if not result.summary.strip():
        notes.append("summary is empty")
    if result.confidence < 0.5:
        notes.append("confidence is below 0.5")
    if not result.evidence_card_ids and spec.name in {"archivist", "detective", "curator"}:
        notes.append("direct evidence references are empty")

    blocking = (
        missing_dependencies
        or invalid_evidence_ids
        or invalid_entity_ids
        or invalid_relation_ids
        or not result.summary.strip()
    )
    status = "needs_review" if blocking or notes else "accepted"
    return {
        "status": status,
        "missing_dependencies": missing_dependencies,
        "missing_outputs": missing_outputs,
        "invalid_evidence_ids": invalid_evidence_ids,
        "invalid_entity_ids": invalid_entity_ids,
        "invalid_relation_ids": invalid_relation_ids,
        "notes": notes,
    }


def _agent_work_log(
    result: AgentRoleResult,
    spec: AgentSpec,
    validation: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "step": "load_contract",
            "detail": f"Loaded {spec.title} contract and dependencies.",
            "tools": [],
        },
        {
            "step": "run_tools",
            "detail": f"Executed {len(spec.tools)} deterministic tool(s).",
            "tools": list(spec.tools),
        },
        {
            "step": "produce_structured_output",
            "detail": (
                f"Produced {len(result.findings)} finding(s), {len(result.risks)} risk(s), "
                f"{len(result.next_actions)} next action(s)."
            ),
            "tools": [],
        },
        {
            "step": "validate_grounding",
            "detail": f"Validation status: {validation['status']}.",
            "tools": ["output_validator"],
        },
    ]


def _relation_crosses_halls(
    relation: ProjectRelation,
    draft: ProjectArchiveDraft,
) -> bool:
    hall_ids_by_entity: dict[str, set[str]] = {}
    for hall in draft.halls:
        for entity_id in hall.entity_ids:
            hall_ids_by_entity.setdefault(entity_id, set()).add(hall.id)
    source_halls = hall_ids_by_entity.get(relation.source_id, set())
    target_halls = hall_ids_by_entity.get(relation.target_id, set())
    return bool(source_halls and target_halls and source_halls != target_halls)


def _top_evidence(evidence_cards: list[EvidenceCard], limit: int) -> list[EvidenceCard]:
    return sorted(evidence_cards, key=lambda card: card.confidence, reverse=True)[:limit]


def _entry_entities(entities: list[ProjectEntity]) -> list[ProjectEntity]:
    keywords = ("main", "app", "server", "cli", "index", "application")
    entries = [
        entity
        for entity in entities
        if entity.type == "File"
        and any(keyword in entity.name.lower() for keyword in keywords)
    ]
    return entries[:10] or [entity for entity in entities if entity.type == "File"][:10]


def _important_paths(evidence_cards: list[EvidenceCard]) -> list[str]:
    counts = Counter(card.source_path for card in evidence_cards)
    return [path for path, _ in counts.most_common(12)]


def _evidence_ids_from_relations(relations: list[ProjectRelation]) -> list[str]:
    return _unique(
        evidence_id
        for relation in relations
        for evidence_id in relation.evidence_ids
    )


def _evidence_ids_for_type(
    relations: list[ProjectRelation],
    relation_type: str,
) -> list[str]:
    return _evidence_ids_from_relations(
        [relation for relation in relations if relation.type == relation_type]
    )


def _unique(values) -> list[str]:  # noqa: ANN001
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            rows.append(value)
            seen.add(value)
    return rows


def _parse_json_object(content: str) -> dict[str, Any]:
    stripped = _strip_fences(content).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        if not match:
            raise ValueError("LLM response did not contain JSON.")
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON must be an object.")
    return parsed


def _repair_role_json_response(
    *,
    llm: BaseLLM,
    raw_content: str,
    result: AgentRoleResult,
) -> dict[str, Any]:
    repair_payload = {
        "task": "Convert the model response into one valid JSON object for this Agent role.",
        "schema": {
            "summary": "string",
            "findings": [{"title": "string", "detail": "string", "evidence_ids": ["string"]}],
            "risks": [{"title": "string", "detail": "string", "severity": "low|medium|high"}],
            "next_actions": ["string"],
            "evidence_card_ids": ["string"],
            "confidence": "number between 0 and 1",
        },
        "fallback_payload": {
            "summary": result.summary,
            "findings": result.findings,
            "risks": result.risks,
            "next_actions": result.next_actions,
            "evidence_card_ids": result.evidence_card_ids,
            "confidence": result.confidence,
        },
        "model_response": raw_content,
        "rules": [
            "Return JSON only.",
            "Do not add Markdown fences.",
            "Do not invent evidence_card_ids; use fallback_payload evidence_card_ids when unsure.",
            "Preserve useful content from model_response in summary and findings.",
        ],
    }
    repair_response = llm.chat(
        [
            Message(
                role="system",
                content=(
                    "You are a strict JSON repair adapter for an Agent pipeline. "
                    "Return one valid json object only, with no prose and no Markdown fences."
                ),
            ),
            Message(role="user", content=json.dumps(repair_payload, ensure_ascii=False)),
        ],
        temperature=0.0,
        max_tokens=STRUCTURED_ROLE_MAX_TOKENS,
        response_format=JSON_OBJECT_RESPONSE_FORMAT,
    )
    return _parse_json_object(repair_response.content)


def _strip_fences(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped


def _string_value(value: Any, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        nested = _parse_nested_json_object(value)
        if nested is not None:
            nested_summary = nested.get("summary")
            if isinstance(nested_summary, str) and nested_summary.strip():
                return nested_summary.strip()
        return value.strip()
    return fallback


def _string_list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        rows = [str(item).strip() for item in value if str(item).strip()]
        if rows:
            return rows
    return fallback


def _dict_list(value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(value, list):
        rows = [item for item in value if isinstance(item, dict)]
        if rows:
            return rows
    return fallback


def _parse_nested_json_object(value: str) -> dict[str, Any] | None:
    stripped = _strip_fences(value).strip()
    if not stripped.startswith("{"):
        return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _validated_ids(value: Any, allowed: set[str], fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return fallback
    rows = [str(item) for item in value if str(item) in allowed]
    return rows or fallback


def _confidence(value: Any, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return min(1.0, max(0.0, number))


def run_specialist_role(
    draft: ProjectArchiveDraft,
    role: str,
    prior_agents: dict[str, AgentRoleResult] | None = None,
) -> AgentRoleResult:
    """Run one deterministic specialist role with its missing dependencies."""

    pipeline = MultiAgentPipeline()
    agents = dict(prior_agents or {})
    runners = {
        "archivist": pipeline._run_archivist,
        "cartographer": pipeline._run_cartographer,
        "detective": pipeline._run_detective,
        "skeptic": pipeline._run_skeptic,
        "curator": pipeline._run_curator,
    }

    def run_role(agent_name: str) -> None:
        if agent_name in agents:
            return
        runner = runners.get(agent_name)
        spec = AGENT_SPECS.get(agent_name)
        if runner is None or spec is None:
            raise ValueError(f"Unknown specialist role: {agent_name}")
        for dependency in spec.depends_on:
            run_role(dependency)
        started_at = datetime.now(UTC).isoformat()
        result = runner(draft, agents)
        agents[agent_name] = _attach_agent_runtime_metadata(
            result=result,
            draft=draft,
            spec=spec,
            prior_agents=agents,
            started_at=started_at,
            completed_at=datetime.now(UTC).isoformat(),
        )

    if role not in runners:
        raise ValueError(f"Unknown specialist role: {role}")
    run_role(role)
    return agents[role]
