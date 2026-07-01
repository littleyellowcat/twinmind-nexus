"""Core contracts for TwinMind project archives."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class QueryMode(str, Enum):
    """Supported TwinMind Archive query modes."""

    ARCHITECTURE_TOUR = "architecture_tour"
    IMPACT_ANALYSIS = "impact_analysis"
    RISK_AUDIT = "risk_audit"
    EVIDENCE_QA = "evidence_qa"


@dataclass(frozen=True)
class EvidenceCard:
    id: str
    source_type: str
    source_path: str
    title: str
    snippet: str
    line_start: int | None = None
    line_end: int | None = None
    linked_entities: list[str] = field(default_factory=list)
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceCard:
        return cls(**data)


@dataclass(frozen=True)
class ProjectEntity:
    id: str
    type: str
    name: str
    source_path: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectEntity:
        return cls(**data)


@dataclass(frozen=True)
class ProjectRelation:
    id: str
    source_id: str
    target_id: str
    type: str
    evidence_ids: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectRelation:
        return cls(**data)


@dataclass(frozen=True)
class ArchiveHall:
    id: str
    name: str
    description: str
    entity_ids: list[str] = field(default_factory=list)
    risk_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArchiveHall:
        return cls(**data)


@dataclass(frozen=True)
class GraphPath:
    nodes: list[str]
    relations: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphPath:
        return cls(**data)


@dataclass(frozen=True)
class ProjectFile:
    id: str
    path: str
    language: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectFile:
        return cls(**data)


@dataclass(frozen=True)
class ProjectArchiveDraft:
    project_id: str
    halls: list[ArchiveHall] = field(default_factory=list)
    entities: list[ProjectEntity] = field(default_factory=list)
    relations: list[ProjectRelation] = field(default_factory=list)
    evidence_cards: list[EvidenceCard] = field(default_factory=list)
    confirmation_items: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectArchiveDraft:
        return cls(
            project_id=data["project_id"],
            halls=[ArchiveHall.from_dict(item) for item in data.get("halls", [])],
            entities=[ProjectEntity.from_dict(item) for item in data.get("entities", [])],
            relations=[
                ProjectRelation.from_dict(item) for item in data.get("relations", [])
            ],
            evidence_cards=[
                EvidenceCard.from_dict(item) for item in data.get("evidence_cards", [])
            ],
            confirmation_items=list(data.get("confirmation_items", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class GraphMergeCandidate:
    id: str
    label: str
    entity_ids: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphMergeCandidate:
        return cls(
            id=str(data.get("id", "")),
            label=str(data.get("label", "")),
            entity_ids=[str(item) for item in data.get("entity_ids", [])],
            created_at=str(data.get("created_at", "")),
        )


@dataclass(frozen=True)
class GraphCurationState:
    project_id: str
    important_entity_ids: list[str] = field(default_factory=list)
    hidden_relation_ids: list[str] = field(default_factory=list)
    merge_candidates: list[GraphMergeCandidate] = field(default_factory=list)
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "important_entity_ids": list(self.important_entity_ids),
            "hidden_relation_ids": list(self.hidden_relation_ids),
            "merge_candidates": [
                candidate.to_dict() for candidate in self.merge_candidates
            ],
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphCurationState:
        return cls(
            project_id=str(data.get("project_id", "")),
            important_entity_ids=[
                str(item) for item in data.get("important_entity_ids", [])
            ],
            hidden_relation_ids=[
                str(item) for item in data.get("hidden_relation_ids", [])
            ],
            merge_candidates=[
                GraphMergeCandidate.from_dict(item)
                for item in data.get("merge_candidates", [])
                if isinstance(item, dict)
            ],
            updated_at=str(data.get("updated_at", "")),
        )


@dataclass(frozen=True)
class ArchiveGoldenQuestion:
    id: str
    question: str
    category: str
    expected_entity_ids: list[str] = field(default_factory=list)
    expected_relation_ids: list[str] = field(default_factory=list)
    expected_evidence_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArchiveGoldenQuestion:
        return cls(
            id=str(data.get("id", "")),
            question=str(data.get("question", "")),
            category=str(data.get("category", "general")),
            expected_entity_ids=[
                str(item) for item in data.get("expected_entity_ids", [])
            ],
            expected_relation_ids=[
                str(item) for item in data.get("expected_relation_ids", [])
            ],
            expected_evidence_ids=[
                str(item) for item in data.get("expected_evidence_ids", [])
            ],
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class ArchiveEvaluationCaseResult:
    question_id: str
    question: str
    category: str
    mode: str
    expected_entity_ids: list[str] = field(default_factory=list)
    expected_relation_ids: list[str] = field(default_factory=list)
    expected_evidence_ids: list[str] = field(default_factory=list)
    matched_entity_ids: list[str] = field(default_factory=list)
    matched_relation_ids: list[str] = field(default_factory=list)
    matched_evidence_ids: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArchiveEvaluationCaseResult:
        return cls(
            question_id=str(data.get("question_id", "")),
            question=str(data.get("question", "")),
            category=str(data.get("category", "general")),
            mode=str(data.get("mode", "deterministic_graph_rag")),
            expected_entity_ids=[
                str(item) for item in data.get("expected_entity_ids", [])
            ],
            expected_relation_ids=[
                str(item) for item in data.get("expected_relation_ids", [])
            ],
            expected_evidence_ids=[
                str(item) for item in data.get("expected_evidence_ids", [])
            ],
            matched_entity_ids=[
                str(item) for item in data.get("matched_entity_ids", [])
            ],
            matched_relation_ids=[
                str(item) for item in data.get("matched_relation_ids", [])
            ],
            matched_evidence_ids=[
                str(item) for item in data.get("matched_evidence_ids", [])
            ],
            metrics={
                str(key): float(value)
                for key, value in data.get("metrics", {}).items()
            },
            summary=str(data.get("summary", "")),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class ArchiveEvaluationReport:
    project_id: str
    created_at: str
    golden_question_count: int
    aggregate_metrics: dict[str, float] = field(default_factory=dict)
    case_results: list[ArchiveEvaluationCaseResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "created_at": self.created_at,
            "golden_question_count": self.golden_question_count,
            "aggregate_metrics": dict(self.aggregate_metrics),
            "case_results": [case.to_dict() for case in self.case_results],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArchiveEvaluationReport:
        return cls(
            project_id=str(data.get("project_id", "")),
            created_at=str(data.get("created_at", "")),
            golden_question_count=int(data.get("golden_question_count", 0)),
            aggregate_metrics={
                str(key): float(value)
                for key, value in data.get("aggregate_metrics", {}).items()
            },
            case_results=[
                ArchiveEvaluationCaseResult.from_dict(item)
                for item in data.get("case_results", [])
                if isinstance(item, dict)
            ],
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class ProjectUniverseProject:
    project_id: str
    metrics: dict[str, int] = field(default_factory=dict)
    top_entity_types: list[dict[str, Any]] = field(default_factory=list)
    evidence_modalities: dict[str, int] = field(default_factory=dict)
    hall_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "metrics": dict(self.metrics),
            "top_entity_types": [dict(item) for item in self.top_entity_types],
            "evidence_modalities": dict(self.evidence_modalities),
            "hall_names": list(self.hall_names),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectUniverseProject:
        return cls(
            project_id=str(data.get("project_id", "")),
            metrics={str(key): int(value) for key, value in data.get("metrics", {}).items()},
            top_entity_types=[
                dict(item) for item in data.get("top_entity_types", []) if isinstance(item, dict)
            ],
            evidence_modalities={
                str(key): int(value)
                for key, value in data.get("evidence_modalities", {}).items()
            },
            hall_names=[str(item) for item in data.get("hall_names", [])],
        )


@dataclass(frozen=True)
class ProjectUniverseEntityRef:
    project_id: str
    entity_id: str
    label: str
    type: str
    source_path: str | None = None
    degree: int = 0
    evidence_count: int = 0
    hall_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectUniverseEntityRef:
        return cls(
            project_id=str(data.get("project_id", "")),
            entity_id=str(data.get("entity_id", "")),
            label=str(data.get("label", "")),
            type=str(data.get("type", "")),
            source_path=data.get("source_path"),
            degree=int(data.get("degree", 0)),
            evidence_count=int(data.get("evidence_count", 0)),
            hall_ids=[str(item) for item in data.get("hall_ids", [])],
        )


@dataclass(frozen=True)
class ProjectUniverseLink:
    id: str
    type: str
    source: ProjectUniverseEntityRef
    target: ProjectUniverseEntityRef
    score: float
    reason: str
    shared_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "score": self.score,
            "reason": self.reason,
            "shared_key": self.shared_key,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectUniverseLink:
        return cls(
            id=str(data.get("id", "")),
            type=str(data.get("type", "")),
            source=ProjectUniverseEntityRef.from_dict(data.get("source", {})),
            target=ProjectUniverseEntityRef.from_dict(data.get("target", {})),
            score=float(data.get("score", 0.0)),
            reason=str(data.get("reason", "")),
            shared_key=str(data.get("shared_key", "")),
        )


@dataclass(frozen=True)
class ProjectUniverseCluster:
    id: str
    label: str
    type: str
    project_ids: list[str] = field(default_factory=list)
    entity_refs: list[ProjectUniverseEntityRef] = field(default_factory=list)
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "type": self.type,
            "project_ids": list(self.project_ids),
            "entity_refs": [ref.to_dict() for ref in self.entity_refs],
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectUniverseCluster:
        return cls(
            id=str(data.get("id", "")),
            label=str(data.get("label", "")),
            type=str(data.get("type", "")),
            project_ids=[str(item) for item in data.get("project_ids", [])],
            entity_refs=[
                ProjectUniverseEntityRef.from_dict(item)
                for item in data.get("entity_refs", [])
                if isinstance(item, dict)
            ],
            score=float(data.get("score", 0.0)),
        )


@dataclass(frozen=True)
class ProjectKnowledgeUniverse:
    created_at: str
    project_ids: list[str] = field(default_factory=list)
    metrics: dict[str, int] = field(default_factory=dict)
    projects: list[ProjectUniverseProject] = field(default_factory=list)
    links: list[ProjectUniverseLink] = field(default_factory=list)
    clusters: list[ProjectUniverseCluster] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_at": self.created_at,
            "project_ids": list(self.project_ids),
            "metrics": dict(self.metrics),
            "projects": [project.to_dict() for project in self.projects],
            "links": [link.to_dict() for link in self.links],
            "clusters": [cluster.to_dict() for cluster in self.clusters],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectKnowledgeUniverse:
        return cls(
            created_at=str(data.get("created_at", "")),
            project_ids=[str(item) for item in data.get("project_ids", [])],
            metrics={str(key): int(value) for key, value in data.get("metrics", {}).items()},
            projects=[
                ProjectUniverseProject.from_dict(item)
                for item in data.get("projects", [])
                if isinstance(item, dict)
            ],
            links=[
                ProjectUniverseLink.from_dict(item)
                for item in data.get("links", [])
                if isinstance(item, dict)
            ],
            clusters=[
                ProjectUniverseCluster.from_dict(item)
                for item in data.get("clusters", [])
                if isinstance(item, dict)
            ],
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class UniverseExplorationPath:
    id: str
    name: str
    project_ids: list[str] = field(default_factory=list)
    cluster_ids: list[str] = field(default_factory=list)
    link_ids: list[str] = field(default_factory=list)
    notes: str = ""
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UniverseExplorationPath:
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            project_ids=[str(item) for item in data.get("project_ids", [])],
            cluster_ids=[str(item) for item in data.get("cluster_ids", [])],
            link_ids=[str(item) for item in data.get("link_ids", [])],
            notes=str(data.get("notes", "")),
            created_at=str(data.get("created_at", "")),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class UniverseAgentTask:
    id: str
    status: str
    objective: str
    project_ids: list[str] = field(default_factory=list)
    cluster_ids: list[str] = field(default_factory=list)
    link_ids: list[str] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    created_at: str = ""
    completed_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UniverseAgentTask:
        return cls(
            id=str(data.get("id", "")),
            status=str(data.get("status", "planned")),
            objective=str(data.get("objective", "")),
            project_ids=[str(item) for item in data.get("project_ids", [])],
            cluster_ids=[str(item) for item in data.get("cluster_ids", [])],
            link_ids=[str(item) for item in data.get("link_ids", [])],
            findings=[
                dict(item) for item in data.get("findings", []) if isinstance(item, dict)
            ],
            evidence=[
                dict(item) for item in data.get("evidence", []) if isinstance(item, dict)
            ],
            next_actions=[str(item) for item in data.get("next_actions", [])],
            created_at=str(data.get("created_at", "")),
            completed_at=str(data.get("completed_at", "")),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class ProjectArchitectureDiffReport:
    id: str
    left_project_id: str
    right_project_id: str
    created_at: str
    summary: str
    shared_clusters: list[ProjectUniverseCluster] = field(default_factory=list)
    shared_links: list[ProjectUniverseLink] = field(default_factory=list)
    only_left: list[ProjectUniverseEntityRef] = field(default_factory=list)
    only_right: list[ProjectUniverseEntityRef] = field(default_factory=list)
    metric_delta: dict[str, int] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)
    evidence_chain: list[dict[str, Any]] = field(default_factory=list)
    component_delta: dict[str, Any] = field(default_factory=dict)
    risk_points: list[dict[str, Any]] = field(default_factory=list)
    migration_notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "left_project_id": self.left_project_id,
            "right_project_id": self.right_project_id,
            "created_at": self.created_at,
            "summary": self.summary,
            "shared_clusters": [cluster.to_dict() for cluster in self.shared_clusters],
            "shared_links": [link.to_dict() for link in self.shared_links],
            "only_left": [ref.to_dict() for ref in self.only_left],
            "only_right": [ref.to_dict() for ref in self.only_right],
            "metric_delta": dict(self.metric_delta),
            "findings": [dict(item) for item in self.findings],
            "recommendations": list(self.recommendations),
            "sections": [dict(item) for item in self.sections],
            "evidence_chain": [dict(item) for item in self.evidence_chain],
            "component_delta": dict(self.component_delta),
            "risk_points": [dict(item) for item in self.risk_points],
            "migration_notes": list(self.migration_notes),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectArchitectureDiffReport:
        return cls(
            id=str(data.get("id", "")),
            left_project_id=str(data.get("left_project_id", "")),
            right_project_id=str(data.get("right_project_id", "")),
            created_at=str(data.get("created_at", "")),
            summary=str(data.get("summary", "")),
            shared_clusters=[
                ProjectUniverseCluster.from_dict(item)
                for item in data.get("shared_clusters", [])
                if isinstance(item, dict)
            ],
            shared_links=[
                ProjectUniverseLink.from_dict(item)
                for item in data.get("shared_links", [])
                if isinstance(item, dict)
            ],
            only_left=[
                ProjectUniverseEntityRef.from_dict(item)
                for item in data.get("only_left", [])
                if isinstance(item, dict)
            ],
            only_right=[
                ProjectUniverseEntityRef.from_dict(item)
                for item in data.get("only_right", [])
                if isinstance(item, dict)
            ],
            metric_delta={str(key): int(value) for key, value in data.get("metric_delta", {}).items()},
            findings=[
                dict(item) for item in data.get("findings", []) if isinstance(item, dict)
            ],
            recommendations=[str(item) for item in data.get("recommendations", [])],
            sections=[
                dict(item) for item in data.get("sections", []) if isinstance(item, dict)
            ],
            evidence_chain=[
                dict(item) for item in data.get("evidence_chain", []) if isinstance(item, dict)
            ],
            component_delta=dict(data.get("component_delta", {})),
            risk_points=[
                dict(item) for item in data.get("risk_points", []) if isinstance(item, dict)
            ],
            migration_notes=[str(item) for item in data.get("migration_notes", [])],
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentResult:
    mode: QueryMode
    question: str
    summary: str
    affected_entities: list[str] = field(default_factory=list)
    graph_paths: list[GraphPath] = field(default_factory=list)
    evidence_card_ids: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["mode"] = self.mode.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentResult:
        payload = dict(data)
        payload["mode"] = QueryMode(payload["mode"])
        payload["graph_paths"] = [
            GraphPath.from_dict(path) if isinstance(path, dict) else path
            for path in payload.get("graph_paths", [])
        ]
        return cls(**payload)


@dataclass(frozen=True)
class AgentRoleResult:
    agent: str
    status: str
    summary: str
    evidence_card_ids: list[str] = field(default_factory=list)
    entity_ids: list[str] = field(default_factory=list)
    relation_ids: list[str] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    risks: list[dict[str, Any]] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentRoleResult:
        return cls(**data)


@dataclass(frozen=True)
class ProjectAgentReport:
    project_id: str
    status: str
    provider: str
    model: str | None
    created_at: str
    scan_profile: str
    agents: dict[str, AgentRoleResult] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    metrics: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["agents"] = {
            name: result.to_dict() for name, result in self.agents.items()
        }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectAgentReport:
        return cls(
            project_id=data["project_id"],
            status=data.get("status", "unknown"),
            provider=data.get("provider", "rules"),
            model=data.get("model"),
            created_at=data.get("created_at", ""),
            scan_profile=data.get("scan_profile", "architecture"),
            agents={
                name: AgentRoleResult.from_dict(result)
                for name, result in data.get("agents", {}).items()
            },
            errors=list(data.get("errors", [])),
            metrics={key: int(value) for key, value in data.get("metrics", {}).items()},
        )


@dataclass(frozen=True)
class GraphExplorerNode:
    id: str
    label: str
    type: str
    hall_ids: list[str] = field(default_factory=list)
    source_path: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    degree: int = 0
    importance: float = 0.0
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphExplorerNode:
        return cls(**data)


@dataclass(frozen=True)
class GraphExplorerRelation:
    id: str
    source_id: str
    target_id: str
    type: str
    evidence_ids: list[str] = field(default_factory=list)
    hall_ids: list[str] = field(default_factory=list)
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphExplorerRelation:
        return cls(**data)


@dataclass(frozen=True)
class RecommendedGraphStart:
    entity_id: str
    label: str
    group: str
    reason: str
    score: float
    hall_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecommendedGraphStart:
        return cls(**data)


@dataclass(frozen=True)
class GraphSearchResult:
    entity_id: str
    label: str
    type: str
    source_path: str | None = None
    hall_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    degree: int = 0
    score: float = 0.0
    matched_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphSearchResult:
        return cls(**data)


@dataclass(frozen=True)
class GraphSummary:
    project_id: str
    metrics: dict[str, int]
    recommended_starts: list[RecommendedGraphStart] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "metrics": dict(self.metrics),
            "recommended_starts": [
                start.to_dict() for start in self.recommended_starts
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphSummary:
        return cls(
            project_id=data["project_id"],
            metrics={key: int(value) for key, value in data.get("metrics", {}).items()},
            recommended_starts=[
                RecommendedGraphStart.from_dict(start)
                if isinstance(start, dict)
                else start
                for start in data.get("recommended_starts", [])
            ],
        )


@dataclass(frozen=True)
class GraphNeighborhood:
    project_id: str
    hall_id: str | None
    focus_entity_id: str | None
    depth: int
    nodes: list[GraphExplorerNode] = field(default_factory=list)
    relations: list[GraphExplorerRelation] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    is_sparse: bool = False
    sparse_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "hall_id": self.hall_id,
            "focus_entity_id": self.focus_entity_id,
            "depth": self.depth,
            "nodes": [node.to_dict() for node in self.nodes],
            "relations": [relation.to_dict() for relation in self.relations],
            "evidence_ids": list(self.evidence_ids),
            "is_sparse": self.is_sparse,
            "sparse_reason": self.sparse_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphNeighborhood:
        return cls(
            project_id=data["project_id"],
            hall_id=data.get("hall_id"),
            focus_entity_id=data.get("focus_entity_id"),
            depth=int(data.get("depth", 1)),
            nodes=[
                GraphExplorerNode.from_dict(node) if isinstance(node, dict) else node
                for node in data.get("nodes", [])
            ],
            relations=[
                GraphExplorerRelation.from_dict(relation)
                if isinstance(relation, dict)
                else relation
                for relation in data.get("relations", [])
            ],
            evidence_ids=list(data.get("evidence_ids", [])),
            is_sparse=bool(data.get("is_sparse", False)),
            sparse_reason=data.get("sparse_reason"),
        )


@dataclass(frozen=True)
class MissionGraphOverlay:
    mission_id: str
    explored_node_ids: list[str] = field(default_factory=list)
    explored_relation_ids: list[str] = field(default_factory=list)
    risk_node_ids: list[str] = field(default_factory=list)
    risk_relation_ids: list[str] = field(default_factory=list)
    annotations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MissionGraphOverlay:
        return cls(**data)


@dataclass(frozen=True)
class MissionTask:
    id: str
    mission_id: str
    status: str
    agent: str
    task_type: str
    title: str
    input_entity_ids: list[str] = field(default_factory=list)
    input_relation_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    risks: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    verifier_status: str = "uncertain"
    created_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MissionTask:
        return cls(**data)


@dataclass(frozen=True)
class AutonomousMission:
    id: str
    project_id: str
    goal: str
    status: str
    max_steps: int
    stop_reason: str
    created_at: str
    completed_at: str
    tasks: list[MissionTask] = field(default_factory=list)
    graph_overlay: MissionGraphOverlay | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "goal": self.goal,
            "status": self.status,
            "max_steps": self.max_steps,
            "stop_reason": self.stop_reason,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "tasks": [task.to_dict() for task in self.tasks],
            "graph_overlay": self.graph_overlay.to_dict()
            if self.graph_overlay
            else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutonomousMission:
        return cls(
            id=data["id"],
            project_id=data["project_id"],
            goal=data["goal"],
            status=data["status"],
            max_steps=int(data["max_steps"]),
            stop_reason=data.get("stop_reason", ""),
            created_at=data.get("created_at", ""),
            completed_at=data.get("completed_at", ""),
            tasks=[MissionTask.from_dict(task) for task in data.get("tasks", [])],
            graph_overlay=MissionGraphOverlay.from_dict(data["graph_overlay"])
            if data.get("graph_overlay")
            else None,
        )


@dataclass(frozen=True)
class AgentMissionBudget:
    max_tasks: int = 5
    max_steps_per_task: int = 4
    max_tool_calls: int = 16
    timeout_seconds: int = 90

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMissionBudget:
        return cls(
            max_tasks=int(data.get("max_tasks", 5)),
            max_steps_per_task=int(data.get("max_steps_per_task", 4)),
            max_tool_calls=int(data.get("max_tool_calls", 16)),
            timeout_seconds=int(data.get("timeout_seconds", 90)),
        )


@dataclass(frozen=True)
class AgentMissionTask:
    id: str
    mission_id: str
    task_type: str
    objective: str
    status: str
    allowed_tools: list[str] = field(default_factory=list)
    max_steps: int = 4
    steps_used: int = 0
    input_entity_ids: list[str] = field(default_factory=list)
    output_entity_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    risks: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    created_at: str = ""
    completed_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMissionTask:
        return cls(
            id=data["id"],
            mission_id=data["mission_id"],
            task_type=data["task_type"],
            objective=data["objective"],
            status=data.get("status", "pending"),
            allowed_tools=list(data.get("allowed_tools", [])),
            max_steps=int(data.get("max_steps", 4)),
            steps_used=int(data.get("steps_used", 0)),
            input_entity_ids=list(data.get("input_entity_ids", [])),
            output_entity_ids=list(data.get("output_entity_ids", [])),
            evidence_ids=list(data.get("evidence_ids", [])),
            findings=list(data.get("findings", [])),
            risks=list(data.get("risks", [])),
            confidence=float(data.get("confidence", 0.0)),
            created_at=data.get("created_at", ""),
            completed_at=data.get("completed_at", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentTraceEvent:
    id: str
    mission_id: str
    task_id: str
    sequence: int
    event_type: str
    tool_name: str | None = None
    tool_input: dict[str, Any] = field(default_factory=dict)
    observation_summary: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    entity_ids: list[str] = field(default_factory=list)
    relation_ids: list[str] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceEvent:
        return cls(
            id=data["id"],
            mission_id=data["mission_id"],
            task_id=data["task_id"],
            sequence=int(data["sequence"]),
            event_type=data["event_type"],
            tool_name=data.get("tool_name"),
            tool_input=dict(data.get("tool_input", {})),
            observation_summary=data.get("observation_summary", ""),
            evidence_ids=list(data.get("evidence_ids", [])),
            entity_ids=list(data.get("entity_ids", [])),
            relation_ids=list(data.get("relation_ids", [])),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at", ""),
            error=data.get("error"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentMissionVerifierResult:
    status: str
    supported_finding_count: int = 0
    uncertain_finding_count: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMissionVerifierResult:
        return cls(
            status=data.get("status", "uncertain"),
            supported_finding_count=int(data.get("supported_finding_count", 0)),
            uncertain_finding_count=int(data.get("uncertain_finding_count", 0)),
            warnings=list(data.get("warnings", [])),
        )


@dataclass(frozen=True)
class AgentMissionFinalReport:
    summary: str
    findings: list[dict[str, Any]] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMissionFinalReport:
        return cls(
            summary=data.get("summary", ""),
            findings=list(data.get("findings", [])),
            evidence_ids=list(data.get("evidence_ids", [])),
            confidence=float(data.get("confidence", 0.0)),
        )


@dataclass(frozen=True)
class AgentMission:
    id: str
    project_id: str
    goal: str
    status: str
    created_at: str
    completed_at: str = ""
    budget: AgentMissionBudget = field(default_factory=AgentMissionBudget)
    tasks: list[AgentMissionTask] = field(default_factory=list)
    trace_events: list[AgentTraceEvent] = field(default_factory=list)
    verifier_result: AgentMissionVerifierResult | None = None
    final_report: AgentMissionFinalReport | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "goal": self.goal,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "budget": self.budget.to_dict(),
            "tasks": [task.to_dict() for task in self.tasks],
            "trace_events": [event.to_dict() for event in self.trace_events],
            "verifier_result": self.verifier_result.to_dict()
            if self.verifier_result
            else None,
            "final_report": self.final_report.to_dict() if self.final_report else None,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMission:
        return cls(
            id=data["id"],
            project_id=data["project_id"],
            goal=data["goal"],
            status=data.get("status", "pending"),
            created_at=data.get("created_at", ""),
            completed_at=data.get("completed_at", ""),
            budget=AgentMissionBudget.from_dict(data.get("budget", {})),
            tasks=[
                AgentMissionTask.from_dict(task) for task in data.get("tasks", [])
            ],
            trace_events=[
                AgentTraceEvent.from_dict(event)
                for event in data.get("trace_events", [])
            ],
            verifier_result=AgentMissionVerifierResult.from_dict(
                data["verifier_result"]
            )
            if data.get("verifier_result")
            else None,
            final_report=AgentMissionFinalReport.from_dict(data["final_report"])
            if data.get("final_report")
            else None,
            metadata=dict(data.get("metadata", {})),
        )
