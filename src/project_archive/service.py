"""Service layer for TwinMind Archive ingestion and querying."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

from src.project_archive.agent_mission import (
    TERMINAL_MISSION_STATUSES,
    AgentMissionRuntime,
    MissionStore,
)
from src.project_archive.agent_tools import AgentToolRegistry
from src.project_archive.agents import AgentWorkflow
from src.project_archive.archive_builder import ArchiveBuilder
from src.project_archive.autonomous_mission import (
    ARCHITECTURE_GOAL,
    run_architecture_mission,
)
from src.project_archive.graph_explorer import (
    build_graph_neighborhood,
    build_graph_summary,
    search_graph_entities,
)
from src.project_archive.graph_store import create_graph_store
from src.project_archive.hybrid_rag import (
    ProjectHybridRAGIndex,
    retrieval_results_to_evidence_cards,
)
from src.project_archive.llm import create_archive_llm_enhancer_from_config
from src.project_archive.multi_agent import MultiAgentPipeline
from src.project_archive.scanner import SCAN_PROFILE_ARCHITECTURE
from src.project_archive.types import (
    AgentMission,
    AgentResult,
    AgentTraceEvent,
    AutonomousMission,
    GraphNeighborhood,
    GraphSearchResult,
    GraphSummary,
    ProjectAgentReport,
    ProjectArchiveDraft,
    QueryMode,
)

MISSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
TERMINAL_AGENT_MISSION_STATUSES = TERMINAL_MISSION_STATUSES


class ProjectArchiveService:
    """Coordinate project archive persistence and deterministic query workflows."""

    def __init__(
        self,
        storage_dir: Path | str = "data/project_archive",
        graph_provider: str = "sqlite",
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.graph_provider = graph_provider
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def ingest_project(
        self,
        project_root: Path | str,
        project_id: str,
        scan_profile: str = SCAN_PROFILE_ARCHITECTURE,
    ) -> ProjectArchiveDraft:
        graph_store = create_graph_store(
            path=self._graph_path(project_id),
            preferred_provider=self.graph_provider,
        )
        builder = ArchiveBuilder(graph_store=graph_store)
        draft = builder.build(
            project_root=project_root,
            project_id=project_id,
            scan_profile=scan_profile,
        )
        try:
            rag_result = ProjectHybridRAGIndex(self.storage_dir).build(
                project_root=project_root,
                draft=draft,
            )
            if rag_result.image_evidence_cards:
                draft = replace(
                    draft,
                    evidence_cards=[
                        *draft.evidence_cards,
                        *rag_result.image_evidence_cards,
                    ],
                    confirmation_items=[
                        *draft.confirmation_items,
                        (
                            "Hybrid RAG indexed "
                            f"{rag_result.indexed_chunks} chunks with "
                            f"{rag_result.image_chunks} image chunk(s)."
                        ),
                    ],
                )
        except Exception as exc:
            draft = replace(
                draft,
                confirmation_items=[
                    *draft.confirmation_items,
                    f"Hybrid RAG indexing failed: {exc}",
                ],
            )

        self._draft_path(project_id).write_text(
            json.dumps(draft.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        agent_report_path = self._agent_report_path(project_id)
        if agent_report_path.exists():
            agent_report_path.unlink()
        return draft

    def run_agent_report(
        self,
        project_id: str,
        scan_profile: str = SCAN_PROFILE_ARCHITECTURE,
    ) -> ProjectAgentReport:
        draft = self.load_draft(project_id)
        report = MultiAgentPipeline.from_config().run(
            draft=draft,
            scan_profile=scan_profile,
        )
        self._agent_report_path(project_id).write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return report

    def query_project(
        self,
        project_id: str,
        question: str,
        mode: QueryMode,
        hall_id: str | None = None,
    ) -> AgentResult:
        draft = self.load_draft(project_id)
        entities = draft.entities
        relations = draft.relations
        evidence_cards = draft.evidence_cards
        scoped_question = question
        rag_metadata: dict | None = None

        if hall_id:
            hall = next((item for item in draft.halls if item.id == hall_id), None)
            if hall is None:
                raise ValueError(f"Archive hall not found: {hall_id}")
            entities, relations, evidence_cards = _scope_archive_to_hall(draft, hall_id)
            scoped_question = (
                f"{question}\n\n"
                f"Selected archive hall: {hall.name}\n"
                f"Hall description: {hall.description}\n"
                "Use the scoped hall entities, relations, and evidence as the primary context. "
                "Do not treat the hall display label itself as a required source-code term."
            )

        rag_result = None
        try:
            rag_result = ProjectHybridRAGIndex(self.storage_dir).search(
                project_id=project_id,
                query=question,
                hall_id=hall_id,
                top_k=8,
            )
        except Exception as exc:
            rag_metadata = {"enabled": True, "error": str(exc), "result_count": 0}

        if rag_result is not None:
            rag_cards = retrieval_results_to_evidence_cards(rag_result.results)
            if rag_cards:
                evidence_cards = [*rag_cards, *evidence_cards]
                scoped_question = (
                    f"{scoped_question}\n\n"
                    "Hybrid RAG retrieved context has been prepended to evidence cards. "
                    "Prefer these retrieved chunks when they directly answer the question."
                )
            rag_metadata = rag_result.to_metadata()

        workflow = AgentWorkflow(
            entities=entities,
            relations=relations,
            evidence_cards=evidence_cards,
            enhancer=create_archive_llm_enhancer_from_config(),
        )
        result = workflow.run(question=scoped_question, mode=mode)
        if rag_metadata is None:
            return result
        return replace(
            result,
            metadata={
                **result.metadata,
                "hybrid_rag": rag_metadata,
            },
        )

    def agent_status(self) -> dict[str, str | bool | None]:
        enhancer = create_archive_llm_enhancer_from_config()
        if enhancer is None:
            return {
                "llm_enabled": False,
                "provider": "rules",
                "mode": "deterministic",
                "model": None,
            }
        return {
            "llm_enabled": True,
            "provider": enhancer.provider,
            "mode": "llm_enhanced",
            "model": getattr(enhancer.llm, "model", None),
        }

    def list_project_ids(self) -> list[str]:
        """Return project IDs with persisted draft archives."""
        if not self.storage_dir.exists():
            return []
        return sorted(
            child.name
            for child in self.storage_dir.iterdir()
            if child.is_dir() and (child / "draft_archive.json").exists()
        )

    def load_draft(self, project_id: str) -> ProjectArchiveDraft:
        path = self._draft_path(project_id)
        if not path.exists():
            raise ValueError(f"Project archive not found: {project_id}")

        data = json.loads(path.read_text(encoding="utf-8"))
        return ProjectArchiveDraft.from_dict(data)

    def load_agent_report(self, project_id: str) -> ProjectAgentReport:
        path = self._agent_report_path(project_id)
        if not path.exists():
            raise ValueError(f"Project agent report not found: {project_id}")

        data = json.loads(path.read_text(encoding="utf-8"))
        return ProjectAgentReport.from_dict(data)

    def graph_summary(self, project_id: str) -> GraphSummary:
        draft = self.load_draft(project_id)
        return build_graph_summary(draft)

    def graph_neighborhood(
        self,
        project_id: str,
        *,
        hall_id: str | None = None,
        focus_entity_id: str | None = None,
        depth: int = 1,
        relation_types: list[str] | None = None,
        node_limit: int = 80,
        relation_limit: int = 120,
    ) -> GraphNeighborhood:
        draft = self.load_draft(project_id)
        return build_graph_neighborhood(
            draft,
            hall_id=hall_id,
            focus_entity_id=focus_entity_id,
            depth=depth,
            relation_types=relation_types or [],
            node_limit=node_limit,
            relation_limit=relation_limit,
        )

    def search_graph_entities(
        self,
        project_id: str,
        *,
        query: str,
        limit: int = 20,
    ) -> list[GraphSearchResult]:
        draft = self.load_draft(project_id)
        return search_graph_entities(draft, query=query, limit=limit)

    def hybrid_rag_status(self, project_id: str) -> dict:
        status = ProjectHybridRAGIndex(self.storage_dir).load_status(project_id)
        if status is None:
            raise ValueError(f"Hybrid RAG index not found: {project_id}")
        return status

    def start_architecture_mission(
        self,
        project_id: str,
        *,
        max_steps: int = 12,
    ) -> AutonomousMission:
        draft = self.load_draft(project_id)
        mission = run_architecture_mission(draft, max_steps=max_steps)
        if mission.goal != ARCHITECTURE_GOAL:
            raise ValueError(f"Unsupported mission goal: {mission.goal}")
        self._mission_path(project_id, mission.id).write_text(
            json.dumps(mission.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return mission

    def load_mission(self, mission_id: str) -> AutonomousMission:
        self._validate_mission_id(mission_id)
        for project_dir in self.storage_dir.iterdir():
            path = project_dir / "missions" / f"{mission_id}.json"
            if path.exists():
                return AutonomousMission.from_dict(
                    json.loads(path.read_text(encoding="utf-8"))
                )
        raise ValueError(f"Mission not found: {mission_id}")

    def update_mission_status(self, mission_id: str, status: str) -> AutonomousMission:
        mission = self.load_mission(mission_id)
        updated = replace(mission, status=status)
        self._mission_path(updated.project_id, updated.id).write_text(
            json.dumps(updated.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return updated

    def create_agent_mission(
        self,
        project_id: str,
        goal: str,
        *,
        max_tasks: int = 5,
        max_steps_per_task: int = 4,
    ) -> AgentMission:
        draft = self.load_draft(project_id)
        runtime = self._agent_mission_runtime()
        mission = runtime.create(
            draft=draft,
            goal=goal,
            max_tasks=max_tasks,
            max_steps_per_task=max_steps_per_task,
        )
        return mission

    def run_agent_mission(self, mission_id: str) -> AgentMission:
        self._validate_mission_id(mission_id)
        runtime = self._agent_mission_runtime()
        mission = runtime.load(mission_id)
        if mission.status in TERMINAL_AGENT_MISSION_STATUSES:
            return mission
        return runtime.run(mission_id)

    def start_agent_mission(
        self,
        project_id: str,
        goal: str,
        *,
        max_tasks: int = 5,
        max_steps_per_task: int = 4,
    ) -> AgentMission:
        planned = self.create_agent_mission(
            project_id=project_id,
            goal=goal,
            max_tasks=max_tasks,
            max_steps_per_task=max_steps_per_task,
        )
        return self.run_agent_mission(planned.id)

    def load_agent_mission(self, mission_id: str) -> AgentMission:
        self._validate_mission_id(mission_id)
        return self._agent_mission_runtime().load(mission_id)

    def agent_mission_trace(self, mission_id: str) -> list[AgentTraceEvent]:
        self._validate_mission_id(mission_id)
        return self._agent_mission_runtime().trace(mission_id)

    def update_agent_mission_status(self, mission_id: str, status: str) -> AgentMission:
        self._validate_mission_id(mission_id)
        return self._agent_mission_runtime().update_status(mission_id, status)

    def _agent_mission_runtime(self) -> AgentMissionRuntime:
        enhancer = create_archive_llm_enhancer_from_config()
        return AgentMissionRuntime(
            service=self,
            store=MissionStore(self.storage_dir),
            tool_registry=AgentToolRegistry(self),
            llm=enhancer.llm if enhancer is not None else None,
        )

    def _project_dir(self, project_id: str) -> Path:
        safe_project_id = project_id.replace("/", "_").replace(" ", "_")
        path = self.storage_dir / safe_project_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _draft_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "draft_archive.json"

    def _agent_report_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "agent_report.json"

    def _mission_path(self, project_id: str, mission_id: str) -> Path:
        self._validate_mission_id(mission_id)
        path = self._project_dir(project_id) / "missions"
        path.mkdir(parents=True, exist_ok=True)
        return path / f"{mission_id}.json"

    def _validate_mission_id(self, mission_id: str) -> None:
        if not MISSION_ID_PATTERN.fullmatch(mission_id):
            raise ValueError(f"Invalid mission id: {mission_id}")

    def _graph_path(self, project_id: str) -> Path:
        if self.graph_provider.lower() == "kuzu":
            return self._project_dir(project_id) / "graph.kuzu"
        return self._project_dir(project_id) / "graph.sqlite"


def _scope_archive_to_hall(
    draft: ProjectArchiveDraft,
    hall_id: str,
) -> tuple[list, list, list]:
    hall = next(item for item in draft.halls if item.id == hall_id)
    hall_entity_ids = set(hall.entity_ids)
    relation_ids = set()
    related_entity_ids = set(hall_entity_ids)
    evidence_ids = set()

    for relation in draft.relations:
        touches_hall = (
            relation.source_id in hall_entity_ids
            or relation.target_id in hall_entity_ids
        )
        if not touches_hall:
            continue
        relation_ids.add(relation.id)
        related_entity_ids.add(relation.source_id)
        related_entity_ids.add(relation.target_id)
        evidence_ids.update(relation.evidence_ids)

    for entity in draft.entities:
        if entity.id in hall_entity_ids:
            evidence_ids.update(entity.evidence_ids)

    for card in draft.evidence_cards:
        if any(entity_id in hall_entity_ids for entity_id in card.linked_entities):
            evidence_ids.add(card.id)

    scoped_entities = [
        entity for entity in draft.entities if entity.id in related_entity_ids
    ]
    scoped_relations = [
        relation for relation in draft.relations if relation.id in relation_ids
    ]
    scoped_evidence = [
        card for card in draft.evidence_cards if card.id in evidence_ids
    ]

    return (
        scoped_entities or draft.entities,
        scoped_relations,
        scoped_evidence or draft.evidence_cards[:3],
    )
