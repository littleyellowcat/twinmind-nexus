"""Deterministic agent workflows for TwinMind project archives."""

from __future__ import annotations

from collections.abc import Iterable

from src.project_archive.types import (
    AgentResult,
    EvidenceCard,
    GraphPath,
    ProjectEntity,
    ProjectRelation,
    QueryMode,
)


class AgentWorkflow:
    """Rule-based archive workflows with no model calls or external state."""

    _ARCHITECTURE_TYPES = {"File", "Module", "Class", "Function"}
    _IMPACT_RELATION_TYPES = {"AFFECTS", "DEFINES", "CONFIGURES"}
    _RISK_TERMS = ("placeholder", "will be implemented", "phase")

    def __init__(
        self,
        entities: list[ProjectEntity],
        relations: list[ProjectRelation],
        evidence_cards: list[EvidenceCard],
    ) -> None:
        self.entities = list(entities)
        self.relations = list(relations)
        self.evidence_cards = list(evidence_cards)

    def run(self, question: str, mode: QueryMode) -> AgentResult:
        if mode == QueryMode.ARCHITECTURE_TOUR:
            return self._architecture_tour(question)
        if mode == QueryMode.IMPACT_ANALYSIS:
            return self._impact_analysis(question)
        if mode == QueryMode.RISK_AUDIT:
            return self._risk_audit(question)
        return self._evidence_qa(question)

    def _architecture_tour(self, question: str) -> AgentResult:
        entity_ids = [
            entity.id
            for entity in self.entities
            if entity.type in self._ARCHITECTURE_TYPES
        ][:12]
        evidence_ids = self._first_evidence_ids()

        return AgentResult(
            mode=QueryMode.ARCHITECTURE_TOUR,
            question=question,
            summary="Architecture tour assembled from archive structure.",
            affected_entities=entity_ids,
            evidence_card_ids=evidence_ids,
            next_actions=["Review the listed entry points and module boundaries."],
            confidence=0.7 if entity_ids or evidence_ids else 0.0,
        )

    def _impact_analysis(self, question: str) -> AgentResult:
        impact_relations = [
            relation
            for relation in self.relations
            if relation.type in self._IMPACT_RELATION_TYPES
        ]
        affected_entities = self._unique_ids(
            entity_id
            for relation in impact_relations
            for entity_id in (relation.source_id, relation.target_id)
        )
        graph_paths = [
            GraphPath(
                nodes=[relation.source_id, relation.target_id],
                relations=[relation.id],
                evidence_ids=list(relation.evidence_ids),
            )
            for relation in impact_relations
        ]
        evidence_ids = self._unique_ids(
            evidence_id
            for relation in impact_relations
            for evidence_id in relation.evidence_ids
        )

        return AgentResult(
            mode=QueryMode.IMPACT_ANALYSIS,
            question=question,
            summary="Impact analysis traced deterministic archive relationships.",
            affected_entities=affected_entities,
            graph_paths=graph_paths,
            evidence_card_ids=evidence_ids,
            risks=[
                "Relationship-driven impact may miss behavior without archived edges."
            ]
            if impact_relations
            else ["No impact relationships were available in the archive."],
            next_actions=[
                "Inspect each related source and target entity before changing the graph.",
                "Confirm relation evidence still matches the planned implementation.",
            ],
            confidence=0.8 if impact_relations else 0.2,
        )

    def _risk_audit(self, question: str) -> AgentResult:
        risky_evidence = [
            card
            for card in self.evidence_cards
            if any(term in card.snippet.lower() for term in self._RISK_TERMS)
        ]

        return AgentResult(
            mode=QueryMode.RISK_AUDIT,
            question=question,
            summary="Risk audit found implementation-placeholder evidence."
            if risky_evidence
            else "Risk audit found no placeholder evidence.",
            evidence_card_ids=[card.id for card in risky_evidence],
            risks=[
                f"{card.source_path} contains placeholder or phase-oriented implementation text."
                for card in risky_evidence
            ],
            next_actions=[
                "Replace placeholder implementation notes with current behavior.",
                "Cross-check documentation against the referenced source files.",
            ]
            if risky_evidence
            else ["Continue monitoring archive evidence for stale implementation notes."],
            confidence=0.85 if risky_evidence else 0.5,
        )

    def _evidence_qa(self, question: str) -> AgentResult:
        evidence_ids = self._first_evidence_ids()
        return AgentResult(
            mode=QueryMode.EVIDENCE_QA,
            question=question,
            summary="Evidence answer grounded in the first archived evidence cards.",
            evidence_card_ids=evidence_ids,
            next_actions=["Open the cited evidence cards for exact source context."],
            confidence=0.65 if evidence_ids else 0.0,
        )

    def _first_evidence_ids(self, limit: int = 3) -> list[str]:
        return [card.id for card in self.evidence_cards[:limit]]

    @staticmethod
    def _unique_ids(values: Iterable[str]) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value not in seen:
                seen.add(value)
                unique.append(value)
        return unique
