"""Service layer for TwinMind Archive ingestion and querying."""

from __future__ import annotations

import json
from pathlib import Path

from src.project_archive.agents import AgentWorkflow
from src.project_archive.archive_builder import ArchiveBuilder
from src.project_archive.graph_store import create_graph_store
from src.project_archive.types import AgentResult, ProjectArchiveDraft, QueryMode


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
        self, project_root: Path | str, project_id: str
    ) -> ProjectArchiveDraft:
        graph_store = create_graph_store(
            path=self._graph_path(project_id),
            preferred_provider=self.graph_provider,
        )
        builder = ArchiveBuilder(graph_store=graph_store)
        draft = builder.build(project_root=project_root, project_id=project_id)

        self._draft_path(project_id).write_text(
            json.dumps(draft.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return draft

    def query_project(
        self, project_id: str, question: str, mode: QueryMode
    ) -> AgentResult:
        draft = self.load_draft(project_id)
        workflow = AgentWorkflow(
            entities=draft.entities,
            relations=draft.relations,
            evidence_cards=draft.evidence_cards,
        )
        return workflow.run(question=question, mode=mode)

    def load_draft(self, project_id: str) -> ProjectArchiveDraft:
        path = self._draft_path(project_id)
        if not path.exists():
            raise ValueError(f"Project archive not found: {project_id}")

        data = json.loads(path.read_text(encoding="utf-8"))
        return ProjectArchiveDraft.from_dict(data)

    def _project_dir(self, project_id: str) -> Path:
        safe_project_id = project_id.replace("/", "_").replace(" ", "_")
        path = self.storage_dir / safe_project_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _draft_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "draft_archive.json"

    def _graph_path(self, project_id: str) -> Path:
        if self.graph_provider.lower() == "kuzu":
            return self._project_dir(project_id) / "graph.kuzu"
        return self._project_dir(project_id) / "graph.sqlite"
