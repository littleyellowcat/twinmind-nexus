"""FastAPI app for TwinMind Archive frontend integration."""

from __future__ import annotations

import re
import json
import shutil
import threading
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Annotated, Any
from zipfile import BadZipFile, ZipFile

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field

from src.project_archive.autonomous_mission import ARCHITECTURE_GOAL
from src.project_archive.scanner import (
    SCAN_PROFILE_ARCHITECTURE,
    ignore_prefixes_for_profile,
    include_prefixes_for_profile,
    normalize_scan_profile,
)
from src.project_archive.service import (
    TERMINAL_AGENT_MISSION_STATUSES,
    ProjectArchiveService,
)
from src.project_archive.types import GraphMergeCandidate, QueryMode

DEFAULT_ARCHIVE_STORAGE_DIR = Path("data/project_archive")
MAX_UPLOAD_BYTES = 512 * 1024 * 1024
MAX_MEMBER_BYTES = 1_000_000
MAX_IMAGE_MEMBER_BYTES = 6 * 1024 * 1024
AGENT_REPORT_JOB_STALE_SECONDS = 45 * 60
MAX_UNIVERSE_PROJECT_IDS = 50
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
TEXT_SUFFIXES = {
    ".c",
    ".cc",
    ".cfg",
    ".conf",
    ".cpp",
    ".cs",
    ".css",
    ".env",
    ".go",
    ".gradle",
    ".h",
    ".hpp",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".lock",
    ".md",
    ".mjs",
    ".php",
    ".properties",
    ".py",
    ".rb",
    ".rs",
    ".rst",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
TEXT_FILENAMES = {
    ".env",
    ".gitignore",
    "dockerfile",
    "makefile",
    "readme",
}
IGNORED_PARTS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".venv",
    "__MACOSX",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
    "vendor",
}


class ArchiveQueryRequest(BaseModel):
    question: str = Field(min_length=1)
    mode: QueryMode = QueryMode.EVIDENCE_QA
    hall_id: str | None = None


class MissionStartRequest(BaseModel):
    goal: str = ARCHITECTURE_GOAL
    max_steps: int = Field(default=12, ge=1, le=12)


class AgentMissionStartRequest(BaseModel):
    goal: str = Field(default="Understand project architecture", min_length=1)
    max_tasks: int = Field(default=5, ge=1, le=8)
    max_steps_per_task: int = Field(default=4, ge=1, le=8)


class GraphMergeCandidateRequest(BaseModel):
    id: str = Field(min_length=1, max_length=512)
    label: str = Field(default="", max_length=512)
    entity_ids: list[str] = Field(default_factory=list, max_length=20)
    created_at: str = Field(default="", max_length=80)


class GraphCurationRequest(BaseModel):
    important_entity_ids: list[str] = Field(default_factory=list, max_length=500)
    hidden_relation_ids: list[str] = Field(default_factory=list, max_length=500)
    merge_candidates: list[GraphMergeCandidateRequest] = Field(
        default_factory=list,
        max_length=100,
    )


class UniversePathRequest(BaseModel):
    name: str = Field(default="", max_length=160)
    project_ids: list[str] = Field(default_factory=list, max_length=MAX_UNIVERSE_PROJECT_IDS)
    cluster_ids: list[str] = Field(default_factory=list, max_length=24)
    link_ids: list[str] = Field(default_factory=list, max_length=80)
    notes: str = Field(default="", max_length=1200)


class UniverseAgentTasksRequest(BaseModel):
    project_ids: list[str] = Field(default_factory=list, max_length=MAX_UNIVERSE_PROJECT_IDS)
    max_tasks: int = Field(default=6, ge=1, le=12)


class UniverseCompareRequest(BaseModel):
    left_project_id: str = Field(min_length=1, max_length=160)
    right_project_id: str = Field(min_length=1, max_length=160)


class StressTestRunRequest(BaseModel):
    project_ids: list[str] = Field(default_factory=list, max_length=50)
    run_evaluation: bool = False
    evaluation_limit: int = Field(default=6, ge=1, le=20)


class AgentEvalRunRequest(BaseModel):
    run_evaluation: bool = False
    evaluation_limit: int = Field(default=8, ge=1, le=30)
    run_agent_report: bool = False
    agent_llm_mode: str = Field(default="fast", max_length=20)


class HarnessPolicyCheckRequest(BaseModel):
    action: str = Field(default="read_only", min_length=1, max_length=80)
    resource: str = Field(default="archive", max_length=240)


class HarnessCommandDryRunRequest(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)


@dataclass
class ArchiveJob:
    id: str
    kind: str
    status: str = "queued"
    progress: int = 1
    message: str = "Queued"
    project_id: str | None = None
    result: dict | None = None
    error: str | None = None
    steps: list[dict[str, str | int]] = field(default_factory=list)
    cancel_requested: bool = False
    retry_count: int = 0
    retry_of: str | None = None
    created_at: str = field(default_factory=lambda: _utc_now())
    updated_at: str = field(default_factory=lambda: _utc_now())

    def to_dict(self, *, include_result: bool = True) -> dict:
        payload = asdict(self)
        if not include_result:
            payload.pop("result", None)
        return payload


