"""Service layer for TwinMind Archive ingestion and querying."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

from src.project_archive.agents import AgentWorkflow
from src.project_archive.archive_builder import ArchiveBuilder
from src.project_archive.autonomous_mission import (
    ARCHITECTURE_GOAL,
    run_architecture_mission,
)
from src.project_archive.graph_explorer import (
    build_graph_neighborhood,
    build_graph_summary,
)
from src.project_archive.graph_store import create_graph_store
from src.project_archive.llm import create_archive_llm_enhancer_from_config
from src.project_archive.multi_agent import MultiAgentPipeline
from src.project_archive.scanner import SCAN_PROFILE_ARCHITECTURE
from src.project_archive.types import (
    AgentResult,
    AutonomousMission,
    GraphNeighborhood,
    GraphSummary,
    ProjectAgentReport,
    ProjectArchiveDraft,
    QueryMode,
)

MISSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


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

        self._draft_path(project_id).write_text(
            json.dumps(draft.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
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
        self, project_id: str, question: str, mode: QueryMode
    ) -> AgentResult:
        draft = self.load_draft(project_id)
        workflow = AgentWorkflow(
            entities=draft.entities,
            relations=draft.relations,
            evidence_cards=draft.evidence_cards,
            enhancer=create_archive_llm_enhancer_from_config(),
        )
        return workflow.run(question=question, mode=mode)

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
