"""LLM enhancement for TwinMind Archive agent reports."""

from __future__ import annotations

import json
import os
import re
from dataclasses import is_dataclass, replace
from typing import Any

from src.core.settings import load_settings
from src.libs.llm import BaseLLM, LLMFactory, Message
from src.project_archive.types import (
    AgentResult,
    EvidenceCard,
    ProjectEntity,
    ProjectRelation,
)

DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
JSON_OBJECT_RESPONSE_FORMAT = {"type": "json_object"}
STRUCTURED_AGENT_MAX_TOKENS = 1800


class ArchiveLLMEnhancer:
    """Use a chat LLM to turn deterministic graph evidence into a report."""

    def __init__(self, llm: BaseLLM, provider: str = "deepseek") -> None:
        self.llm = llm
        self.provider = provider

    def enhance(
        self,
        result: AgentResult,
        *,
        evidence_cards: list[EvidenceCard],
        entities: list[ProjectEntity],
        relations: list[ProjectRelation],
    ) -> AgentResult:
        selected_evidence = _select_evidence(result, evidence_cards)
        messages = [
            Message(
                role="system",
                content=(
                    "You are TwinMind Archive's project-analysis agent. "
                    "Write concise bilingual-friendly analysis grounded only in the provided "
                    "project archive evidence. Do not invent files, APIs, or dependencies. "
                    "Return one json object only. Do not include Markdown fences, prose, or comments. "
                    'Example json output: {"summary":"...","risks":[],"next_actions":[],"evidence_card_ids":[],"confidence":0.8}'
                ),
            ),
            Message(
                role="user",
                content=_build_prompt(
                    result=result,
                    evidence_cards=selected_evidence,
                    entities=entities,
                    relations=relations,
                ),
            ),
        ]
        response = self.llm.chat(
            messages,
            temperature=0.0,
            max_tokens=STRUCTURED_AGENT_MAX_TOKENS,
            response_format=JSON_OBJECT_RESPONSE_FORMAT,
        )
        try:
            payload = _parse_json_object(response.content)
        except ValueError as exc:
            try:
                payload = _repair_json_response(
                    llm=self.llm,
                    raw_content=response.content,
                    schema=_agent_result_schema(),
                    fallback_payload={
                        "summary": result.summary,
                        "risks": result.risks,
                        "next_actions": result.next_actions,
                        "evidence_card_ids": result.evidence_card_ids,
                        "confidence": result.confidence,
                    },
                )
                payload["__json_repaired"] = True
            except ValueError as repair_exc:
                return _fallback_from_plain_text_response(
                    result=result,
                    response_content=response.content,
                    response_model=response.model,
                    response_usage=response.usage,
                    provider=self.provider,
                    error=f"{exc}; repair failed: {repair_exc}",
                )
        evidence_ids = _validated_ids(
            payload.get("evidence_card_ids"),
            {card.id for card in selected_evidence},
            result.evidence_card_ids,
        )
        metadata = {
            **result.metadata,
            "llm": {
                "enabled": True,
                "provider": self.provider,
                "model": response.model,
                "usage": response.usage,
                **({"json_repaired": True} if payload.get("__json_repaired") else {}),
            },
        }
        return replace(
            result,
            summary=_string_value(payload.get("summary"), result.summary),
            risks=_string_list(payload.get("risks"), result.risks),
            next_actions=_string_list(payload.get("next_actions"), result.next_actions),
            evidence_card_ids=evidence_ids,
            confidence=_confidence(payload.get("confidence"), result.confidence),
            metadata=metadata,
        )


def create_archive_llm_enhancer_from_config() -> ArchiveLLMEnhancer | None:
    """Create a DeepSeek-backed enhancer from settings.yaml and env overrides."""
    enabled = os.getenv("TWINMIND_AGENT_LLM_ENABLED", "auto").strip().lower()
    if enabled in {"0", "false", "no", "off"}:
        return None

    try:
        settings = load_settings()
    except Exception:
        return None

    if settings.llm.provider.lower() != "deepseek":
        return None

    api_key = _configured_secret(
        os.getenv("DEEPSEEK_API_KEY") or settings.llm.api_key
    )
    if api_key is None:
        return None

    settings = _replace_llm_settings(
        settings,
        model=os.getenv("TWINMIND_DEEPSEEK_MODEL")
        or settings.llm.model
        or DEFAULT_DEEPSEEK_MODEL,
        temperature=_env_float(
            "TWINMIND_DEEPSEEK_TEMPERATURE", settings.llm.temperature
        ),
        max_tokens=_env_int("TWINMIND_DEEPSEEK_MAX_TOKENS", settings.llm.max_tokens),
    )
    timeout_seconds = _env_float(
        "TWINMIND_DEEPSEEK_TIMEOUT_SECONDS",
        getattr(settings.llm, "timeout_seconds", 60.0),
    )
    llm = LLMFactory.create(
        settings,
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL") or settings.llm.base_url or DEFAULT_DEEPSEEK_BASE_URL,
        timeout=timeout_seconds,
    )
    return ArchiveLLMEnhancer(llm=llm, provider="deepseek")


def create_archive_llm_enhancer_from_env() -> ArchiveLLMEnhancer | None:
    """Backward-compatible alias for the config-driven enhancer factory."""
    return create_archive_llm_enhancer_from_config()


