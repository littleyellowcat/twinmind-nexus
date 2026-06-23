"""Core contracts for TwinMind project archives."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


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
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    linked_entities: List[str] = field(default_factory=list)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceCard":
        return cls(**data)


@dataclass(frozen=True)
class ProjectEntity:
    id: str
    type: str
    name: str
    source_path: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    evidence_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectEntity":
        return cls(**data)


@dataclass(frozen=True)
class ProjectRelation:
    id: str
    source_id: str
    target_id: str
    type: str
    evidence_ids: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectRelation":
        return cls(**data)


@dataclass(frozen=True)
class ArchiveHall:
    id: str
    name: str
    description: str
    entity_ids: List[str] = field(default_factory=list)
    risk_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArchiveHall":
        return cls(**data)


@dataclass(frozen=True)
class GraphPath:
    nodes: List[str]
    relations: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphPath":
        return cls(**data)


@dataclass(frozen=True)
class ProjectFile:
    id: str
    path: str
    language: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectFile":
        return cls(**data)


@dataclass(frozen=True)
class AgentResult:
    mode: QueryMode
    question: str
    summary: str
    affected_entities: List[str] = field(default_factory=list)
    graph_paths: List[GraphPath] = field(default_factory=list)
    evidence_card_ids: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    next_actions: List[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["mode"] = self.mode.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentResult":
        payload = dict(data)
        payload["mode"] = QueryMode(payload["mode"])
        payload["graph_paths"] = [
            GraphPath.from_dict(path) if isinstance(path, dict) else path
            for path in payload.get("graph_paths", [])
        ]
        return cls(**payload)
