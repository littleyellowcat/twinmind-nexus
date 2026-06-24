"""FastAPI app for TwinMind Archive frontend integration."""

from __future__ import annotations

import re
import shutil
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Annotated
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
from pydantic import BaseModel, Field

from src.project_archive.autonomous_mission import ARCHITECTURE_GOAL
from src.project_archive.scanner import (
    SCAN_PROFILE_ARCHITECTURE,
    ignore_prefixes_for_profile,
    include_prefixes_for_profile,
    normalize_scan_profile,
)
from src.project_archive.service import ProjectArchiveService
from src.project_archive.types import QueryMode

DEFAULT_ARCHIVE_STORAGE_DIR = Path("data/project_archive")
MAX_UPLOAD_BYTES = 512 * 1024 * 1024
MAX_MEMBER_BYTES = 1_000_000
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


class MissionStartRequest(BaseModel):
    goal: str = ARCHITECTURE_GOAL
    max_steps: int = Field(default=12, ge=1, le=12)


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

    def to_dict(self) -> dict:
        return asdict(self)


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

    @app.get("/api/archives")
    def list_archives(service: ServiceDep) -> dict[str, list[str]]:
        return {"archives": service.list_project_ids()}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        job = _get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        return job.to_dict()

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
                agent_report = service.run_agent_report(
                    project_id=draft.project_id,
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
            "agent_report": agent_report.to_dict(),
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
            ).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/agent-report")
    def get_agent_report(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.load_agent_report(project_id).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/archives/{project_id}/agent-report/run")
    def run_agent_report(
        project_id: str,
        service: ServiceDep,
        scan_profile: str = SCAN_PROFILE_ARCHITECTURE,
    ) -> dict:
        try:
            return service.run_agent_report(
                project_id=project_id,
                scan_profile=normalize_scan_profile(scan_profile),
            ).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/archives/{project_id}/agent-report/run-job", status_code=202)
    def run_agent_report_job(
        project_id: str,
        background_tasks: BackgroundTasks,
        service: ServiceDep,
        scan_profile: str = SCAN_PROFILE_ARCHITECTURE,
    ) -> dict:
        try:
            service.load_draft(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

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
        return _JOBS.get(job_id)


def _update_job(
    job_id: str,
    *,
    status: str | None = None,
    progress: int | None = None,
    message: str | None = None,
    project_id: str | None = None,
    result: dict | None = None,
    error: str | None = None,
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
        with TemporaryDirectory(prefix="twinmind-upload-") as tmpdir:
            project_root = _extract_project_zip(payload, Path(tmpdir), scan_profile=scan_profile)
            _update_job(job_id, progress=38, message="Building project knowledge graph.")
            draft = service.ingest_project(
                project_root=project_root,
                project_id=archive_id,
                scan_profile=scan_profile,
            )
            _update_job(job_id, progress=72, message="Running multi-agent archive analysis.")
            agent_report = service.run_agent_report(
                project_id=draft.project_id,
                scan_profile=scan_profile,
            )
        _update_job(
            job_id,
            status="complete",
            progress=100,
            message="Archive and Agent report are ready.",
            project_id=draft.project_id,
            result={
                "project_id": draft.project_id,
                "metrics": {
                    "halls": len(draft.halls),
                    "entities": len(draft.entities),
                    "relations": len(draft.relations),
                    "evidence": len(draft.evidence_cards),
                },
                "archive": draft.to_dict(),
                "agent_report": agent_report.to_dict(),
            },
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


def _run_agent_report_job(
    job_id: str,
    service: ProjectArchiveService,
    project_id: str,
    scan_profile: str,
) -> None:
    try:
        _update_job(job_id, status="running", progress=18, message="Loading project archive.")
        service.load_draft(project_id)
        _update_job(job_id, progress=42, message="Running five Agent roles.")
        report = service.run_agent_report(project_id=project_id, scan_profile=scan_profile)
        _update_job(
            job_id,
            status="complete",
            progress=100,
            message="Agent report is ready.",
            project_id=project_id,
            result={"agent_report": report.to_dict()},
        )
    except Exception as exc:  # noqa: BLE001
        _update_job(
            job_id,
            status="failed",
            progress=100,
            message="Agent analysis failed.",
            error=str(exc),
        )


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
    if size > MAX_MEMBER_BYTES:
        return False
    lowered_parts = {part.lower() for part in path.parts}
    if lowered_parts & {part.lower() for part in IGNORED_PARTS}:
        return False
    if _matches_upload_path_filter(path, ignore_prefixes_for_profile(scan_profile)):
        return False
    include_prefixes = include_prefixes_for_profile(scan_profile)
    if include_prefixes is not None and not _matches_upload_path_filter(path, include_prefixes):
        return False
    name = path.name.lower()
    return name in TEXT_FILENAMES or PurePosixPath(name).suffix in TEXT_SUFFIXES


def _extract_project_zip(
    payload: bytes,
    target: Path,
    scan_profile: str = SCAN_PROFILE_ARCHITECTURE,
) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    saved_files = 0
    zip_path = target / "upload.zip"
    zip_path.write_bytes(payload)
    source_root = target / "source"
    source_root.mkdir()

    with ZipFile(zip_path) as archive:
        for member in archive.infolist():
            member_path = _safe_zip_path(member.filename)
            if member.is_dir() or not _is_supported_member(
                member_path,
                member.file_size,
                scan_profile,
            ):
                continue
            output_path = source_root / Path(*member_path.parts)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, output_path.open("wb") as destination:
                shutil.copyfileobj(source, destination)
            saved_files += 1

    if saved_files == 0:
        raise ValueError("No supported source, configuration, or documentation files were found.")
    return _select_project_root(source_root)


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