def _configured_secret(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    placeholders = {
        "YOUR_API_KEY_HERE",
        "YOUR_DEEPSEEK_API_KEY_HERE",
        "sk-xxxxxxxx",
    }
    if stripped in placeholders or stripped.startswith("YOUR_"):
        return None
    return stripped


def _env_float(name: str, fallback: float) -> float:
    value = os.getenv(name)
    if value is None:
        return fallback
    try:
        return float(value)
    except ValueError:
        return fallback


def _env_int(name: str, fallback: int) -> int:
    value = os.getenv(name)
    if value is None:
        return fallback
    try:
        return int(value)
    except ValueError:
        return fallback


def _replace_llm_settings(settings: Any, **updates: Any) -> Any:
    if is_dataclass(settings) and is_dataclass(settings.llm):
        return replace(settings, llm=replace(settings.llm, **updates))
    for key, value in updates.items():
        setattr(settings.llm, key, value)
    return settings


def _build_prompt(
    *,
    result: AgentResult,
    evidence_cards: list[EvidenceCard],
    entities: list[ProjectEntity],
    relations: list[ProjectRelation],
) -> str:
    entity_lookup = {entity.id: entity for entity in entities}
    affected_entities = [
        _entity_row(entity_lookup[entity_id])
        for entity_id in result.affected_entities[:12]
        if entity_id in entity_lookup
    ]
    relation_rows = [
        {
            "id": relation.id,
            "type": relation.type,
            "source_id": relation.source_id,
            "target_id": relation.target_id,
            "evidence_ids": relation.evidence_ids,
        }
        for relation in relations[:20]
    ]
    evidence_rows = [
        {
            "id": card.id,
            "source_type": card.source_type,
            "source_path": card.source_path,
            "title": card.title,
            "line_start": card.line_start,
            "line_end": card.line_end,
            "snippet": card.snippet[:900],
        }
        for card in evidence_cards
    ]
    payload = {
        "question": result.question,
        "mode": result.mode.value,
        "deterministic_summary": result.summary,
        "affected_entities": affected_entities,
        "relations_sample": relation_rows,
        "evidence_cards": evidence_rows,
        "deterministic_risks": result.risks,
        "deterministic_next_actions": result.next_actions,
        "required_json_schema": {
            **_agent_result_schema(),
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _entity_row(entity: ProjectEntity) -> dict[str, Any]:
    return {
        "id": entity.id,
        "type": entity.type,
        "name": entity.name,
        "source_path": entity.source_path,
    }


def _select_evidence(
    result: AgentResult,
    evidence_cards: list[EvidenceCard],
    limit: int = 8,
) -> list[EvidenceCard]:
    by_id = {card.id: card for card in evidence_cards}
    selected = [by_id[evidence_id] for evidence_id in result.evidence_card_ids if evidence_id in by_id]
    if len(selected) < limit:
        seen = {card.id for card in selected}
        selected.extend(card for card in evidence_cards if card.id not in seen)
    return selected[:limit]


def _parse_json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        if not match:
            raise ValueError("LLM response did not contain a JSON object.")
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON must be an object.")
    return parsed


def _repair_json_response(
    *,
    llm: BaseLLM,
    raw_content: str,
    schema: dict[str, Any],
    fallback_payload: dict[str, Any],
) -> dict[str, Any]:
    repair_payload = {
        "task": "Convert the model response into one valid JSON object that matches the schema.",
        "schema": schema,
        "fallback_payload": fallback_payload,
        "model_response": raw_content,
        "rules": [
            "Return JSON only.",
            "Do not add Markdown fences.",
            "Do not invent evidence_card_ids; use fallback_payload evidence_card_ids when unsure.",
            "Preserve the useful meaning of model_response in summary.",
        ],
    }
    repair_response = llm.chat(
        [
            Message(
                role="system",
                content=(
                    "You are a strict JSON repair adapter. Convert input into one valid JSON object. "
                    "Return json only, with no prose and no Markdown fences."
                ),
            ),
            Message(role="user", content=json.dumps(repair_payload, ensure_ascii=False)),
        ],
        temperature=0.0,
        max_tokens=STRUCTURED_AGENT_MAX_TOKENS,
        response_format=JSON_OBJECT_RESPONSE_FORMAT,
    )
    return _parse_json_object(repair_response.content)


def _agent_result_schema() -> dict[str, Any]:
    return {
        "summary": "string, answer in Chinese when the question is Chinese",
        "risks": ["string"],
        "next_actions": ["string"],
        "evidence_card_ids": ["string from evidence_cards"],
        "confidence": "number between 0 and 1",
    }


def _fallback_from_plain_text_response(
    *,
    result: AgentResult,
    response_content: str,
    response_model: str | None,
    response_usage: dict[str, Any],
    provider: str,
    error: str,
) -> AgentResult:
    plain_text = re.sub(r"\s+", " ", _strip_fences(response_content)).strip()
    summary = plain_text[:1200] if plain_text else result.summary
    return replace(
        result,
        summary=summary,
        confidence=min(result.confidence, 0.72),
        metadata={
            **result.metadata,
            "llm": {
                "enabled": True,
                "provider": provider,
                "model": response_model,
                "usage": response_usage,
                "fallback": True,
                "error": error,
            },
        },
    )


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


def _parse_nested_json_object(value: str) -> dict[str, Any] | None:
    stripped = _strip_fences(value).strip()
    if not stripped.startswith("{"):
        return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
