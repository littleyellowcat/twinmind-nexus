"""Service layer for TwinMind Archive ingestion and querying."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

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
from src.core.settings import DEFAULT_SETTINGS_PATH, load_settings
from src.project_archive.types import (
    AgentMission,
    AgentResult,
    AgentTraceEvent,
    ArchiveEvaluationCaseResult,
    ArchiveEvaluationReport,
    ArchiveGoldenQuestion,
    AutonomousMission,
    EvidenceCard,
    GraphCurationState,
    GraphMergeCandidate,
    GraphNeighborhood,
    GraphSearchResult,
    GraphSummary,
    ProjectArchitectureDiffReport,
    ProjectAgentReport,
    ProjectArchiveDraft,
    ProjectKnowledgeUniverse,
    UniverseAgentTask,
    UniverseExplorationPath,
    ProjectUniverseCluster,
    ProjectUniverseEntityRef,
    ProjectUniverseLink,
    ProjectUniverseProject,
    QueryMode,
)

MISSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
TERMINAL_AGENT_MISSION_STATUSES = TERMINAL_MISSION_STATUSES


class ProjectArchiveService:
    """Coordinate project archive persistence and deterministic query workflows."""

    def __init__(
        self,
        storage_dir: Path | str = "data/project_archive",
        graph_provider: str | None = None,
    ) -> None:
        self.storage_dir = Path(storage_dir)
        configured_provider, configured_graph = _project_archive_graph_store_config()
        self.graph_provider = graph_provider or configured_provider
        self.graph_config = configured_graph
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def ingest_project(
        self,
        project_root: Path | str,
        project_id: str,
        scan_profile: str = SCAN_PROFILE_ARCHITECTURE,
        on_stage: Callable[[str, int, str], None] | None = None,
    ) -> ProjectArchiveDraft:
        stage_timings: list[dict[str, Any]] = []

        def mark_stage(name: str, started_at: float, status: str = "complete", error: str | None = None) -> None:
            item: dict[str, Any] = {
                "stage": name,
                "status": status,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                "completed_at": datetime.now(UTC).isoformat(),
            }
            if error:
                item["error"] = error
            stage_timings.append(item)

        total_started_at = time.perf_counter()
        if on_stage:
            on_stage("graph_build", 38, "Scanning files and building the project graph.")
        graph_store = create_graph_store(
            path=self._graph_path(project_id),
            preferred_provider=self.graph_provider,
            project_id=project_id,
            config=self.graph_config,
        )
        builder = ArchiveBuilder(graph_store=graph_store)
        graph_started_at = time.perf_counter()
        draft = builder.build(
            project_root=project_root,
            project_id=project_id,
            scan_profile=scan_profile,
        )
        mark_stage("scan_extract_graph", graph_started_at)
        draft = _draft_with_ingestion_updates(
            draft,
            {
                "status": "partial_graph_ready",
                "stage_timings": list(stage_timings),
                "partial_archive_preserved": True,
            },
        )
        self._write_draft(draft)

        if on_stage:
            on_stage("hybrid_rag", 68, "Indexing Chroma + BM25 + RRF and image evidence.")
        rag_started_at = time.perf_counter()
        try:
            def on_rag_progress(progress: int, message: str) -> None:
                if on_stage:
                    on_stage("hybrid_rag", progress, message)

            rag_result = ProjectHybridRAGIndex(self.storage_dir).build(
                project_root=project_root,
                draft=draft,
                on_progress=on_rag_progress,
            )
            mark_stage("hybrid_rag_vision", rag_started_at)
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
            mark_stage("hybrid_rag_vision", rag_started_at, status="failed", error=str(exc))
            draft = replace(
                draft,
                confirmation_items=[
                    *draft.confirmation_items,
                    f"Hybrid RAG indexing failed: {exc}",
                ],
            )

        mark_stage("archive_finalize", total_started_at)
        draft = _draft_with_ingestion_updates(
            draft,
            {
                "status": (
                    "complete"
                    if not any(item.get("status") == "failed" for item in stage_timings)
                    else "partial_with_failed_stage"
                ),
                "stage_timings": stage_timings,
                "partial_archive_preserved": True,
                "last_completed_stage": stage_timings[-1]["stage"] if stage_timings else None,
            },
        )
        self._write_draft(draft)
        self._append_version_event(
            project_id,
            kind="archive_ingestion",
            status="complete",
            metrics={
                "entities": len(draft.entities),
                "relations": len(draft.relations),
                "evidence": len(draft.evidence_cards),
            },
            artifact_path=str(self._draft_path(project_id)),
        )
        agent_report_path = self._agent_report_path(project_id)
        if agent_report_path.exists():
            agent_report_path.unlink()
        return draft

    def run_agent_report(
        self,
        project_id: str,
        scan_profile: str = SCAN_PROFILE_ARCHITECTURE,
        llm_mode: str = "deep",
    ) -> ProjectAgentReport:
        draft = self.load_draft(project_id)
        normalized_mode = "fast" if llm_mode == "fast" else "deep"
        report = MultiAgentPipeline.from_config(normalized_mode).run(
            draft=draft,
            scan_profile=scan_profile,
        )
        report = replace(
            report,
            metrics={
                **report.metrics,
                "llm_mode_fast": 1 if normalized_mode == "fast" else 0,
            },
        )
        self._agent_report_path(project_id).write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._append_version_event(
            project_id,
            kind="agent_report",
            status=report.status,
            metrics=report.metrics,
            artifact_path=str(self._agent_report_path(project_id)),
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
        result_metadata = {
            **result.metadata,
            "evidence_modalities": _evidence_modalities_for_ids(
                evidence_cards,
                result.evidence_card_ids,
            ),
            "cited_image_evidence_count": _cited_image_evidence_count(
                evidence_cards,
                result.evidence_card_ids,
            ),
        }
        return replace(
            result,
            metadata={
                **result_metadata,
                **({"hybrid_rag": rag_metadata} if rag_metadata is not None else {}),
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

    def graph_store_status(self) -> dict[str, str | bool | None]:
        provider = self.graph_provider.lower()
        return {
            "provider": provider,
            "mode": "production" if provider == "neo4j" else "local",
            "database": self.graph_config.get("database") if provider == "neo4j" else None,
            "uri": self.graph_config.get("uri") if provider == "neo4j" else None,
            "project_isolation": True,
        }

    def system_config_check(self) -> dict[str, Any]:
        try:
            settings = load_settings()
            settings_error = None
        except Exception as exc:  # noqa: BLE001
            settings = None
            settings_error = str(exc)

        if settings is None:
            return {
                "status": "error",
                "summary": "Settings could not be loaded.",
                "components": [
                    {
                        "id": "settings",
                        "label": "Settings",
                        "status": "error",
                        "provider": "config",
                        "model": None,
                        "configured": False,
                        "working": False,
                        "details": {},
                        "warnings": [settings_error or "Unknown settings error."],
                        "last_success": None,
                    }
                ],
                "metadata": {
                    "settings_path": _settings_path_text(),
                    "error": settings_error,
                },
            }

        agent_status = self.agent_status()
        graph_status = self.graph_store_status()
        latest_rag_status = self._latest_hybrid_rag_status()
        components = [
            _system_llm_component(settings, agent_status),
            _system_embedding_component(settings, latest_rag_status),
            _system_vision_component(settings, latest_rag_status),
            _system_graph_component(graph_status),
            _system_vector_component(settings, latest_rag_status),
            _system_hybrid_retrieval_component(settings, latest_rag_status),
            _system_agent_component(agent_status),
        ]
        overall = _system_overall_status(components)
        return {
            "status": overall,
            "summary": _system_config_summary(overall, components),
            "components": components,
            "metadata": {
                "settings_path": _settings_path_text(),
                "latest_hybrid_rag_project_id": latest_rag_status.get("project_id") if latest_rag_status else None,
                "archive_count": len(self.list_project_ids()),
                "runtime_evidence": _runtime_evidence_report(
                    components=components,
                    agent_status=agent_status,
                    graph_status=graph_status,
                    latest_rag_status=latest_rag_status,
                ),
            },
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

    def build_knowledge_universe(
        self,
        project_ids: list[str] | None = None,
        *,
        link_limit: int = 80,
        cluster_limit: int = 24,
    ) -> ProjectKnowledgeUniverse:
        available_project_ids = self.list_project_ids()
        selected_project_ids = _normalize_universe_project_ids(
            project_ids or available_project_ids,
            available_project_ids,
        )
        drafts: list[ProjectArchiveDraft] = []
        skipped_projects: list[dict[str, str]] = []
        for project_id in selected_project_ids:
            try:
                drafts.append(self.load_draft(project_id))
            except Exception as exc:  # noqa: BLE001
                skipped_projects.append({"project_id": project_id, "error": str(exc)})
        project_summaries = [
            _universe_project_summary(draft) for draft in drafts
        ]
        refs_by_project = {
            draft.project_id: _universe_entity_refs(draft, limit=180)
            for draft in drafts
        }
        neo4j_refs_by_project = self._neo4j_universe_refs(
            [draft.project_id for draft in drafts],
            limit_per_project=180,
        )
        if neo4j_refs_by_project:
            refs_by_project = _merge_universe_refs_by_project(
                refs_by_project,
                neo4j_refs_by_project,
                limit=220,
            )
        links, clusters = _build_cross_project_universe(
            refs_by_project,
            link_limit=link_limit,
            cluster_limit=cluster_limit,
        )
        metrics = {
            "projects": len(drafts),
            "entities": sum(len(draft.entities) for draft in drafts),
            "relations": sum(len(draft.relations) for draft in drafts),
            "evidence": sum(len(draft.evidence_cards) for draft in drafts),
            "links": len(links),
            "clusters": len(clusters),
            "skipped_projects": len(skipped_projects),
        }
        return ProjectKnowledgeUniverse(
            created_at=datetime.now(UTC).isoformat(),
            project_ids=[draft.project_id for draft in drafts],
            metrics=metrics,
            projects=project_summaries,
            links=links,
            clusters=clusters,
            metadata={
                "available_project_ids": available_project_ids,
                "requested_project_ids": selected_project_ids,
                "skipped_projects": skipped_projects,
                "method": "deterministic_entity_name_path_token_matching",
                "graph_provider": self.graph_provider,
                "neo4j_global_refs": sum(len(refs) for refs in neo4j_refs_by_project.values()),
                "limits": {
                    "links": link_limit,
                    "clusters": cluster_limit,
                    "entity_refs_per_project": 180,
                },
            },
        )

    def list_universe_paths(self) -> list[UniverseExplorationPath]:
        path = self._universe_paths_path()
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return [
            UniverseExplorationPath.from_dict(item)
            for item in data.get("paths", [])
            if isinstance(item, dict)
        ]

    def save_universe_path(
        self,
        *,
        name: str,
        project_ids: list[str],
        cluster_ids: list[str] | None = None,
        link_ids: list[str] | None = None,
        notes: str = "",
    ) -> UniverseExplorationPath:
        available = set(self.list_project_ids())
        normalized_project_ids = _unique_preserve_order(
            [project_id for project_id in project_ids if project_id in available],
            limit=12,
        )
        if not normalized_project_ids:
            raise ValueError("At least one known project id is required.")
        universe = self.build_knowledge_universe(normalized_project_ids)
        valid_cluster_ids = {cluster.id for cluster in universe.clusters}
        valid_link_ids = {link.id for link in universe.links}
        now = datetime.now(UTC).isoformat()
        selected_cluster_ids = _unique_preserve_order(
            [cluster_id for cluster_id in (cluster_ids or []) if cluster_id in valid_cluster_ids],
            limit=24,
        )
        selected_link_ids = _unique_preserve_order(
            [link_id for link_id in (link_ids or []) if link_id in valid_link_ids],
            limit=80,
        )
        saved = UniverseExplorationPath(
            id=f"path:{_stable_eval_id('|'.join([now, *normalized_project_ids, name]))}",
            name=name.strip() or _universe_path_default_name(normalized_project_ids),
            project_ids=normalized_project_ids,
            cluster_ids=selected_cluster_ids,
            link_ids=selected_link_ids,
            notes=notes.strip(),
            created_at=now,
            metadata={
                "cluster_count": len(selected_cluster_ids),
                "link_count": len(selected_link_ids),
                "method": "manual_universe_focus_save",
            },
        )
        paths = [saved, *self.list_universe_paths()]
        self._write_universe_paths(paths[:100])
        return saved

    def run_universe_agent_tasks(
        self,
        project_ids: list[str] | None = None,
        *,
        max_tasks: int = 6,
    ) -> list[UniverseAgentTask]:
        universe = self.build_knowledge_universe(project_ids=project_ids)
        tasks = _plan_universe_agent_tasks(universe, max_tasks=max_tasks)
        self._write_universe_tasks(tasks)
        return tasks

    def list_universe_agent_tasks(self) -> list[UniverseAgentTask]:
        path = self._universe_tasks_path()
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return [
            UniverseAgentTask.from_dict(item)
            for item in data.get("tasks", [])
            if isinstance(item, dict)
        ]

    def compare_project_architecture(
        self,
        left_project_id: str,
        right_project_id: str,
    ) -> ProjectArchitectureDiffReport:
        left = self.load_draft(left_project_id)
        right = self.load_draft(right_project_id)
        universe = self.build_knowledge_universe(
            project_ids=[left.project_id, right.project_id],
            link_limit=120,
            cluster_limit=80,
        )
        left_refs = _universe_entity_refs(left, limit=260)
        right_refs = _universe_entity_refs(right, limit=260)
        left_keys = {_universe_ref_key(ref): ref for ref in left_refs}
        right_keys = {_universe_ref_key(ref): ref for ref in right_refs}
        shared_keys = {key for key in left_keys if key and key in right_keys}
        only_left = [
            ref for key, ref in left_keys.items() if key and key not in shared_keys
        ][:24]
        only_right = [
            ref for key, ref in right_keys.items() if key and key not in shared_keys
        ][:24]
        metric_delta = {
            "halls": len(left.halls) - len(right.halls),
            "entities": len(left.entities) - len(right.entities),
            "relations": len(left.relations) - len(right.relations),
            "evidence": len(left.evidence_cards) - len(right.evidence_cards),
        }
        shared_clusters = [
            cluster
            for cluster in universe.clusters
            if {left.project_id, right.project_id}.issubset(set(cluster.project_ids))
        ][:18]
        shared_links = [
            link
            for link in universe.links
            if {link.source.project_id, link.target.project_id}
            == {left.project_id, right.project_id}
        ][:30]
        findings = _architecture_diff_findings(
            left_project_id=left.project_id,
            right_project_id=right.project_id,
            metric_delta=metric_delta,
            shared_clusters=shared_clusters,
            shared_links=shared_links,
            only_left=only_left,
            only_right=only_right,
        )
        component_delta = _architecture_component_delta(left, right)
        evidence_chain = _architecture_diff_evidence_chain(
            left=left,
            right=right,
            shared_links=shared_links,
            only_left=only_left,
            only_right=only_right,
        )
        risk_points = _architecture_diff_risk_points(
            metric_delta=metric_delta,
            shared_links=shared_links,
            only_left=only_left,
            only_right=only_right,
            component_delta=component_delta,
        )
        migration_notes = _architecture_diff_migration_notes(
            left.project_id,
            right.project_id,
            shared_clusters=shared_clusters,
            component_delta=component_delta,
            risk_points=risk_points,
        )
        sections = _architecture_diff_sections(
            left_project_id=left.project_id,
            right_project_id=right.project_id,
            shared_clusters=shared_clusters,
            shared_links=shared_links,
            only_left=only_left,
            only_right=only_right,
            component_delta=component_delta,
            risk_points=risk_points,
            migration_notes=migration_notes,
        )
        report = ProjectArchitectureDiffReport(
            id=f"diff:{_stable_eval_id(left.project_id + '|' + right.project_id)}",
            left_project_id=left.project_id,
            right_project_id=right.project_id,
            created_at=datetime.now(UTC).isoformat(),
            summary=_architecture_diff_summary(
                left.project_id,
                right.project_id,
                shared_clusters,
                shared_links,
                only_left,
                only_right,
            ),
            shared_clusters=shared_clusters,
            shared_links=shared_links,
            only_left=only_left,
            only_right=only_right,
            metric_delta=metric_delta,
            findings=findings,
            recommendations=_architecture_diff_recommendations(findings),
            sections=sections,
            evidence_chain=evidence_chain,
            component_delta=component_delta,
            risk_points=risk_points,
            migration_notes=migration_notes,
            metadata={
                "method": "deterministic_cross_project_graph_diff",
                "shared_key_count": len(shared_keys),
                "evidence_chain_count": len(evidence_chain),
                "universe_method": universe.metadata.get("method"),
                "neo4j_global_refs": universe.metadata.get("neo4j_global_refs", 0),
            },
        )
        self._architecture_diff_path(left.project_id, right.project_id).write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return report

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

    def load_project_intelligence_report(self, project_id: str) -> dict[str, Any]:
        self.load_draft(project_id)
        path = self._intelligence_report_path(project_id)
        if not path.exists():
            raise ValueError(f"Project intelligence report not found: {project_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def load_project_intelligence_markdown(self, project_id: str) -> str:
        self.load_draft(project_id)
        path = self._intelligence_report_markdown_path(project_id)
        if not path.exists():
            report = self.generate_project_intelligence_report(project_id)
            return self._intelligence_report_markdown_path(project_id).read_text(
                encoding="utf-8"
            )
        return path.read_text(encoding="utf-8")

    def load_project_intelligence_pdf(self, project_id: str) -> bytes:
        markdown = self.load_project_intelligence_markdown(project_id)
        return _simple_text_pdf(
            title=f"{project_id} Intelligence Report",
            lines=markdown.splitlines(),
        )

    def generate_project_intelligence_report(self, project_id: str) -> dict[str, Any]:
        draft = self.load_draft(project_id)
        entity_by_id = {entity.id: entity for entity in draft.entities}
        evidence_by_id = {card.id: card for card in draft.evidence_cards}
        relation_by_id = {relation.id: relation for relation in draft.relations}
        graph_report = self.graph_workspace_report(project_id)
        trust_report = self.agent_trust_report(project_id)
        multimodal = self.multimodal_insights(project_id)
        hybrid_status = ProjectHybridRAGIndex(self.storage_dir).load_status(project_id) or {}
        evaluation: ArchiveEvaluationReport | None = None
        evaluation_error = ""
        try:
            evaluation = self.load_evaluation_report(project_id)
        except ValueError as exc:
            evaluation_error = str(exc)
        agent_report: ProjectAgentReport | None = None
        agent_error = ""
        try:
            agent_report = self.load_agent_report(project_id)
        except ValueError as exc:
            agent_error = str(exc)

        core_entities = [
            {
                "id": start.get("entity_ids", [""])[0],
                "label": str(start.get("title", "")),
                "category": str(start.get("category", "")),
                "reason": str(start.get("reason", "")),
                "score": float(start.get("score", 0.0) or 0.0),
            }
            for start in graph_report.get("entry_points", [])[:8]
            if isinstance(start, dict) and start.get("entity_ids")
        ]
        architecture_layers = [
            {
                "name": str(cluster.get("label", "")),
                "entity_count": int(cluster.get("entity_count", 0) or 0),
                "relation_touch_count": int(cluster.get("relation_touch_count", 0) or 0),
                "top_entity_types": cluster.get("top_entity_types", []),
            }
            for cluster in graph_report.get("module_clusters", [])[:10]
            if isinstance(cluster, dict)
        ]
        risk_items = _project_report_risk_items(
            graph_report=graph_report,
            trust_report=trust_report,
            evaluation=evaluation,
            agent_report=agent_report,
            agent_error=agent_error,
            evaluation_error=evaluation_error,
        )
        evidence_chain = _project_report_evidence_chain(
            entity_by_id=entity_by_id,
            evidence_by_id=evidence_by_id,
            relation_by_id=relation_by_id,
            trust_report=trust_report,
            agent_report=agent_report,
            limit=18,
        )
        report = {
            "project_id": project_id,
            "created_at": datetime.now(UTC).isoformat(),
            "summary": _project_report_summary(
                draft=draft,
                graph_report=graph_report,
                agent_report=agent_report,
                evaluation=evaluation,
                hybrid_status=hybrid_status,
                multimodal=multimodal,
            ),
            "architecture_layers": architecture_layers,
            "core_modules": core_entities,
            "entry_points": graph_report.get("entry_points", []),
            "config_dependencies": _project_report_config_dependencies(draft),
            "call_chains": _project_report_call_chains(draft),
            "risks": risk_items,
            "evidence_chain": evidence_chain,
            "rag_citations": _project_report_rag_citations(hybrid_status),
            "multimodal_evidence": _project_report_multimodal_evidence(multimodal),
            "next_actions": _project_report_next_actions(
                graph_report=graph_report,
                risk_items=risk_items,
                evaluation=evaluation,
                hybrid_status=hybrid_status,
                multimodal=multimodal,
            ),
            "sections": _project_report_sections(
                architecture_layers=architecture_layers,
                core_entities=core_entities,
                risk_items=risk_items,
                evidence_chain=evidence_chain,
            ),
            "risk_index": _project_report_risk_index(risk_items),
            "evidence_index": _project_report_evidence_index(evidence_chain),
            "coverage": {
                "entities": len(draft.entities),
                "relations": len(draft.relations),
                "evidence": len(draft.evidence_cards),
                "quality_score": graph_report.get("quality", {}).get("score", 0.0),
                "quality_grade": graph_report.get("quality", {}).get("grade", "E"),
                "evaluation_score": (
                    evaluation.aggregate_metrics.get("case_score", 0.0)
                    if evaluation is not None
                    else 0.0
                ),
                "supported_claims": trust_report.get("metrics", {}).get("supported_claims", 0),
                "unsupported_claims": trust_report.get("metrics", {}).get("unsupported_claims", 0),
            },
            "metadata": {
                "method": "graph_quality_agent_trust_evaluation_multimodal_compiler",
                "agent_report_available": agent_report is not None,
                "agent_error": agent_error,
                "evaluation_available": evaluation is not None,
                "evaluation_error": evaluation_error,
                "markdown_path": str(self._intelligence_report_markdown_path(project_id)),
            },
        }
        self._write_project_intelligence_report(project_id, report)
        self._append_version_event(
            project_id,
            kind="intelligence_report",
            status="complete",
            metrics=report.get("coverage", {}),
            artifact_path=str(self._intelligence_report_path(project_id)),
        )
        return report

    def agent_task_plan(self, project_id: str) -> dict[str, Any]:
        draft = self.load_draft(project_id)
        graph_report = self.graph_workspace_report(project_id)
        hybrid_status = ProjectHybridRAGIndex(self.storage_dir).load_status(project_id) or {}
        multimodal = self.multimodal_insights(project_id)
        evaluation_available = True
        try:
            self.load_evaluation_report(project_id)
        except ValueError:
            evaluation_available = False
        tasks = _project_agent_task_plan(
            draft=draft,
            graph_report=graph_report,
            hybrid_status=hybrid_status,
            multimodal=multimodal,
            evaluation_available=evaluation_available,
        )
        return {
            "project_id": project_id,
            "created_at": datetime.now(UTC).isoformat(),
            "tasks": tasks,
            "summary": (
                f"Planned {len(tasks)} task(s) from graph quality, entry points, "
                "Hybrid RAG, multimodal, and evaluation status."
            ),
            "metadata": {
                "method": "deterministic_graph_quality_react_task_planner",
                "entity_count": len(draft.entities),
                "relation_count": len(draft.relations),
            },
        }

    def load_graph_curation(self, project_id: str) -> GraphCurationState:
        self.load_draft(project_id)
        path = self._graph_curation_path(project_id)
        if not path.exists():
            return GraphCurationState(project_id=project_id)

        data = json.loads(path.read_text(encoding="utf-8"))
        state = GraphCurationState.from_dict(data)
        if state.project_id and state.project_id != project_id:
            raise ValueError(f"Graph curation project mismatch: {project_id}")
        return replace(state, project_id=project_id)

    def save_graph_curation(
        self,
        project_id: str,
        *,
        important_entity_ids: list[str],
        hidden_relation_ids: list[str],
        merge_candidates: list[GraphMergeCandidate],
    ) -> GraphCurationState:
        draft = self.load_draft(project_id)
        entity_ids = {entity.id for entity in draft.entities}
        relation_ids = {relation.id for relation in draft.relations}
        normalized = GraphCurationState(
            project_id=project_id,
            important_entity_ids=_unique_existing(important_entity_ids, entity_ids, limit=500),
            hidden_relation_ids=_unique_existing(hidden_relation_ids, relation_ids, limit=500),
            merge_candidates=_normalize_merge_candidates(
                merge_candidates,
                entity_ids=entity_ids,
                limit=100,
            ),
            updated_at=datetime.now(UTC).isoformat(),
        )
        path = self._graph_curation_path(project_id)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(normalized.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(path)
        self._append_version_event(
            project_id,
            kind="graph_curation",
            status="complete",
            metrics={
                "important_entities": len(normalized.important_entity_ids),
                "hidden_relations": len(normalized.hidden_relation_ids),
                "merge_candidates": len(normalized.merge_candidates),
            },
            artifact_path=str(path),
        )
        return normalized

    def apply_graph_curation_suggestions(self, project_id: str) -> GraphCurationState:
        draft = self.load_draft(project_id)
        report = self.graph_workspace_report(project_id)
        entity_ids = {entity.id for entity in draft.entities}
        relation_ids = {relation.id for relation in draft.relations}
        current = self.load_graph_curation(project_id)
        quality = report.get("entity_quality", {}) if isinstance(report.get("entity_quality"), dict) else {}
        important = [
            str(item.get("id"))
            for item in quality.get("important_entities", [])[:40]
            if isinstance(item, dict) and item.get("id") in entity_ids
        ]
        hidden_relations = [
            str(item.get("id"))
            for item in quality.get("unsupported_relations", [])[:80]
            if isinstance(item, dict) and item.get("id") in relation_ids
        ]
        merge_candidates = list(current.merge_candidates)
        existing_candidate_ids = {candidate.id for candidate in merge_candidates}
        for item in quality.get("duplicate_candidates", [])[:30]:
            if not isinstance(item, dict):
                continue
            candidate_entity_ids = [
                str(entity_id)
                for entity_id in item.get("entity_ids", [])
                if str(entity_id) in entity_ids
            ][:12]
            if len(candidate_entity_ids) < 2:
                continue
            candidate_id = f"merge:suggestion:{_stable_eval_id(':'.join(candidate_entity_ids))}"
            if candidate_id in existing_candidate_ids:
                continue
            merge_candidates.append(
                GraphMergeCandidate(
                    id=candidate_id,
                    label=str(item.get("label") or item.get("key") or "Duplicate candidate"),
                    entity_ids=candidate_entity_ids,
                    created_at=datetime.now(UTC).isoformat(),
                )
            )
            existing_candidate_ids.add(candidate_id)
        return self.save_graph_curation(
            project_id,
            important_entity_ids=[
                *current.important_entity_ids,
                *important,
            ],
            hidden_relation_ids=[
                *current.hidden_relation_ids,
                *hidden_relations,
            ],
            merge_candidates=merge_candidates,
        )

    def list_version_history(self, project_id: str | None = None) -> dict[str, Any]:
        if project_id:
            self.load_draft(project_id)
            path = self._version_history_path(project_id)
            payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"events": []}
            events = payload.get("events", [])
        else:
            events = []
            if self.storage_dir.exists():
                for project in self.list_project_ids():
                    path = self._version_history_path(project)
                    if path.exists():
                        events.extend(json.loads(path.read_text(encoding="utf-8")).get("events", []))
        events = sorted(
            [event for event in events if isinstance(event, dict)],
            key=lambda event: str(event.get("created_at", "")),
            reverse=True,
        )
        return {
            "project_id": project_id,
            "events": events[:250],
            "metrics": {
                "events": len(events),
                "projects": len({event.get("project_id") for event in events if event.get("project_id")}),
            },
        }

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

    def graph_workspace_report(self, project_id: str) -> dict[str, Any]:
        draft = self.load_draft(project_id)
        summary = build_graph_summary(draft)
        curation = self.load_graph_curation(project_id)
        entity_by_id = {entity.id: entity for entity in draft.entities}
        evidence_by_id = {card.id: card for card in draft.evidence_cards}
        relations_by_entity: dict[str, list[ProjectRelation]] = defaultdict(list)
        for relation in draft.relations:
            relations_by_entity[relation.source_id].append(relation)
            relations_by_entity[relation.target_id].append(relation)

        module_clusters = _graph_module_clusters(draft, relations_by_entity)
        relation_confidence = [
            _relation_confidence_record(relation, evidence_by_id)
            for relation in draft.relations[:250]
        ]
        weak_relations = [
            item for item in relation_confidence
            if float(item["confidence"]) < 0.5
        ][:20]
        entity_quality = _graph_entity_quality_report(
            draft=draft,
            relations_by_entity=relations_by_entity,
            relation_confidence=relation_confidence,
        )
        language_structure = _language_structure_report(draft)
        boundary_candidates = _module_boundary_candidates(draft)
        snapshot = _graph_snapshot_payload(draft)
        previous_snapshot = self._load_graph_snapshot(project_id)
        snapshot_diff = _graph_snapshot_diff(previous_snapshot, snapshot)
        hybrid_status = ProjectHybridRAGIndex(self.storage_dir).load_status(project_id)
        quality = _graph_quality_report(
            draft=draft,
            relations_by_entity=relations_by_entity,
            hybrid_status=hybrid_status,
        )
        entry_points = _graph_entry_points(
            draft=draft,
            summary=summary,
            relations_by_entity=relations_by_entity,
            quality=quality,
        )
        self._write_graph_snapshot(project_id, snapshot)

        return {
            "project_id": project_id,
            "created_at": datetime.now(UTC).isoformat(),
            "summary": summary.to_dict(),
            "quality": quality,
            "entry_points": entry_points,
            "entity_quality": entity_quality,
            "language_structure": language_structure,
            "module_clusters": module_clusters,
            "module_boundaries": boundary_candidates,
            "relation_confidence": relation_confidence,
            "weak_relations": weak_relations,
            "curation": curation.to_dict(),
            "saved_viewpoints": {
                "important_entity_ids": curation.important_entity_ids,
                "hidden_relation_ids": curation.hidden_relation_ids,
                "merge_candidate_count": len(curation.merge_candidates),
            },
            "snapshot": snapshot,
            "snapshot_diff": snapshot_diff,
            "metadata": {
                "entity_count": len(entity_by_id),
                "evidence_count": len(evidence_by_id),
                "method": "degree_directory_hall_clustering_with_evidence_strength",
                "large_graph_policy": _large_graph_policy(draft, entity_quality),
            },
        }

    def agent_trust_report(self, project_id: str) -> dict[str, Any]:
        draft = self.load_draft(project_id)
        evidence_ids = {card.id for card in draft.evidence_cards}
        entity_ids = {entity.id for entity in draft.entities}
        relation_ids = {relation.id for relation in draft.relations}
        report = None
        report_error = None
        try:
            report = self.load_agent_report(project_id)
        except ValueError as exc:
            report_error = str(exc)

        mission_records = self._agent_mission_records(project_id)
        claims: list[dict[str, Any]] = []
        if report is not None:
            for agent_name, agent_result in report.agents.items():
                claim_evidence = [item for item in agent_result.evidence_card_ids if item in evidence_ids]
                claim_entities = [item for item in agent_result.entity_ids if item in entity_ids]
                claim_relations = [item for item in agent_result.relation_ids if item in relation_ids]
                claims.append(
                    {
                        "id": f"agent:{agent_name}",
                        "source": "multi_agent_report",
                        "agent": agent_name,
                        "summary": agent_result.summary,
                        "confidence": agent_result.confidence,
                        "evidence_ids": claim_evidence,
                        "entity_ids": claim_entities,
                        "relation_ids": claim_relations,
                        "status": _claim_support_status(claim_evidence, claim_entities, claim_relations),
                        "derivation": _agent_derivation(agent_result.metadata or {}),
                    }
                )
        for mission in mission_records[:5]:
            for task in mission.tasks:
                task_evidence = [item for item in task.evidence_ids if item in evidence_ids]
                task_entities = [
                    item
                    for item in [*task.input_entity_ids, *task.output_entity_ids]
                    if item in entity_ids
                ]
                claims.append(
                    {
                        "id": f"mission:{mission.id}:{task.id}",
                        "source": "react_agent_mission",
                        "agent": task.task_type,
                        "summary": task.objective,
                        "confidence": task.confidence,
                        "evidence_ids": task_evidence,
                        "entity_ids": _unique_preserve_order(task_entities, limit=20),
                        "relation_ids": [],
                        "status": _claim_support_status(task_evidence, task_entities, []),
                        "derivation": {
                            "allowed_tools": task.allowed_tools,
                            "steps_used": task.steps_used,
                            "verifier": mission.verifier_result.to_dict() if mission.verifier_result else None,
                        },
                    }
                )
        warnings = [
            f"Agent report unavailable: {report_error}"
        ] if report_error else []
        unsupported = [claim for claim in claims if claim["status"] == "unsupported"]
        low_confidence = [claim for claim in claims if float(claim.get("confidence", 0.0)) < 0.55]
        if unsupported:
            warnings.append(f"{len(unsupported)} claim(s) do not cite archive evidence.")
        if low_confidence:
            warnings.append(f"{len(low_confidence)} claim(s) are low confidence.")
        return {
            "project_id": project_id,
            "created_at": datetime.now(UTC).isoformat(),
            "claims": claims,
            "warnings": warnings,
            "metrics": {
                "claims": len(claims),
                "supported_claims": sum(1 for claim in claims if claim["status"] == "supported"),
                "partial_claims": sum(1 for claim in claims if claim["status"] == "partial"),
                "unsupported_claims": len(unsupported),
                "low_confidence_claims": len(low_confidence),
                "missions": len(mission_records),
            },
            "metadata": {
                "report_available": report is not None,
                "mission_ids": [mission.id for mission in mission_records[:12]],
                "method": "citation_presence_and_archive_id_validation",
            },
        }

    def multimodal_insights(self, project_id: str) -> dict[str, Any]:
        draft = self.load_draft(project_id)
        image_cards = [
            card for card in draft.evidence_cards
            if card.source_type == "image" or card.metadata.get("modality") == "image"
        ]
        extracted_entities: list[dict[str, Any]] = []
        extracted_relations: list[dict[str, Any]] = []
        for card in image_cards:
            extracted_entities.extend(_image_entity_candidates(card))
            extracted_relations.extend(_image_relation_candidates(card))
        quality_scores = [
            float(card.metadata.get("image_quality_score", 0.0) or 0.0)
            for card in image_cards
        ]
        alignments = _multimodal_entity_alignments(draft, image_cards)
        method_counts = Counter(
            str(card.metadata.get("understanding_method", "metadata_fallback"))
            for card in image_cards
        )
        supported_image_ids = {
            item["evidence_id"] for item in alignments if item.get("aligned_entities")
        }
        return {
            "project_id": project_id,
            "created_at": datetime.now(UTC).isoformat(),
            "image_count": len(image_cards),
            "vision_supported": sum(1 for card in image_cards if card.metadata.get("vision_enabled")),
            "ocr_supported": sum(1 for card in image_cards if card.metadata.get("ocr_text")),
            "average_quality": round(sum(quality_scores) / len(quality_scores), 4) if quality_scores else 0.0,
            "method_counts": dict(method_counts),
            "entity_alignment": {
                "aligned_image_count": len(supported_image_ids),
                "alignment_count": sum(len(item.get("aligned_entities", [])) for item in alignments),
                "items": alignments[:80],
            },
            "evidence_support": {
                "image_evidence_ids": [card.id for card in image_cards],
                "supported_image_evidence_ids": sorted(supported_image_ids),
                "support_status": (
                    "graph_aligned"
                    if supported_image_ids
                    else "image_only" if image_cards else "none"
                ),
            },
            "images": [
                {
                    "evidence_id": card.id,
                    "source_path": card.source_path,
                    "title": card.title,
                    "summary": card.snippet[:600],
                    "asset_id": card.metadata.get("asset_id"),
                    "understanding_method": card.metadata.get("understanding_method", "metadata_fallback"),
                    "vision_enabled": bool(card.metadata.get("vision_enabled")),
                    "ocr_text": card.metadata.get("ocr_text", ""),
                    "quality_score": card.metadata.get("image_quality_score", 0.0),
                    "diagram_entities": card.metadata.get("diagram_entities", []),
                    "diagram_relations": card.metadata.get("diagram_relations", []),
                    "aligned_entities": next(
                        (
                            item.get("aligned_entities", [])
                            for item in alignments
                            if item.get("evidence_id") == card.id
                        ),
                        [],
                    ),
                    "warnings": [card.metadata.get("vision_error")] if card.metadata.get("vision_error") else [],
                }
                for card in image_cards
            ],
            "graph_contributions": {
                "candidate_entities": extracted_entities[:80],
                "candidate_relations": extracted_relations[:80],
                "aligned_entities": [
                    entity
                    for item in alignments
                    for entity in item.get("aligned_entities", [])
                ][:80],
                "status": "candidate_only",
            },
            "metadata": {
                "method": "vision_caption_plus_heuristic_ocr_and_diagram_token_extraction",
                "note": "Image-derived graph items are exposed as candidates until human review or a stronger diagram parser promotes them.",
            },
        }

    def hybrid_rag_status(self, project_id: str) -> dict:
        status = ProjectHybridRAGIndex(self.storage_dir).load_status(project_id)
        if status is None:
            raise ValueError(f"Hybrid RAG index not found: {project_id}")
        draft = self.load_draft(project_id)
        return _hybrid_status_with_health(
            status=status,
            draft=draft,
            draft_path=self._draft_path(project_id),
            status_path=self._project_dir(project_id) / "hybrid_rag_status.json",
        )

    def rebuild_hybrid_rag_index(
        self,
        project_id: str,
        on_progress: Callable[[int, str], None] | None = None,
    ) -> dict:
        draft = self.load_draft(project_id)
        result = ProjectHybridRAGIndex(self.storage_dir).rebuild_from_draft(
            draft,
            on_progress=on_progress,
        )
        self._append_version_event(
            project_id,
            kind="hybrid_rag_rebuild",
            status="complete",
            metrics={
                "indexed_chunks": result.indexed_chunks,
                "candidate_chunks": result.candidate_chunks,
            },
            artifact_path=str(self._project_dir(project_id) / "hybrid_rag_status.json"),
        )
        return self.hybrid_rag_status(project_id)

    def _latest_hybrid_rag_status(self) -> dict[str, Any] | None:
        index = ProjectHybridRAGIndex(self.storage_dir)
        statuses = [
            status
            for project_id in self.list_project_ids()
            if (status := index.load_status(project_id)) is not None
        ]
        if not statuses:
            return None
        return sorted(
            statuses,
            key=lambda item: str(item.get("created_at", "")),
            reverse=True,
        )[0]

    def ingestion_diagnostics(self, project_id: str) -> dict[str, Any]:
        draft = self.load_draft(project_id)
        ingestion = dict(draft.metadata.get("ingestion", {}))
        scan = dict(ingestion.get("scan", {}))
        extraction = dict(ingestion.get("extraction", {}))
        upload = dict(ingestion.get("upload", {}))
        graph = dict(ingestion.get("graph", {}))
        if not graph:
            graph = {
                "entities": len(draft.entities),
                "relations": len(draft.relations),
                "evidence": len(draft.evidence_cards),
                "halls": len(draft.halls),
            }
        hybrid_status = ProjectHybridRAGIndex(self.storage_dir).load_status(project_id)
        image_cards = [
            card for card in draft.evidence_cards
            if card.source_type == "image" or card.metadata.get("modality") == "image"
        ]
        vision_enabled = sum(1 for card in image_cards if card.metadata.get("vision_enabled"))
        vision_errors = [
            str(card.metadata.get("vision_error"))
            for card in image_cards
            if card.metadata.get("vision_error")
        ]
        diagnostics = {
            "project_id": project_id,
            "created_at": datetime.now(UTC).isoformat(),
            "scan_profile": ingestion.get("scan_profile", "unknown"),
            "upload": upload,
            "scan": scan,
            "extraction": extraction,
            "graph": graph,
            "images": {
                "evidence_cards": len(image_cards),
                "vision_enabled_cards": vision_enabled,
                "fallback_cards": max(0, len(image_cards) - vision_enabled),
                "vision_errors": vision_errors[:12],
            },
            "hybrid_rag": hybrid_status or {
                "status": "missing",
                "indexed_chunks": 0,
                "text_chunks": 0,
                "image_chunks": 0,
                "fallback_reasons": ["Hybrid RAG status file was not found."],
            },
            "health": _ingestion_health(graph, scan, extraction, hybrid_status, image_cards),
            "recommendations": _ingestion_diagnostic_recommendations(
                graph=graph,
                scan=scan,
                extraction=extraction,
                upload=upload,
                hybrid_status=hybrid_status,
                image_cards=image_cards,
                vision_errors=vision_errors,
            ),
        }
        return diagnostics

    def load_evidence_asset(self, project_id: str, asset_id: str) -> Path:
        self.load_draft(project_id)
        if not re.fullmatch(r"[A-Fa-f0-9]{16}\.(png|jpg|jpeg|webp|gif|bmp)", asset_id):
            raise ValueError(f"Invalid evidence asset id: {asset_id}")
        path = self._project_dir(project_id) / "assets" / "images" / asset_id
        if not path.exists() or not path.is_file():
            raise ValueError(f"Evidence asset not found: {asset_id}")
        return path

    def generate_golden_questions(
        self,
        project_id: str,
        *,
        limit: int = 8,
    ) -> list[ArchiveGoldenQuestion]:
        draft = self.load_draft(project_id)
        entity_lookup = {entity.id: entity for entity in draft.entities}
        relation_lookup = {relation.id: relation for relation in draft.relations}
        relations_by_entity: dict[str, list] = {}
        for relation in draft.relations:
            relations_by_entity.setdefault(relation.source_id, []).append(relation)
            relations_by_entity.setdefault(relation.target_id, []).append(relation)

        questions: list[ArchiveGoldenQuestion] = []
        candidate_entities = [
            entity for entity in draft.entities if _is_eval_entity_candidate(entity)
        ] or draft.entities
        top_entities = sorted(
            candidate_entities,
            key=lambda entity: (
                _eval_entity_type_priority(entity),
                _eval_entity_path_priority(entity),
                len(relations_by_entity.get(entity.id, [])),
                len(entity.evidence_ids),
                1 if entity.source_path else 0,
                entity.name.lower(),
            ),
            reverse=True,
        )
        core_entity_ids = [entity.id for entity in top_entities[: min(5, len(top_entities))]]
        core_evidence_ids = _unique_preserve_order(
            [
                evidence_id
                for entity_id in core_entity_ids
                for evidence_id in entity_lookup[entity_id].evidence_ids
            ],
            limit=10,
        )
        core_relation_ids = _unique_preserve_order(
            [
                relation.id
                for entity_id in core_entity_ids
                for relation in relations_by_entity.get(entity_id, [])
            ],
            limit=10,
        )
        if core_entity_ids:
            questions.append(
                ArchiveGoldenQuestion(
                    id="golden:architecture-core",
                    question="What are the core architecture components in this project?",
                    category="architecture",
                    expected_entity_ids=core_entity_ids,
                    expected_relation_ids=core_relation_ids,
                    expected_evidence_ids=core_evidence_ids,
                    metadata={"source": "top_degree_entities"},
                )
            )

        for entity in top_entities[: max(0, limit - len(questions))]:
            related_relations = relations_by_entity.get(entity.id, [])[:6]
            evidence_ids = _unique_preserve_order(
                [
                    *entity.evidence_ids,
                    *[
                        evidence_id
                        for relation in related_relations
                        for evidence_id in relation.evidence_ids
                    ],
                ],
                limit=8,
            )
            questions.append(
                ArchiveGoldenQuestion(
                    id=f"golden:entity:{_stable_eval_id(entity.id)}",
                    question=(
                        f"Which evidence and graph neighbors explain {entity.name}"
                        f"{f' in {entity.source_path}' if entity.source_path else ''}?"
                    ),
                    category="evidence",
                    expected_entity_ids=[entity.id],
                    expected_relation_ids=[relation.id for relation in related_relations],
                    expected_evidence_ids=evidence_ids,
                    metadata={
                        "entity_type": entity.type,
                        "source_path": entity.source_path,
                    },
                )
            )
            if len(questions) >= limit:
                return questions

        relation_candidates = [
            relation
            for relation in draft.relations
            if relation.evidence_ids
            and (
                relation.source_id in entity_lookup
                and relation.target_id in entity_lookup
            )
        ] or draft.relations
        for relation in relation_candidates[: max(0, limit - len(questions))]:
            source = entity_lookup.get(relation.source_id)
            target = entity_lookup.get(relation.target_id)
            source_name = source.name if source else relation.source_id
            target_name = target.name if target else relation.target_id
            questions.append(
                ArchiveGoldenQuestion(
                    id=f"golden:relation:{_stable_eval_id(relation.id)}",
                    question=(
                        f"What evidence supports the {relation.type} relation "
                        f"between {source_name} and {target_name}?"
                    ),
                    category="relation",
                    expected_entity_ids=[relation.source_id, relation.target_id],
                    expected_relation_ids=[relation.id],
                    expected_evidence_ids=list(relation.evidence_ids),
                    metadata={"relation_type": relation.type},
                )
            )
            if len(questions) >= limit:
                return questions

        return questions

    def load_evaluation_report(self, project_id: str) -> ArchiveEvaluationReport:
        self.load_draft(project_id)
        path = self._evaluation_report_path(project_id)
        if not path.exists():
            raise ValueError(f"Project evaluation report not found: {project_id}")
        return ArchiveEvaluationReport.from_dict(
            json.loads(path.read_text(encoding="utf-8"))
        )

    def list_evaluation_history(self, project_id: str | None = None) -> dict[str, Any]:
        paths = []
        if project_id:
            self.load_draft(project_id)
            paths = [self._evaluation_history_path(project_id)]
        else:
            paths = [
                child / "evaluation_history.json"
                for child in self.storage_dir.iterdir()
                if child.is_dir()
            ] if self.storage_dir.exists() else []
        runs: list[dict[str, Any]] = []
        for path in paths:
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            runs.extend(
                dict(item)
                for item in payload.get("runs", [])
                if isinstance(item, dict)
            )
        runs = sorted(runs, key=lambda item: str(item.get("created_at", "")), reverse=True)
        return {
            "project_id": project_id,
            "runs": runs[:200],
            "metrics": {
                "runs": len(runs),
                "projects": len({str(run.get("project_id", "")) for run in runs if run.get("project_id")}),
            },
        }

    def load_stress_test_report(self) -> dict[str, Any]:
        path = self._stress_test_report_path()
        if not path.exists():
            raise ValueError("Project archive stress test report not found")
        return json.loads(path.read_text(encoding="utf-8"))

    def run_stress_test(
        self,
        project_ids: list[str] | None = None,
        *,
        run_evaluation: bool = False,
        evaluation_limit: int = 6,
    ) -> dict[str, Any]:
        available_project_ids = self.list_project_ids()
        selected_project_ids = project_ids or available_project_ids
        missing_project_ids = [
            project_id for project_id in selected_project_ids
            if project_id not in available_project_ids
        ]
        if missing_project_ids:
            raise ValueError(
                "Project archive not found: " + ", ".join(missing_project_ids[:5])
            )

        started_at = time.perf_counter()
        project_reports = [
            self._stress_test_project_report(
                project_id,
                run_evaluation=run_evaluation,
                evaluation_limit=evaluation_limit,
            )
            for project_id in selected_project_ids
        ]
        status_counts = Counter(str(item.get("status", "unknown")) for item in project_reports)
        quality_scores = [
            float(item.get("quality_score", 0.0) or 0.0)
            for item in project_reports
        ]
        evaluation_scores = [
            float(item.get("evaluation_score", 0.0) or 0.0)
            for item in project_reports
            if item.get("evaluation_available")
        ]
        report = {
            "id": f"stress:{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
            "created_at": datetime.now(UTC).isoformat(),
            "project_ids": selected_project_ids,
            "summary": {
                "project_count": len(project_reports),
                "pass_count": int(status_counts.get("pass", 0)),
                "warn_count": int(status_counts.get("warn", 0)),
                "fail_count": int(status_counts.get("fail", 0)),
                "average_quality_score": round(
                    sum(quality_scores) / len(quality_scores), 2
                ) if quality_scores else 0.0,
                "average_evaluation_score": round(
                    sum(evaluation_scores) / len(evaluation_scores), 4
                ) if evaluation_scores else 0.0,
                "hybrid_rag_ready_count": sum(
                    1 for item in project_reports if item.get("hybrid_rag_ready")
                ),
                "multimodal_ready_count": sum(
                    1 for item in project_reports if item.get("multimodal_ready")
                ),
                "duration_seconds": round(time.perf_counter() - started_at, 3),
            },
            "projects": project_reports,
            "regression_matrix": _stress_regression_matrix(project_reports),
            "language_coverage": _stress_language_coverage(project_reports),
            "blocking_failures": _stress_blocking_failures(project_reports),
            "recommendations": _stress_test_recommendations(project_reports),
            "metadata": {
                "method": "archive_quality_evaluation_hybrid_rag_multimodal_health_check",
                "run_evaluation": run_evaluation,
                "evaluation_limit": evaluation_limit,
            },
        }
        self._stress_test_report_path().write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return report

    def _stress_test_project_report(
        self,
        project_id: str,
        *,
        run_evaluation: bool,
        evaluation_limit: int,
    ) -> dict[str, Any]:
        try:
            draft = self.load_draft(project_id)
            relations_by_entity: dict[str, list[ProjectRelation]] = defaultdict(list)
            for relation in draft.relations:
                relations_by_entity[relation.source_id].append(relation)
                relations_by_entity[relation.target_id].append(relation)

            hybrid_status = ProjectHybridRAGIndex(self.storage_dir).load_status(project_id)
            quality = _graph_quality_report(
                draft=draft,
                relations_by_entity=relations_by_entity,
                hybrid_status=hybrid_status,
            )
            multimodal = self.multimodal_insights(project_id)
            evaluation_report: ArchiveEvaluationReport | None = None
            evaluation_error = ""
            try:
                evaluation_report = (
                    self.run_archive_evaluation(project_id, limit=evaluation_limit)
                    if run_evaluation
                    else self.load_evaluation_report(project_id)
                )
            except ValueError as exc:
                evaluation_error = str(exc)

            evaluation_metrics = (
                dict(evaluation_report.aggregate_metrics)
                if evaluation_report is not None
                else {}
            )
            evaluation_score = float(evaluation_metrics.get("case_score", 0.0) or 0.0)
            hybrid_rag_ready = bool(hybrid_status and int(hybrid_status.get("indexed_chunks", 0) or 0) > 0)
            multimodal_ready = bool(
                multimodal.get("image_count", 0)
                and (
                    multimodal.get("vision_supported", 0)
                    or multimodal.get("ocr_supported", 0)
                )
            )
            warnings = list(quality.get("warnings", []))
            if not evaluation_report:
                warnings.append("No evaluation report exists yet.")
            if not hybrid_rag_ready:
                warnings.append("Hybrid RAG index is missing or empty.")
            if int(multimodal.get("image_count", 0) or 0) and not multimodal_ready:
                warnings.append("Images exist but vision/OCR support is not active.")

            quality_score = float(quality.get("score", 0.0) or 0.0)
            status = "pass"
            if quality_score < 45 or len(draft.entities) == 0:
                status = "fail"
            elif quality_score < 70 or warnings:
                status = "warn"

            return {
                "project_id": project_id,
                "status": status,
                "quality_score": round(quality_score, 2),
                "quality_grade": quality.get("grade", "E"),
                "evaluation_available": evaluation_report is not None,
                "evaluation_score": round(evaluation_score, 4),
                "evaluation_metrics": evaluation_metrics,
                "evaluation_error": evaluation_error,
                "hybrid_rag_ready": hybrid_rag_ready,
                "hybrid_rag": hybrid_status or {},
                "multimodal_ready": multimodal_ready,
                "multimodal": {
                    "image_count": multimodal.get("image_count", 0),
                    "vision_supported": multimodal.get("vision_supported", 0),
                    "ocr_supported": multimodal.get("ocr_supported", 0),
                    "average_quality": multimodal.get("average_quality", 0.0),
                },
                "metrics": {
                    "halls": len(draft.halls),
                    "entities": len(draft.entities),
                    "relations": len(draft.relations),
                    "evidence": len(draft.evidence_cards),
                },
                "top_entity_types": Counter(
                    entity.type for entity in draft.entities
                ).most_common(8),
                "language_structure": _language_structure_report(draft),
                "warnings": warnings[:12],
                "recommendations": list(quality.get("recommendations", []))[:8],
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "project_id": project_id,
                "status": "fail",
                "quality_score": 0.0,
                "quality_grade": "E",
                "evaluation_available": False,
                "evaluation_score": 0.0,
                "evaluation_metrics": {},
                "evaluation_error": str(exc),
                "hybrid_rag_ready": False,
                "hybrid_rag": {},
                "multimodal_ready": False,
                "multimodal": {},
                "metrics": {
                    "halls": 0,
                    "entities": 0,
                    "relations": 0,
                    "evidence": 0,
                },
                "top_entity_types": [],
                "warnings": [str(exc)],
                "recommendations": ["Open the archive generation logs and rerun ingestion for this project."],
            }

    def run_archive_evaluation(
        self,
        project_id: str,
        *,
        limit: int = 8,
    ) -> ArchiveEvaluationReport:
        draft = self.load_draft(project_id)
        questions = self.generate_golden_questions(project_id, limit=limit)
        entity_lookup = {entity.id: entity for entity in draft.entities}
        evidence_lookup = {card.id: card for card in draft.evidence_cards}
        entity_ids = {entity.id for entity in draft.entities}
        relation_ids = {relation.id for relation in draft.relations}
        evidence_ids = {card.id for card in draft.evidence_cards}
        relation_lookup = {relation.id: relation for relation in draft.relations}
        relations_by_entity: dict[str, list] = {}
        for relation in draft.relations:
            relations_by_entity.setdefault(relation.source_id, []).append(relation)
            relations_by_entity.setdefault(relation.target_id, []).append(relation)
        recommended_start_ids = [
            start.entity_id for start in build_graph_summary(draft).recommended_starts
        ]

        case_results: list[ArchiveEvaluationCaseResult] = []
        hybrid_rag_failures: list[str] = []
        for question in questions:
            graph_matches = self.search_graph_entities(
                project_id,
                query=question.question,
                limit=12,
            )
            matched_entity_ids = _unique_preserve_order(
                [
                    *[result.entity_id for result in graph_matches],
                    *(
                        recommended_start_ids
                        if question.category == "architecture"
                        else []
                    ),
                ],
                limit=20,
            )
            matched_relation_ids = _unique_preserve_order(
                [
                    relation.id
                    for entity_id in matched_entity_ids[:8]
                    for relation in relations_by_entity.get(entity_id, [])
                ],
                limit=30,
            )
            matched_evidence_ids = _unique_preserve_order(
                [
                    evidence_id
                    for entity_id in matched_entity_ids[:8]
                    for entity in draft.entities
                    if entity.id == entity_id
                    for evidence_id in entity.evidence_ids
                ],
                limit=30,
            )
            matched_evidence_ids = _unique_preserve_order(
                [
                    *matched_evidence_ids,
                    *[
                        evidence_id
                        for relation_id in matched_relation_ids
                        for evidence_id in relation_lookup[relation_id].evidence_ids
                    ],
                ],
                limit=40,
            )

            rag_metadata: dict[str, Any] = {"enabled": False, "result_count": 0}
            try:
                rag_result = ProjectHybridRAGIndex(self.storage_dir).search(
                    project_id=project_id,
                    query=question.question,
                    top_k=8,
                )
                if rag_result is not None:
                    rag_metadata = rag_result.to_metadata()
                    for result in rag_result.results:
                        metadata = result.metadata
                        if metadata.get("entity_id"):
                            matched_entity_ids.append(str(metadata["entity_id"]))
                        if metadata.get("relation_id"):
                            matched_relation_ids.append(str(metadata["relation_id"]))
                        if metadata.get("evidence_id"):
                            matched_evidence_ids.append(str(metadata["evidence_id"]))
            except Exception as exc:  # noqa: BLE001
                rag_metadata = {
                    "enabled": True,
                    "error": str(exc),
                    "result_count": 0,
                }
                hybrid_rag_failures.append(str(exc))

            expanded_relation_ids = _unique_preserve_order(
                [
                    relation.id
                    for entity_id in matched_entity_ids[:16]
                    for relation in relations_by_entity.get(entity_id, [])
                ],
                limit=60,
            )
            matched_relation_ids = _unique_preserve_order(
                [*matched_relation_ids, *expanded_relation_ids],
                limit=60,
            )
            matched_evidence_ids = _unique_preserve_order(
                [
                    *matched_evidence_ids,
                    *[
                        evidence_id
                        for entity_id in matched_entity_ids[:16]
                        if entity_id in entity_lookup
                        for evidence_id in entity_lookup[entity_id].evidence_ids
                    ],
                    *[
                        evidence_id
                        for relation_id in matched_relation_ids
                        if relation_id in relation_lookup
                        for evidence_id in relation_lookup[relation_id].evidence_ids
                    ],
                ],
                limit=80,
            )

            matched_entity_ids = _unique_preserve_order(
                [item for item in matched_entity_ids if item in entity_ids],
                limit=20,
            )
            matched_relation_ids = _unique_preserve_order(
                [item for item in matched_relation_ids if item in relation_ids],
                limit=60,
            )
            matched_evidence_ids = _unique_preserve_order(
                [item for item in matched_evidence_ids if item in evidence_ids],
                limit=80,
            )
            metrics = {
                "entity_hit_rate": _soft_entity_hit_rate(
                    question.expected_entity_ids,
                    matched_entity_ids,
                    entity_lookup=entity_lookup,
                    relations_by_entity=relations_by_entity,
                ),
                "relation_hit_rate": _soft_relation_hit_rate(
                    question.expected_relation_ids,
                    matched_relation_ids,
                    relation_lookup=relation_lookup,
                ),
                "evidence_hit_rate": _soft_evidence_hit_rate(
                    question.expected_evidence_ids,
                    matched_evidence_ids,
                    evidence_lookup=evidence_lookup,
                ),
            }
            metrics["case_score"] = round(
                (
                    metrics["entity_hit_rate"] * 0.42
                    + metrics["relation_hit_rate"] * 0.28
                    + metrics["evidence_hit_rate"] * 0.30
                ),
                4,
            )
            case_results.append(
                ArchiveEvaluationCaseResult(
                    question_id=question.id,
                    question=question.question,
                    category=question.category,
                    mode="deterministic_graph_hybrid_rag",
                    expected_entity_ids=question.expected_entity_ids,
                    expected_relation_ids=question.expected_relation_ids,
                    expected_evidence_ids=question.expected_evidence_ids,
                    matched_entity_ids=matched_entity_ids,
                    matched_relation_ids=matched_relation_ids,
                    matched_evidence_ids=matched_evidence_ids,
                    metrics=metrics,
                    summary=_evaluation_case_summary(metrics, rag_metadata),
                    metadata={
                        "golden_metadata": question.metadata,
                        "hybrid_rag": rag_metadata,
                    },
                )
            )

        aggregate_metrics = _aggregate_evaluation_metrics(
            case_results,
            total_entities=len(entity_ids),
            total_relations=len(relation_ids),
            total_evidence=len(evidence_ids),
        )
        report = ArchiveEvaluationReport(
            project_id=project_id,
            created_at=datetime.now(UTC).isoformat(),
            golden_question_count=len(questions),
            aggregate_metrics=aggregate_metrics,
            case_results=case_results,
            metadata={
                "method": "golden_questions_from_archive_graph",
                "hybrid_rag_failures": hybrid_rag_failures[:5],
                "limits": {"golden_questions": limit},
            },
        )
        path = self._evaluation_report_path(project_id)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(path)
        self._append_evaluation_history(report)
        self._append_version_event(
            project_id,
            kind="evaluation",
            status="complete",
            metrics=report.aggregate_metrics,
            artifact_path=str(path),
        )
        return report

    def run_agent_eval_harness(
        self,
        project_id: str,
        *,
        run_evaluation: bool = False,
        evaluation_limit: int = 8,
        run_agent_report: bool = False,
        agent_llm_mode: str = "fast",
    ) -> dict[str, Any]:
        draft = self.load_draft(project_id)
        started_at = time.perf_counter()
        previous_report = self._latest_agent_eval_history(project_id)

        agent_report: ProjectAgentReport | None = None
        agent_error = ""
        try:
            agent_report = (
                self.run_agent_report(project_id, llm_mode=agent_llm_mode)
                if run_agent_report
                else self.load_agent_report(project_id)
            )
        except ValueError as exc:
            agent_error = str(exc)

        evaluation: ArchiveEvaluationReport | None = None
        evaluation_error = ""
        try:
            evaluation = (
                self.run_archive_evaluation(project_id, limit=evaluation_limit)
                if run_evaluation
                else self.load_evaluation_report(project_id)
            )
        except ValueError as exc:
            evaluation_error = str(exc)

        try:
            trust_report = self.agent_trust_report(project_id)
        except ValueError:
            trust_report = _empty_agent_trust_report(project_id)

        try:
            rag_status = self.hybrid_rag_status(project_id)
        except ValueError as exc:
            rag_status = {"error": str(exc), "indexed_chunks": 0, "health": "missing"}

        try:
            multimodal = self.multimodal_insights(project_id)
        except ValueError:
            multimodal = {"project_id": project_id, "image_count": 0, "quality_score": 0.0}

        missions = self._agent_mission_records(project_id)
        metrics = _agent_eval_metrics(
            draft=draft,
            agent_report=agent_report,
            agent_error=agent_error,
            evaluation=evaluation,
            evaluation_error=evaluation_error,
            trust_report=trust_report,
            rag_status=rag_status,
            multimodal=multimodal,
            missions=missions,
        )
        gates = _agent_eval_gates(metrics)
        regression = _agent_eval_regression(metrics, previous_report)
        recommendations = _agent_eval_recommendations(
            metrics=metrics,
            gates=gates,
            regression=regression,
            agent_error=agent_error,
            evaluation_error=evaluation_error,
        )
        report = {
            "id": f"agent-eval:{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}",
            "project_id": project_id,
            "created_at": datetime.now(UTC).isoformat(),
            "status": _agent_eval_overall_status(gates, regression),
            "duration_seconds": round(time.perf_counter() - started_at, 3),
            "metrics": metrics,
            "quality_gates": gates,
            "regression": regression,
            "recommendations": recommendations,
            "artifacts": {
                "agent_report": str(self._agent_report_path(project_id)) if agent_report else "",
                "evaluation_report": str(self._evaluation_report_path(project_id)) if evaluation else "",
                "memory": str(self._agent_memory_path(project_id)),
            },
            "metadata": {
                "method": "deterministic_agent_eval_harness_v1",
                "run_evaluation": run_evaluation,
                "evaluation_limit": evaluation_limit,
                "run_agent_report": run_agent_report,
                "agent_llm_mode": agent_llm_mode,
                "agent_error": agent_error,
                "evaluation_error": evaluation_error,
            },
        }
        memory = self._update_agent_memory(
            project_id=project_id,
            draft=draft,
            report=report,
            agent_report=agent_report,
            evaluation=evaluation,
            trust_report=trust_report,
            rag_status=rag_status,
            missions=missions,
        )
        report["memory_update"] = {
            "fact_count": len(memory.get("facts", [])),
            "risk_count": len(memory.get("risks", [])),
            "run_count": len(memory.get("harness_runs", [])),
            "updated_at": memory.get("updated_at", ""),
        }
        self._write_agent_eval_report(project_id, report)
        self._append_agent_eval_history(project_id, report)
        self._append_version_event(
            project_id,
            kind="agent_eval_harness",
            status=report["status"],
            metrics=metrics,
            artifact_path=str(self._agent_eval_report_path(project_id)),
        )
        return report

    def load_agent_eval_report(self, project_id: str) -> dict[str, Any]:
        self.load_draft(project_id)
        path = self._agent_eval_report_path(project_id)
        if not path.exists():
            raise ValueError(f"Project AgentEval report not found: {project_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def load_agent_memory(self, project_id: str) -> dict[str, Any]:
        self.load_draft(project_id)
        path = self._agent_memory_path(project_id)
        if not path.exists():
            return _empty_agent_memory(project_id)
        return json.loads(path.read_text(encoding="utf-8"))

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

    def _write_agent_eval_report(self, project_id: str, report: dict[str, Any]) -> None:
        path = self._agent_eval_report_path(project_id)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(path)

    def _append_agent_eval_history(self, project_id: str, report: dict[str, Any]) -> None:
        path = self._agent_eval_history_path(project_id)
        payload = {"project_id": project_id, "runs": []}
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {"project_id": project_id, "runs": []}
        runs = [
            {
                "id": report.get("id"),
                "project_id": project_id,
                "created_at": report.get("created_at"),
                "status": report.get("status"),
                "metrics": report.get("metrics", {}),
                "regression": report.get("regression", {}),
                "quality_gates": report.get("quality_gates", []),
            },
            *[
                dict(item)
                for item in payload.get("runs", [])
                if isinstance(item, dict)
            ],
        ][:100]
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps({"project_id": project_id, "runs": runs}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(path)

    def _latest_agent_eval_history(self, project_id: str) -> dict[str, Any] | None:
        path = self._agent_eval_history_path(project_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        runs = [item for item in payload.get("runs", []) if isinstance(item, dict)]
        return runs[0] if runs else None

    def _update_agent_memory(
        self,
        *,
        project_id: str,
        draft: ProjectArchiveDraft,
        report: dict[str, Any],
        agent_report: ProjectAgentReport | None,
        evaluation: ArchiveEvaluationReport | None,
        trust_report: dict[str, Any],
        rag_status: dict[str, Any],
        missions: list[AgentMission],
    ) -> dict[str, Any]:
        memory = self.load_agent_memory(project_id)
        facts = list(memory.get("facts", []))
        facts.extend(_agent_memory_facts(draft, report, evaluation, rag_status))
        risks = list(memory.get("risks", []))
        risks.extend(_agent_memory_risks(report, trust_report, rag_status))
        entities = list(memory.get("entities", []))
        evidence = list(memory.get("evidence", []))
        relations = list(memory.get("relations", []))
        if agent_report is not None:
            for role_result in agent_report.agents.values():
                entities.extend(role_result.entity_ids)
                evidence.extend(role_result.evidence_card_ids)
                relations.extend(role_result.relation_ids)
        for mission in missions[:3]:
            for task in mission.tasks:
                entities.extend([*task.input_entity_ids, *task.output_entity_ids])
                evidence.extend(task.evidence_ids)
                relations.extend(_agent_task_relation_ids(task))
        harness_runs = [
            {
                "id": report.get("id"),
                "created_at": report.get("created_at"),
                "status": report.get("status"),
                "metrics": report.get("metrics", {}),
                "regression": report.get("regression", {}),
            },
            *[
                dict(item)
                for item in memory.get("harness_runs", [])
                if isinstance(item, dict)
            ],
        ][:50]
        updated = {
            "project_id": project_id,
            "updated_at": datetime.now(UTC).isoformat(),
            "facts": _dedupe_memory_items(facts, key="text", limit=80),
            "entities": _unique_preserve_order([str(item) for item in entities if item], limit=120),
            "evidence": _unique_preserve_order([str(item) for item in evidence if item], limit=120),
            "relations": _unique_preserve_order([str(item) for item in relations if item], limit=120),
            "risks": _dedupe_memory_items(risks, key="title", limit=80),
            "harness_runs": harness_runs,
            "recommendations": _unique_preserve_order(
                [str(item) for item in report.get("recommendations", [])],
                limit=30,
            ),
            "metadata": {
                "method": "project_scoped_file_memory_v1",
                "storage": str(self._agent_memory_path(project_id)),
            },
        }
        path = self._agent_memory_path(project_id)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(updated, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(path)
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

    def agent_mission_visualization(self, mission_id: str) -> dict[str, Any]:
        self._validate_mission_id(mission_id)
        mission = self.load_agent_mission(mission_id)
        return _agent_mission_visualization_report(mission)

    def update_agent_mission_status(self, mission_id: str, status: str) -> AgentMission:
        self._validate_mission_id(mission_id)
        return self._agent_mission_runtime().update_status(mission_id, status)

    def _agent_mission_records(self, project_id: str) -> list[AgentMission]:
        project_dir = self._project_dir(project_id)
        candidates = [
            project_dir / "agent_missions",
            project_dir / "missions" / "agent",
            project_dir / "missions",
        ]
        records: list[AgentMission] = []
        for directory in candidates:
            if not directory.exists() or not directory.is_dir():
                continue
            for path in directory.glob("*.json"):
                try:
                    mission = AgentMission.from_dict(json.loads(path.read_text(encoding="utf-8")))
                except Exception:
                    continue
                if mission.project_id == project_id:
                    records.append(mission)
        deduped = {mission.id: mission for mission in records}
        return sorted(
            deduped.values(),
            key=lambda mission: mission.created_at,
            reverse=True,
        )

    def _agent_mission_runtime(self) -> AgentMissionRuntime:
        enhancer = create_archive_llm_enhancer_from_config()
        if enhancer is not None and hasattr(enhancer.llm, "timeout"):
            enhancer.llm.timeout = max(float(getattr(enhancer.llm, "timeout", 60.0)), 120.0)
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

    def _write_draft(self, draft: ProjectArchiveDraft) -> None:
        path = self._draft_path(draft.project_id)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(draft.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(path)

    def _agent_report_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "agent_report.json"

    def _intelligence_report_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "project_intelligence_report.json"

    def _intelligence_report_markdown_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "project_intelligence_report.md"

    def _write_project_intelligence_report(
        self,
        project_id: str,
        report: dict[str, Any],
    ) -> None:
        json_path = self._intelligence_report_path(project_id)
        json_tmp = json_path.with_suffix(".tmp")
        json_tmp.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        json_tmp.replace(json_path)
        markdown_path = self._intelligence_report_markdown_path(project_id)
        markdown_tmp = markdown_path.with_suffix(".tmp")
        markdown_tmp.write_text(
            _project_report_markdown(report),
            encoding="utf-8",
        )
        markdown_tmp.replace(markdown_path)

    def _graph_curation_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "graph_curation.json"

    def _evaluation_report_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "evaluation_report.json"

    def _evaluation_history_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "evaluation_history.json"

    def _agent_eval_report_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "agent_eval_report.json"

    def _agent_eval_history_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "agent_eval_history.json"

    def _agent_memory_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "agent_memory.json"

    def _stress_test_report_path(self) -> Path:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        return self.storage_dir / "stress_test_report.json"

    def _version_history_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "version_history.json"

    def _append_version_event(
        self,
        project_id: str,
        *,
        kind: str,
        status: str,
        metrics: dict[str, Any],
        artifact_path: str,
    ) -> None:
        path = self._version_history_path(project_id)
        payload = {"events": []}
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {"events": []}
        events = [
            event for event in payload.get("events", [])
            if isinstance(event, dict)
        ]
        event = {
            "id": f"version:{kind}:{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}",
            "project_id": project_id,
            "kind": kind,
            "status": status,
            "created_at": datetime.now(UTC).isoformat(),
            "metrics": metrics,
            "artifact_path": artifact_path,
        }
        payload["events"] = [event, *events][:300]
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(path)

    def _append_evaluation_history(self, report: ArchiveEvaluationReport) -> None:
        path = self._evaluation_history_path(report.project_id)
        payload = {"runs": []}
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
        runs = [
            {
                "project_id": report.project_id,
                "created_at": report.created_at,
                "golden_question_count": report.golden_question_count,
                "aggregate_metrics": report.aggregate_metrics,
                "case_count": len(report.case_results),
                "metadata": report.metadata,
            },
            *[
                dict(item)
                for item in payload.get("runs", [])
                if isinstance(item, dict)
            ],
        ][:100]
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps({"runs": runs}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(path)

    def _graph_snapshot_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "graph_snapshot.json"

    def _load_graph_snapshot(self, project_id: str) -> dict[str, Any] | None:
        path = self._graph_snapshot_path(project_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_graph_snapshot(self, project_id: str, snapshot: dict[str, Any]) -> None:
        path = self._graph_snapshot_path(project_id)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(path)

    def _universe_dir(self) -> Path:
        path = self.storage_dir / "_universe"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _universe_paths_path(self) -> Path:
        return self._universe_dir() / "exploration_paths.json"

    def _universe_tasks_path(self) -> Path:
        return self._universe_dir() / "agent_tasks.json"

    def _architecture_diff_path(
        self,
        left_project_id: str,
        right_project_id: str,
    ) -> Path:
        diff_id = _stable_eval_id("|".join(sorted([left_project_id, right_project_id])))
        return self._universe_dir() / f"architecture_diff_{diff_id}.json"

    def _write_universe_paths(self, paths: list[UniverseExplorationPath]) -> None:
        path = self._universe_paths_path()
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(
                {"paths": [item.to_dict() for item in paths]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp_path.replace(path)

    def _write_universe_tasks(self, tasks: list[UniverseAgentTask]) -> None:
        path = self._universe_tasks_path()
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(
                {"tasks": [task.to_dict() for task in tasks]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp_path.replace(path)

    def _neo4j_universe_refs(
        self,
        project_ids: list[str],
        *,
        limit_per_project: int,
    ) -> dict[str, list[ProjectUniverseEntityRef]]:
        if self.graph_provider.lower() != "neo4j":
            return {}
        store = None
        try:
            store = create_graph_store(
                path=self._graph_path("__universe__"),
                preferred_provider=self.graph_provider,
                project_id="__universe__",
                config=self.graph_config,
            )
            refs = store.list_universe_entity_refs(
                project_ids,
                limit_per_project=limit_per_project,
            )
        except Exception:
            return {}
        finally:
            if store is not None and hasattr(store, "close"):
                try:
                    store.close()  # type: ignore[attr-defined]
                except Exception:
                    pass
        refs_by_project: dict[str, list[ProjectUniverseEntityRef]] = {}
        for ref in refs:
            refs_by_project.setdefault(ref.project_id, []).append(ref)
        return refs_by_project

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
        if self.graph_provider.lower() == "neo4j":
            return self._project_dir(project_id) / "graph.neo4j"
        return self._project_dir(project_id) / "graph.sqlite"


def _unique_existing(
    values: list[str],
    existing_values: set[str],
    *,
    limit: int,
) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        item = str(value)
        if item in seen or item not in existing_values:
            continue
        seen.add(item)
        normalized.append(item)
        if len(normalized) >= limit:
            break
    return normalized


def _normalize_merge_candidates(
    candidates: list[GraphMergeCandidate],
    *,
    entity_ids: set[str],
    limit: int,
) -> list[GraphMergeCandidate]:
    normalized: list[GraphMergeCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate_entity_ids = _unique_existing(
            candidate.entity_ids,
            entity_ids,
            limit=20,
        )
        if len(candidate_entity_ids) < 2:
            continue
        candidate_id = candidate.id or f"merge:{'|'.join(sorted(candidate_entity_ids))}"
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        normalized.append(
            GraphMergeCandidate(
                id=candidate_id,
                label=candidate.label or candidate_entity_ids[0],
                entity_ids=candidate_entity_ids,
                created_at=candidate.created_at,
            )
        )
        if len(normalized) >= limit:
            break
    return normalized


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


def _draft_with_ingestion_updates(
    draft: ProjectArchiveDraft,
    updates: dict[str, Any],
) -> ProjectArchiveDraft:
    metadata = dict(draft.metadata)
    ingestion = dict(metadata.get("ingestion", {}))
    ingestion.update(updates)
    if "stage_timings" in updates:
        ingestion["stage_timings"] = list(updates.get("stage_timings") or [])
    metadata["ingestion"] = ingestion
    return replace(draft, metadata=metadata)


def _project_archive_graph_store_config() -> tuple[str, dict[str, Any]]:
    try:
        settings = load_settings()
    except Exception:
        return "sqlite", {}
    archive_settings = getattr(settings, "project_archive", None)
    graph_settings = getattr(archive_settings, "graph_store", None)
    if graph_settings is None:
        return "sqlite", {}
    provider = str(getattr(graph_settings, "provider", "sqlite") or "sqlite").lower()
    return provider, {
        "uri": getattr(graph_settings, "uri", None),
        "username": getattr(graph_settings, "username", None),
        "password": getattr(graph_settings, "password", None),
        "database": getattr(graph_settings, "database", None),
    }


def _normalize_universe_project_ids(
    requested_project_ids: list[str],
    available_project_ids: list[str],
) -> list[str]:
    available = set(available_project_ids)
    selected: list[str] = []
    for project_id in requested_project_ids:
        item = str(project_id).strip()
        if not item:
            continue
        if item not in available:
            raise ValueError(f"Project archive not found: {item}")
        if item not in selected:
            selected.append(item)
    return selected


def _universe_project_summary(draft: ProjectArchiveDraft) -> ProjectUniverseProject:
    entity_type_counts = Counter(entity.type for entity in draft.entities)
    modality_counts = Counter(
        str(card.metadata.get("modality") or card.source_type)
        for card in draft.evidence_cards
    )
    return ProjectUniverseProject(
        project_id=draft.project_id,
        metrics={
            "halls": len(draft.halls),
            "entities": len(draft.entities),
            "relations": len(draft.relations),
            "evidence": len(draft.evidence_cards),
        },
        top_entity_types=[
            {"type": entity_type, "count": count}
            for entity_type, count in entity_type_counts.most_common(6)
        ],
        evidence_modalities=dict(modality_counts),
        hall_names=[hall.name for hall in draft.halls[:8]],
    )


def _universe_entity_refs(
    draft: ProjectArchiveDraft,
    *,
    limit: int,
) -> list[ProjectUniverseEntityRef]:
    degree_counts = Counter()
    for relation in draft.relations:
        degree_counts[relation.source_id] += 1
        degree_counts[relation.target_id] += 1
    hall_ids_by_entity: dict[str, list[str]] = {}
    for hall in draft.halls:
        for entity_id in hall.entity_ids:
            hall_ids_by_entity.setdefault(entity_id, []).append(hall.id)
    ranked_entities = sorted(
        draft.entities,
        key=lambda entity: (
            degree_counts[entity.id],
            len(entity.evidence_ids),
            entity.type != "File",
            entity.name.lower(),
        ),
        reverse=True,
    )
    return [
        ProjectUniverseEntityRef(
            project_id=draft.project_id,
            entity_id=entity.id,
            label=entity.name,
            type=entity.type,
            source_path=entity.source_path,
            degree=int(degree_counts[entity.id]),
            evidence_count=len(entity.evidence_ids),
            hall_ids=hall_ids_by_entity.get(entity.id, []),
        )
        for entity in ranked_entities[:limit]
    ]


def _build_cross_project_universe(
    refs_by_project: dict[str, list[ProjectUniverseEntityRef]],
    *,
    link_limit: int,
    cluster_limit: int,
) -> tuple[list[ProjectUniverseLink], list[ProjectUniverseCluster]]:
    buckets: dict[tuple[str, str], list[ProjectUniverseEntityRef]] = defaultdict(list)
    for refs in refs_by_project.values():
        for ref in refs:
            name_key = _universe_name_key(ref.label)
            if name_key:
                buckets[("shared_name", name_key)].append(ref)
            path_key = _universe_path_key(ref.source_path)
            if path_key:
                buckets[("shared_path", path_key)].append(ref)
            for token in _universe_tokens(ref.label):
                buckets[("shared_concept", token)].append(ref)

    links_by_id: dict[str, ProjectUniverseLink] = {}
    clusters: list[ProjectUniverseCluster] = []
    for (bucket_type, bucket_key), refs in buckets.items():
        refs_by_seen_project: dict[str, ProjectUniverseEntityRef] = {}
        for ref in sorted(
            refs,
            key=lambda item: (item.degree, item.evidence_count, item.label.lower()),
            reverse=True,
        ):
            refs_by_seen_project.setdefault(ref.project_id, ref)
        if len(refs_by_seen_project) < 2:
            continue
        selected_refs = list(refs_by_seen_project.values())[:8]
        score = _universe_bucket_score(bucket_type, selected_refs)
        clusters.append(
            ProjectUniverseCluster(
                id=f"cluster:{bucket_type}:{_stable_eval_id(bucket_key)}",
                label=_universe_cluster_label(bucket_key, selected_refs),
                type=bucket_type,
                project_ids=sorted(refs_by_seen_project),
                entity_refs=selected_refs,
                score=score,
            )
        )
        for left_index, left in enumerate(selected_refs):
            for right in selected_refs[left_index + 1 :]:
                if left.project_id == right.project_id:
                    continue
                link_id = (
                    "link:"
                    f"{bucket_type}:"
                    f"{_stable_eval_id(left.project_id + left.entity_id)}:"
                    f"{_stable_eval_id(right.project_id + right.entity_id)}"
                )
                candidate = ProjectUniverseLink(
                    id=link_id,
                    type=bucket_type,
                    source=left,
                    target=right,
                    score=score,
                    reason=_universe_link_reason(bucket_type, bucket_key),
                    shared_key=bucket_key,
                )
                existing = links_by_id.get(link_id)
                if existing is None or candidate.score > existing.score:
                    links_by_id[link_id] = candidate

    links = sorted(
        links_by_id.values(),
        key=lambda link: (
            link.score,
            link.source.degree + link.target.degree,
            link.source.label.lower(),
        ),
        reverse=True,
    )[:link_limit]
    clusters = sorted(
        clusters,
        key=lambda cluster: (
            len(cluster.project_ids),
            cluster.score,
            sum(ref.degree for ref in cluster.entity_refs),
        ),
        reverse=True,
    )[:cluster_limit]
    return links, clusters


def _merge_universe_refs_by_project(
    primary: dict[str, list[ProjectUniverseEntityRef]],
    secondary: dict[str, list[ProjectUniverseEntityRef]],
    *,
    limit: int,
) -> dict[str, list[ProjectUniverseEntityRef]]:
    merged: dict[str, list[ProjectUniverseEntityRef]] = {}
    for project_id in sorted({*primary, *secondary}):
        refs_by_id: dict[str, ProjectUniverseEntityRef] = {}
        for ref in [*primary.get(project_id, []), *secondary.get(project_id, [])]:
            current = refs_by_id.get(ref.entity_id)
            if current is None or (ref.degree, ref.evidence_count) > (
                current.degree,
                current.evidence_count,
            ):
                refs_by_id[ref.entity_id] = ref
        merged[project_id] = sorted(
            refs_by_id.values(),
            key=lambda item: (
                item.degree,
                item.evidence_count,
                item.label.lower(),
            ),
            reverse=True,
        )[:limit]
    return merged


def _plan_universe_agent_tasks(
    universe: ProjectKnowledgeUniverse,
    *,
    max_tasks: int,
) -> list[UniverseAgentTask]:
    now = datetime.now(UTC).isoformat()
    tasks: list[UniverseAgentTask] = []
    for cluster in universe.clusters[: max(1, max_tasks // 2)]:
        tasks.append(
            UniverseAgentTask(
                id=f"universe-task:{_stable_eval_id(cluster.id)}",
                status="complete",
                objective=(
                    "Explain the shared architecture concept "
                    f"'{cluster.label}' across {', '.join(cluster.project_ids)}."
                ),
                project_ids=cluster.project_ids,
                cluster_ids=[cluster.id],
                findings=[
                    {
                        "type": "shared_cluster",
                        "title": cluster.label,
                        "summary": (
                            f"{len(cluster.entity_refs)} entity references connect "
                            f"{len(cluster.project_ids)} project(s) with score {cluster.score}."
                        ),
                    }
                ],
                evidence=[
                    {
                        "project_id": ref.project_id,
                        "entity_id": ref.entity_id,
                        "label": ref.label,
                        "source_path": ref.source_path,
                    }
                    for ref in cluster.entity_refs[:8]
                ],
                next_actions=[
                    "Open each referenced project and inspect the local entity neighborhood.",
                    "Generate an A/B architecture diff for the two most important projects.",
                ],
                created_at=now,
                completed_at=now,
                metadata={"agent_paradigm": "deterministic_planner_executor_verifier"},
            )
        )
        if len(tasks) >= max_tasks:
            return tasks

    for link in universe.links[: max(0, max_tasks - len(tasks))]:
        tasks.append(
            UniverseAgentTask(
                id=f"universe-task:{_stable_eval_id(link.id)}",
                status="complete",
                objective=(
                    "Trace why "
                    f"{link.source.project_id}:{link.source.label} relates to "
                    f"{link.target.project_id}:{link.target.label}."
                ),
                project_ids=[link.source.project_id, link.target.project_id],
                link_ids=[link.id],
                findings=[
                    {
                        "type": link.type,
                        "title": link.shared_key,
                        "summary": link.reason,
                        "score": link.score,
                    }
                ],
                evidence=[
                    {
                        "project_id": link.source.project_id,
                        "entity_id": link.source.entity_id,
                        "label": link.source.label,
                        "source_path": link.source.source_path,
                    },
                    {
                        "project_id": link.target.project_id,
                        "entity_id": link.target.entity_id,
                        "label": link.target.label,
                        "source_path": link.target.source_path,
                    },
                ],
                next_actions=[
                    "Compare relation neighborhoods around both linked entities.",
                    "Check whether the similarity is architectural, naming-only, or configuration-driven.",
                ],
                created_at=now,
                completed_at=now,
                metadata={"agent_paradigm": "deterministic_planner_executor_verifier"},
            )
        )
    return tasks


def _universe_ref_key(ref: ProjectUniverseEntityRef) -> str:
    name_key = _universe_name_key(ref.label)
    if name_key:
        return f"name:{name_key}"
    path_key = _universe_path_key(ref.source_path)
    if path_key:
        return f"path:{path_key}"
    tokens = _universe_tokens(ref.label)
    return f"token:{tokens[0]}" if tokens else ""


def _architecture_component_delta(
    left: ProjectArchiveDraft,
    right: ProjectArchiveDraft,
) -> dict[str, Any]:
    left_counts = _architecture_component_counts(left)
    right_counts = _architecture_component_counts(right)
    categories = sorted({*left_counts, *right_counts})
    return {
        "left": left_counts,
        "right": right_counts,
        "delta": {
            category: left_counts.get(category, 0) - right_counts.get(category, 0)
            for category in categories
        },
    }


def _architecture_component_counts(draft: ProjectArchiveDraft) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for entity in draft.entities:
        haystack = " ".join(
            [
                entity.type,
                entity.name,
                entity.source_path or "",
                " ".join(str(value) for value in entity.properties.values()),
            ]
        ).lower()
        matched = False
        if any(token in haystack for token in ("rag", "retrieval", "vector", "embedding", "bm25", "rerank", "chroma")):
            counts["rag"] += 1
            matched = True
        if any(token in haystack for token in ("agent", "mission", "tool", "planner", "react")):
            counts["agent"] += 1
            matched = True
        if any(token in haystack for token in ("api", "route", "endpoint", "fastapi", "controller", "server")):
            counts["api"] += 1
            matched = True
        if any(token in haystack for token in ("ui", "frontend", "react", "component", "page", "view")):
            counts["frontend"] += 1
            matched = True
        if any(token in haystack for token in ("config", "setting", "env", "yaml", "toml", "json")):
            counts["config"] += 1
            matched = True
        if any(token in haystack for token in ("test", "spec", "fixture", "pytest")):
            counts["test"] += 1
            matched = True
        if not matched:
            counts["core"] += 1
    return dict(counts)


def _architecture_diff_evidence_chain(
    *,
    left: ProjectArchiveDraft,
    right: ProjectArchiveDraft,
    shared_links: list[ProjectUniverseLink],
    only_left: list[ProjectUniverseEntityRef],
    only_right: list[ProjectUniverseEntityRef],
) -> list[dict[str, Any]]:
    drafts = {left.project_id: left, right.project_id: right}
    refs = [
        *[link.source for link in shared_links[:10]],
        *[link.target for link in shared_links[:10]],
        *only_left[:8],
        *only_right[:8],
    ]
    chain: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ref in refs:
        draft = drafts.get(ref.project_id)
        if draft is None:
            continue
        entity = next((item for item in draft.entities if item.id == ref.entity_id), None)
        evidence_ids = entity.evidence_ids if entity else []
        if not evidence_ids:
            evidence_ids = [
                card.id for card in draft.evidence_cards
                if ref.entity_id in card.linked_entities
            ][:2]
        for evidence_id in evidence_ids[:2]:
            card = next((item for item in draft.evidence_cards if item.id == evidence_id), None)
            if card is None:
                continue
            key = f"{ref.project_id}:{card.id}"
            if key in seen:
                continue
            seen.add(key)
            chain.append(
                {
                    "project_id": ref.project_id,
                    "entity_id": ref.entity_id,
                    "entity_label": ref.label,
                    "evidence_id": card.id,
                    "title": card.title,
                    "source_path": card.source_path,
                    "source_type": card.source_type,
                    "snippet": card.snippet[:240],
                    "reason": "Supports a shared or project-unique architecture surface.",
                }
            )
            if len(chain) >= 24:
                return chain
    return chain


def _architecture_diff_risk_points(
    *,
    metric_delta: dict[str, int],
    shared_links: list[ProjectUniverseLink],
    only_left: list[ProjectUniverseEntityRef],
    only_right: list[ProjectUniverseEntityRef],
    component_delta: dict[str, Any],
) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    if abs(metric_delta.get("relations", 0)) > max(5, abs(metric_delta.get("entities", 0)) // 3):
        risks.append(
            {
                "title": "Relation coverage differs significantly",
                "severity": "medium",
                "summary": "The graph may compare different extraction depths, not only architecture differences.",
            }
        )
    if not shared_links:
        risks.append(
            {
                "title": "No direct shared links",
                "severity": "high",
                "summary": "The projects may be unrelated, or shared concepts were not extracted strongly enough.",
            }
        )
    if len(only_left) > 12 or len(only_right) > 12:
        risks.append(
            {
                "title": "Large unique architecture surface",
                "severity": "medium",
                "summary": "Review unique entities before assuming migration or reuse parity.",
            }
        )
    delta = component_delta.get("delta", {}) if isinstance(component_delta, dict) else {}
    for category, value in sorted(delta.items()):
        if abs(int(value)) >= 5:
            risks.append(
                {
                    "title": f"{category.upper()} component imbalance",
                    "severity": "review",
                    "summary": f"Component signal differs by {value}; inspect evidence before drawing conclusions.",
                }
            )
    return risks[:8]


def _architecture_diff_migration_notes(
    left_project_id: str,
    right_project_id: str,
    *,
    shared_clusters: list[ProjectUniverseCluster],
    component_delta: dict[str, Any],
    risk_points: list[dict[str, Any]],
) -> list[str]:
    notes = [
        f"Use the strongest shared clusters as anchors before comparing {left_project_id} and {right_project_id} module-by-module.",
        "Treat unique entities as review candidates, not automatic incompatibilities.",
    ]
    if shared_clusters:
        notes.append(
            "Start with shared clusters: "
            + ", ".join(cluster.label for cluster in shared_clusters[:4])
            + "."
        )
    delta = component_delta.get("delta", {}) if isinstance(component_delta, dict) else {}
    if any(abs(int(value)) >= 5 for value in delta.values()):
        notes.append("Normalize component categories before using this report for migration planning.")
    if risk_points:
        notes.append("Resolve high or medium risk points before treating the comparison as final.")
    return notes


def _architecture_diff_sections(
    *,
    left_project_id: str,
    right_project_id: str,
    shared_clusters: list[ProjectUniverseCluster],
    shared_links: list[ProjectUniverseLink],
    only_left: list[ProjectUniverseEntityRef],
    only_right: list[ProjectUniverseEntityRef],
    component_delta: dict[str, Any],
    risk_points: list[dict[str, Any]],
    migration_notes: list[str],
) -> list[dict[str, Any]]:
    return [
        {
            "id": "shared-surfaces",
            "title": "Shared Architecture Surfaces",
            "summary": (
                f"{left_project_id} and {right_project_id} share "
                f"{len(shared_clusters)} concept cluster(s) and {len(shared_links)} direct link(s)."
            ),
            "bullets": [cluster.label for cluster in shared_clusters[:6]],
        },
        {
            "id": "module-boundary-delta",
            "title": "Module Boundary Differences",
            "summary": (
                f"{len(only_left)} prominent refs appear only in {left_project_id}; "
                f"{len(only_right)} appear only in {right_project_id}."
            ),
            "bullets": [
                f"{left_project_id}: " + ", ".join(ref.label for ref in only_left[:5]),
                f"{right_project_id}: " + ", ".join(ref.label for ref in only_right[:5]),
            ],
        },
        {
            "id": "component-delta",
            "title": "Component Recognition",
            "summary": "Detected broad component signals such as RAG, Agent, API, frontend, config, and tests.",
            "bullets": [
                f"{category}: {value}"
                for category, value in sorted(component_delta.get("delta", {}).items())
            ][:8],
        },
        {
            "id": "risk-and-migration",
            "title": "Risk and Migration Notes",
            "summary": f"{len(risk_points)} risk point(s) and {len(migration_notes)} migration note(s) were generated.",
            "bullets": [
                *[str(item.get("title", "")) for item in risk_points[:4]],
                *migration_notes[:4],
            ],
        },
    ]


def _architecture_diff_findings(
    *,
    left_project_id: str,
    right_project_id: str,
    metric_delta: dict[str, int],
    shared_clusters: list[ProjectUniverseCluster],
    shared_links: list[ProjectUniverseLink],
    only_left: list[ProjectUniverseEntityRef],
    only_right: list[ProjectUniverseEntityRef],
) -> list[dict[str, Any]]:
    findings = [
        {
            "type": "shared_architecture_surface",
            "title": "Shared graph surface",
            "summary": (
                f"{left_project_id} and {right_project_id} share "
                f"{len(shared_clusters)} cluster(s) and {len(shared_links)} direct link(s)."
            ),
            "severity": "info",
        },
        {
            "type": "metric_delta",
            "title": "Archive shape delta",
            "summary": (
                f"Entity delta {metric_delta.get('entities', 0)}, relation delta "
                f"{metric_delta.get('relations', 0)}, evidence delta {metric_delta.get('evidence', 0)}."
            ),
            "severity": "info",
        },
    ]
    if only_left:
        findings.append(
            {
                "type": "left_unique_entities",
                "title": f"Unique surface in {left_project_id}",
                "summary": ", ".join(ref.label for ref in only_left[:6]),
                "severity": "review",
            }
        )
    if only_right:
        findings.append(
            {
                "type": "right_unique_entities",
                "title": f"Unique surface in {right_project_id}",
                "summary": ", ".join(ref.label for ref in only_right[:6]),
                "severity": "review",
            }
        )
    return findings


def _architecture_diff_recommendations(findings: list[dict[str, Any]]) -> list[str]:
    if not findings:
        return ["Regenerate both archives with full audit mode and rerun the diff."]
    return [
        "Inspect the strongest shared clusters first; they are the best anchors for migration or reuse analysis.",
        "Open unique entities on both sides to separate true architecture differences from scan coverage differences.",
        "Run project-local Agent analysis for each project before using this report as a final technical comparison.",
    ]


def _project_report_summary(
    *,
    draft: ProjectArchiveDraft,
    graph_report: dict[str, Any],
    agent_report: ProjectAgentReport | None,
    evaluation: ArchiveEvaluationReport | None,
    hybrid_status: dict[str, Any],
    multimodal: dict[str, Any],
) -> str:
    quality = graph_report.get("quality", {}) if isinstance(graph_report, dict) else {}
    quality_score = float(quality.get("score", 0.0) or 0.0)
    quality_grade = str(quality.get("grade", "E"))
    agent_status = agent_report.status if agent_report else "not_run"
    eval_score = (
        evaluation.aggregate_metrics.get("case_score", 0.0)
        if evaluation is not None
        else 0.0
    )
    return (
        f"{draft.project_id} contains {len(draft.entities)} entities, "
        f"{len(draft.relations)} relations, and {len(draft.evidence_cards)} evidence cards. "
        f"Graph quality is {round(quality_score)} ({quality_grade}); "
        f"Agent status is {agent_status}; evaluation score is {round(eval_score * 100)}%. "
        f"Hybrid RAG indexed {int(hybrid_status.get('indexed_chunks', 0) or 0)} chunks "
        f"and multimodal analysis found {int(multimodal.get('image_count', 0) or 0)} image evidence item(s)."
    )


def _project_report_risk_items(
    *,
    graph_report: dict[str, Any],
    trust_report: dict[str, Any],
    evaluation: ArchiveEvaluationReport | None,
    agent_report: ProjectAgentReport | None,
    agent_error: str,
    evaluation_error: str,
) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    for warning in graph_report.get("quality", {}).get("warnings", [])[:6]:
        risks.append(
            {
                "severity": "medium",
                "source": "graph_quality",
                "title": "Graph quality warning",
                "detail": str(warning),
                "evidence_ids": [],
            }
        )
    for warning in trust_report.get("warnings", [])[:6]:
        risks.append(
            {
                "severity": "high" if "unsupported" in str(warning).lower() else "medium",
                "source": "agent_trust",
                "title": "Agent support warning",
                "detail": str(warning),
                "evidence_ids": [],
            }
        )
    if evaluation is not None and evaluation.aggregate_metrics.get("case_score", 0.0) < 0.55:
        risks.append(
            {
                "severity": "medium",
                "source": "evaluation",
                "title": "Low benchmark score",
                "detail": f"Case score is {evaluation.aggregate_metrics.get('case_score', 0.0):.2f}.",
                "evidence_ids": [],
            }
        )
    if agent_error:
        risks.append(
            {
                "severity": "medium",
                "source": "agent",
                "title": "Agent report unavailable",
                "detail": agent_error,
                "evidence_ids": [],
            }
        )
    if evaluation_error:
        risks.append(
            {
                "severity": "low",
                "source": "evaluation",
                "title": "Evaluation report unavailable",
                "detail": evaluation_error,
                "evidence_ids": [],
            }
        )
    if agent_report is not None:
        for role, result in agent_report.agents.items():
            for risk in result.risks[:3]:
                risks.append(
                    {
                        "severity": str(risk.get("severity", "medium")),
                        "source": f"agent:{role}",
                        "title": str(risk.get("title", "Agent risk")),
                        "detail": str(risk.get("detail", result.summary)),
                        "evidence_ids": result.evidence_card_ids[:8],
                    }
                )
    return risks[:18]


def _project_report_evidence_chain(
    *,
    entity_by_id: dict[str, ProjectEntity],
    evidence_by_id: dict[str, EvidenceCard],
    relation_by_id: dict[str, ProjectRelation],
    trust_report: dict[str, Any],
    agent_report: ProjectAgentReport | None,
    limit: int,
) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    claims = trust_report.get("claims", []) if isinstance(trust_report, dict) else []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        evidence_ids = [
            evidence_id for evidence_id in claim.get("evidence_ids", [])
            if evidence_id in evidence_by_id
        ]
        entity_ids = [
            entity_id for entity_id in claim.get("entity_ids", [])
            if entity_id in entity_by_id
        ]
        relation_ids = [
            relation_id for relation_id in claim.get("relation_ids", [])
            if relation_id in relation_by_id
        ]
        chain.append(
            {
                "claim": str(claim.get("summary", "")),
                "status": str(claim.get("status", "unknown")),
                "confidence": float(claim.get("confidence", 0.0) or 0.0),
                "evidence": [
                    {
                        "id": card.id,
                        "title": card.title,
                        "source_path": card.source_path,
                        "source_type": card.source_type,
                    }
                    for evidence_id in evidence_ids[:6]
                    for card in [evidence_by_id[evidence_id]]
                ],
                "entities": [
                    {"id": entity.id, "name": entity.name, "type": entity.type}
                    for entity_id in entity_ids[:8]
                    for entity in [entity_by_id[entity_id]]
                ],
                "relations": [
                    {
                        "id": relation.id,
                        "type": relation.type,
                        "source_id": relation.source_id,
                        "target_id": relation.target_id,
                    }
                    for relation_id in relation_ids[:8]
                    for relation in [relation_by_id[relation_id]]
                ],
            }
        )
        if len(chain) >= limit:
            return chain
    if agent_report is not None and not chain:
        for role, result in agent_report.agents.items():
            chain.append(
                {
                    "claim": result.summary,
                    "status": "supported" if result.evidence_card_ids else "unsupported",
                    "confidence": result.confidence,
                    "evidence": [
                        {
                            "id": card.id,
                            "title": card.title,
                            "source_path": card.source_path,
                            "source_type": card.source_type,
                        }
                        for evidence_id in result.evidence_card_ids[:6]
                        if evidence_id in evidence_by_id
                        for card in [evidence_by_id[evidence_id]]
                    ],
                    "entities": [],
                    "relations": [],
                    "source": role,
                }
            )
    return chain[:limit]


def _project_report_config_dependencies(draft: ProjectArchiveDraft) -> list[dict[str, Any]]:
    terms = ("config", "setting", "env", "yaml", "toml", "json", "properties", "docker", "compose")
    items = [
        entity for entity in draft.entities
        if any(term in f"{entity.type} {entity.name} {entity.source_path or ''}".lower() for term in terms)
    ]
    return [
        {
            "id": entity.id,
            "name": entity.name,
            "type": entity.type,
            "source_path": entity.source_path,
            "evidence_ids": entity.evidence_ids[:6],
        }
        for entity in items[:20]
    ]


def _project_report_call_chains(draft: ProjectArchiveDraft) -> list[dict[str, Any]]:
    entity_by_id = {entity.id: entity for entity in draft.entities}
    chain_relations = [
        relation for relation in draft.relations
        if any(token in relation.type.lower() for token in ("call", "use", "import", "depend", "route", "invoke"))
    ]
    return [
        {
            "id": relation.id,
            "type": relation.type,
            "source": entity_by_id.get(relation.source_id).name if relation.source_id in entity_by_id else relation.source_id,
            "target": entity_by_id.get(relation.target_id).name if relation.target_id in entity_by_id else relation.target_id,
            "source_id": relation.source_id,
            "target_id": relation.target_id,
            "evidence_ids": relation.evidence_ids[:6],
        }
        for relation in chain_relations[:24]
    ]


def _project_report_rag_citations(hybrid_status: dict[str, Any]) -> dict[str, Any]:
    return {
        "indexed_chunks": int(hybrid_status.get("indexed_chunks", 0) or 0),
        "text_chunks": int(hybrid_status.get("text_chunks", 0) or 0),
        "image_chunks": int(hybrid_status.get("image_chunks", 0) or 0),
        "dense_provider": hybrid_status.get("dense_provider", "none"),
        "bm25_collection": hybrid_status.get("bm25_collection"),
        "rrf_enabled": bool(int(hybrid_status.get("indexed_chunks", 0) or 0) > 0),
        "fallback_reasons": hybrid_status.get("fallback_reasons", []),
    }


def _project_report_multimodal_evidence(multimodal: dict[str, Any]) -> dict[str, Any]:
    images = multimodal.get("images", []) if isinstance(multimodal, dict) else []
    return {
        "image_count": int(multimodal.get("image_count", 0) or 0),
        "vision_supported": int(multimodal.get("vision_supported", 0) or 0),
        "ocr_supported": int(multimodal.get("ocr_supported", 0) or 0),
        "average_quality": float(multimodal.get("average_quality", 0.0) or 0.0),
        "images": images[:10],
        "graph_contributions": multimodal.get("graph_contributions", {}),
    }


def _project_report_next_actions(
    *,
    graph_report: dict[str, Any],
    risk_items: list[dict[str, Any]],
    evaluation: ArchiveEvaluationReport | None,
    hybrid_status: dict[str, Any],
    multimodal: dict[str, Any],
) -> list[str]:
    actions = list(graph_report.get("quality", {}).get("recommendations", [])[:4])
    if risk_items:
        actions.append("Resolve high and medium risk items before using the report as a final architecture decision record.")
    if evaluation is None:
        actions.append("Run the evaluation benchmark to verify graph, relation, and evidence hit rates.")
    if int(hybrid_status.get("indexed_chunks", 0) or 0) <= 0:
        actions.append("Build the Hybrid RAG index so future answers can cite Chroma, BM25, and RRF retrieval evidence.")
    if int(multimodal.get("image_count", 0) or 0) and not int(multimodal.get("vision_supported", 0) or 0):
        actions.append("Enable vision/OCR for architecture diagrams before trusting image-derived graph claims.")
    if not actions:
        actions.append("Use the recommended graph entry points to inspect core paths and save important exploration routes.")
    return _unique_preserve_order(actions, limit=10)


def _project_report_sections(
    *,
    architecture_layers: list[dict[str, Any]],
    core_entities: list[dict[str, Any]],
    risk_items: list[dict[str, Any]],
    evidence_chain: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "id": "overview",
            "title": "Project Overview",
            "summary": "High-level archive shape, graph quality, evaluation, and RAG readiness.",
        },
        {
            "id": "architecture",
            "title": "Architecture Layers",
            "summary": f"{len(architecture_layers)} module/layer cluster(s) were identified.",
            "highlights": [str(item.get("name", "")) for item in architecture_layers[:6]],
        },
        {
            "id": "entry-points",
            "title": "Recommended Reading Path",
            "summary": f"{len(core_entities)} core entry point(s) are available for graph-first exploration.",
            "highlights": [str(item.get("label", "")) for item in core_entities[:6]],
        },
        {
            "id": "risks",
            "title": "Risks And Unsupported Claims",
            "summary": f"{len(risk_items)} risk item(s) require review.",
            "highlights": [str(item.get("title", "")) for item in risk_items[:6]],
        },
        {
            "id": "evidence",
            "title": "Evidence Chain",
            "summary": f"{len(evidence_chain)} evidence-backed claim chain(s) were compiled.",
        },
    ]


def _project_report_risk_index(risk_items: list[dict[str, Any]]) -> dict[str, Any]:
    by_severity = Counter(str(item.get("severity", "review")) for item in risk_items)
    by_source = Counter(str(item.get("source", "unknown")) for item in risk_items)
    return {
        "total": len(risk_items),
        "by_severity": dict(by_severity),
        "by_source": dict(by_source),
        "top": risk_items[:10],
    }


def _project_report_evidence_index(evidence_chain: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_paths: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    for item in evidence_chain:
        statuses[str(item.get("status", "unknown"))] += 1
        for card in item.get("evidence", []):
            if isinstance(card, dict):
                evidence_paths[str(card.get("source_path", card.get("id", "")))] += 1
    return {
        "claim_count": len(evidence_chain),
        "by_status": dict(statuses),
        "top_sources": evidence_paths.most_common(20),
    }


def _project_agent_task_plan(
    *,
    draft: ProjectArchiveDraft,
    graph_report: dict[str, Any],
    hybrid_status: dict[str, Any],
    multimodal: dict[str, Any],
    evaluation_available: bool,
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []

    def add_task(
        task_type: str,
        title: str,
        reason: str,
        tools: list[str],
        entity_ids: list[str] | None = None,
        priority: int = 50,
    ) -> None:
        tasks.append(
            {
                "id": f"plan:{task_type}:{len(tasks) + 1}",
                "task_type": task_type,
                "title": title,
                "reason": reason,
                "priority": priority,
                "recommended_tools": tools,
                "input_entity_ids": _unique_preserve_order(entity_ids or [], limit=20),
                "expected_outputs": [
                    "findings",
                    "evidence_ids",
                    "entity_ids",
                    "risks",
                ],
            }
        )

    entry_points = [
        entity_id
        for entry in graph_report.get("entry_points", [])[:3]
        if isinstance(entry, dict)
        for entity_id in entry.get("entity_ids", [])[:3]
    ]
    add_task(
        "entrypoint_walkthrough",
        "Inspect recommended graph entry points",
        "Start from backend-ranked entry points so the Agent does not guess search keywords.",
        ["graph_summary", "graph_neighborhood", "evidence_lookup"],
        entry_points,
        95,
    )
    quality = graph_report.get("quality", {}) if isinstance(graph_report.get("quality"), dict) else {}
    if quality.get("warnings"):
        add_task(
            "quality_risk_review",
            "Review graph quality warnings",
            "Quality warnings can distort downstream Agent conclusions.",
            ["graph_quality", "relation_confidence", "evidence_lookup"],
            priority=90,
        )
    entity_quality = graph_report.get("entity_quality", {}) if isinstance(graph_report.get("entity_quality"), dict) else {}
    noisy_entities = [
        item.get("id")
        for item in entity_quality.get("noisy_entities", [])[:8]
        if isinstance(item, dict) and item.get("id")
    ]
    if noisy_entities or entity_quality.get("duplicate_candidates"):
        add_task(
            "curation_candidates",
            "Review duplicate and noisy graph entities",
            "Large projects need graph cleanup before broad analysis.",
            ["entity_quality", "graph_curation", "graph_search"],
            [str(item) for item in noisy_entities],
            86,
        )
    if int(hybrid_status.get("indexed_chunks", 0) or 0) <= 0:
        add_task(
            "hybrid_rag_gap",
            "Check Hybrid RAG indexing gap",
            "Semantic answers need Chroma, BM25, and RRF evidence before they are trustworthy.",
            ["rag_status", "ingestion_diagnostics"],
            priority=82,
        )
    if int(multimodal.get("image_count", 0) or 0) and not int(multimodal.get("vision_supported", 0) or 0):
        add_task(
            "multimodal_gap",
            "Review image understanding fallback",
            "Images exist but vision support is not active, so diagram evidence may be weak.",
            ["multimodal_insights", "evidence_lookup"],
            priority=78,
        )
    if not evaluation_available:
        add_task(
            "evaluation_gap",
            "Run evaluation benchmark",
            "Benchmarking validates whether graph and evidence retrieval actually work.",
            ["evaluation_runner", "golden_questions"],
            priority=74,
        )
    add_task(
        "project_report",
        "Generate formal project intelligence report",
        "Compile findings into a report after graph, RAG, multimodal, and evaluation checks.",
        ["intelligence_report", "agent_trust", "markdown_export"],
        priority=60,
    )
    return sorted(tasks, key=lambda item: (-int(item["priority"]), str(item["id"])))[:8]


def _runtime_evidence_report(
    *,
    components: list[dict[str, Any]],
    agent_status: dict[str, Any],
    graph_status: dict[str, Any],
    latest_rag_status: dict[str, Any] | None,
) -> dict[str, Any]:
    component_by_id = {str(component.get("id")): component for component in components}
    rag = latest_rag_status or {}
    return {
        "llm": {
            "used": bool(agent_status.get("llm_enabled")),
            "provider": agent_status.get("provider"),
            "model": agent_status.get("model"),
            "fallback": not bool(agent_status.get("llm_enabled")),
        },
        "embedding": {
            "provider": rag.get("dense_provider", component_by_id.get("embedding", {}).get("provider")),
            "dimension": rag.get("dense_dimension"),
            "fallback_reasons": rag.get("fallback_reasons", []),
        },
        "vector_store": {
            "provider": component_by_id.get("vector_store", {}).get("provider"),
            "collection": rag.get("collection_name"),
            "indexed_chunks": rag.get("indexed_chunks", 0),
        },
        "hybrid_retrieval": {
            "chroma_ready": bool(rag.get("collection_name")),
            "bm25_ready": bool(rag.get("bm25_collection")),
            "rrf_ready": int(rag.get("indexed_chunks", 0) or 0) > 0,
            "text_chunks": rag.get("text_chunks", 0),
            "image_chunks": rag.get("image_chunks", 0),
        },
        "graph_store": {
            "provider": graph_status.get("provider"),
            "mode": graph_status.get("mode"),
            "project_isolation": graph_status.get("project_isolation"),
        },
        "vision": {
            "provider": rag.get("vision_provider", component_by_id.get("vision", {}).get("provider")),
            "enabled": bool(rag.get("vision_enabled")),
            "image_chunks": rag.get("image_chunks", 0),
        },
        "fallbacks": [
            warning
            for component in components
            for warning in component.get("warnings", [])
            if isinstance(warning, str)
        ][:12],
    }


def _project_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Project Intelligence Report: {report.get('project_id', '')}",
        "",
        f"Generated: {report.get('created_at', '')}",
        "",
        "## Contents",
        "",
    ]
    for section in report.get("sections", []):
        if isinstance(section, dict):
            lines.append(f"- {section.get('title', '')}: {section.get('summary', '')}")
    lines.extend([
        "",
        "## Summary",
        "",
        str(report.get("summary", "")),
        "",
        "## Coverage",
        "",
    ])
    coverage = report.get("coverage", {}) if isinstance(report.get("coverage"), dict) else {}
    for key, value in coverage.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Architecture Layers", ""])
    for layer in report.get("architecture_layers", [])[:10]:
        if isinstance(layer, dict):
            lines.append(
                f"- {layer.get('name', '')}: {layer.get('entity_count', 0)} entities, "
                f"{layer.get('relation_touch_count', 0)} relation touches"
            )
    lines.extend(["", "## Entry Points", ""])
    for entry in report.get("entry_points", [])[:8]:
        if isinstance(entry, dict):
            lines.append(f"- {entry.get('title', '')}: {entry.get('reason', '')}")
    lines.extend(["", "## Risks", ""])
    for risk in report.get("risks", [])[:12]:
        if isinstance(risk, dict):
            lines.append(
                f"- [{risk.get('severity', 'review')}] {risk.get('title', '')}: {risk.get('detail', '')}"
            )
    risk_index = report.get("risk_index", {}) if isinstance(report.get("risk_index"), dict) else {}
    if risk_index:
        lines.extend(["", "Risk index:", ""])
        for key, value in (risk_index.get("by_severity", {}) or {}).items():
            lines.append(f"- {key}: {value}")
    lines.extend(["", "## Evidence Chain", ""])
    for item in report.get("evidence_chain", [])[:12]:
        if not isinstance(item, dict):
            continue
        evidence = item.get("evidence", [])
        evidence_text = ", ".join(
            str(card.get("source_path", card.get("id", "")))
            for card in evidence[:4]
            if isinstance(card, dict)
        )
        lines.append(f"- {item.get('claim', '')} ({item.get('status', '')})")
        if evidence_text:
            lines.append(f"  Evidence: {evidence_text}")
    evidence_index = report.get("evidence_index", {}) if isinstance(report.get("evidence_index"), dict) else {}
    top_sources = evidence_index.get("top_sources", []) if isinstance(evidence_index, dict) else []
    if top_sources:
        lines.extend(["", "Evidence index:", ""])
        for source, count in top_sources[:10]:
            lines.append(f"- {source}: {count}")
    lines.extend(["", "## Hybrid RAG", ""])
    rag = report.get("rag_citations", {}) if isinstance(report.get("rag_citations"), dict) else {}
    for key in ("indexed_chunks", "text_chunks", "image_chunks", "dense_provider", "bm25_collection", "rrf_enabled"):
        lines.append(f"- {key}: {rag.get(key)}")
    lines.extend(["", "## Multimodal Evidence", ""])
    multimodal = report.get("multimodal_evidence", {}) if isinstance(report.get("multimodal_evidence"), dict) else {}
    for key in ("image_count", "vision_supported", "ocr_supported", "average_quality"):
        lines.append(f"- {key}: {multimodal.get(key)}")
    lines.extend(["", "## Next Actions", ""])
    for action in report.get("next_actions", [])[:10]:
        lines.append(f"- {action}")
    lines.append("")
    return "\n".join(lines)


def _simple_text_pdf(title: str, lines: list[str]) -> bytes:
    page_width = 612
    page_height = 792
    margin = 50
    line_height = 14
    max_lines = int((page_height - margin * 2) / line_height)
    clean_lines = [title, "", *[line[:110] for line in lines]]
    pages = [
        clean_lines[index:index + max_lines]
        for index in range(0, len(clean_lines), max_lines)
    ] or [[title]]
    objects: list[bytes] = []

    def add_object(payload: bytes) -> int:
        objects.append(payload)
        return len(objects)

    font_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids: list[int] = []
    content_ids: list[int] = []
    for page_lines in pages:
        commands = ["BT", "/F1 10 Tf", f"{margin} {page_height - margin} Td"]
        for line_number, line in enumerate(page_lines):
            if line_number:
                commands.append(f"0 -{line_height} Td")
            commands.append(f"({_pdf_escape(line)}) Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("utf-8")
        content_id = add_object(
            b"<< /Length " + str(len(stream)).encode("ascii")
            + b" >>\nstream\n" + stream + b"\nendstream"
        )
        content_ids.append(content_id)
        page_id = add_object(b"")
        page_ids.append(page_id)
    pages_id = add_object(b"")
    for index, page_id in enumerate(page_ids):
        objects[page_id - 1] = (
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {page_width} {page_height}] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
            f"/Contents {content_ids[index]} 0 R >>"
        ).encode("utf-8")
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("utf-8")
    catalog_id = add_object(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("utf-8"))
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, payload in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(payload)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _stress_test_recommendations(project_reports: list[dict[str, Any]]) -> list[str]:
    if not project_reports:
        return ["Generate at least one project archive, then run the stress test again."]
    recommendations: list[str] = []
    failed = [item for item in project_reports if item.get("status") == "fail"]
    sparse = [
        item for item in project_reports
        if int(dict(item.get("metrics", {})).get("entities", 0) or 0) < 20
    ]
    missing_rag = [item for item in project_reports if not item.get("hybrid_rag_ready")]
    missing_eval = [item for item in project_reports if not item.get("evaluation_available")]
    if failed:
        recommendations.append(
            f"Review failed archives first: {', '.join(str(item.get('project_id')) for item in failed[:5])}."
        )
    if sparse:
        recommendations.append(
            "Sparse archives detected. Rerun ingestion with a broader scan profile and inspect ignored paths."
        )
    if missing_rag:
        recommendations.append(
            "Build Hybrid RAG indexes for projects without indexed chunks before trusting semantic search."
        )
    if missing_eval:
        recommendations.append(
            "Run evaluation for projects without a benchmark report to verify graph and evidence hit rates."
        )
    if not recommendations:
        recommendations.append(
            "Archive health looks usable. Continue with graph exploration, project reports, and cross-project universe analysis."
        )
    return recommendations


def _stress_regression_matrix(project_reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in project_reports:
        metrics = item.get("metrics", {}) if isinstance(item.get("metrics"), dict) else {}
        rows.append(
            {
                "project_id": item.get("project_id"),
                "status": item.get("status"),
                "graph_quality": item.get("quality_score", 0.0),
                "evaluation": item.get("evaluation_score", 0.0),
                "hybrid_rag": "pass" if item.get("hybrid_rag_ready") else "fail",
                "multimodal": "pass" if item.get("multimodal_ready") else "review",
                "entities": metrics.get("entities", 0),
                "relations": metrics.get("relations", 0),
                "evidence": metrics.get("evidence", 0),
                "warnings": len(item.get("warnings", [])),
            }
        )
    return rows


def _stress_language_coverage(project_reports: list[dict[str, Any]]) -> dict[str, Any]:
    language_counts: Counter[str] = Counter()
    parsed_counts: Counter[str] = Counter()
    for item in project_reports:
        structure = item.get("language_structure", {}) if isinstance(item, dict) else {}
        for row in structure.get("languages", []) if isinstance(structure, dict) else []:
            if not isinstance(row, dict):
                continue
            language = str(row.get("language", "unknown"))
            language_counts[language] += int(row.get("files", 0) or 0)
            if int(row.get("entities", 0) or 0) > 0:
                parsed_counts[language] += 1
    return {
        "languages": dict(language_counts),
        "projects_with_structure": dict(parsed_counts),
        "language_count": len(language_counts),
    }


def _stress_blocking_failures(project_reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures = []
    for item in project_reports:
        metrics = item.get("metrics", {}) if isinstance(item.get("metrics"), dict) else {}
        reasons = []
        if item.get("status") == "fail":
            reasons.append("stress_status_failed")
        if int(metrics.get("entities", 0) or 0) == 0:
            reasons.append("no_entities")
        if not item.get("hybrid_rag_ready"):
            reasons.append("hybrid_rag_missing")
        if item.get("evaluation_error"):
            reasons.append("evaluation_missing")
        if reasons:
            failures.append(
                {
                    "project_id": item.get("project_id"),
                    "reasons": reasons,
                    "recommendation": "Regenerate the archive, inspect ingestion diagnostics, then rerun stress test.",
                }
            )
    return failures


def _graph_entry_points(
    *,
    draft: ProjectArchiveDraft,
    summary: GraphSummary,
    relations_by_entity: dict[str, list[ProjectRelation]],
    quality: dict[str, Any],
) -> list[dict[str, Any]]:
    entity_by_id = {entity.id: entity for entity in draft.entities}
    entries: list[dict[str, Any]] = []

    def add_entry(
        *,
        category: str,
        title: str,
        reason: str,
        entity_ids: list[str],
        score: float,
        action: str,
    ) -> None:
        clean_ids = [entity_id for entity_id in _unique_preserve_order(entity_ids, limit=8) if entity_id in entity_by_id]
        if not clean_ids:
            return
        entries.append(
            {
                "id": f"entry:{category}:{_stable_eval_id(':'.join(clean_ids))}",
                "category": category,
                "title": title,
                "reason": reason,
                "score": round(score, 2),
                "entity_ids": clean_ids,
                "entities": [
                    {
                        "id": entity.id,
                        "label": entity.name,
                        "type": entity.type,
                        "source_path": entity.source_path,
                        "degree": len(relations_by_entity.get(entity.id, [])),
                    }
                    for entity_id in clean_ids[:5]
                    for entity in [entity_by_id[entity_id]]
                ],
                "action": action,
            }
        )

    starts_by_group: dict[str, list[str]] = defaultdict(list)
    for start in summary.recommended_starts:
        starts_by_group[start.group].append(start.entity_id)

    add_entry(
        category="architecture_entry",
        title="Start From Runtime Entry Points",
        reason="Likely entry files and central modules help explain the execution path first.",
        entity_ids=[*starts_by_group.get("entry_file", []), *starts_by_group.get("high_degree", [])],
        score=96.0,
        action="Open the first entity, expand two hops, then inspect evidence before moving to modules.",
    )
    add_entry(
        category="configuration_center",
        title="Inspect Configuration Centers",
        reason="Configuration-like nodes often reveal model, vector store, database, and runtime wiring.",
        entity_ids=starts_by_group.get("config_hotspot", []),
        score=88.0,
        action="Expand config nodes and follow relations to services, adapters, and external providers.",
    )
    add_entry(
        category="documentation_center",
        title="Read Documentation Anchors",
        reason="Documentation nodes are useful when the graph is unfamiliar or sparse.",
        entity_ids=starts_by_group.get("document_center", []),
        score=76.0,
        action="Use documentation anchors to form search terms, then jump back into graph neighborhoods.",
    )

    dependency_candidates = sorted(
        [
            entity for entity in draft.entities
            if any(
                token in f"{entity.type} {entity.name} {entity.source_path or ''}".lower()
                for token in ("import", "dependency", "package", "requirements", "pom", "gradle", "cargo", "go.mod")
            )
        ],
        key=lambda entity: (-len(relations_by_entity.get(entity.id, [])), entity.name.lower()),
    )
    add_entry(
        category="dependency_surface",
        title="Trace External Dependency Surfaces",
        reason="Dependency files and import/package nodes show what this project relies on.",
        entity_ids=[entity.id for entity in dependency_candidates],
        score=82.0,
        action="Follow dependency nodes toward modules that consume external services or frameworks.",
    )

    boundary_candidates = sorted(
        [
            entity for entity in draft.entities
            if any(
                token in f"{entity.type} {entity.name}".lower()
                for token in ("api", "route", "controller", "service", "interface", "adapter", "client")
            )
        ],
        key=lambda entity: (-len(relations_by_entity.get(entity.id, [])), entity.name.lower()),
    )
    add_entry(
        category="service_boundary",
        title="Map Service And API Boundaries",
        reason="Boundary-like entities are good first stops for understanding collaboration between modules.",
        entity_ids=[entity.id for entity in boundary_candidates],
        score=84.0,
        action="Expand one boundary at a time and save paths that cross modules or external providers.",
    )

    weak_entities = sorted(
        [
            entity for entity in draft.entities
            if not entity.evidence_ids and relations_by_entity.get(entity.id)
        ],
        key=lambda entity: (-len(relations_by_entity.get(entity.id, [])), entity.name.lower()),
    )
    if quality.get("warnings") or weak_entities:
        add_entry(
            category="risk_region",
            title="Review Weak Evidence Regions",
            reason="These nodes are connected but have thin evidence, so they can distort later Agent conclusions.",
            entity_ids=[entity.id for entity in weak_entities],
            score=72.0,
            action="Open evidence cards and mark weak or noisy relations before trusting generated reports.",
        )

    return sorted(
        entries,
        key=lambda item: (-float(item["score"]), str(item["category"])),
    )[:8]


def _graph_entity_quality_report(
    *,
    draft: ProjectArchiveDraft,
    relations_by_entity: dict[str, list[ProjectRelation]],
    relation_confidence: list[dict[str, Any]],
) -> dict[str, Any]:
    buckets: dict[tuple[str, str], list[ProjectEntity]] = defaultdict(list)
    for entity in draft.entities:
        buckets[(_normalize_entity_label(entity.name), entity.type.lower())].append(entity)
    duplicate_candidates = [
        {
            "key": f"{entity_type}:{label}",
            "label": label,
            "type": entity_type,
            "entity_ids": [entity.id for entity in entities[:12]],
            "count": len(entities),
        }
        for (label, entity_type), entities in buckets.items()
        if label and len(entities) > 1
    ]
    noisy_entities = [
        {
            "id": entity.id,
            "label": entity.name,
            "type": entity.type,
            "source_path": entity.source_path,
            "reason": _entity_noise_reason(entity, relations_by_entity),
        }
        for entity in draft.entities
        if _entity_noise_reason(entity, relations_by_entity)
    ][:80]
    important_entities = sorted(
        [
            {
                "id": entity.id,
                "label": entity.name,
                "type": entity.type,
                "source_path": entity.source_path,
                "degree": len(relations_by_entity.get(entity.id, [])),
                "evidence_count": len(entity.evidence_ids),
                "importance": round(
                    len(relations_by_entity.get(entity.id, [])) * 0.7
                    + len(entity.evidence_ids) * 0.3,
                    3,
                ),
            }
            for entity in draft.entities
        ],
        key=lambda item: (-float(item["importance"]), str(item["label"]).lower()),
    )[:30]
    unsupported_relations = [
        item for item in relation_confidence
        if int(item.get("evidence_count", 0) or 0) == 0
    ][:40]
    isolated_count = sum(1 for entity in draft.entities if not relations_by_entity.get(entity.id))
    score = 100.0
    if draft.entities:
        score -= min(28.0, len(duplicate_candidates) / max(1, len(draft.entities)) * 180)
        score -= min(24.0, len(noisy_entities) / max(1, len(draft.entities)) * 120)
        score -= min(24.0, isolated_count / max(1, len(draft.entities)) * 55)
    if draft.relations:
        score -= min(20.0, len(unsupported_relations) / max(1, len(draft.relations)) * 80)
    score = round(max(0.0, min(100.0, score)), 2)
    return {
        "score": score,
        "grade": _graph_quality_grade(score),
        "duplicate_candidates": duplicate_candidates[:40],
        "noisy_entities": noisy_entities,
        "important_entities": important_entities,
        "unsupported_relations": unsupported_relations,
        "metrics": {
            "duplicate_candidate_groups": len(duplicate_candidates),
            "noisy_entities": len(noisy_entities),
            "isolated_entities": isolated_count,
            "unsupported_relations": len(unsupported_relations),
            "important_entities": len(important_entities),
        },
        "recommendations": _entity_quality_recommendations(
            duplicate_candidates=duplicate_candidates,
            noisy_entities=noisy_entities,
            unsupported_relations=unsupported_relations,
            isolated_count=isolated_count,
        ),
    }


def _language_structure_report(draft: ProjectArchiveDraft) -> dict[str, Any]:
    ingestion = draft.metadata.get("ingestion", {}) if isinstance(draft.metadata, dict) else {}
    extraction = ingestion.get("extraction", {}) if isinstance(ingestion, dict) else {}
    languages = extraction.get("languages", {}) if isinstance(extraction, dict) else {}
    tree_sitter = extraction.get("tree_sitter", {}) if isinstance(extraction, dict) else {}
    supported_tree_sitter = {"java", "cpp", "typescript", "tsx", "javascript", "go", "rust"}
    entity_counts_by_language: dict[str, Counter[str]] = defaultdict(Counter)
    relation_counts_by_language: dict[str, Counter[str]] = defaultdict(Counter)
    for entity in draft.entities:
        language = str(entity.properties.get("language") or _language_from_path(entity.source_path or "unknown"))
        entity_counts_by_language[language][entity.type] += 1
    entity_language_by_id = {
        entity.id: str(entity.properties.get("language") or _language_from_path(entity.source_path or "unknown"))
        for entity in draft.entities
    }
    for relation in draft.relations:
        language = entity_language_by_id.get(relation.source_id) or entity_language_by_id.get(relation.target_id) or "unknown"
        relation_counts_by_language[language][relation.type] += 1
    language_rows = []
    for language in sorted(set(languages) | set(entity_counts_by_language) | set(relation_counts_by_language)):
        stats = languages.get(language, {}) if isinstance(languages, dict) else {}
        language_rows.append(
            {
                "language": language,
                "files": int(stats.get("files", 0) or stats.get("count", 0) or 0) if isinstance(stats, dict) else 0,
                "entities": sum(entity_counts_by_language[language].values()),
                "relations": sum(relation_counts_by_language[language].values()),
                "evidence": int(stats.get("evidence", 0) or 0) if isinstance(stats, dict) else 0,
                "tree_sitter_supported": language in supported_tree_sitter,
                "top_entities": entity_counts_by_language[language].most_common(8),
                "top_relations": relation_counts_by_language[language].most_common(8),
            }
        )
    return {
        "languages": language_rows,
        "tree_sitter": {
            "files": _safe_int(tree_sitter.get("files")) if isinstance(tree_sitter, dict) else 0,
            "parsed": _safe_int(tree_sitter.get("parsed")) if isinstance(tree_sitter, dict) else 0,
            "unavailable": _safe_int(tree_sitter.get("unavailable")) if isinstance(tree_sitter, dict) else 0,
            "fallbacks": _safe_int(tree_sitter.get("fallbacks")) if isinstance(tree_sitter, dict) else 0,
            "supported_languages": sorted(supported_tree_sitter),
        },
        "semantic_relation_hints": Counter(relation.type for relation in draft.relations).most_common(20),
        "warnings": _language_structure_warnings(language_rows, tree_sitter if isinstance(tree_sitter, dict) else {}),
    }


def _large_graph_policy(
    draft: ProjectArchiveDraft,
    entity_quality: dict[str, Any],
) -> dict[str, Any]:
    entity_count = len(draft.entities)
    relation_count = len(draft.relations)
    return {
        "mode": "search_neighborhood" if entity_count > 1200 or relation_count > 2000 else "direct_neighborhood",
        "default_node_limit": 120 if entity_count > 1200 else 80,
        "default_relation_limit": 180 if relation_count > 2000 else 120,
        "reason": (
            "Large archive: use search, recommended entry points, clusters, and neighborhood expansion."
            if entity_count > 1200 or relation_count > 2000
            else "Archive fits the standard neighborhood graph workflow."
        ),
        "noise_hint_count": int(entity_quality.get("metrics", {}).get("noisy_entities", 0) or 0),
        "duplicate_hint_count": int(entity_quality.get("metrics", {}).get("duplicate_candidate_groups", 0) or 0),
    }


def _normalize_entity_label(value: str) -> str:
    return re.sub(r"[^a-z0-9_./:-]+", "", value.strip().lower())


def _entity_noise_reason(
    entity: ProjectEntity,
    relations_by_entity: dict[str, list[ProjectRelation]],
) -> str:
    path = (entity.source_path or entity.name).lower()
    degree = len(relations_by_entity.get(entity.id, []))
    if any(part in path for part in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "dist/", "build/", "target/")):
        return "Generated or lock/build artifact."
    if degree == 0 and not entity.evidence_ids and entity.type.lower() in {"value", "token", "symbol", "unknown"}:
        return "Isolated low-information entity without evidence."
    if len(entity.name) <= 2 and degree == 0:
        return "Very short isolated label."
    return ""


def _entity_quality_recommendations(
    *,
    duplicate_candidates: list[dict[str, Any]],
    noisy_entities: list[dict[str, Any]],
    unsupported_relations: list[dict[str, Any]],
    isolated_count: int,
) -> list[str]:
    recommendations: list[str] = []
    if duplicate_candidates:
        recommendations.append("Review duplicate entity candidates and merge obvious aliases in graph curation.")
    if noisy_entities:
        recommendations.append("Hide generated artifacts and low-information entities before exploring large graphs.")
    if unsupported_relations:
        recommendations.append("Inspect unsupported relations before using Agent conclusions as final evidence.")
    if isolated_count:
        recommendations.append("Use recommended entry points instead of rendering isolated nodes by default.")
    if not recommendations:
        recommendations.append("Entity quality looks usable. Continue with graph exploration and report generation.")
    return recommendations


def _language_from_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".py": "python",
        ".java": "java",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".c": "c",
        ".h": "cpp",
        ".hpp": "cpp",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".js": "javascript",
        ".jsx": "javascript",
        ".go": "go",
        ".rs": "rust",
        ".md": "markdown",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".toml": "toml",
    }.get(suffix, "unknown")


def _language_structure_warnings(
    language_rows: list[dict[str, Any]],
    tree_sitter: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    files = _safe_int(tree_sitter.get("files"))
    parsed = _safe_int(tree_sitter.get("parsed"))
    unavailable = _safe_int(tree_sitter.get("unavailable"))
    if files and parsed == 0:
        warnings.append("Tree-sitter saw code files but parsed none of them.")
    if unavailable:
        warnings.append(f"{unavailable} Tree-sitter file(s) had unavailable parsers.")
    for row in language_rows:
        if row.get("tree_sitter_supported") and int(row.get("entities", 0) or 0) == 0:
            warnings.append(f"{row.get('language')} is supported but produced no structure entities.")
    return warnings[:12]


def _graph_module_clusters(
    draft: ProjectArchiveDraft,
    relations_by_entity: dict[str, list[ProjectRelation]],
) -> list[dict[str, Any]]:
    buckets: dict[str, list[ProjectEntity]] = defaultdict(list)
    for entity in draft.entities:
        buckets[_module_key(entity)].append(entity)
    clusters: list[dict[str, Any]] = []
    for key, entities in buckets.items():
        entity_ids = [entity.id for entity in entities]
        degree = sum(len(relations_by_entity.get(entity_id, [])) for entity_id in entity_ids)
        evidence_count = sum(len(entity.evidence_ids) for entity in entities)
        type_counts = Counter(entity.type for entity in entities)
        clusters.append(
            {
                "id": f"module:{_stable_eval_id(key)}",
                "label": key,
                "entity_count": len(entities),
                "relation_touch_count": degree,
                "evidence_count": evidence_count,
                "top_entity_types": [
                    {"type": entity_type, "count": count}
                    for entity_type, count in type_counts.most_common(6)
                ],
                "sample_entity_ids": entity_ids[:12],
                "confidence": round(min(1.0, 0.35 + len(entities) / 40 + degree / 160), 4),
            }
        )
    return sorted(
        clusters,
        key=lambda item: (
            int(item["entity_count"]),
            int(item["relation_touch_count"]),
            int(item["evidence_count"]),
        ),
        reverse=True,
    )[:80]


def _relation_confidence_record(
    relation: ProjectRelation,
    evidence_by_id: dict[str, EvidenceCard],
) -> dict[str, Any]:
    evidence_count = sum(1 for evidence_id in relation.evidence_ids if evidence_id in evidence_by_id)
    property_confidence = relation.properties.get("confidence")
    if isinstance(property_confidence, int | float):
        confidence = float(property_confidence)
    else:
        confidence = 0.35 + min(0.45, evidence_count * 0.15)
        if relation.type.upper() in {"DEFINES", "IMPORTS", "CALLS", "DEPENDS_ON"}:
            confidence += 0.12
    confidence = round(max(0.0, min(1.0, confidence)), 4)
    return {
        "relation_id": relation.id,
        "source_id": relation.source_id,
        "target_id": relation.target_id,
        "type": relation.type,
        "confidence": confidence,
        "evidence_count": evidence_count,
        "strength": "strong" if confidence >= 0.72 else "medium" if confidence >= 0.5 else "weak",
    }


def _module_boundary_candidates(draft: ProjectArchiveDraft) -> list[dict[str, Any]]:
    entity_by_id = {entity.id: entity for entity in draft.entities}
    boundary_counts: Counter[tuple[str, str]] = Counter()
    relation_ids_by_boundary: dict[tuple[str, str], list[str]] = defaultdict(list)
    evidence_counts: Counter[tuple[str, str]] = Counter()
    for relation in draft.relations:
        source = entity_by_id.get(relation.source_id)
        target = entity_by_id.get(relation.target_id)
        if source is None or target is None:
            continue
        source_module = _module_key(source)
        target_module = _module_key(target)
        if source_module == target_module:
            continue
        key = tuple(sorted([source_module, target_module]))
        boundary_counts[key] += 1
        relation_ids_by_boundary[key].append(relation.id)
        evidence_counts[key] += len(relation.evidence_ids)
    return [
        {
            "id": f"boundary:{_stable_eval_id(left + '|' + right)}",
            "left_module": left,
            "right_module": right,
            "relation_count": count,
            "evidence_count": evidence_counts[(left, right)],
            "sample_relation_ids": relation_ids_by_boundary[(left, right)][:12],
            "confidence": round(min(1.0, 0.45 + count / 24 + evidence_counts[(left, right)] / 48), 4),
        }
        for (left, right), count in boundary_counts.most_common(60)
    ]


def _graph_quality_report(
    *,
    draft: ProjectArchiveDraft,
    relations_by_entity: dict[str, list[ProjectRelation]],
    hybrid_status: dict[str, Any] | None,
) -> dict[str, Any]:
    entity_count = len(draft.entities)
    relation_count = len(draft.relations)
    evidence_count = len(draft.evidence_cards)
    connected_entity_ids = {
        entity_id
        for relation in draft.relations
        for entity_id in (relation.source_id, relation.target_id)
    }
    isolated_count = max(0, entity_count - len(connected_entity_ids))
    entity_evidence_count = sum(1 for entity in draft.entities if entity.evidence_ids)
    relation_evidence_count = sum(1 for relation in draft.relations if relation.evidence_ids)
    image_cards = [
        card for card in draft.evidence_cards
        if card.source_type == "image" or card.metadata.get("modality") == "image"
    ]
    vision_supported = sum(1 for card in image_cards if card.metadata.get("vision_enabled"))
    ingestion = dict(draft.metadata.get("ingestion", {}))
    extraction = ingestion.get("extraction", {}) if isinstance(ingestion.get("extraction"), dict) else {}
    tree_sitter = extraction.get("tree_sitter", {}) if isinstance(extraction, dict) else {}
    tree_sitter_files = _safe_int(tree_sitter.get("files"))
    tree_sitter_parsed = _safe_int(tree_sitter.get("parsed"))
    relation_density = relation_count / entity_count if entity_count else 0.0
    isolated_ratio = isolated_count / entity_count if entity_count else 1.0
    entity_evidence_coverage = entity_evidence_count / entity_count if entity_count else 0.0
    relation_evidence_coverage = relation_evidence_count / relation_count if relation_count else 0.0
    tree_sitter_success = (
        tree_sitter_parsed / tree_sitter_files
        if tree_sitter_files
        else 1.0 if entity_count else 0.0
    )
    hybrid_indexed_chunks = _safe_int((hybrid_status or {}).get("indexed_chunks"))
    hybrid_score = min(1.0, hybrid_indexed_chunks / max(8, evidence_count or 1))
    multimodal_score = (
        vision_supported / len(image_cards)
        if image_cards
        else 1.0
    )
    relation_density_score = min(1.0, relation_density / 1.4)
    connected_score = 1.0 - isolated_ratio
    component_scores = {
        "entity_coverage": round(min(1.0, entity_count / 50), 4),
        "relation_density": round(relation_density_score, 4),
        "connectedness": round(max(0.0, connected_score), 4),
        "entity_evidence_coverage": round(entity_evidence_coverage, 4),
        "relation_evidence_coverage": round(relation_evidence_coverage, 4),
        "tree_sitter_success": round(max(0.0, min(1.0, tree_sitter_success)), 4),
        "hybrid_rag_health": round(hybrid_score, 4),
        "multimodal_support": round(max(0.0, min(1.0, multimodal_score)), 4),
    }
    weights = {
        "entity_coverage": 0.12,
        "relation_density": 0.16,
        "connectedness": 0.14,
        "entity_evidence_coverage": 0.16,
        "relation_evidence_coverage": 0.12,
        "tree_sitter_success": 0.10,
        "hybrid_rag_health": 0.14,
        "multimodal_support": 0.06,
    }
    score = round(
        sum(component_scores[key] * weight for key, weight in weights.items()) * 100,
        1,
    )
    warnings: list[str] = []
    recommendations: list[str] = []
    if entity_count < 10:
        warnings.append("The graph has very few entities.")
        recommendations.append("Regenerate with the full scan profile or inspect skipped-file diagnostics.")
    if relation_density < 0.35 and entity_count > 10:
        warnings.append("Relation density is low for the extracted entity count.")
        recommendations.append("Check Tree-sitter availability and language adapter coverage.")
    if isolated_ratio > 0.45 and entity_count > 10:
        warnings.append("Many entities are isolated from the project graph.")
        recommendations.append("Start exploration from high-degree nodes and review weak relation extraction.")
    if entity_evidence_coverage < 0.45 and entity_count:
        warnings.append("Many entities lack direct evidence cards.")
        recommendations.append("Increase evidence extraction depth or rerun with a broader scan profile.")
    if hybrid_status is None or hybrid_indexed_chunks == 0:
        warnings.append("Hybrid RAG index is missing or empty.")
        recommendations.append("Rebuild the archive after verifying embedding and vector-store configuration.")
    if image_cards and vision_supported == 0:
        warnings.append("Image evidence exists, but vision understanding did not run successfully.")
        recommendations.append("Verify the configured vision model or Ollama vision endpoint.")
    if not recommendations:
        recommendations.append("Archive quality looks usable. Continue with graph exploration and Agent analysis.")
    return {
        "score": score,
        "grade": _graph_quality_grade(score),
        "component_scores": component_scores,
        "weights": weights,
        "signals": {
            "entities": entity_count,
            "relations": relation_count,
            "evidence": evidence_count,
            "isolated_entities": isolated_count,
            "relation_density": round(relation_density, 4),
            "tree_sitter_files": tree_sitter_files,
            "tree_sitter_parsed": tree_sitter_parsed,
            "hybrid_indexed_chunks": hybrid_indexed_chunks,
            "image_cards": len(image_cards),
            "vision_supported_cards": vision_supported,
        },
        "warnings": warnings[:8],
        "recommendations": recommendations[:8],
    }


def _graph_quality_grade(score: float) -> str:
    if score >= 86:
        return "A"
    if score >= 72:
        return "B"
    if score >= 55:
        return "C"
    if score >= 38:
        return "D"
    return "E"


def _graph_snapshot_payload(draft: ProjectArchiveDraft) -> dict[str, Any]:
    entity_types = Counter(entity.type for entity in draft.entities)
    relation_types = Counter(relation.type for relation in draft.relations)
    modules = Counter(_module_key(entity) for entity in draft.entities)
    return {
        "project_id": draft.project_id,
        "created_at": datetime.now(UTC).isoformat(),
        "counts": {
            "halls": len(draft.halls),
            "entities": len(draft.entities),
            "relations": len(draft.relations),
            "evidence": len(draft.evidence_cards),
        },
        "entity_types": dict(entity_types),
        "relation_types": dict(relation_types),
        "modules": dict(modules.most_common(80)),
        "fingerprint": hashlib.sha1(
            json.dumps(
                {
                    "entities": sorted(entity.id for entity in draft.entities),
                    "relations": sorted(relation.id for relation in draft.relations),
                    "evidence": sorted(card.id for card in draft.evidence_cards),
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest(),
    }


def _graph_snapshot_diff(
    previous_snapshot: dict[str, Any] | None,
    current_snapshot: dict[str, Any],
) -> dict[str, Any]:
    if previous_snapshot is None:
        return {
            "status": "baseline",
            "added": 0,
            "removed": 0,
            "changed": 0,
            "count_delta": current_snapshot.get("counts", {}),
        }
    previous_counts = previous_snapshot.get("counts", {})
    current_counts = current_snapshot.get("counts", {})
    keys = sorted({*previous_counts, *current_counts})
    count_delta = {
        key: _safe_int(current_counts.get(key)) - _safe_int(previous_counts.get(key))
        for key in keys
    }
    changed = sum(1 for value in count_delta.values() if value != 0)
    return {
        "status": "unchanged" if previous_snapshot.get("fingerprint") == current_snapshot.get("fingerprint") else "changed",
        "added": sum(max(0, value) for value in count_delta.values()),
        "removed": sum(abs(min(0, value)) for value in count_delta.values()),
        "changed": changed,
        "count_delta": count_delta,
        "previous_created_at": previous_snapshot.get("created_at"),
    }


def _claim_support_status(
    evidence_ids: list[str],
    entity_ids: list[str],
    relation_ids: list[str],
) -> str:
    if evidence_ids and (entity_ids or relation_ids):
        return "supported"
    if evidence_ids or entity_ids or relation_ids:
        return "partial"
    return "unsupported"


def _agent_mission_visualization_report(mission: AgentMission) -> dict[str, Any]:
    trace_events = sorted(mission.trace_events, key=lambda event: event.sequence)
    tool_counts = Counter(
        event.tool_name or event.event_type
        for event in trace_events
        if event.tool_name or event.event_type
    )
    phase_buckets: dict[str, list[AgentTraceEvent]] = defaultdict(list)
    for event in trace_events:
        phase_buckets[_react_visual_phase(event)].append(event)
    task_cards = [
        {
            "id": task.id,
            "task_type": task.task_type,
            "objective": task.objective,
            "status": task.status,
            "steps_used": task.steps_used,
            "max_steps": task.max_steps,
            "allowed_tools": task.allowed_tools,
            "evidence_count": len(task.evidence_ids),
            "entity_count": len(_unique_preserve_order([*task.input_entity_ids, *task.output_entity_ids], limit=200)),
            "confidence": task.confidence,
            "unsupported": not task.evidence_ids and not task.output_entity_ids,
            "findings": task.findings[:5],
            "risks": task.risks[:5],
        }
        for task in mission.tasks
    ]
    loop_phases = [
        _react_visual_phase_record("planning", phase_buckets.get("planning", [])),
        _react_visual_phase_record("action", phase_buckets.get("action", [])),
        _react_visual_phase_record("observation", phase_buckets.get("observation", [])),
        _react_visual_phase_record("verification", phase_buckets.get("verification", [])),
        _react_visual_phase_record("final", phase_buckets.get("final", [])),
    ]
    critic_reviews = (
        mission.metadata.get("critic_reviews", [])
        if isinstance(mission.metadata.get("critic_reviews", []), list)
        else []
    )
    return {
        "mission_id": mission.id,
        "project_id": mission.project_id,
        "created_at": datetime.now(UTC).isoformat(),
        "status": mission.status,
        "goal": mission.goal,
        "loop_phases": loop_phases,
        "task_cards": task_cards,
        "tool_timeline": [
            {
                "id": event.id,
                "sequence": event.sequence,
                "phase": _react_visual_phase(event),
                "event_type": event.event_type,
                "tool_name": event.tool_name,
                "summary": event.observation_summary,
                "evidence_count": len(event.evidence_ids),
                "entity_count": len(event.entity_ids),
                "relation_count": len(event.relation_ids),
                "error": event.error,
            }
            for event in trace_events[:120]
        ],
        "audit": {
            "trace_events": len(trace_events),
            "tool_calls": sum(1 for event in trace_events if event.tool_name),
            "tools": dict(tool_counts),
            "errors": sum(1 for event in trace_events if event.error),
            "critic_reviews": len(critic_reviews),
            "retries": sum(1 for review in critic_reviews if isinstance(review, dict) and review.get("retry_performed")),
            "supported_tasks": sum(1 for task in task_cards if not task["unsupported"]),
            "unsupported_tasks": sum(1 for task in task_cards if task["unsupported"]),
        },
        "warnings": _react_visual_warnings(mission, trace_events, task_cards),
        "metadata": {
            "method": "react_trace_phase_grouping_with_task_and_tool_audit",
            "verifier": mission.verifier_result.to_dict() if mission.verifier_result else None,
        },
    }


def _react_visual_phase(event: AgentTraceEvent) -> str:
    event_type = event.event_type.lower()
    if "plan" in event_type or "task" in event_type and not event.tool_name:
        return "planning"
    if event.tool_name or "tool" in event_type or "action" in event_type:
        return "action"
    if "observe" in event_type or "observation" in event_type:
        return "observation"
    if "verify" in event_type or "critic" in event_type or "review" in event_type:
        return "verification"
    if "final" in event_type or "complete" in event_type:
        return "final"
    return "observation" if event.observation_summary else "action"


def _react_visual_phase_record(
    phase: str,
    events: list[AgentTraceEvent],
) -> dict[str, Any]:
    return {
        "phase": phase,
        "event_count": len(events),
        "tool_count": sum(1 for event in events if event.tool_name),
        "evidence_count": len({evidence_id for event in events for evidence_id in event.evidence_ids}),
        "entity_count": len({entity_id for event in events for entity_id in event.entity_ids}),
        "relation_count": len({relation_id for event in events for relation_id in event.relation_ids}),
        "error_count": sum(1 for event in events if event.error),
        "summary": _react_phase_summary(phase, events),
    }


def _react_phase_summary(phase: str, events: list[AgentTraceEvent]) -> str:
    if not events:
        return f"No {phase} events were recorded."
    latest = next((event for event in reversed(events) if event.observation_summary), events[-1])
    return latest.observation_summary or f"{len(events)} {phase} event(s) recorded."


def _react_visual_warnings(
    mission: AgentMission,
    trace_events: list[AgentTraceEvent],
    task_cards: list[dict[str, Any]],
) -> list[str]:
    warnings: list[str] = []
    if not trace_events:
        warnings.append("No trace events were recorded for this ReAct mission.")
    unsupported = [task for task in task_cards if task.get("unsupported")]
    if unsupported:
        warnings.append(f"{len(unsupported)} task(s) do not cite evidence or output entities.")
    error_count = sum(1 for event in trace_events if event.error)
    if error_count:
        warnings.append(f"{error_count} trace event(s) contain errors.")
    if mission.verifier_result and mission.verifier_result.status not in {"supported", "complete", "passed"}:
        warnings.extend(mission.verifier_result.warnings[:5])
    return warnings


def _agent_derivation(metadata: dict[str, Any]) -> dict[str, Any]:
    agent_sdk = metadata.get("agent_sdk")
    llm = metadata.get("llm")
    return {
        "source": "llm" if isinstance(llm, dict) and llm.get("enabled") else "deterministic_or_tool",
        "llm": llm if isinstance(llm, dict) else None,
        "tools": agent_sdk.get("tools", []) if isinstance(agent_sdk, dict) else [],
        "validation": agent_sdk.get("validation") if isinstance(agent_sdk, dict) else None,
        "work_log_count": len(agent_sdk.get("work_log", [])) if isinstance(agent_sdk, dict) else 0,
    }


def _image_entity_candidates(card: EvidenceCard) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    raw_entities = card.metadata.get("diagram_entities", [])
    if isinstance(raw_entities, list):
        for item in raw_entities:
            label = _image_candidate_label(item)
            if label:
                candidates.append(_image_candidate_record(card, "image_entity", label))
    if not candidates:
        for token in _image_candidate_tokens(" ".join([card.title, card.snippet])):
            candidates.append(_image_candidate_record(card, "image_token", token))
            if len(candidates) >= 12:
                break
    return candidates


def _image_relation_candidates(card: EvidenceCard) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    raw_relations = card.metadata.get("diagram_relations", [])
    if isinstance(raw_relations, list):
        for item in raw_relations:
            if isinstance(item, dict):
                source = _image_candidate_label(item.get("source") or item.get("from"))
                target = _image_candidate_label(item.get("target") or item.get("to"))
                relation_type = str(item.get("type") or "IMAGE_LINK")
            else:
                source = ""
                target = ""
                relation_type = str(item)
            if source and target:
                candidates.append(
                    {
                        "id": f"image-relation:{_stable_eval_id(card.id + source + target)}",
                        "type": relation_type,
                        "source_label": source,
                        "target_label": target,
                        "evidence_id": card.id,
                        "source_path": card.source_path,
                        "confidence": float(card.metadata.get("image_quality_score", card.confidence) or 0.5),
                    }
                )
    return candidates


def _multimodal_entity_alignments(
    draft: ProjectArchiveDraft,
    image_cards: list[EvidenceCard],
) -> list[dict[str, Any]]:
    entity_by_id = {entity.id: entity for entity in draft.entities}
    alignments: list[dict[str, Any]] = []
    for card in image_cards:
        tokens = set(_image_candidate_tokens(" ".join([
            card.title,
            card.snippet,
            card.source_path,
            str(card.metadata.get("ocr_text", "")),
            " ".join(
                _image_candidate_label(item)
                for item in card.metadata.get("diagram_entities", [])
                if _image_candidate_label(item)
            ) if isinstance(card.metadata.get("diagram_entities", []), list) else "",
        ])))
        matched: list[dict[str, Any]] = []
        for linked_id in card.linked_entities:
            entity = entity_by_id.get(linked_id)
            if entity is not None:
                matched.append(_multimodal_alignment_record(entity, "linked_evidence", 1.0))
        for entity in draft.entities:
            if entity.id in {item["id"] for item in matched}:
                continue
            haystack = f"{entity.name} {entity.type} {entity.source_path or ''}".lower()
            entity_tokens = set(_image_candidate_tokens(haystack))
            overlap = sorted(tokens & entity_tokens)
            if not overlap:
                continue
            score = min(0.95, 0.42 + len(overlap) * 0.12)
            matched.append(
                _multimodal_alignment_record(
                    entity,
                    "ocr_or_diagram_token",
                    score,
                    overlap=overlap[:6],
                )
            )
            if len(matched) >= 10:
                break
        alignments.append(
            {
                "evidence_id": card.id,
                "source_path": card.source_path,
                "understanding_method": card.metadata.get("understanding_method", "metadata_fallback"),
                "vision_enabled": bool(card.metadata.get("vision_enabled")),
                "ocr_supported": bool(card.metadata.get("ocr_text")),
                "aligned_entities": sorted(
                    matched,
                    key=lambda item: (-float(item.get("score", 0.0)), str(item.get("label", ""))),
                )[:10],
            }
        )
    return alignments


def _multimodal_alignment_record(
    entity: ProjectEntity,
    method: str,
    score: float,
    *,
    overlap: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": entity.id,
        "label": entity.name,
        "type": entity.type,
        "source_path": entity.source_path,
        "method": method,
        "score": round(score, 3),
        "matched_terms": overlap or [],
    }


def _module_key(entity: ProjectEntity) -> str:
    if entity.source_path:
        parts = [part for part in Path(entity.source_path).parts if part not in {"", "."}]
        if len(parts) >= 2:
            return "/".join(parts[:2])
        if parts:
            return parts[0]
    return entity.type or "unknown"


def _image_candidate_label(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("label") or value.get("name") or value.get("id")
    if not isinstance(value, str):
        return ""
    return value.strip()[:160]


def _image_candidate_record(card: EvidenceCard, candidate_type: str, label: str) -> dict[str, Any]:
    return {
        "id": f"{candidate_type}:{_stable_eval_id(card.id + ':' + label)}",
        "type": candidate_type,
        "label": label,
        "evidence_id": card.id,
        "source_path": card.source_path,
        "confidence": float(card.metadata.get("image_quality_score", card.confidence) or 0.5),
    }


def _image_candidate_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_./-]{3,}", text)
    ignored = {"image", "diagram", "project", "architecture", "fallback", "summary"}
    return _unique_preserve_order(
        [token for token in tokens if token.lower() not in ignored],
        limit=20,
    )


def _ingestion_health(
    graph: dict[str, Any],
    scan: dict[str, Any],
    extraction: dict[str, Any],
    hybrid_status: dict[str, Any] | None,
    image_cards: list,
) -> dict[str, Any]:
    score = 100
    warnings: list[str] = []
    entities = _safe_int(graph.get("entities"))
    relations = _safe_int(graph.get("relations"))
    kept_files = _safe_int(scan.get("kept_files"))
    skipped_files = _safe_int(scan.get("skipped_files"))
    if entities == 0:
        score -= 35
        warnings.append("No entities were extracted.")
    elif entities < 10 and kept_files > 10:
        score -= 18
        warnings.append("The archive looks sparse compared with the scanned file count.")
    if relations == 0 and entities > 1:
        score -= 18
        warnings.append("Entities were extracted, but no relationships were found.")
    if skipped_files > kept_files and skipped_files > 20:
        score -= 12
        warnings.append("More files were skipped than kept.")
    tree_sitter = extraction.get("tree_sitter", {}) if isinstance(extraction, dict) else {}
    if _safe_int(tree_sitter.get("files")) and _safe_int(tree_sitter.get("parsed")) == 0:
        score -= 12
        warnings.append("Tree-sitter files were detected but no Tree-sitter parse succeeded.")
    if hybrid_status is None:
        score -= 10
        warnings.append("Hybrid RAG index status is missing.")
    if image_cards and not any(card.metadata.get("vision_enabled") for card in image_cards):
        score -= 6
        warnings.append("Image evidence exists, but vision understanding used fallback captions.")
    return {
        "score": max(0, min(100, score)),
        "status": "healthy" if score >= 80 else "review" if score >= 55 else "attention",
        "warnings": warnings,
    }


def _ingestion_diagnostic_recommendations(
    *,
    graph: dict[str, Any],
    scan: dict[str, Any],
    extraction: dict[str, Any],
    upload: dict[str, Any],
    hybrid_status: dict[str, Any] | None,
    image_cards: list,
    vision_errors: list[str],
) -> list[str]:
    recommendations: list[str] = []
    kept_files = _safe_int(scan.get("kept_files"))
    total_zip_files = _safe_int(upload.get("total_zip_files"))
    if total_zip_files and kept_files and kept_files < total_zip_files * 0.15:
        recommendations.append("Most ZIP files were filtered before scanning. Try the full scan profile if the project looks too small.")
    if _safe_int(graph.get("entities")) < 10 and kept_files > 10:
        recommendations.append("The graph is sparse. Check extraction errors and consider adding language adapters for dominant file types.")
    tree_sitter = extraction.get("tree_sitter", {}) if isinstance(extraction, dict) else {}
    if _safe_int(tree_sitter.get("unavailable")):
        recommendations.append("Install the missing Tree-sitter language packages to improve Java/C++/TS/Go/Rust structure extraction.")
    if _safe_int(tree_sitter.get("fallbacks")):
        recommendations.append("Some Tree-sitter files fell back to generic extraction. Inspect the extraction error samples.")
    if hybrid_status is None:
        recommendations.append("Hybrid RAG status is missing. Regenerate the archive to rebuild Chroma, BM25, and RRF indexes.")
    elif _safe_int(hybrid_status.get("indexed_chunks")) == 0:
        recommendations.append("Hybrid RAG indexed zero chunks. Check embedding/Ollama settings and source text availability.")
    if image_cards and vision_errors:
        recommendations.append("Vision model calls produced errors. Check Ollama vision model availability or provider credentials.")
    if not recommendations:
        recommendations.append("Ingestion looks consistent. Use graph exploration or Agent analysis to inspect semantic quality next.")
    return recommendations[:8]


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _empty_agent_memory(project_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "updated_at": "",
        "facts": [],
        "entities": [],
        "evidence": [],
        "relations": [],
        "risks": [],
        "harness_runs": [],
        "recommendations": [],
        "metadata": {"method": "project_scoped_file_memory_v1"},
    }


def _empty_agent_trust_report(project_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "created_at": datetime.now(UTC).isoformat(),
        "claims": [],
        "warnings": ["Agent trust report unavailable."],
        "metrics": {
            "claims": 0,
            "supported_claims": 0,
            "partial_claims": 0,
            "unsupported_claims": 0,
            "low_confidence_claims": 0,
            "missions": 0,
        },
        "metadata": {
            "report_available": False,
            "method": "empty_agent_trust_report",
        },
    }


def _agent_eval_metrics(
    *,
    draft: ProjectArchiveDraft,
    agent_report: ProjectAgentReport | None,
    agent_error: str,
    evaluation: ArchiveEvaluationReport | None,
    evaluation_error: str,
    trust_report: dict[str, Any],
    rag_status: dict[str, Any],
    multimodal: dict[str, Any],
    missions: list[AgentMission],
) -> dict[str, Any]:
    eval_metrics = evaluation.aggregate_metrics if evaluation is not None else {}
    trust_metrics = trust_report.get("metrics", {})
    candidate_chunks = _safe_int(rag_status.get("candidate_chunks")) or (
        len(draft.entities) + len(draft.relations) + len(draft.evidence_cards)
    )
    indexed_chunks = _safe_int(rag_status.get("indexed_chunks"))
    rag_coverage_ratio = (
        _safe_float(rag_status.get("coverage_ratio"))
        if rag_status.get("coverage_ratio") is not None
        else (indexed_chunks / candidate_chunks if candidate_chunks else 0.0)
    )
    latest_mission = missions[0] if missions else None
    mission_task_counts = _agent_mission_task_counts(
        [latest_mission] if latest_mission is not None else []
    )
    mission_history_task_counts = _agent_mission_task_counts(missions)
    agent_confidences = [
        _safe_float(result.confidence)
        for result in (agent_report.agents.values() if agent_report is not None else [])
    ]
    agent_llm_metadata = [
        (result.metadata or {}).get("llm", {})
        for result in (agent_report.agents.values() if agent_report is not None else [])
    ]
    agent_llm_enabled = sum(1 for metadata in agent_llm_metadata if metadata.get("enabled"))
    agent_llm_fallbacks = sum(1 for metadata in agent_llm_metadata if metadata.get("fallback"))
    agent_json_repairs = sum(1 for metadata in agent_llm_metadata if metadata.get("json_repaired"))
    entity_types = Counter(entity.type for entity in draft.entities)
    evidence_modalities = Counter(
        str(card.metadata.get("modality") or card.source_type or "unknown")
        for card in draft.evidence_cards
    )
    return {
        "entities": len(draft.entities),
        "relations": len(draft.relations),
        "evidence": len(draft.evidence_cards),
        "halls": len(draft.halls),
        "top_entity_types": dict(entity_types.most_common(8)),
        "evidence_modalities": dict(evidence_modalities.most_common(8)),
        "agent_report_available": agent_report is not None,
        "agent_status": agent_report.status if agent_report is not None else "missing",
        "agent_error": agent_error,
        "agent_count": len(agent_report.agents) if agent_report is not None else 0,
        "agent_llm_enabled_count": agent_llm_enabled,
        "agent_llm_fallback_count": agent_llm_fallbacks,
        "agent_json_repair_count": agent_json_repairs,
        "agent_confidence_avg": round(sum(agent_confidences) / len(agent_confidences), 4)
        if agent_confidences
        else 0.0,
        "evaluation_available": evaluation is not None,
        "evaluation_error": evaluation_error,
        "evaluation_score": round(_safe_float(eval_metrics.get("case_score")), 4),
        "entity_hit_rate": round(_safe_float(eval_metrics.get("entity_hit_rate")), 4),
        "relation_hit_rate": round(_safe_float(eval_metrics.get("relation_hit_rate")), 4),
        "evidence_hit_rate": round(_safe_float(eval_metrics.get("evidence_hit_rate")), 4),
        "graph_coverage": round(_safe_float(eval_metrics.get("graph_coverage")), 4),
        "evidence_coverage": round(_safe_float(eval_metrics.get("evidence_coverage")), 4),
        "trust_claims": _safe_int(trust_metrics.get("claims")),
        "trust_supported_claims": _safe_int(trust_metrics.get("supported_claims")),
        "trust_partial_claims": _safe_int(trust_metrics.get("partial_claims")),
        "trust_unsupported_claims": _safe_int(trust_metrics.get("unsupported_claims")),
        "trust_low_confidence_claims": _safe_int(trust_metrics.get("low_confidence_claims")),
        "rag_health": str(rag_status.get("health", "missing")),
        "rag_indexed_chunks": indexed_chunks,
        "rag_candidate_chunks": candidate_chunks,
        "rag_coverage_ratio": round(rag_coverage_ratio, 4),
        "rag_stale": bool(rag_status.get("stale")),
        "rag_error": str(rag_status.get("error", "")),
        "multimodal_images": _safe_int(
            multimodal.get("image_count", multimodal.get("images", 0))
        ),
        "multimodal_vision_supported": _safe_int(multimodal.get("vision_supported")),
        "multimodal_quality_score": round(
            _safe_float(
                multimodal.get("quality_score", multimodal.get("average_quality"))
            ),
            4,
        ),
        "mission_count": len(missions),
        "mission_scope": "latest",
        "latest_mission_id": latest_mission.id if latest_mission is not None else "",
        "latest_mission_status": latest_mission.status if latest_mission is not None else "",
        "mission_task_count": mission_task_counts["total"],
        "mission_supported_tasks": mission_task_counts["supported"],
        "mission_partial_tasks": mission_task_counts["partial"],
        "mission_timeout_tasks": mission_task_counts["timeout"],
        "mission_skipped_tasks": mission_task_counts["skipped"],
        "mission_unsupported_tasks": mission_task_counts["unsupported"],
        "mission_history_task_count": mission_history_task_counts["total"],
        "mission_history_supported_tasks": mission_history_task_counts["supported"],
        "mission_history_partial_tasks": mission_history_task_counts["partial"],
        "mission_history_timeout_tasks": mission_history_task_counts["timeout"],
        "mission_history_skipped_tasks": mission_history_task_counts["skipped"],
        "mission_history_unsupported_tasks": mission_history_task_counts["unsupported"],
    }


def _agent_eval_gates(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    gates = [
        _agent_eval_gate(
            gate_id="archive_graph",
            label="Archive graph has usable structure",
            score=1.0 if _safe_int(metrics.get("entities")) >= 3 and _safe_int(metrics.get("evidence")) >= 1 else 0.0,
            warn_threshold=0.5,
            fail_threshold=0.1,
            summary=(
                f"{metrics.get('entities', 0)} entities, "
                f"{metrics.get('relations', 0)} relations, "
                f"{metrics.get('evidence', 0)} evidence cards"
            ),
        ),
        _agent_eval_gate(
            gate_id="golden_eval",
            label="Golden-question retrieval quality",
            score=_safe_float(metrics.get("evaluation_score")),
            warn_threshold=0.45,
            fail_threshold=0.25,
            summary=(
                "Evaluation report available."
                if metrics.get("evaluation_available")
                else f"Evaluation missing: {metrics.get('evaluation_error') or 'not run'}"
            ),
            missing_status="warn",
            available=bool(metrics.get("evaluation_available")),
        ),
        _agent_eval_gate(
            gate_id="evidence_coverage",
            label="Evidence coverage",
            score=max(
                _safe_float(metrics.get("evidence_hit_rate")),
                _safe_float(metrics.get("evidence_coverage")),
            ),
            warn_threshold=0.35,
            fail_threshold=0.10,
            summary="Evidence hit/coverage should stay high enough for grounded answers.",
            missing_status="warn",
            available=bool(metrics.get("evaluation_available")),
        ),
        _agent_eval_gate(
            gate_id="agent_trust",
            label="Agent claims cite archive evidence",
            score=_claim_support_score(metrics),
            warn_threshold=0.70,
            fail_threshold=0.40,
            summary=(
                f"{metrics.get('trust_supported_claims', 0)} supported, "
                f"{metrics.get('trust_partial_claims', 0)} partial, "
                f"{metrics.get('trust_unsupported_claims', 0)} unsupported claims"
            ),
            missing_status="warn",
            available=_safe_int(metrics.get("trust_claims")) > 0,
        ),
        _agent_eval_gate(
            gate_id="agent_llm_runtime",
            label="Agent LLM runtime completed without fallback",
            score=_agent_llm_runtime_score(metrics),
            warn_threshold=0.80,
            fail_threshold=0.45,
            summary=(
                f"{metrics.get('agent_llm_enabled_count', 0)} LLM-enabled agents, "
                f"{metrics.get('agent_llm_fallback_count', 0)} fallback agents, "
                f"{metrics.get('agent_json_repair_count', 0)} JSON repair events"
            ),
            missing_status="warn",
            available=_safe_int(metrics.get("agent_count")) > 0,
        ),
        _agent_eval_gate(
            gate_id="hybrid_rag",
            label="Hybrid RAG index health",
            score=_rag_health_score(metrics),
            warn_threshold=0.45,
            fail_threshold=0.10,
            summary=(
                f"{metrics.get('rag_indexed_chunks', 0)}/"
                f"{metrics.get('rag_candidate_chunks', 0)} chunks indexed; "
                f"health={metrics.get('rag_health')}"
            ),
        ),
        _agent_eval_gate(
            gate_id="mission_verifier",
            label="Agent mission task grounding",
            score=_mission_grounding_score(metrics),
            warn_threshold=0.55,
            fail_threshold=0.20,
            summary=(
                f"{metrics.get('mission_supported_tasks', 0)} supported tasks, "
                f"{metrics.get('mission_partial_tasks', 0)} partial tasks, "
                f"{metrics.get('mission_timeout_tasks', 0)} timeout tasks, "
                f"{metrics.get('mission_skipped_tasks', 0)} skipped tasks, "
                f"{metrics.get('mission_unsupported_tasks', 0)} unsupported tasks"
            ),
            missing_status="warn",
            available=_safe_int(metrics.get("mission_task_count")) > 0,
        ),
    ]
    return gates


def _agent_eval_gate(
    *,
    gate_id: str,
    label: str,
    score: float,
    warn_threshold: float,
    fail_threshold: float,
    summary: str,
    available: bool = True,
    missing_status: str = "warn",
) -> dict[str, Any]:
    normalized = max(0.0, min(1.0, round(score, 4)))
    if not available:
        status = missing_status
    elif normalized < fail_threshold:
        status = "fail"
    elif normalized < warn_threshold:
        status = "warn"
    else:
        status = "pass"
    return {
        "id": gate_id,
        "label": label,
        "status": status,
        "score": normalized,
        "warn_threshold": warn_threshold,
        "fail_threshold": fail_threshold,
        "summary": summary,
    }


def _claim_support_score(metrics: dict[str, Any]) -> float:
    total = _safe_int(metrics.get("trust_claims"))
    if total <= 0:
        return 0.0
    supported = _safe_int(metrics.get("trust_supported_claims"))
    partial = _safe_int(metrics.get("trust_partial_claims"))
    unsupported = _safe_int(metrics.get("trust_unsupported_claims"))
    low_confidence = _safe_int(metrics.get("trust_low_confidence_claims"))
    score = (supported + partial * 0.55) / total
    penalty = min(0.4, (unsupported + low_confidence * 0.5) / max(total, 1) * 0.4)
    return max(0.0, score - penalty)


def _rag_health_score(metrics: dict[str, Any]) -> float:
    health = str(metrics.get("rag_health", "missing"))
    coverage = _safe_float(metrics.get("rag_coverage_ratio"))
    indexed = _safe_int(metrics.get("rag_indexed_chunks"))
    if metrics.get("rag_error") or health in {"missing", "error"}:
        return 0.0
    score = max(coverage, 1.0 if indexed else 0.0)
    if metrics.get("rag_stale"):
        score *= 0.6
    if health == "warning":
        score *= 0.8
    return score


def _agent_llm_runtime_score(metrics: dict[str, Any]) -> float:
    total = _safe_int(metrics.get("agent_count"))
    if total <= 0:
        return 0.0
    fallback = _safe_int(metrics.get("agent_llm_fallback_count"))
    repaired = _safe_int(metrics.get("agent_json_repair_count"))
    enabled = _safe_int(metrics.get("agent_llm_enabled_count"))
    if enabled <= 0:
        return 0.0
    score = (enabled - fallback) / total
    if repaired:
        score -= min(0.25, repaired / total * 0.25)
    return max(0.0, score)


def _agent_mission_task_counts(missions: list[AgentMission]) -> dict[str, int]:
    counts = {
        "total": 0,
        "supported": 0,
        "partial": 0,
        "timeout": 0,
        "skipped": 0,
        "unsupported": 0,
    }
    for mission in missions:
        for task in mission.tasks:
            counts["total"] += 1
            status = str(task.status)
            has_grounding = bool(
                task.evidence_ids
                or task.output_entity_ids
                or any(
                    isinstance(finding, dict)
                    and (
                        finding.get("evidence_ids")
                        or finding.get("entity_ids")
                        or finding.get("relation_ids")
                    )
                    for finding in task.findings
                )
            )
            if status in {"complete", "completed"} and has_grounding:
                counts["supported"] += 1
            elif status in {"partial", "timeout"} and has_grounding:
                counts["partial"] += 1
                if status == "timeout":
                    counts["timeout"] += 1
            elif status == "skipped":
                counts["skipped"] += 1
                counts["unsupported"] += 1
            elif status in {"failed", "error", "timeout"}:
                if status == "timeout":
                    counts["timeout"] += 1
                counts["unsupported"] += 1
            elif status in {"complete", "completed"}:
                counts["unsupported"] += 1
    return counts


def _mission_grounding_score(metrics: dict[str, Any]) -> float:
    total = _safe_int(metrics.get("mission_task_count"))
    if total <= 0:
        return 0.0
    supported = _safe_int(metrics.get("mission_supported_tasks"))
    partial = _safe_int(metrics.get("mission_partial_tasks"))
    unsupported = _safe_int(metrics.get("mission_unsupported_tasks"))
    skipped = _safe_int(metrics.get("mission_skipped_tasks"))
    score = (supported + partial * 0.5) / total
    if unsupported:
        score -= min(0.35, unsupported / total * 0.35)
    if skipped:
        score -= min(0.2, skipped / total * 0.2)
    return max(0.0, score)


def _agent_eval_regression(
    metrics: dict[str, Any],
    previous_report: dict[str, Any] | None,
) -> dict[str, Any]:
    if not previous_report:
        return {
            "status": "baseline",
            "summary": "No previous AgentEval run for this project.",
            "checks": [],
        }
    previous_metrics = previous_report.get("metrics", {})
    checks = [
        _regression_numeric_check(
            metric="evaluation_score",
            current=_safe_float(metrics.get("evaluation_score")),
            previous=_safe_float(previous_metrics.get("evaluation_score")),
            warn_drop=0.05,
            fail_drop=0.15,
        ),
        _regression_numeric_check(
            metric="evidence_hit_rate",
            current=_safe_float(metrics.get("evidence_hit_rate")),
            previous=_safe_float(previous_metrics.get("evidence_hit_rate")),
            warn_drop=0.08,
            fail_drop=0.20,
        ),
        _regression_count_floor_check(
            metric="rag_indexed_chunks",
            current=_safe_int(metrics.get("rag_indexed_chunks")),
            previous=_safe_int(previous_metrics.get("rag_indexed_chunks")),
        ),
        _regression_count_ceiling_check(
            metric="trust_unsupported_claims",
            current=_safe_int(metrics.get("trust_unsupported_claims")),
            previous=_safe_int(previous_metrics.get("trust_unsupported_claims")),
        ),
    ]
    status = "pass"
    if any(check["status"] == "fail" for check in checks):
        status = "fail"
    elif any(check["status"] == "warn" for check in checks):
        status = "warn"
    return {
        "status": status,
        "summary": f"Compared against {previous_report.get('id') or 'previous run'}.",
        "previous_run_id": previous_report.get("id"),
        "previous_created_at": previous_report.get("created_at"),
        "checks": checks,
    }


def _regression_numeric_check(
    *,
    metric: str,
    current: float,
    previous: float,
    warn_drop: float,
    fail_drop: float,
) -> dict[str, Any]:
    delta = round(current - previous, 4)
    if delta <= -fail_drop:
        status = "fail"
    elif delta <= -warn_drop:
        status = "warn"
    else:
        status = "pass"
    return {
        "metric": metric,
        "status": status,
        "previous": round(previous, 4),
        "current": round(current, 4),
        "delta": delta,
    }


def _regression_count_floor_check(
    *,
    metric: str,
    current: int,
    previous: int,
) -> dict[str, Any]:
    delta = current - previous
    status = "warn" if previous > 0 and current < previous else "pass"
    return {
        "metric": metric,
        "status": status,
        "previous": previous,
        "current": current,
        "delta": delta,
    }


def _regression_count_ceiling_check(
    *,
    metric: str,
    current: int,
    previous: int,
) -> dict[str, Any]:
    delta = current - previous
    status = "warn" if current > previous else "pass"
    return {
        "metric": metric,
        "status": status,
        "previous": previous,
        "current": current,
        "delta": delta,
    }


def _agent_eval_overall_status(
    gates: list[dict[str, Any]],
    regression: dict[str, Any],
) -> str:
    gate_statuses = {str(gate.get("status")) for gate in gates}
    regression_status = str(regression.get("status", "pass"))
    if "fail" in gate_statuses or regression_status == "fail":
        return "fail"
    if "warn" in gate_statuses or regression_status == "warn":
        return "warn"
    return "pass"


def _agent_eval_recommendations(
    *,
    metrics: dict[str, Any],
    gates: list[dict[str, Any]],
    regression: dict[str, Any],
    agent_error: str,
    evaluation_error: str,
) -> list[str]:
    recommendations: list[str] = []
    if agent_error:
        recommendations.append("Regenerate the Agent report so trust checks can verify fresh agent claims.")
    if _safe_int(metrics.get("agent_llm_fallback_count")) > 0:
        recommendations.append("Agent LLM calls fell back during analysis; use a faster model, async job fan-out, or shorter role prompts before trusting the Agent report.")
    if evaluation_error or not metrics.get("evaluation_available"):
        recommendations.append("Run golden-question evaluation to establish a measurable quality baseline.")
    if _safe_int(metrics.get("rag_indexed_chunks")) == 0:
        recommendations.append("Rebuild Hybrid RAG indexes before relying on retrieval or evidence QA.")
    if metrics.get("rag_stale"):
        recommendations.append("Hybrid RAG index is stale; rebuild it after archive regeneration.")
    if _safe_int(metrics.get("trust_unsupported_claims")) > 0:
        recommendations.append("Tighten agent prompts/tools so every claim cites entity, relation, or evidence IDs.")
    if _safe_int(metrics.get("mission_task_count")) == 0:
        recommendations.append("Run a ReAct architecture mission to populate task-level trace and verifier memory.")
    if _safe_int(metrics.get("mission_timeout_tasks")) > 0:
        recommendations.append("Increase ReAct mission timeout or reduce task count; at least one mission task timed out.")
    if _safe_int(metrics.get("mission_skipped_tasks")) > 0:
        recommendations.append("Inspect ReAct mission budget usage because some planned tasks were skipped.")
    if _safe_int(metrics.get("multimodal_images")) > 0 and _safe_int(metrics.get("multimodal_vision_supported")) == 0:
        recommendations.append("Enable the vision model path for image evidence so multimodal cards become grounded.")
    failed_or_warned = [
        str(gate.get("label"))
        for gate in gates
        if gate.get("status") in {"fail", "warn"}
    ]
    if failed_or_warned:
        recommendations.append("Review quality gates: " + "; ".join(failed_or_warned[:4]) + ".")
    if regression.get("status") in {"fail", "warn"}:
        recommendations.append("Inspect regression checks before accepting this archive version as better than the previous run.")
    if not recommendations:
        recommendations.append("Quality gates passed. Save this run as the current AgentEval baseline.")
    return _unique_preserve_order(recommendations, limit=8)


def _agent_memory_facts(
    draft: ProjectArchiveDraft,
    report: dict[str, Any],
    evaluation: ArchiveEvaluationReport | None,
    rag_status: dict[str, Any],
) -> list[dict[str, Any]]:
    now = datetime.now(UTC).isoformat()
    metrics = report.get("metrics", {})
    facts = [
        {
            "text": (
                f"Archive {draft.project_id} has {len(draft.entities)} entities, "
                f"{len(draft.relations)} relations, and {len(draft.evidence_cards)} evidence cards."
            ),
            "source": "agent_eval",
            "created_at": now,
            "metadata": {"run_id": report.get("id"), "kind": "archive_shape"},
        },
        {
            "text": f"Latest AgentEval status is {report.get('status')} for {draft.project_id}.",
            "source": "agent_eval",
            "created_at": now,
            "metadata": {"run_id": report.get("id"), "kind": "quality_status"},
        },
        {
            "text": (
                f"Hybrid RAG indexed {metrics.get('rag_indexed_chunks', 0)} of "
                f"{metrics.get('rag_candidate_chunks', 0)} candidate chunks."
            ),
            "source": "hybrid_rag",
            "created_at": now,
            "metadata": {"run_id": report.get("id"), "health": rag_status.get("health", "missing")},
        },
    ]
    if evaluation is not None:
        facts.append(
            {
                "text": (
                    f"Golden-question evaluation score is "
                    f"{evaluation.aggregate_metrics.get('case_score', 0.0):.4f}."
                ),
                "source": "archive_evaluation",
                "created_at": now,
                "metadata": {"run_id": report.get("id"), "questions": evaluation.golden_question_count},
            }
        )
    return facts


def _agent_memory_risks(
    report: dict[str, Any],
    trust_report: dict[str, Any],
    rag_status: dict[str, Any],
) -> list[dict[str, Any]]:
    now = datetime.now(UTC).isoformat()
    risks: list[dict[str, Any]] = []
    for gate in report.get("quality_gates", []):
        if gate.get("status") in {"fail", "warn"}:
            risks.append(
                {
                    "title": f"{gate.get('label')} is {gate.get('status')}",
                    "severity": "high" if gate.get("status") == "fail" else "medium",
                    "source": "agent_eval_gate",
                    "created_at": now,
                    "metadata": {"gate_id": gate.get("id"), "run_id": report.get("id")},
                }
            )
    trust_metrics = trust_report.get("metrics", {})
    if _safe_int(trust_metrics.get("unsupported_claims")) > 0:
        risks.append(
            {
                "title": "Agent report contains unsupported claims",
                "severity": "high",
                "source": "agent_trust",
                "created_at": now,
                "metadata": {"run_id": report.get("id"), "metrics": trust_metrics},
            }
        )
    if rag_status.get("stale") or rag_status.get("error"):
        risks.append(
            {
                "title": "Hybrid RAG index is stale or unavailable",
                "severity": "medium",
                "source": "hybrid_rag",
                "created_at": now,
                "metadata": {"run_id": report.get("id"), "health": rag_status.get("health")},
            }
        )
    return risks


def _agent_task_relation_ids(task: Any) -> list[str]:
    relation_ids = list(getattr(task, "relation_ids", []) or [])
    for finding in getattr(task, "findings", []) or []:
        if not isinstance(finding, dict):
            continue
        relation_ids.extend(str(item) for item in finding.get("relation_ids", []) if item)
    return _unique_preserve_order([str(item) for item in relation_ids if item], limit=80)


def _dedupe_memory_items(
    items: list[Any],
    *,
    key: str,
    limit: int,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = str(item.get(key, "")).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(dict(item))
        if len(deduped) >= limit:
            break
    return deduped


def _hybrid_status_with_health(
    *,
    status: dict[str, Any],
    draft: ProjectArchiveDraft,
    draft_path: Path,
    status_path: Path,
) -> dict[str, Any]:
    candidate_chunks = _safe_int(status.get("candidate_chunks")) or (
        len(draft.evidence_cards) + len(draft.entities) + len(draft.relations)
    )
    indexed_chunks = _safe_int(status.get("indexed_chunks"))
    coverage_ratio = indexed_chunks / candidate_chunks if candidate_chunks else 0.0
    status_mtime = status_path.stat().st_mtime if status_path.exists() else 0.0
    draft_mtime = draft_path.stat().st_mtime if draft_path.exists() else 0.0
    stale = status_mtime < draft_mtime
    warnings: list[str] = []
    if stale:
        warnings.append("Hybrid RAG index is older than draft_archive.json.")
    if candidate_chunks and coverage_ratio < 0.05:
        warnings.append("Hybrid RAG coverage is very low for this archive.")
    return {
        **status,
        "candidate_chunks": candidate_chunks,
        "coverage_ratio": round(coverage_ratio, 4),
        "coverage_percent": round(coverage_ratio * 100, 2),
        "stale": stale,
        "health": "warning" if warnings else "working",
        "health_warnings": warnings,
    }


def _system_llm_component(settings: Any, agent_status: dict[str, Any]) -> dict[str, Any]:
    llm = settings.llm
    provider = str(getattr(llm, "provider", "unknown"))
    key_present = _credential_present(
        getattr(llm, "api_key", None),
        _env_for_provider(provider),
    )
    configured = provider == "ollama" or key_present or bool(getattr(llm, "base_url", None))
    working = bool(agent_status.get("llm_enabled"))
    warnings: list[str] = []
    if not configured:
        warnings.append("LLM provider is selected, but no usable credential or local endpoint was detected.")
    if configured and not working:
        warnings.append("LLM is configured, but the project Agent is currently using deterministic fallback.")
    return _system_component(
        component_id="llm",
        label="LLM",
        provider=provider,
        model=getattr(llm, "model", None),
        configured=configured,
        working=working,
        details={
            "api_key_present": key_present,
            "base_url_present": bool(getattr(llm, "base_url", None)),
            "mode": agent_status.get("mode"),
        },
        warnings=warnings,
    )


def _system_embedding_component(settings: Any, latest_rag_status: dict[str, Any] | None) -> dict[str, Any]:
    embedding = settings.embedding
    provider = str(getattr(embedding, "provider", "unknown"))
    key_present = _credential_present(
        getattr(embedding, "api_key", None),
        _env_for_provider(provider, prefix="embedding"),
    )
    configured = provider == "ollama" or key_present or bool(getattr(embedding, "base_url", None))
    dense_provider = str((latest_rag_status or {}).get("dense_provider", ""))
    working = bool(latest_rag_status and _safe_int(latest_rag_status.get("indexed_chunks")) > 0)
    warnings: list[str] = []
    if not configured:
        warnings.append("Embedding provider is selected, but no usable credential or local endpoint was detected.")
    if dense_provider == "local_hash":
        warnings.append("Latest Hybrid RAG index used local_hash fallback embeddings.")
    if configured and not latest_rag_status:
        warnings.append("No Hybrid RAG index status exists yet; upload or regenerate an archive to verify embeddings.")
    return _system_component(
        component_id="embedding",
        label="Embedding",
        provider=provider,
        model=getattr(embedding, "model", None),
        configured=configured,
        working=working and dense_provider != "local_hash",
        details={
            "api_key_present": key_present,
            "base_url_present": bool(getattr(embedding, "base_url", None)),
            "configured_dimensions": getattr(embedding, "dimensions", None),
            "latest_dense_provider": dense_provider or None,
            "latest_dense_dimension": (latest_rag_status or {}).get("dense_dimension"),
        },
        warnings=warnings,
        last_success=_rag_last_success(latest_rag_status),
    )


def _system_vision_component(settings: Any, latest_rag_status: dict[str, Any] | None) -> dict[str, Any]:
    vision = getattr(settings, "vision_llm", None)
    if vision is None or not getattr(vision, "enabled", False):
        return _system_component(
            component_id="vision",
            label="Vision",
            provider=getattr(vision, "provider", "none") if vision else "none",
            model=getattr(vision, "model", None) if vision else None,
            configured=False,
            working=False,
            status="disabled",
            details={},
            warnings=["Vision LLM is disabled in settings."],
        )
    provider = str(getattr(vision, "provider", "unknown"))
    normalized_provider = provider.lower()
    key_present = _credential_present(
        getattr(vision, "api_key", None),
        _env_for_provider(provider, prefix="vision"),
    )
    base_url = str(getattr(vision, "base_url", "") or "").rstrip("/")
    model = getattr(vision, "model", None)
    ollama_status = (
        _ollama_model_status(base_url=base_url or "http://localhost:11434", model=str(model or ""))
        if normalized_provider == "ollama"
        else {"endpoint_reachable": None, "model_available": None, "available_models": []}
    )
    configured = normalized_provider == "ollama" or key_present or bool(base_url)
    latest_used_vision = bool((latest_rag_status or {}).get("vision_enabled"))
    latest_image_chunks = _safe_int((latest_rag_status or {}).get("image_chunks"))
    if normalized_provider == "ollama":
        working = bool(configured and ollama_status.get("endpoint_reachable") and ollama_status.get("model_available"))
    else:
        working = bool(configured)
    warnings: list[str] = []
    if not configured:
        warnings.append("Vision is enabled, but no usable credential or local endpoint was detected.")
    if normalized_provider == "ollama" and configured and not ollama_status.get("endpoint_reachable"):
        warnings.append(f"Ollama vision endpoint is not reachable: {base_url or 'http://localhost:11434'}.")
    if normalized_provider == "ollama" and configured and ollama_status.get("endpoint_reachable") and not ollama_status.get("model_available"):
        warnings.append(f"Configured Ollama vision model is not installed: {model}.")
    if configured and latest_rag_status and latest_image_chunks > 0 and not latest_used_vision:
        warnings.append("Latest archive has image chunks but did not successfully use vision; image evidence may be metadata fallback only.")
    if configured and not latest_rag_status:
        warnings.append("No archive with image/vision status has been generated yet.")
    if configured and latest_rag_status and latest_image_chunks == 0:
        warnings.append("Latest archive has no image chunks, so vision has not been exercised by archive ingestion yet.")
    latest_provider = (latest_rag_status or {}).get("vision_provider")
    if latest_provider in {"none", "", None}:
        latest_provider = None
    return _system_component(
        component_id="vision",
        label="Vision",
        provider=provider,
        model=model,
        configured=configured,
        working=working,
        details={
            "api_key_present": key_present,
            "api_key_required": normalized_provider != "ollama",
            "base_url_present": bool(base_url),
            "endpoint_reachable": ollama_status.get("endpoint_reachable"),
            "model_available": ollama_status.get("model_available"),
            "max_image_size": getattr(vision, "max_image_size", None),
            "latest_archive_used_vision": latest_used_vision,
            "latest_image_chunks": latest_image_chunks,
            "latest_vision_provider": latest_provider,
        },
        warnings=warnings,
        last_success=_rag_last_success(latest_rag_status) if latest_used_vision else None,
    )


def _system_graph_component(graph_status: dict[str, Any]) -> dict[str, Any]:
    provider = str(graph_status.get("provider") or "unknown")
    working = provider != "neo4j" or bool(graph_status.get("uri"))
    warnings = []
    if provider == "neo4j" and not graph_status.get("uri"):
        warnings.append("Neo4j provider is selected but no URI is configured.")
    return _system_component(
        component_id="graph_store",
        label="Graph Store",
        provider=provider,
        model=str(graph_status.get("mode") or ""),
        configured=True,
        working=working,
        details={
            "mode": graph_status.get("mode"),
            "database": graph_status.get("database"),
            "uri_present": bool(graph_status.get("uri")),
            "project_isolation": graph_status.get("project_isolation"),
        },
        warnings=warnings,
    )


def _system_vector_component(settings: Any, latest_rag_status: dict[str, Any] | None) -> dict[str, Any]:
    vector_store = settings.vector_store
    provider = str(getattr(vector_store, "provider", "unknown"))
    indexed_chunks = _safe_int((latest_rag_status or {}).get("indexed_chunks"))
    warnings = []
    if not latest_rag_status:
        warnings.append("No archive has built a vector index yet.")
    return _system_component(
        component_id="vector_store",
        label="Vector Store",
        provider=provider,
        model=getattr(vector_store, "collection_name", None),
        configured=bool(provider),
        working=indexed_chunks > 0,
        details={
            "persist_directory": getattr(vector_store, "persist_directory", None),
            "latest_collection": (latest_rag_status or {}).get("collection_name"),
            "latest_indexed_chunks": indexed_chunks,
        },
        warnings=warnings,
        last_success=_rag_last_success(latest_rag_status) if indexed_chunks > 0 else None,
    )


def _system_hybrid_retrieval_component(settings: Any, latest_rag_status: dict[str, Any] | None) -> dict[str, Any]:
    retrieval = settings.retrieval
    bm25_collection = (latest_rag_status or {}).get("bm25_collection")
    indexed_chunks = _safe_int((latest_rag_status or {}).get("indexed_chunks"))
    warnings = []
    if not latest_rag_status:
        warnings.append("No Hybrid RAG index status exists yet.")
    elif not bm25_collection:
        warnings.append("Latest Hybrid RAG status did not include a BM25 collection.")
    return _system_component(
        component_id="hybrid_rag",
        label="Hybrid RAG",
        provider="Chroma + BM25 + RRF",
        model=f"rrf_k={getattr(retrieval, 'rrf_k', '')}",
        configured=True,
        working=indexed_chunks > 0 and bool(bm25_collection),
        details={
            "dense_top_k": getattr(retrieval, "dense_top_k", None),
            "sparse_top_k": getattr(retrieval, "sparse_top_k", None),
            "fusion_top_k": getattr(retrieval, "fusion_top_k", None),
            "rrf_k": getattr(retrieval, "rrf_k", None),
            "latest_bm25_collection": bm25_collection,
            "latest_text_chunks": (latest_rag_status or {}).get("text_chunks"),
            "latest_image_chunks": (latest_rag_status or {}).get("image_chunks"),
        },
        warnings=warnings,
        last_success=_rag_last_success(latest_rag_status) if indexed_chunks > 0 else None,
    )


def _system_agent_component(agent_status: dict[str, Any]) -> dict[str, Any]:
    working = bool(agent_status.get("llm_enabled"))
    return _system_component(
        component_id="agent",
        label="Agent Runtime",
        provider=str(agent_status.get("provider") or "rules"),
        model=agent_status.get("model"),
        configured=True,
        working=True,
        status="working" if working else "warning",
        details={
            "mode": agent_status.get("mode"),
            "llm_enabled": agent_status.get("llm_enabled"),
        },
        warnings=[] if working else ["Agent runtime is available, but currently using deterministic rules instead of LLM enhancement."],
    )


def _system_component(
    *,
    component_id: str,
    label: str,
    provider: str,
    model: Any,
    configured: bool,
    working: bool,
    details: dict[str, Any],
    warnings: list[str],
    status: str | None = None,
    last_success: dict[str, Any] | None = None,
) -> dict[str, Any]:
    next_status = status or (
        "working" if working else "warning" if configured else "disabled"
    )
    return {
        "id": component_id,
        "label": label,
        "status": next_status,
        "provider": provider,
        "model": str(model) if model is not None else None,
        "configured": configured,
        "working": working,
        "details": details,
        "warnings": warnings,
        "last_success": last_success,
    }


def _system_overall_status(components: list[dict[str, Any]]) -> str:
    statuses = {str(component.get("status")) for component in components}
    if "error" in statuses:
        return "error"
    if "warning" in statuses:
        return "warning"
    if "disabled" in statuses:
        return "partial"
    return "working"


def _system_config_summary(overall: str, components: list[dict[str, Any]]) -> str:
    working = sum(1 for component in components if component.get("status") == "working")
    warning = sum(1 for component in components if component.get("status") == "warning")
    disabled = sum(1 for component in components if component.get("status") == "disabled")
    return (
        f"{working} component(s) working, {warning} need review, "
        f"{disabled} disabled. Overall status: {overall}."
    )


def _credential_present(config_value: Any, env_names: tuple[str, ...]) -> bool:
    candidates = [config_value, *(os.getenv(name) for name in env_names)]
    return any(_usable_secret(value) for value in candidates)


def _ollama_model_status(*, base_url: str, model: str) -> dict[str, Any]:
    endpoint = f"{base_url.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(endpoint, timeout=1.2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        return {
            "endpoint_reachable": False,
            "model_available": False,
            "available_models": [],
        }
    models = [
        str(item.get("name") or item.get("model") or "")
        for item in payload.get("models", [])
        if isinstance(item, dict)
    ]
    normalized_models = {_normalize_ollama_model_name(item) for item in models}
    normalized_target = _normalize_ollama_model_name(model)
    return {
        "endpoint_reachable": True,
        "model_available": bool(normalized_target and normalized_target in normalized_models),
        "available_models": models[:24],
    }


def _normalize_ollama_model_name(value: str) -> str:
    normalized = value.strip().lower()
    if normalized.endswith(":latest"):
        return normalized.removesuffix(":latest")
    return normalized


def _usable_secret(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    return not any(token in lowered for token in ("your_", "your-", "placeholder", "changeme"))


def _env_for_provider(provider: str, *, prefix: str = "llm") -> tuple[str, ...]:
    normalized = provider.lower()
    if normalized == "deepseek":
        return ("DEEPSEEK_API_KEY",)
    if normalized == "openai":
        return ("OPENAI_API_KEY",)
    if normalized == "azure":
        return ("AZURE_OPENAI_API_KEY",)
    if normalized == "ollama":
        return ()
    if prefix == "embedding":
        return ("OPENAI_API_KEY", "AZURE_OPENAI_API_KEY")
    if prefix == "vision":
        return ("OPENAI_API_KEY", "AZURE_OPENAI_API_KEY")
    return ()


def _rag_last_success(latest_rag_status: dict[str, Any] | None) -> dict[str, Any] | None:
    if not latest_rag_status:
        return None
    return {
        "project_id": latest_rag_status.get("project_id"),
        "created_at": latest_rag_status.get("created_at"),
        "indexed_chunks": latest_rag_status.get("indexed_chunks"),
    }


def _settings_path_text() -> str:
    return str(DEFAULT_SETTINGS_PATH)


def _evidence_modalities_for_ids(
    evidence_cards: list[EvidenceCard],
    evidence_ids: list[str],
) -> dict[str, int]:
    cards_by_id = {card.id: card for card in evidence_cards}
    counts: Counter[str] = Counter()
    for evidence_id in evidence_ids:
        card = cards_by_id.get(evidence_id)
        if card is None:
            continue
        counts[_evidence_modality(card)] += 1
    return dict(sorted(counts.items()))


def _cited_image_evidence_count(
    evidence_cards: list[EvidenceCard],
    evidence_ids: list[str],
) -> int:
    return _evidence_modalities_for_ids(evidence_cards, evidence_ids).get("image", 0)


def _evidence_modality(card: EvidenceCard) -> str:
    raw = str(card.metadata.get("modality") or card.source_type).lower()
    if raw == "image" or card.source_type == "image":
        return "image"
    if raw in {"config", "yaml", "toml", "json"} or card.source_type == "config":
        return "config"
    if raw in {"code", "python", "java", "typescript", "javascript", "go", "rust", "cpp"} or card.source_type == "code":
        return "code"
    return "text"


def _architecture_diff_summary(
    left_project_id: str,
    right_project_id: str,
    shared_clusters: list[ProjectUniverseCluster],
    shared_links: list[ProjectUniverseLink],
    only_left: list[ProjectUniverseEntityRef],
    only_right: list[ProjectUniverseEntityRef],
) -> str:
    return (
        f"{left_project_id} and {right_project_id} have "
        f"{len(shared_clusters)} shared concept cluster(s), {len(shared_links)} direct "
        f"cross-project link(s), {len(only_left)} prominent left-only entity refs, and "
        f"{len(only_right)} prominent right-only entity refs."
    )


def _universe_path_default_name(project_ids: list[str]) -> str:
    if len(project_ids) == 1:
        return f"Universe path for {project_ids[0]}"
    return f"Universe path across {len(project_ids)} projects"


def _universe_name_key(label: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "", label.lower())
    if len(normalized) < 4 or normalized in _UNIVERSE_STOP_KEYS:
        return ""
    return normalized


def _universe_path_key(source_path: str | None) -> str:
    if not source_path:
        return ""
    name = Path(source_path).name.lower()
    if not name or name in {"index.ts", "index.js", "__init__.py", "main.py"}:
        return ""
    stem = re.sub(r"[^a-z0-9]+", "", Path(name).stem)
    return stem if len(stem) >= 5 and stem not in _UNIVERSE_STOP_KEYS else ""


def _universe_tokens(label: str) -> list[str]:
    tokens = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|[0-9]+", label)
    normalized = []
    for token in tokens:
        item = token.lower()
        if len(item) >= 5 and item not in _UNIVERSE_STOP_KEYS:
            normalized.append(item)
    return _unique_preserve_order(normalized, limit=4)


def _universe_bucket_score(
    bucket_type: str,
    refs: list[ProjectUniverseEntityRef],
) -> float:
    base = {
        "shared_name": 0.96,
        "shared_path": 0.84,
        "shared_concept": 0.68,
    }.get(bucket_type, 0.5)
    project_bonus = min(0.08, max(0, len({ref.project_id for ref in refs}) - 2) * 0.02)
    degree_bonus = min(0.06, sum(ref.degree for ref in refs) / 180)
    return round(min(1.0, base + project_bonus + degree_bonus), 4)


def _universe_cluster_label(
    bucket_key: str,
    refs: list[ProjectUniverseEntityRef],
) -> str:
    labels = Counter(ref.label for ref in refs)
    label = labels.most_common(1)[0][0] if labels else bucket_key
    return label or bucket_key


def _universe_link_reason(bucket_type: str, bucket_key: str) -> str:
    if bucket_type == "shared_name":
        return f"Shared normalized entity name: {bucket_key}"
    if bucket_type == "shared_path":
        return f"Shared source filename or module stem: {bucket_key}"
    if bucket_type == "shared_concept":
        return f"Shared concept token: {bucket_key}"
    return f"Shared signal: {bucket_key}"


_UNIVERSE_STOP_KEYS = {
    "config",
    "configuration",
    "default",
    "example",
    "index",
    "main",
    "readme",
    "service",
    "test",
    "tests",
    "utils",
}


def _stable_eval_id(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-._")[:48]
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]
    return f"{slug or 'item'}:{digest}"


def _unique_preserve_order(values: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        item = str(value)
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
        if len(normalized) >= limit:
            break
    return normalized


def _hit_rate(expected_ids: list[str], matched_ids: list[str]) -> float:
    expected = {item for item in expected_ids if item}
    if not expected:
        return 1.0
    matched = {item for item in matched_ids if item}
    return round(len(expected & matched) / len(expected), 4)


def _soft_entity_hit_rate(
    expected_ids: list[str],
    matched_ids: list[str],
    *,
    entity_lookup: dict[str, Any],
    relations_by_entity: dict[str, list],
) -> float:
    expected = [item for item in expected_ids if item]
    if not expected:
        return 1.0
    matched = {item for item in matched_ids if item}
    score = 0.0
    for entity_id in expected:
        if entity_id in matched:
            score += 1.0
            continue
        expected_entity = entity_lookup.get(entity_id)
        expected_path = getattr(expected_entity, "source_path", None)
        neighbors = {
            relation.source_id if relation.target_id == entity_id else relation.target_id
            for relation in relations_by_entity.get(entity_id, [])
        }
        if neighbors & matched:
            score += 0.5
            continue
        if expected_path and any(
            getattr(entity_lookup.get(matched_id), "source_path", None) == expected_path
            for matched_id in matched
        ):
            score += 0.35
    return round(score / len(expected), 4)


def _soft_relation_hit_rate(
    expected_ids: list[str],
    matched_ids: list[str],
    *,
    relation_lookup: dict[str, Any],
) -> float:
    expected = [item for item in expected_ids if item]
    if not expected:
        return 1.0
    matched = {item for item in matched_ids if item}
    matched_relations = [relation_lookup[item] for item in matched if item in relation_lookup]
    score = 0.0
    for relation_id in expected:
        if relation_id in matched:
            score += 1.0
            continue
        relation = relation_lookup.get(relation_id)
        if relation and any(
            relation.source_id in {candidate.source_id, candidate.target_id}
            or relation.target_id in {candidate.source_id, candidate.target_id}
            for candidate in matched_relations
        ):
            score += 0.55
    return round(score / len(expected), 4)


def _soft_evidence_hit_rate(
    expected_ids: list[str],
    matched_ids: list[str],
    *,
    evidence_lookup: dict[str, EvidenceCard],
) -> float:
    expected = [item for item in expected_ids if item]
    if not expected:
        return 1.0
    matched = {item for item in matched_ids if item}
    matched_paths = {
        evidence_lookup[item].source_path
        for item in matched
        if item in evidence_lookup and evidence_lookup[item].source_path
    }
    score = 0.0
    for evidence_id in expected:
        if evidence_id in matched:
            score += 1.0
            continue
        evidence = evidence_lookup.get(evidence_id)
        if evidence and evidence.source_path in matched_paths:
            score += 0.5
    return round(score / len(expected), 4)


def _aggregate_evaluation_metrics(
    case_results: list[ArchiveEvaluationCaseResult],
    *,
    total_entities: int,
    total_relations: int,
    total_evidence: int,
) -> dict[str, float]:
    if not case_results:
        return {
            "entity_hit_rate": 0.0,
            "relation_hit_rate": 0.0,
            "evidence_hit_rate": 0.0,
            "case_score": 0.0,
            "graph_coverage": 0.0,
            "evidence_coverage": 0.0,
            "answer_confidence_avg": 0.0,
        }

    unique_entities = {
        entity_id for case in case_results for entity_id in case.matched_entity_ids
    }
    unique_relations = {
        relation_id for case in case_results for relation_id in case.matched_relation_ids
    }
    unique_evidence = {
        evidence_id for case in case_results for evidence_id in case.matched_evidence_ids
    }
    return {
        "entity_hit_rate": _average_metric(case_results, "entity_hit_rate"),
        "relation_hit_rate": _average_metric(case_results, "relation_hit_rate"),
        "evidence_hit_rate": _average_metric(case_results, "evidence_hit_rate"),
        "case_score": _average_metric(case_results, "case_score"),
        "graph_coverage": round(
            (
                (len(unique_entities) / total_entities if total_entities else 0.0)
                + (len(unique_relations) / total_relations if total_relations else 0.0)
            )
            / 2,
            4,
        ),
        "evidence_coverage": round(
            len(unique_evidence) / total_evidence if total_evidence else 0.0,
            4,
        ),
        "answer_confidence_avg": _average_metric(case_results, "case_score"),
    }


def _average_metric(
    case_results: list[ArchiveEvaluationCaseResult],
    metric_name: str,
) -> float:
    values = [case.metrics.get(metric_name, 0.0) for case in case_results]
    return round(sum(values) / len(values), 4) if values else 0.0


def _is_eval_entity_candidate(entity: Any) -> bool:
    name = str(getattr(entity, "name", "") or "").strip()
    if len(name) < 3:
        return False
    if name.lower() in {
        "com",
        "org",
        "net",
        "java",
        "src",
        "main",
        "test",
        "api",
        "data",
        "service",
        "controller",
        "config",
        "criteria",
        "criterion",
        "generatedcriteria",
    }:
        return False
    source_path = str(getattr(entity, "source_path", "") or "").lower()
    if source_path.endswith("example.java") and name.lower() in {
        "generatedcriteria",
        "criteria",
        "criterion",
    }:
        return False
    entity_type = str(getattr(entity, "type", "") or "").lower()
    if entity_type in {"import", "concept"} and not getattr(entity, "source_path", None):
        return False
    return entity_type in {
        "class",
        "function",
        "interface",
        "struct",
        "enum",
        "config",
        "file",
        "module",
        "concept",
    }


def _eval_entity_type_priority(entity: Any) -> int:
    entity_type = str(getattr(entity, "type", "") or "").lower()
    return {
        "class": 9,
        "interface": 9,
        "function": 8,
        "config": 8,
        "file": 7,
        "module": 7,
        "struct": 7,
        "enum": 6,
        "concept": 3,
    }.get(entity_type, 1)


def _eval_entity_path_priority(entity: Any) -> int:
    source_path = str(getattr(entity, "source_path", "") or "").lower()
    if any(marker in source_path for marker in ("controller", "service", "config", "security")):
        return 9
    if any(marker in source_path for marker in ("mapper", "repository", "dao")):
        return 7
    if any(marker in source_path for marker in ("application", "bootstrap", "pom.xml", "build.gradle")):
        return 6
    if "/model/" in source_path or source_path.endswith("model.java"):
        return 3
    return 4


def _evaluation_case_summary(
    metrics: dict[str, float],
    rag_metadata: dict[str, Any],
) -> str:
    rag_count = int(rag_metadata.get("result_count", 0) or 0)
    return (
        "Matched "
        f"{round(metrics.get('case_score', 0.0) * 100)}% of expected graph/evidence "
        f"signals; Hybrid RAG returned {rag_count} chunk(s)."
    )
