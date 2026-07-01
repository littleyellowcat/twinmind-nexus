#!/usr/bin/env python3
"""Run TwinMind Archive regression checks against local GitHub ZIP fixtures."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.project_archive.scanner import SCAN_PROFILE_ARCHITECTURE
from src.project_archive.service import ProjectArchiveService

DEFAULT_ZIP_DIR = ROOT_DIR.parent / "github-test-zips"
DEFAULT_OUTPUT = ROOT_DIR / "output" / "github_zip_regression_report.md"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip-dir", type=Path, default=DEFAULT_ZIP_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--storage-dir", type=Path, default=ROOT_DIR / "data" / "project_archive")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--run-evaluation", action="store_true")
    parser.add_argument("--scan-profile", default=SCAN_PROFILE_ARCHITECTURE)
    args = parser.parse_args()

    zip_paths = sorted(args.zip_dir.glob("*.zip"))[: max(1, args.limit)]
    service = ProjectArchiveService(storage_dir=args.storage_dir)
    rows: list[dict] = []
    for zip_path in zip_paths:
        project_id = zip_path.stem.replace("__", "_").replace(" ", "_")
        if args.skip_existing and project_id in service.list_project_ids():
            rows.append(_existing_project_row(service, project_id, zip_path))
            continue
        started_at = time.perf_counter()
        try:
            with TemporaryDirectory() as tmp:
                extract_root = Path(tmp) / "project"
                extract_root.mkdir(parents=True, exist_ok=True)
                _safe_extract(zip_path, extract_root)
                project_root = _single_project_root(extract_root)
                draft = service.ingest_project(
                    project_root=project_root,
                    project_id=project_id,
                    scan_profile=args.scan_profile,
                )
            graph_report = _safe_dict(lambda: service.graph_workspace_report(project_id))
            diagnostics = _safe_dict(lambda: service.ingestion_diagnostics(project_id))
            hybrid_status = _safe_dict(lambda: service.hybrid_rag_status(project_id))
            multimodal = _safe_dict(lambda: service.multimodal_insights(project_id))
            if args.run_evaluation:
                service.run_archive_evaluation(project_id)
            service.generate_project_intelligence_report(project_id)
            rows.append(_project_row(
                draft=draft,
                diagnostics=diagnostics,
                duration_seconds=time.perf_counter() - started_at,
                graph_report=graph_report,
                hybrid_status=hybrid_status,
                multimodal=multimodal,
                status="complete",
                zip_path=zip_path,
            ))
        except Exception as exc:  # noqa: BLE001 - regression runner must continue.
            rows.append(
                {
                    "project_id": project_id,
                    "zip": zip_path.name,
                    "status": "failed",
                    "error": str(exc),
                    "duration_seconds": round(time.perf_counter() - started_at, 3),
                }
            )

    measurable_statuses = {"complete", "review", "skipped"}
    stress = service.run_stress_test(
        project_ids=[row["project_id"] for row in rows if row.get("status") in measurable_statuses],
        run_evaluation=False,
    ) if any(row.get("status") in measurable_statuses for row in rows) else {}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(_markdown_report(rows, stress), encoding="utf-8")
    print(f"Wrote regression report: {args.output}")
    print(json.dumps({"rows": rows, "stress_summary": stress.get("summary", {})}, ensure_ascii=False, indent=2))


def _safe_extract(zip_path: Path, target: Path) -> None:
    try:
        with ZipFile(zip_path) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                destination = target / member.filename
                if not destination.resolve().is_relative_to(target.resolve()):
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output)
    except BadZipFile as exc:
        raise ValueError(f"Invalid ZIP file: {zip_path}") from exc


def _single_project_root(extract_root: Path) -> Path:
    children = [child for child in extract_root.iterdir() if child.is_dir()]
    if len(children) == 1:
        return children[0]
    return extract_root


def _existing_project_row(service: ProjectArchiveService, project_id: str, zip_path: Path) -> dict:
    draft = service.load_draft(project_id)
    graph_report = _safe_dict(lambda: service.graph_workspace_report(project_id))
    diagnostics = _safe_dict(lambda: service.ingestion_diagnostics(project_id))
    hybrid_status = _safe_dict(lambda: service.hybrid_rag_status(project_id))
    multimodal = _safe_dict(lambda: service.multimodal_insights(project_id))
    return _project_row(
        draft=draft,
        diagnostics=diagnostics,
        duration_seconds=0.0,
        graph_report=graph_report,
        hybrid_status=hybrid_status,
        multimodal=multimodal,
        status="skipped",
        zip_path=zip_path,
    )


def _project_row(
    *,
    draft,
    diagnostics: dict,
    duration_seconds: float,
    graph_report: dict,
    hybrid_status: dict,
    multimodal: dict,
    status: str,
    zip_path: Path,
) -> dict:
    quality = graph_report.get("quality", {}) if isinstance(graph_report, dict) else {}
    health = diagnostics.get("health", {}) if isinstance(diagnostics, dict) else {}
    sparse_halls = [
        hall for hall in draft.halls
        if not hall.entity_ids or len(hall.entity_ids) < 3
    ]
    warnings = [
        *[str(item) for item in quality.get("warnings", [])],
        *[str(item) for item in health.get("warnings", [])],
    ]
    for label, payload in (
        ("graph workspace", graph_report),
        ("ingestion diagnostics", diagnostics),
        ("Hybrid RAG status", hybrid_status),
        ("multimodal insights", multimodal),
    ):
        if payload.get("error"):
            warnings.append(f"{label} unavailable: {payload['error']}")
    if sparse_halls:
        warnings.append(f"{len(sparse_halls)} sparse hall(s)")
    if len(draft.relations) == 0 and len(draft.entities) > 1:
        warnings.append("No graph relations were extracted.")
    if int(hybrid_status.get("indexed_chunks", 0) or 0) == 0:
        warnings.append("Hybrid RAG index is empty.")
    if int(multimodal.get("image_count", 0) or 0) and not int(multimodal.get("vision_supported", 0) or 0):
        warnings.append("Image evidence exists but vision support did not run.")

    row_status = status
    if status == "complete":
        if float(quality.get("score", 0) or 0) < 45 or len(draft.entities) == 0:
            row_status = "failed"
        elif warnings:
            row_status = "review"

    return {
        "project_id": draft.project_id,
        "zip": zip_path.name,
        "status": row_status,
        "entities": len(draft.entities),
        "relations": len(draft.relations),
        "evidence": len(draft.evidence_cards),
        "halls": len(draft.halls),
        "sparse_halls": len(sparse_halls),
        "quality": round(float(quality.get("score", 0) or 0), 2),
        "grade": quality.get("grade", "E"),
        "health": round(float(health.get("score", 0) or 0), 2),
        "hybrid_chunks": int(hybrid_status.get("indexed_chunks", 0) or 0),
        "image_count": int(multimodal.get("image_count", 0) or 0),
        "vision_supported": int(multimodal.get("vision_supported", 0) or 0),
        "duration_seconds": round(duration_seconds, 3),
        "warnings": _unique(warnings)[:10],
        "recommendations": _unique([
            *[str(item) for item in quality.get("recommendations", [])],
            *[str(item) for item in diagnostics.get("recommendations", [])],
        ])[:8],
    }


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        clean = item.strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def _safe_dict(loader) -> dict:
    try:
        value = loader()
    except Exception as exc:  # noqa: BLE001 - regression report should capture gaps.
        return {"error": str(exc)}
    return value if isinstance(value, dict) else {}


def _markdown_report(rows: list[dict], stress: dict) -> str:
    lines = [
        "# TwinMind GitHub ZIP Regression Report",
        "",
        "## Summary",
        "",
    ]
    summary = stress.get("summary", {}) if isinstance(stress, dict) else {}
    if summary:
        for key, value in summary.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- No stress summary was generated.")
    lines.extend([
        "",
        "## Projects",
        "",
        "| Project | Status | Entities | Relations | Evidence | Halls | Sparse Halls | Quality | Health | Hybrid Chunks | Images | Vision | Notes |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ])
    for row in rows:
        lines.append(
            "| {project} | {status} | {entities} | {relations} | {evidence} | {halls} | {sparse_halls} | {quality} | {health} | {hybrid_chunks} | {image_count} | {vision_supported} | {notes} |".format(
                project=row.get("project_id", ""),
                status=row.get("status", ""),
                entities=row.get("entities", 0),
                relations=row.get("relations", 0),
                evidence=row.get("evidence", 0),
                halls=row.get("halls", 0),
                sparse_halls=row.get("sparse_halls", 0),
                quality=row.get("quality", "-"),
                health=row.get("health", "-"),
                hybrid_chunks=row.get("hybrid_chunks", 0),
                image_count=row.get("image_count", 0),
                vision_supported=row.get("vision_supported", 0),
                notes=_table_text(row.get("error") or "; ".join(row.get("warnings", [])) or f"grade={row.get('grade', '-')}"),
            )
        )
    lines.extend(["", "## Recommendations", ""])
    emitted = False
    for row in rows:
        recommendations = row.get("recommendations", [])
        if not recommendations:
            continue
        emitted = True
        lines.append(f"### {row.get('project_id', '')}")
        for item in recommendations[:5]:
            lines.append(f"- {item}")
        lines.append("")
    if not emitted:
        lines.append("- No project-specific recommendations were produced.")
        lines.append("")
    lines.extend([
        "## How To Read This",
        "",
        "- `complete` means the archive passed the current checks.",
        "- `review` means the archive exists, but sparse graph, missing Hybrid RAG, missing multimodal support, or quality warnings need inspection.",
        "- `failed` means ingestion or core archive generation failed.",
        "- `skipped` means `--skip-existing` reused a persisted archive and still measured it.",
        "",
    ])
    lines.append("")
    return "\n".join(lines)


def _table_text(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")[:220]


if __name__ == "__main__":
    main()