_JOBS: dict[str, ArchiveJob] = {}
_JOBS_LOCK = threading.Lock()


def get_project_archive_service() -> ProjectArchiveService:
    return ProjectArchiveService(storage_dir=DEFAULT_ARCHIVE_STORAGE_DIR)


ServiceDep = Annotated[ProjectArchiveService, Depends(get_project_archive_service)]


def create_app() -> FastAPI:
    app = FastAPI(title="TwinMind Archive API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_origin_regex=r"^http://(127\.0\.0\.1|localhost):\d+$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/agent/status")
    def agent_status(service: ServiceDep) -> dict[str, str | bool | None]:
        return service.agent_status()

    @app.get("/api/graph-store/status")
    def graph_store_status(service: ServiceDep) -> dict[str, str | bool | None]:
        return service.graph_store_status()

    @app.get("/api/harness/capabilities")
    def harness_capabilities(service: ServiceDep) -> dict:
        return service.harness_capabilities()

    @app.get("/api/harness/policy")
    def harness_policy(service: ServiceDep) -> dict:
        return service.harness_policy()

    @app.get("/api/harness/agent-profiles")
    def harness_agent_profiles(service: ServiceDep) -> dict:
        return service.harness_agent_profiles()

    @app.get("/api/harness/commands")
    def harness_commands(service: ServiceDep) -> dict:
        return service.harness_commands()

    @app.post("/api/harness/commands/{command_id}/dry-run")
    def harness_command_dry_run(
        command_id: str,
        request: HarnessCommandDryRunRequest,
        service: ServiceDep,
    ) -> dict:
        try:
            return service.harness_command_dry_run(
                command_id,
                parameters=request.parameters,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/harness/policy-check")
    def harness_policy_check(
        request: HarnessPolicyCheckRequest,
        service: ServiceDep,
    ) -> dict:
        return service.harness_policy_check(
            action=request.action,
            resource=request.resource,
        )

    @app.get("/api/system/config-check")
    def system_config_check(service: ServiceDep) -> dict:
        return service.system_config_check()

    @app.get("/api/archives")
    def list_archives(service: ServiceDep) -> dict[str, list[str]]:
        return {"archives": service.list_project_ids()}

    @app.get("/api/universe")
    def get_knowledge_universe(
        service: ServiceDep,
        project_ids: Annotated[list[str] | None, Query()] = None,
        link_limit: int = 80,
        cluster_limit: int = 24,
    ) -> dict:
        try:
            return service.build_knowledge_universe(
                project_ids=project_ids,
                link_limit=max(0, min(link_limit, 300)),
                cluster_limit=max(0, min(cluster_limit, 120)),
            ).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/universe/paths")
    def get_universe_paths(service: ServiceDep) -> dict:
        return {
            "paths": [path.to_dict() for path in service.list_universe_paths()],
        }

    @app.post("/api/universe/paths")
    def save_universe_path(
        request: UniversePathRequest,
        service: ServiceDep,
    ) -> dict:
        try:
            return service.save_universe_path(
                name=request.name,
                project_ids=request.project_ids,
                cluster_ids=request.cluster_ids,
                link_ids=request.link_ids,
                notes=request.notes,
            ).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/universe/agent-tasks")
    def get_universe_agent_tasks(service: ServiceDep) -> dict:
        return {
            "tasks": [task.to_dict() for task in service.list_universe_agent_tasks()],
        }

    @app.post("/api/universe/agent-tasks/run")
    def run_universe_agent_tasks(
        request: UniverseAgentTasksRequest,
        service: ServiceDep,
    ) -> dict:
        try:
            tasks = service.run_universe_agent_tasks(
                project_ids=request.project_ids or None,
                max_tasks=request.max_tasks,
            )
            return {"tasks": [task.to_dict() for task in tasks]}
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/universe/compare")
    def compare_universe_projects(
        request: UniverseCompareRequest,
        service: ServiceDep,
    ) -> dict:
        if request.left_project_id == request.right_project_id:
            raise HTTPException(
                status_code=400,
                detail="Choose two different project archives.",
            )
        try:
            return service.compare_project_architecture(
                request.left_project_id,
                request.right_project_id,
            ).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        job = _get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        return job.to_dict()

    @app.get("/api/jobs")
    def list_jobs(project_id: str | None = None, limit: int = 40) -> dict:
        return {
            "jobs": [
                job.to_dict(include_result=False)
                for job in _list_jobs(project_id, limit=limit)
            ]
        }

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict:
        job = _get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        if job.status in {"complete", "failed", "cancelled"}:
            return job.to_dict()
        _update_job(
            job_id,
            status="cancelled" if job.status == "queued" else None,
            progress=job.progress,
            message="Cancellation requested.",
            cancel_requested=True,
        )
        return _get_job(job_id).to_dict()

    @app.post("/api/archives/upload-job", status_code=202)
    async def upload_archive_job(
        background_tasks: BackgroundTasks,
        service: ServiceDep,
        file: UploadFile = File(...),
        project_id: str = Form(""),
        scan_profile: str = Form(SCAN_PROFILE_ARCHITECTURE),
    ) -> dict:
        if not file.filename or not file.filename.lower().endswith(".zip"):
            raise HTTPException(status_code=400, detail="Please upload a .zip file.")

        normalized_scan_profile = normalize_scan_profile(scan_profile)
        payload = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(payload) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Project ZIP is too large.")

        archive_id = _project_id_from_upload(project_id, file.filename)
        job = _create_job(
            kind="archive_upload",
            project_id=archive_id,
            message="Project ZIP received.",
        )
        background_tasks.add_task(
            _run_upload_job,
            job.id,
            service,
            payload,
            archive_id,
            normalized_scan_profile,
        )
        return job.to_dict()

    @app.post("/api/archives/upload")
    async def upload_archive(
        service: ServiceDep,
        file: UploadFile = File(...),
        project_id: str = Form(""),
        scan_profile: str = Form(SCAN_PROFILE_ARCHITECTURE),
    ) -> dict:
        if not file.filename or not file.filename.lower().endswith(".zip"):
            raise HTTPException(status_code=400, detail="Please upload a .zip file.")

        normalized_scan_profile = normalize_scan_profile(scan_profile)
        payload = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(payload) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Project ZIP is too large.")

        archive_id = _project_id_from_upload(project_id, file.filename)
        try:
            with TemporaryDirectory(prefix="twinmind-upload-") as tmpdir:
                project_root = _extract_project_zip(
                    payload,
                    Path(tmpdir),
                    scan_profile=normalized_scan_profile,
                )
                draft = service.ingest_project(
                    project_root=project_root,
                    project_id=archive_id,
                    scan_profile=normalized_scan_profile,
                )
        except BadZipFile as exc:
            raise HTTPException(status_code=400, detail="Invalid ZIP archive.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return {
            "project_id": draft.project_id,
            "metrics": {
                "halls": len(draft.halls),
                "entities": len(draft.entities),
                "relations": len(draft.relations),
                "evidence": len(draft.evidence_cards),
            },
            "archive": draft.to_dict(),
        }

    @app.get("/api/archives/{project_id}")
    def get_archive(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.load_draft(project_id).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/graph")
    def get_graph_summary(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.graph_summary(project_id).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/rag-status")
    def get_hybrid_rag_status(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.hybrid_rag_status(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/archives/{project_id}/rag-status/rebuild-job", status_code=202)
    def rebuild_hybrid_rag_job(
        project_id: str,
        background_tasks: BackgroundTasks,
        service: ServiceDep,
    ) -> dict:
        try:
            service.load_draft(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        existing_job = _find_active_job(kind="hybrid_rag_rebuild", project_id=project_id)
        if existing_job is not None:
            return existing_job.to_dict()

        job = _create_job(
            kind="hybrid_rag_rebuild",
            project_id=project_id,
            message="Hybrid RAG rebuild queued.",
        )
        background_tasks.add_task(
            _run_hybrid_rag_rebuild_job,
            job.id,
            service,
            project_id,
        )
        return job.to_dict()

    @app.get("/api/archives/{project_id}/diagnostics")
    def get_ingestion_diagnostics(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.ingestion_diagnostics(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/harness/events")
    def get_harness_events(
        project_id: str,
        service: ServiceDep,
        event_type: str | None = None,
        limit: int = 200,
    ) -> dict:
        try:
            return service.list_harness_events(
                project_id,
                event_type=event_type,
                limit=limit,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/harness/summary")
    def get_harness_summary(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.harness_run_summary(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/harness/timeline")
    def get_harness_timeline(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.harness_timeline(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/harness/export")
    def get_harness_export(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.harness_export(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/harness/artifacts")
    def get_harness_artifact_manifest(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.harness_artifact_manifest(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/harness/artifacts/validation")
    def get_harness_artifact_validation(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.harness_artifact_validation(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/archives/{project_id}/harness/artifacts/cleanup-dry-run")
    def harness_artifact_cleanup_dry_run(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.harness_artifact_cleanup_dry_run(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/evidence-assets/{asset_id}")
    def get_evidence_asset(
        project_id: str,
        asset_id: str,
        service: ServiceDep,
    ) -> FileResponse:
        try:
            path = service.load_evidence_asset(project_id, asset_id)
            return FileResponse(path)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/graph/neighborhood")
    def get_graph_neighborhood(
        project_id: str,
        service: ServiceDep,
        hall_id: str | None = None,
        focus_entity_id: str | None = None,
        depth: int = 1,
        relation_types: Annotated[list[str] | None, Query()] = None,
        node_limit: int = 80,
        relation_limit: int = 120,
    ) -> dict:
        try:
            return service.graph_neighborhood(
                project_id,
                hall_id=hall_id,
                focus_entity_id=focus_entity_id,
                depth=depth,
                relation_types=relation_types,
                node_limit=node_limit,
                relation_limit=relation_limit,
            ).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/graph/search")
    def search_graph_entities(
        project_id: str,
        service: ServiceDep,
        q: str = "",
        limit: int = 20,
    ) -> dict:
        try:
            results = service.search_graph_entities(
                project_id,
                query=q,
                limit=limit,
            )
            return {"results": [result.to_dict() for result in results]}
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/graph/workspace")
    def get_graph_workspace_report(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.graph_workspace_report(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/graph-curation")
    def get_graph_curation(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.load_graph_curation(project_id).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/archives/{project_id}/graph-curation/apply-suggestions")
    def apply_graph_curation_suggestions(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.apply_graph_curation_suggestions(project_id).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/agent-trust")
    def get_agent_trust_report(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.agent_trust_report(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/multimodal")
    def get_multimodal_insights(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.multimodal_insights(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/evaluation")
    def get_archive_evaluation(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.load_evaluation_report(project_id).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/evaluation/history")
    def get_evaluation_history(
        service: ServiceDep,
        project_id: str | None = None,
    ) -> dict:
        try:
            return service.list_evaluation_history(project_id=project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/versions")
    def get_version_history(service: ServiceDep) -> dict:
        return service.list_version_history()

    @app.get("/api/archives/{project_id}/versions")
    def get_project_version_history(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.list_version_history(project_id=project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/stress-test/latest")
    def get_stress_test_report(service: ServiceDep) -> dict:
        try:
            return service.load_stress_test_report()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/stress-test/run")
    def run_stress_test(
        request: StressTestRunRequest,
        service: ServiceDep,
    ) -> dict:
        try:
            return service.run_stress_test(
                project_ids=request.project_ids or None,
                run_evaluation=request.run_evaluation,
                evaluation_limit=request.evaluation_limit,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/evaluation/golden-questions")
    def get_archive_golden_questions(
        project_id: str,
        service: ServiceDep,
        limit: int = 8,
    ) -> dict:
        try:
            questions = service.generate_golden_questions(project_id, limit=limit)
            return {"questions": [question.to_dict() for question in questions]}
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/archives/{project_id}/evaluation/run")
    def run_archive_evaluation(
        project_id: str,
        service: ServiceDep,
        limit: int = 8,
    ) -> dict:
        try:
            return service.run_archive_evaluation(project_id, limit=limit).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.put("/api/archives/{project_id}/graph-curation")
    def put_graph_curation(
        project_id: str,
        request: GraphCurationRequest,
        service: ServiceDep,
    ) -> dict:
        try:
            return service.save_graph_curation(
                project_id,
                important_entity_ids=request.important_entity_ids,
                hidden_relation_ids=request.hidden_relation_ids,
                merge_candidates=[
                    GraphMergeCandidate(
                        id=candidate.id,
                        label=candidate.label,
                        entity_ids=candidate.entity_ids,
                        created_at=candidate.created_at,
                    )
                    for candidate in request.merge_candidates
                ],
            ).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/archives/{project_id}/missions", status_code=202)
    def start_mission(
        project_id: str,
        request: MissionStartRequest,
        service: ServiceDep,
    ) -> dict:
        if request.goal != ARCHITECTURE_GOAL:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported mission goal: {request.goal}",
            )
        try:
            return service.start_architecture_mission(
                project_id,
                max_steps=request.max_steps,
            ).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/missions/{mission_id}")
    def get_mission(mission_id: str, service: ServiceDep) -> dict:
        try:
            return service.load_mission(mission_id).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/missions/{mission_id}/tasks")
    def get_mission_tasks(mission_id: str, service: ServiceDep) -> dict:
        try:
            mission = service.load_mission(mission_id)
            return {
                "mission_id": mission.id,
                "tasks": [task.to_dict() for task in mission.tasks],
            }
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/missions/{mission_id}/graph-overlay")
    def get_mission_graph_overlay(mission_id: str, service: ServiceDep) -> dict:
        try:
            mission = service.load_mission(mission_id)
            if mission.graph_overlay is None:
                return {
                    "mission_id": mission.id,
                    "explored_node_ids": [],
                    "explored_relation_ids": [],
                    "risk_node_ids": [],
                    "risk_relation_ids": [],
                    "annotations": [],
                }
            return mission.graph_overlay.to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/missions/{mission_id}/pause")
    def pause_mission(mission_id: str, service: ServiceDep) -> dict:
        try:
            return service.update_mission_status(mission_id, "paused").to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/missions/{mission_id}/resume")
    def resume_mission(mission_id: str, service: ServiceDep) -> dict:
        try:
            return service.update_mission_status(mission_id, "complete").to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/missions/{mission_id}/stop")
    def stop_mission(mission_id: str, service: ServiceDep) -> dict:
        try:
            return service.update_mission_status(mission_id, "stopped").to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/archives/{project_id}/agent-missions", status_code=202)
    def start_agent_mission(
        project_id: str,
        request: AgentMissionStartRequest,
        background_tasks: BackgroundTasks,
        service: ServiceDep,
    ) -> dict:
        try:
            mission = service.create_agent_mission(
                project_id=project_id,
                goal=request.goal,
                max_tasks=request.max_tasks,
                max_steps_per_task=request.max_steps_per_task,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        background_tasks.add_task(_run_agent_mission_background, service, mission.id)
        return mission.to_dict()

    @app.get("/api/agent-missions/{mission_id}")
    def get_agent_mission(mission_id: str, service: ServiceDep) -> dict:
        try:
            return service.load_agent_mission(mission_id).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/agent-missions/{mission_id}/trace")
    def get_agent_mission_trace(mission_id: str, service: ServiceDep) -> dict:
        try:
            trace_events = service.agent_mission_trace(mission_id)
            return {
                "mission_id": mission_id,
                "trace_events": [event.to_dict() for event in trace_events],
            }
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/agent-missions/{mission_id}/trace-artifact")
    def get_agent_mission_trace_artifact(mission_id: str, service: ServiceDep) -> dict:
        try:
            return service.agent_mission_trace_artifact(mission_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/agent-missions/{mission_id}/visualization")
    def get_agent_mission_visualization(mission_id: str, service: ServiceDep) -> dict:
        try:
            return service.agent_mission_visualization(mission_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/agent-missions/{mission_id}/pause")
    def pause_agent_mission(mission_id: str, service: ServiceDep) -> dict:
        try:
            service.load_agent_mission(mission_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(
            status_code=409,
            detail="Agent mission pause is not supported yet.",
        )

    @app.post("/api/agent-missions/{mission_id}/resume")
    def resume_agent_mission(mission_id: str, service: ServiceDep) -> dict:
        try:
            service.load_agent_mission(mission_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(
            status_code=409,
            detail="Agent mission resume is not supported yet.",
        )

    @app.post("/api/agent-missions/{mission_id}/stop")
    def stop_agent_mission(mission_id: str, service: ServiceDep) -> dict:
        try:
            mission = service.load_agent_mission(mission_id)
            if mission.status in TERMINAL_AGENT_MISSION_STATUSES:
                return mission.to_dict()
            return service.update_agent_mission_status(mission_id, "stopped").to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/archives/{project_id}/query")
    def query_archive(
        project_id: str,
        request: ArchiveQueryRequest,
        service: ServiceDep,
    ) -> dict:
        try:
            return service.query_project(
                project_id=project_id,
                question=request.question,
                mode=request.mode,
                hall_id=request.hall_id,
            ).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/agent-report")
    def get_agent_report(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.load_agent_report(project_id).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/agent-eval")
    def get_agent_eval_report(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.load_agent_eval_report(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/archives/{project_id}/agent-eval/run")
    def run_agent_eval_harness(
        project_id: str,
        request: AgentEvalRunRequest,
        service: ServiceDep,
    ) -> dict:
        try:
            return service.run_agent_eval_harness(
                project_id,
                run_evaluation=request.run_evaluation,
                evaluation_limit=request.evaluation_limit,
                run_agent_report=request.run_agent_report,
                agent_llm_mode=request.agent_llm_mode,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/agent-memory")
    def get_agent_memory(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.load_agent_memory(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/intelligence-report")
    def get_project_intelligence_report(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.load_project_intelligence_report(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/agent-task-plan")
    def get_project_agent_task_plan(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.agent_task_plan(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/archives/{project_id}/intelligence-report/run")
    def run_project_intelligence_report(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.generate_project_intelligence_report(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/intelligence-report/markdown")
    def get_project_intelligence_markdown(
        project_id: str,
        service: ServiceDep,
    ) -> PlainTextResponse:
        try:
            markdown = service.load_project_intelligence_markdown(project_id)
            return PlainTextResponse(
                markdown,
                media_type="text/markdown; charset=utf-8",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="{project_id}-intelligence-report.md"'
                    ),
                },
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/intelligence-report/pdf")
    def get_project_intelligence_pdf(
        project_id: str,
        service: ServiceDep,
    ) -> Response:
        try:
            payload = service.load_project_intelligence_pdf(project_id)
            return Response(
                payload,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="{project_id}-intelligence-report.pdf"'
                    ),
                },
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/archives/{project_id}/agent-report/run")
    def run_agent_report(
        project_id: str,
        service: ServiceDep,
        scan_profile: str = SCAN_PROFILE_ARCHITECTURE,
        llm_mode: str = "deep",
    ) -> dict:
        try:
            return service.run_agent_report(
                project_id=project_id,
                scan_profile=normalize_scan_profile(scan_profile),
                llm_mode=llm_mode,
            ).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/archives/{project_id}/agent-report/run-job", status_code=202)
    def run_agent_report_job(
        project_id: str,
        background_tasks: BackgroundTasks,
        service: ServiceDep,
        scan_profile: str = SCAN_PROFILE_ARCHITECTURE,
        llm_mode: str = "fast",
    ) -> dict:
        try:
            service.load_draft(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        existing_job = _find_active_job(kind="agent_report", project_id=project_id)
        if existing_job is not None:
            return existing_job.to_dict()

        job = _create_job(
            kind="agent_report",
            project_id=project_id,
            message="Agent analysis queued.",
        )
        background_tasks.add_task(
            _run_agent_report_job,
            job.id,
            service,
            project_id,
            normalize_scan_profile(scan_profile),
            llm_mode,
        )
        return job.to_dict()

    return app


app = create_app()


def _create_job(kind: str, project_id: str | None, message: str) -> ArchiveJob:
    job = ArchiveJob(
        id=uuid.uuid4().hex,
        kind=kind,
        project_id=project_id,
        message=message,
        steps=[{"progress": 1, "message": message}],
    )
    with _JOBS_LOCK:
        _JOBS[job.id] = job
    return job


def _get_job(job_id: str) -> ArchiveJob | None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is not None:
            _expire_stale_job_locked(job)
        return job


def _list_jobs(project_id: str | None, *, limit: int) -> list[ArchiveJob]:
    safe_limit = max(1, min(200, int(limit)))
    with _JOBS_LOCK:
        for job in _JOBS.values():
            _expire_stale_job_locked(job)
        jobs = [
            job
            for job in _JOBS.values()
            if project_id is None or job.project_id == project_id
        ]
    return sorted(jobs, key=lambda item: item.updated_at, reverse=True)[:safe_limit]


def _find_active_job(
    *,
    kind: str,
    project_id: str,
) -> ArchiveJob | None:
    with _JOBS_LOCK:
        candidates = [
            job
            for job in _JOBS.values()
            if job.kind == kind
            and job.project_id == project_id
            and job.status in {"queued", "running"}
        ]
        for job in candidates:
            _expire_stale_job_locked(job)
        active_jobs = [
            job
            for job in candidates
            if job.status in {"queued", "running"}
        ]
    return sorted(active_jobs, key=lambda item: item.updated_at, reverse=True)[0] if active_jobs else None


def _expire_stale_job_locked(job: ArchiveJob) -> None:
    if job.kind != "agent_report" or job.status not in {"queued", "running"}:
        return
    from datetime import UTC, datetime

    try:
        updated_at = datetime.fromisoformat(job.updated_at)
    except ValueError:
        return
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    age_seconds = (datetime.now(UTC) - updated_at).total_seconds()
    if age_seconds < AGENT_REPORT_JOB_STALE_SECONDS:
        return
    job.status = "failed"
    job.progress = 100
    job.message = "Agent analysis timed out. Please start a new run."
    job.error = "agent_report_job_timeout"
    job.updated_at = datetime.now(UTC).isoformat()
    job.steps.append({"progress": job.progress, "message": job.message})


def _job_cancel_requested(job_id: str) -> bool:
    with _JOBS_LOCK:
        return bool(_JOBS[job_id].cancel_requested)


def _update_job(
    job_id: str,
    *,
    status: str | None = None,
    progress: int | None = None,
    message: str | None = None,
    project_id: str | None = None,
    result: dict | None = None,
    error: str | None = None,
    cancel_requested: bool | None = None,
) -> None:
    with _JOBS_LOCK:
        job = _JOBS[job_id]
        if status is not None:
            job.status = status
        if progress is not None:
            job.progress = max(0, min(100, progress))
        if message is not None:
            job.message = message
        if project_id is not None:
            job.project_id = project_id
        if result is not None:
            job.result = result
        if error is not None:
            job.error = error
        if cancel_requested is not None:
            job.cancel_requested = cancel_requested
        job.updated_at = _utc_now()
        if message is not None or progress is not None:
            job.steps.append(
                {
                    "progress": job.progress,
                    "message": job.message,
                }
            )


def _run_upload_job(
    job_id: str,
    service: ProjectArchiveService,
    payload: bytes,
    archive_id: str,
    scan_profile: str,
) -> None:
    try:
        _update_job(job_id, status="running", progress=12, message="Extracting project ZIP.")
        if _job_cancel_requested(job_id):
            raise _ArchiveJobCancelled()
        with TemporaryDirectory(prefix="twinmind-upload-") as tmpdir:
            project_root = _extract_project_zip(payload, Path(tmpdir), scan_profile=scan_profile)
            _update_job(
                job_id,
                progress=38,
                message="Building graph, Hybrid RAG index, and image captions.",
            )

            def on_stage(stage: str, progress: int, message: str) -> None:
                if _job_cancel_requested(job_id):
                    raise _ArchiveJobCancelled()
                _update_job(
                    job_id,
                    progress=progress,
                    message=f"{stage}: {message}",
                )

            draft = service.ingest_project(
                project_root=project_root,
                project_id=archive_id,
                scan_profile=scan_profile,
                on_stage=on_stage,
            )
            if _job_cancel_requested(job_id):
                raise _ArchiveJobCancelled()
            _update_job(job_id, progress=84, message="Finalizing archive.")
        _update_job(
            job_id,
            status="complete",
            progress=100,
            message="Archive is ready. Run Agent analysis when needed.",
            project_id=draft.project_id,
            result={
                "project_id": draft.project_id,
                "metrics": {
                    "halls": len(draft.halls),
                    "entities": len(draft.entities),
                    "relations": len(draft.relations),
                    "evidence": len(draft.evidence_cards),
                },
            },
        )
    except _ArchiveJobCancelled:
        _update_job(
            job_id,
            status="cancelled",
            message="Archive generation cancelled.",
            error="cancelled_by_user",
        )
    except BadZipFile as exc:
        _update_job(
            job_id,
            status="failed",
            progress=100,
            message="Invalid ZIP archive.",
            error=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        _update_job(
            job_id,
            status="failed",
            progress=100,
            message="Archive generation failed.",
            error=str(exc),
        )


def _run_hybrid_rag_rebuild_job(
    job_id: str,
    service: ProjectArchiveService,
    project_id: str,
) -> None:
    try:
        _update_job(job_id, status="running", progress=12, message="Loading project archive.")
        if _job_cancel_requested(job_id):
            raise _ArchiveJobCancelled()
        _update_job(
            job_id,
            progress=38,
            message="Rebuilding prioritized Chroma + BM25 Hybrid RAG index.",
        )

        def on_progress(progress: int, message: str) -> None:
            if _job_cancel_requested(job_id):
                raise _ArchiveJobCancelled()
            _update_job(job_id, progress=progress, message=f"hybrid_rag: {message}")

        status = service.rebuild_hybrid_rag_index(project_id, on_progress=on_progress)
        if _job_cancel_requested(job_id):
            raise _ArchiveJobCancelled()
        _update_job(
            job_id,
            status="complete",
            progress=100,
            message="Hybrid RAG index rebuilt.",
            project_id=project_id,
            result={
                "project_id": project_id,
                "rag_status": {
                    "indexed_chunks": status.get("indexed_chunks", 0),
                    "candidate_chunks": status.get("candidate_chunks", 0),
                    "coverage_percent": status.get("coverage_percent", 0),
                    "indexing_policy": status.get("indexing_policy", ""),
                    "health": status.get("health", ""),
                },
            },
        )
    except _ArchiveJobCancelled:
        _update_job(
            job_id,
            status="cancelled",
            message="Hybrid RAG rebuild cancelled.",
            error="cancelled_by_user",
        )
    except Exception as exc:  # noqa: BLE001
        _update_job(
            job_id,
            status="failed",
            progress=100,
            message="Hybrid RAG rebuild failed.",
            error=str(exc),
        )


def _run_agent_report_job(
    job_id: str,
    service: ProjectArchiveService,
    project_id: str,
    scan_profile: str,
    llm_mode: str,
) -> None:
    try:
        _update_job(job_id, status="running", progress=18, message="Loading project archive.")
        if _job_cancel_requested(job_id):
            raise _ArchiveJobCancelled()
        service.load_draft(project_id)
        _update_job(job_id, progress=42, message="Running five Agent roles.")
        if _job_cancel_requested(job_id):
            raise _ArchiveJobCancelled()
        report = service.run_agent_report(
            project_id=project_id,
            scan_profile=scan_profile,
            llm_mode=llm_mode,
        )
        if _job_cancel_requested(job_id):
            raise _ArchiveJobCancelled()
        _update_job(
            job_id,
            status="complete",
            progress=100,
            message="Agent report is ready.",
            project_id=project_id,
            result={"agent_report": report.to_dict()},
        )
    except _ArchiveJobCancelled:
        _update_job(
            job_id,
            status="cancelled",
            message="Agent analysis cancelled.",
            error="cancelled_by_user",
        )
    except Exception as exc:  # noqa: BLE001
        _update_job(
            job_id,
            status="failed",
            progress=100,
            message="Agent analysis failed.",
            error=str(exc),
        )


def _run_agent_mission_background(
    service: ProjectArchiveService,
    mission_id: str,
) -> None:
    try:
        service.run_agent_mission(mission_id)
    except Exception:  # noqa: BLE001
        try:
            service.update_agent_mission_status(mission_id, "failed")
        except Exception:  # noqa: BLE001
            pass


class _ArchiveJobCancelled(Exception):
    """Raised internally when a user cancels a background archive job."""


def _utc_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


def _slugify_project_id(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-._")
    return normalized or "project-archive"


def _project_id_from_upload(project_id: str, filename: str) -> str:
    if project_id.strip():
        return _slugify_project_id(project_id)
    return _slugify_project_id(Path(filename).stem)


def _safe_zip_path(filename: str) -> PurePosixPath:
    path = PurePosixPath(filename.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"Unsafe ZIP path: {filename}")
    return path


def _is_supported_member(path: PurePosixPath, size: int, scan_profile: str) -> bool:
    return _member_skip_reason(path, size, scan_profile) is None


def _member_skip_reason(path: PurePosixPath, size: int, scan_profile: str) -> str | None:
    suffix = PurePosixPath(path.name.lower()).suffix
    is_image = suffix in IMAGE_SUFFIXES
    if is_image:
        if size > MAX_IMAGE_MEMBER_BYTES:
            return "image_too_large"
    elif size > MAX_MEMBER_BYTES:
        return "file_too_large"
    lowered_parts = {part.lower() for part in path.parts}
    if lowered_parts & {part.lower() for part in IGNORED_PARTS}:
        return "ignored_directory"
    if _matches_upload_path_filter(path, ignore_prefixes_for_profile(scan_profile)):
        return "ignored_by_scan_profile"
    include_prefixes = include_prefixes_for_profile(scan_profile)
    if include_prefixes is not None and not _matches_upload_path_filter(path, include_prefixes):
        return "outside_scan_profile"
    name = path.name.lower()
    if is_image or name in TEXT_FILENAMES or suffix in TEXT_SUFFIXES:
        return None
    return "unsupported_file_type"


def _extract_project_zip(
    payload: bytes,
    target: Path,
    scan_profile: str = SCAN_PROFILE_ARCHITECTURE,
) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    saved_files = 0
    total_members = 0
    skipped_by_reason: Counter[str] = Counter()
    kept_by_type: Counter[str] = Counter()
    skipped_samples: list[dict[str, str]] = []
    zip_path = target / "upload.zip"
    zip_path.write_bytes(payload)
    source_root = target / "source"
    source_root.mkdir()

    with ZipFile(zip_path) as archive:
        for member in archive.infolist():
            member_path = _safe_zip_path(member.filename)
            if member.is_dir():
                continue
            total_members += 1
            skip_reason = _member_skip_reason(member_path, member.file_size, scan_profile)
            if skip_reason is not None:
                skipped_by_reason[skip_reason] += 1
                if len(skipped_samples) < 20:
                    skipped_samples.append(
                        {
                            "path": member_path.as_posix(),
                            "reason": skip_reason,
                        }
                    )
                continue
            output_path = source_root / Path(*member_path.parts)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, output_path.open("wb") as destination:
                shutil.copyfileobj(source, destination)
            saved_files += 1
            kept_by_type["image" if member_path.suffix.lower() in IMAGE_SUFFIXES else "text"] += 1

    if saved_files == 0:
        raise ValueError("No supported source, configuration, or documentation files were found.")
    project_root = _select_project_root(source_root)
    diagnostics_dir = project_root / ".twinmind"
    diagnostics_dir.mkdir(exist_ok=True)
    (diagnostics_dir / "upload_diagnostics.json").write_text(
        json.dumps(
            {
                "total_zip_files": total_members,
                "kept_files": saved_files,
                "skipped_files": sum(skipped_by_reason.values()),
                "skipped_by_reason": dict(sorted(skipped_by_reason.items())),
                "kept_by_type": dict(sorted(kept_by_type.items())),
                "skipped_samples": skipped_samples,
                "limits": {
                    "max_upload_bytes": MAX_UPLOAD_BYTES,
                    "max_member_bytes": MAX_MEMBER_BYTES,
                    "max_image_member_bytes": MAX_IMAGE_MEMBER_BYTES,
                },
                "scan_profile": scan_profile,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return project_root


def _matches_upload_path_filter(path: PurePosixPath, filters: set[str]) -> bool:
    candidate_paths = [path.as_posix().strip("/")]
    if len(path.parts) > 1:
        candidate_paths.append(PurePosixPath(*path.parts[1:]).as_posix().strip("/"))

    for raw_filter in filters:
        normalized_filter = raw_filter.strip("/")
        if not normalized_filter:
            continue
        for normalized_path in candidate_paths:
            if raw_filter.endswith("/") and (
                normalized_path == normalized_filter
                or normalized_path.startswith(f"{normalized_filter}/")
            ):
                return True
            if not raw_filter.endswith("/") and normalized_path == normalized_filter:
                return True
    return False


def _select_project_root(root: Path) -> Path:
    children = [child for child in root.iterdir() if child.name != "__MACOSX"]
    folders = [child for child in children if child.is_dir()]
    files = [child for child in children if child.is_file()]
    if len(folders) == 1 and not files:
        return folders[0]
    return root
