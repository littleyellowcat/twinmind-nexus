"""TwinMind Archive dashboard page.

Provides a lightweight project-archive workbench for ingesting local projects,
inspecting archive halls, viewing graph relationships, and querying the
deterministic TwinMind agent workflows.
"""

from __future__ import annotations

import re
import shutil
from collections import Counter
from collections.abc import Iterable
from html import escape
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import ZipFile

import streamlit as st

from src.observability.dashboard.i18n import current_language, t
from src.project_archive.scanner import (
    DEFAULT_IGNORE_DIRS,
    LANGUAGE_BY_SUFFIX,
    SCAN_PROFILE_ARCHITECTURE,
    SCAN_PROFILE_DOCS,
    SCAN_PROFILE_FULL,
    SCAN_PROFILE_TESTS,
    ignore_prefixes_for_profile,
    include_prefixes_for_profile,
)
from src.project_archive.service import ProjectArchiveService
from src.project_archive.types import AgentResult, ProjectArchiveDraft, QueryMode

ARCHIVE_STORAGE_DIR = Path("data/project_archive")
PROJECT_UPLOAD_DIR = Path("data/project_uploads")
MAX_PROJECT_ZIP_UPLOAD_MB = 1024
MAX_FOLDER_UPLOAD_FILES = 2_000
MAX_FOLDER_UPLOAD_BYTES = 40_000_000
MAX_UPLOAD_FILE_BYTES = 1_000_000
UPLOAD_TEXT_SUFFIXES = set(LANGUAGE_BY_SUFFIX) | {
    ".c",
    ".cfg",
    ".conf",
    ".css",
    ".env",
    ".gradle",
    ".html",
    ".ini",
    ".lock",
    ".properties",
    ".rst",
    ".sh",
    ".sql",
    ".txt",
    ".xml",
}
UPLOAD_TEXT_FILENAMES = {
    ".env",
    ".gitignore",
    "dockerfile",
    "makefile",
    "readme",
}
SAMPLE_PROJECT_PATH = "tests/fixtures/project_archive_sample"
SAMPLE_PROJECT_ID = "sample-project"

MODE_LABEL_KEYS = {
    QueryMode.ARCHITECTURE_TOUR: "twin.mode.architecture_tour",
    QueryMode.IMPACT_ANALYSIS: "twin.mode.impact_analysis",
    QueryMode.RISK_AUDIT: "twin.mode.risk_audit",
    QueryMode.EVIDENCE_QA: "twin.mode.evidence_qa",
}
SCAN_PROFILE_LABEL_KEYS = {
    SCAN_PROFILE_ARCHITECTURE: "twin.scan_profile.architecture",
    SCAN_PROFILE_FULL: "twin.scan_profile.full",
    SCAN_PROFILE_DOCS: "twin.scan_profile.docs",
    SCAN_PROFILE_TESTS: "twin.scan_profile.tests",
}
SCAN_PROFILE_HELP_KEYS = {
    SCAN_PROFILE_ARCHITECTURE: "twin.scan_profile_help.architecture",
    SCAN_PROFILE_FULL: "twin.scan_profile_help.full",
    SCAN_PROFILE_DOCS: "twin.scan_profile_help.docs",
    SCAN_PROFILE_TESTS: "twin.scan_profile_help.tests",
}
SCAN_PROFILE_OPTIONS = [
    SCAN_PROFILE_ARCHITECTURE,
    SCAN_PROFILE_FULL,
    SCAN_PROFILE_DOCS,
    SCAN_PROFILE_TESTS,
]


def _list_archived_project_ids(
    storage_dir: Path | str = ARCHIVE_STORAGE_DIR,
) -> list[str]:
    """Return project IDs with a persisted draft archive."""
    root = Path(storage_dir)
    if not root.exists():
        return []

    return sorted(
        child.name
        for child in root.iterdir()
        if child.is_dir() and (child / "draft_archive.json").exists()
    )


def _archive_metrics(draft: ProjectArchiveDraft) -> dict[str, int]:
    """Compute headline counts for an archive draft."""
    return {
        "halls": len(draft.halls),
        "entities": len(draft.entities),
        "relations": len(draft.relations),
        "evidence": len(draft.evidence_cards),
    }


def _format_count(value: int) -> str:
    """Format compact archive counts for dense UI panels."""
    return f"{value:,}"


def _html(value: Any) -> str:
    """Escape a value for Streamlit HTML snippets."""
    return escape(str(value), quote=True)


def _render_html(markup: str) -> None:
    """Render raw HTML without Markdown converting indented blocks to code."""
    st.html(markup)


def _source_path_for_entity(entity_id: str, draft: ProjectArchiveDraft) -> str | None:
    entity = {item.id: item for item in draft.entities}.get(entity_id)
    if entity is None:
        return None
    return entity.source_path or entity.name


def _language_distribution(draft: ProjectArchiveDraft, limit: int = 5) -> list[dict[str, Any]]:
    """Infer a lightweight language distribution from entity source paths."""
    suffix_counts: Counter[str] = Counter()
    seen_paths: set[str] = set()
    for entity in draft.entities:
        source_path = entity.source_path or entity.name
        if not source_path or source_path in seen_paths:
            continue
        seen_paths.add(source_path)
        suffix = Path(source_path).suffix.lower()
        language = LANGUAGE_BY_SUFFIX.get(suffix)
        if language:
            suffix_counts[language] += 1
    return [
        {"language": language, "count": count}
        for language, count in suffix_counts.most_common(limit)
    ]


def _top_hall_type_labels(
    hall_entity_ids: Iterable[str],
    draft: ProjectArchiveDraft,
    limit: int = 3,
) -> list[str]:
    entity_by_id = {entity.id: entity for entity in draft.entities}
    counts = Counter(
        entity_by_id[entity_id].type
        for entity_id in hall_entity_ids
        if entity_id in entity_by_id
    )
    return [item_type for item_type, _count in counts.most_common(limit)]


def _top_type_rows(values: Iterable[str], limit: int = 8) -> list[dict[str, Any]]:
    """Build rows for compact type distribution tables."""
    return [
        {"type": item_type, "count": count}
        for item_type, count in Counter(values).most_common(limit)
    ]


def _slugify_project_id(value: str) -> str:
    """Convert user-facing project names into stable archive IDs."""
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-._")
    return normalized or "project-archive"


def _safe_upload_path(filename: str) -> PurePosixPath:
    """Return a safe relative upload path or raise for traversal attempts."""
    path = PurePosixPath(filename.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"Unsafe upload path: {filename}")
    return path


def _project_id_from_upload(
    project_id: str,
    *,
    zip_name: str | None = None,
    folder_files: list[Any] | None = None,
    fallback: str = "project-archive",
) -> str:
    """Resolve an optional project ID from explicit input or uploaded names."""
    if project_id.strip():
        return _slugify_project_id(project_id)
    if zip_name:
        return _slugify_project_id(Path(zip_name).stem)
    if folder_files:
        first_name = getattr(folder_files[0], "name", fallback)
        first_part = _safe_upload_path(first_name).parts[0]
        return _slugify_project_id(first_part)
    return _slugify_project_id(fallback)


def _prepare_upload_root(project_id: str) -> Path:
    target = PROJECT_UPLOAD_DIR / project_id / "source"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _select_project_root(root: Path) -> Path:
    """Use a single top-level folder as the project root when uploads wrap it."""
    children = [child for child in root.iterdir() if child.name != "__MACOSX"]
    folders = [child for child in children if child.is_dir()]
    files = [child for child in children if child.is_file()]
    if len(folders) == 1 and not files:
        return folders[0]
    return root


def _scan_profile_label(scan_profile: str, language: str) -> str:
    return t(SCAN_PROFILE_LABEL_KEYS.get(scan_profile, scan_profile), language)


def _is_ignored_upload_path(path: PurePosixPath, scan_profile: str) -> bool:
    return any(part in DEFAULT_IGNORE_DIRS for part in path.parts) or _matches_upload_path_filter(
        path,
        ignore_prefixes_for_profile(scan_profile),
    )


def _is_included_upload_path(path: PurePosixPath, scan_profile: str) -> bool:
    include_prefixes = include_prefixes_for_profile(scan_profile)
    return include_prefixes is None or _matches_upload_path_filter(path, include_prefixes)


def _matches_upload_path_filter(path: PurePosixPath, filters: Iterable[str]) -> bool:
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


def _is_interesting_upload_file(path: PurePosixPath, size: int) -> bool:
    if size > MAX_UPLOAD_FILE_BYTES:
        return False
    name = path.name.lower()
    suffix = PurePosixPath(name).suffix
    return name in UPLOAD_TEXT_FILENAMES or suffix in UPLOAD_TEXT_SUFFIXES


def _uploaded_file_size(uploaded_file: Any) -> int:
    size = getattr(uploaded_file, "size", None)
    if isinstance(size, int):
        return size
    return len(uploaded_file.getvalue())


def _extract_project_zip(
    uploaded_file: Any,
    project_id: str,
    scan_profile: str = SCAN_PROFILE_ARCHITECTURE,
) -> Path:
    """Extract a project ZIP upload and return the project root to ingest."""
    target = _prepare_upload_root(project_id)
    saved_files = 0
    with ZipFile(BytesIO(uploaded_file.getvalue())) as archive:
        for member in archive.infolist():
            member_path = _safe_upload_path(member.filename)
            if (
                member.is_dir()
                or member_path.parts[0] == "__MACOSX"
                or _is_ignored_upload_path(member_path, scan_profile)
                or not _is_included_upload_path(member_path, scan_profile)
                or not _is_interesting_upload_file(member_path, member.file_size)
            ):
                continue
            output_path = target / Path(*member_path.parts)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, output_path.open("wb") as destination:
                shutil.copyfileobj(source, destination)
            saved_files += 1
    if saved_files == 0:
        raise ValueError("No supported source or documentation files were found.")
    return _select_project_root(target)


def _save_project_folder_upload(
    uploaded_files: list[Any],
    project_id: str,
    scan_profile: str = SCAN_PROFILE_ARCHITECTURE,
) -> Path:
    """Persist a browser directory upload and return the project root to ingest."""
    if len(uploaded_files) > MAX_FOLDER_UPLOAD_FILES:
        raise ValueError(
            f"Folder upload contains {len(uploaded_files)} files. "
            "Please upload a ZIP instead."
        )
    total_size = sum(_uploaded_file_size(uploaded_file) for uploaded_file in uploaded_files)
    if total_size > MAX_FOLDER_UPLOAD_BYTES:
        raise ValueError("Folder upload is too large. Please upload a ZIP instead.")

    target = _prepare_upload_root(project_id)
    saved_files = 0
    for uploaded_file in uploaded_files:
        member_path = _safe_upload_path(uploaded_file.name)
        size = _uploaded_file_size(uploaded_file)
        if (
            _is_ignored_upload_path(member_path, scan_profile)
            or not _is_included_upload_path(member_path, scan_profile)
            or not _is_interesting_upload_file(
                member_path,
                size,
            )
        ):
            continue
        output_path = target / Path(*member_path.parts)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(uploaded_file.getvalue())
        saved_files += 1
    if saved_files == 0:
        raise ValueError("No supported source or documentation files were found.")
    return _select_project_root(target)


def _relation_rows(
    draft: ProjectArchiveDraft, limit: int = 30
) -> list[dict[str, str]]:
    """Build source-relation-target rows for the star-map preview."""
    entity_names = {entity.id: entity.name for entity in draft.entities}
    return [
        {
            "source": entity_names.get(relation.source_id, relation.source_id),
            "relation": relation.type,
            "target": entity_names.get(relation.target_id, relation.target_id),
        }
        for relation in draft.relations[:limit]
    ]


def _mode_label(mode: QueryMode, language: str = "en") -> str:
    return t(MODE_LABEL_KEYS.get(mode, mode.value), language)


def _format_agent_result(
    result: AgentResult,
    language: str = "en",
    draft: ProjectArchiveDraft | None = None,
) -> str:
    """Format a deterministic agent result for display."""
    lines = [
        f"{t('twin.result.mode', language)}: {_mode_label(result.mode, language)}",
        f"{t('twin.result.confidence', language)}: {result.confidence:.2f}",
        "",
        result.summary,
    ]
    if result.affected_entities:
        lines.extend(
            [
                "",
                f"{t('twin.result.affected_entities', language)}:",
                *_bullet_lines(
                    _format_entity_refs(result.affected_entities, draft)
                ),
            ]
        )
    if result.evidence_card_ids:
        lines.extend(
            [
                "",
                f"{t('twin.result.evidence_cards', language)}:",
                *_bullet_lines(
                    _format_evidence_refs(result.evidence_card_ids, draft)
                ),
            ]
        )
    if result.risks:
        lines.extend(["", f"{t('twin.result.risks', language)}:", *_bullet_lines(result.risks)])
    if result.next_actions:
        lines.extend(
            ["", f"{t('twin.result.next_actions', language)}:", *_bullet_lines(result.next_actions)]
        )
    return "\n".join(lines)


def _bullet_lines(values: Iterable[str]) -> list[str]:
    return [f"- {value}" for value in values]


def _format_entity_refs(
    entity_ids: Iterable[str],
    draft: ProjectArchiveDraft | None,
) -> list[str]:
    if draft is None:
        return list(entity_ids)
    return [_entity_display_name(entity_id, draft) for entity_id in entity_ids]


def _format_evidence_refs(
    evidence_ids: Iterable[str],
    draft: ProjectArchiveDraft | None,
) -> list[str]:
    if draft is None:
        return list(evidence_ids)
    evidence_by_id = {card.id: card for card in draft.evidence_cards}
    rows = []
    for evidence_id in evidence_ids:
        card = evidence_by_id.get(evidence_id)
        if card is None:
            rows.append(evidence_id)
        else:
            rows.append(f"{card.title} ({card.source_path})")
    return rows


def _entity_display_name(entity_id: str, draft: ProjectArchiveDraft) -> str:
    entity_by_id = {entity.id: entity for entity in draft.entities}
    entity = entity_by_id.get(entity_id)
    if entity is None:
        return entity_id
    if entity.source_path and entity.name != entity.source_path:
        return f"{entity.type}: {entity.name} ({entity.source_path})"
    return f"{entity.type}: {entity.name}"


def _inject_archive_observatory_css() -> None:
    _render_html(
        """
        <style>
        :root {
          --tm-bg: #080d14;
          --tm-bg-elevated: #0d141f;
          --tm-panel: #111a27;
          --tm-panel-2: #162233;
          --tm-border: #263445;
          --tm-border-strong: #3b4d63;
          --tm-text: #eef6ff;
          --tm-text-muted: #9aa9ba;
          --tm-text-subtle: #6f8093;
          --tm-accent: #35d0ba;
          --tm-accent-2: #6aa8ff;
          --tm-risk: #f3b65f;
          --tm-danger: #ef6b7a;
          --tm-success: #6fdc8c;
        }

        .stApp {
          background:
            radial-gradient(circle at 18% 8%, rgba(53, 208, 186, 0.08), transparent 30%),
            linear-gradient(180deg, #080d14 0%, #0a111b 48%, #080d14 100%);
          color: var(--tm-text);
        }

        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"] {
          display: none;
        }

        [data-testid="stSidebar"] {
          background: #121722;
          border-right: 1px solid #263445;
        }

        .block-container {
          max-width: 1320px;
          padding-top: 1.25rem;
          padding-bottom: 4rem;
        }

        h1, h2, h3, [data-testid="stMarkdownContainer"] h1,
        [data-testid="stMarkdownContainer"] h2,
        [data-testid="stMarkdownContainer"] h3 {
          letter-spacing: 0;
        }

        [data-testid="stMetric"],
        [data-testid="stExpander"],
        [data-testid="stDataFrame"],
        [data-testid="stTextInput"],
        [data-testid="stTextArea"],
        [data-testid="stSelectbox"],
        [data-testid="stFileUploader"] {
          color: var(--tm-text);
        }

        [data-testid="stExpander"] {
          border: 1px solid var(--tm-border);
          border-radius: 8px;
          background: rgba(17, 26, 39, 0.72);
        }

        [data-testid="stFileUploader"] section {
          border-color: var(--tm-border-strong);
          background: rgba(13, 20, 31, 0.74);
          border-radius: 8px;
        }

        .stButton > button {
          min-height: 44px;
          border-radius: 8px;
          border: 1px solid rgba(53, 208, 186, 0.42);
          background: linear-gradient(180deg, #1c3c47 0%, #142832 100%);
          color: var(--tm-text);
          font-weight: 650;
          transition: transform 180ms ease, border-color 180ms ease, background 180ms ease;
        }

        .stButton > button:hover {
          border-color: var(--tm-accent);
          background: linear-gradient(180deg, #235260 0%, #17323d 100%);
          transform: translateY(-1px);
        }

        .stButton > button:focus-visible {
          outline: 2px solid var(--tm-accent);
          outline-offset: 2px;
        }

        .tm-shell {
          border: 1px solid var(--tm-border);
          border-radius: 8px;
          background: linear-gradient(135deg, rgba(17, 26, 39, 0.96), rgba(8, 13, 20, 0.96));
          box-shadow: 0 18px 56px rgba(0, 0, 0, 0.22);
          padding: 18px 20px;
          margin-bottom: 14px;
          position: relative;
          overflow: hidden;
        }

        .tm-shell::after {
          content: "";
          position: absolute;
          inset: auto 0 0 0;
          height: 1px;
          background: linear-gradient(90deg, transparent, var(--tm-accent), transparent);
          opacity: 0.64;
        }

        .tm-header {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 20px;
          align-items: end;
        }

        .tm-kicker {
          color: var(--tm-accent);
          font-size: 12px;
          font-weight: 700;
          letter-spacing: 0;
          margin-bottom: 8px;
        }

        .tm-title {
          color: var(--tm-text);
          font-size: 28px;
          line-height: 36px;
          font-weight: 750;
          margin: 0;
        }

        .tm-subtitle {
          color: var(--tm-text-muted);
          font-size: 14px;
          line-height: 22px;
          max-width: 76ch;
          margin: 8px 0 0;
        }

        .tm-status-strip,
        .tm-passport-counts,
        .tm-chip-row {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          align-items: center;
        }

        .tm-chip {
          border: 1px solid var(--tm-border);
          border-radius: 999px;
          background: rgba(22, 34, 51, 0.74);
          color: var(--tm-text-muted);
          font-size: 12px;
          line-height: 16px;
          padding: 6px 10px;
          white-space: nowrap;
        }

        .tm-chip.is-accent {
          border-color: rgba(53, 208, 186, 0.52);
          color: var(--tm-accent);
          background: rgba(53, 208, 186, 0.08);
        }

        .tm-panel {
          border: 1px solid var(--tm-border);
          border-radius: 8px;
          background: rgba(17, 26, 39, 0.82);
          padding: 14px;
          margin: 10px 0;
        }

        .tm-panel-title {
          color: var(--tm-text);
          font-size: 15px;
          line-height: 22px;
          font-weight: 700;
          margin: 0 0 6px;
        }

        .tm-panel-copy {
          color: var(--tm-text-muted);
          font-size: 13px;
          line-height: 21px;
          margin: 0;
        }

        .tm-passport {
          display: block;
          margin-bottom: 12px;
        }

        .tm-passport-main {
          border: 1px solid var(--tm-border-strong);
          border-radius: 8px;
          background: linear-gradient(135deg, rgba(22, 34, 51, 0.96), rgba(13, 20, 31, 0.96));
          padding: 18px;
        }

        .tm-project-name {
          color: var(--tm-text);
          font-size: 20px;
          line-height: 28px;
          font-weight: 750;
          margin: 0 0 8px;
          overflow-wrap: anywhere;
        }

        .tm-count {
          min-width: 86px;
          border: 1px solid rgba(59, 77, 99, 0.72);
          border-radius: 8px;
          background: rgba(8, 13, 20, 0.5);
          padding: 10px 12px;
        }

        .tm-count-value {
          color: var(--tm-text);
          font-size: 18px;
          line-height: 24px;
          font-weight: 750;
          font-variant-numeric: tabular-nums;
        }

        .tm-count-label {
          color: var(--tm-text-subtle);
          font-size: 12px;
          line-height: 16px;
        }

        .tm-hall-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 10px;
        }

        .tm-hall-card {
          border: 1px solid var(--tm-border);
          border-radius: 8px;
          background: rgba(13, 20, 31, 0.86);
          padding: 12px;
          min-width: 0;
          min-height: 0;
          transition: transform 180ms ease, border-color 180ms ease, background 180ms ease;
        }

        .tm-hall-card:hover {
          border-color: rgba(53, 208, 186, 0.5);
          background: rgba(17, 31, 45, 0.92);
          transform: translateY(-2px);
        }

        .tm-hall-head {
          display: flex;
          justify-content: space-between;
          gap: 10px;
          align-items: start;
        }

        .tm-hall-name {
          color: var(--tm-text);
          font-size: 15px;
          line-height: 21px;
          font-weight: 700;
          margin: 0;
          min-width: 0;
          overflow-wrap: anywhere;
        }

        .tm-hall-count {
          color: var(--tm-accent);
          font-size: 12px;
          line-height: 16px;
          font-family: "SF Mono", "JetBrains Mono", "Cascadia Code", monospace;
        }

        .tm-entity-list {
          color: var(--tm-text-muted);
          font-size: 12px;
          line-height: 18px;
          margin: 10px 0 0;
          padding-left: 16px;
        }

        .tm-entity-list li,
        .tm-clamp {
          overflow: hidden;
          overflow-wrap: anywhere;
          word-break: break-word;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
        }

        .tm-workbench-label {
          color: var(--tm-text-subtle);
          font-size: 12px;
          line-height: 16px;
          margin: 4px 0 8px;
        }

        .tm-star-stage {
          min-height: 260px;
          border: 1px solid var(--tm-border-strong);
          border-radius: 8px;
          background:
            radial-gradient(circle at 25% 34%, rgba(106, 168, 255, 0.14), transparent 2px),
            radial-gradient(circle at 74% 28%, rgba(53, 208, 186, 0.2), transparent 2px),
            radial-gradient(circle at 61% 73%, rgba(243, 182, 95, 0.18), transparent 2px),
            linear-gradient(135deg, rgba(8, 13, 20, 0.98), rgba(17, 26, 39, 0.94));
          padding: 18px;
          position: relative;
          overflow: hidden;
        }

        .tm-star-stage::before {
          content: "";
          position: absolute;
          inset: 22px;
          border: 1px solid rgba(53, 208, 186, 0.12);
          border-radius: 999px;
          transform: rotate(-8deg);
        }

        .tm-relation-orbit {
          position: relative;
          z-index: 1;
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
          gap: 10px;
        }

        .tm-relation {
          border: 1px solid rgba(59, 77, 99, 0.72);
          border-radius: 8px;
          background: rgba(8, 13, 20, 0.62);
          padding: 10px;
        }

        .tm-relation-label {
          color: var(--tm-accent);
          font-size: 11px;
          line-height: 15px;
          font-family: "SF Mono", "JetBrains Mono", "Cascadia Code", monospace;
        }

        .tm-relation-path {
          color: var(--tm-text);
          font-size: 12px;
          line-height: 18px;
          overflow-wrap: anywhere;
          word-break: break-word;
        }

        .tm-evidence-card {
          border: 1px solid var(--tm-border);
          border-radius: 8px;
          background: rgba(13, 20, 31, 0.88);
          padding: 12px;
          margin-top: 10px;
          overflow: hidden;
        }

        .tm-evidence-title {
          color: var(--tm-text);
          font-size: 13px;
          line-height: 19px;
          font-weight: 700;
          margin: 0 0 4px;
        }

        .tm-codepath {
          color: var(--tm-accent-2);
          font-family: "SF Mono", "JetBrains Mono", "Cascadia Code", monospace;
          font-size: 12px;
          line-height: 18px;
          overflow-wrap: anywhere;
          word-break: break-word;
        }

        .tm-mini-stat {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          border-bottom: 1px solid rgba(59, 77, 99, 0.42);
          padding: 8px 0;
          color: var(--tm-text-muted);
          font-size: 12px;
          line-height: 18px;
        }

        .tm-mini-stat:last-child {
          border-bottom: 0;
        }

        .tm-mini-stat strong {
          color: var(--tm-text);
          font-variant-numeric: tabular-nums;
        }

        .tm-agent-report {
          border: 1px solid rgba(53, 208, 186, 0.34);
          border-radius: 8px;
          background: rgba(8, 13, 20, 0.78);
          padding: 14px;
          white-space: pre-wrap;
          color: var(--tm-text);
          font-size: 13px;
          line-height: 21px;
        }

        @media (max-width: 820px) {
          .tm-header,
          .tm-passport {
            grid-template-columns: 1fr;
          }
          .tm-title {
            font-size: 26px;
            line-height: 34px;
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .stButton > button,
          .tm-hall-card {
            transition: none;
          }
          .stButton > button:hover,
          .tm-hall-card:hover {
            transform: none;
          }
        }
        </style>
        """
    )


def _render_archive_header(language: str) -> None:
    _render_html(
        f"""
        <section class="tm-shell">
          <div class="tm-header">
            <div>
              <div class="tm-kicker">{_html(t("twin.header_kicker", language))}</div>
              <h1 class="tm-title">{_html(t("twin.header", language))}</h1>
              <p class="tm-subtitle">{_html(t("twin.header_subtitle", language))}</p>
            </div>
            <div class="tm-status-strip">
              <span class="tm-chip is-accent">GraphRAG</span>
              <span class="tm-chip">{_html(t("twin.header_badge_archive", language))}</span>
              <span class="tm-chip">{_html(t("twin.header_badge_agent", language))}</span>
            </div>
          </div>
        </section>
        """
    )


def _render_empty_archive_notice(language: str) -> None:
    _render_html(
        f"""
        <div class="tm-panel">
          <p class="tm-panel-title">{_html(t("twin.empty_title", language))}</p>
          <p class="tm-panel-copy">{_html(t("twin.empty_copy", language))}</p>
        </div>
        """
    )


def _render_metrics(draft: ProjectArchiveDraft, language: str) -> None:
    metrics = _archive_metrics(draft)
    count_html = "\n".join(
        f"""
        <div class="tm-count">
          <div class="tm-count-value">{_html(_format_count(value))}</div>
          <div class="tm-count-label">{_html(t(label_key, language))}</div>
        </div>
        """
        for label_key, value in [
            ("twin.metric.halls", metrics["halls"]),
            ("twin.metric.entities", metrics["entities"]),
            ("twin.metric.relations", metrics["relations"]),
            ("twin.metric.evidence", metrics["evidence"]),
        ]
    )
    _render_html(
        f"""
        <div class="tm-passport-counts">
          {count_html}
        </div>
        """
    )


def _render_project_passport(
    draft: ProjectArchiveDraft,
    project_id: str,
    language: str,
) -> None:
    language_rows = _language_distribution(draft)
    language_chips = "\n".join(
        f'<span class="tm-chip">{_html(row["language"])} · {_html(row["count"])}</span>'
        for row in language_rows
    ) or f'<span class="tm-chip">{_html(t("twin.language_unknown", language))}</span>'

    _render_html(
        f"""
        <section class="tm-passport">
          <div class="tm-passport-main">
            <div class="tm-kicker">{_html(t("twin.project_passport", language))}</div>
            <h2 class="tm-project-name">{_html(project_id)}</h2>
            <p class="tm-panel-copy">{_html(t("twin.project_passport_copy", language))}</p>
            <div class="tm-chip-row" style="margin-top: 12px;">
              <span class="tm-chip is-accent">{_html(t("twin.passport_scope", language))}</span>
              {language_chips}
            </div>
            <div style="margin-top: 14px;">
              {_archive_metrics_html(draft, language)}
            </div>
          </div>
        </section>
        """
    )


def _archive_metrics_html(draft: ProjectArchiveDraft, language: str) -> str:
    metrics = _archive_metrics(draft)
    return (
        '<div class="tm-passport-counts">'
        + "\n".join(
            f"""
            <div class="tm-count">
              <div class="tm-count-value">{_html(_format_count(value))}</div>
              <div class="tm-count-label">{_html(t(label_key, language))}</div>
            </div>
            """
            for label_key, value in [
                ("twin.metric.halls", metrics["halls"]),
                ("twin.metric.entities", metrics["entities"]),
                ("twin.metric.relations", metrics["relations"]),
                ("twin.metric.evidence", metrics["evidence"]),
            ]
        )
        + "</div>"
    )


def _render_halls(draft: ProjectArchiveDraft, language: str) -> None:
    cards = []
    for hall in draft.halls:
        type_chips = "\n".join(
            f'<span class="tm-chip">{_html(item_type)}</span>'
            for item_type in _top_hall_type_labels(hall.entity_ids, draft)
        )
        entity_items = "\n".join(
            f"<li>{_html(_entity_display_name(entity_id, draft))}</li>"
            for entity_id in hall.entity_ids[:3]
        ) or f"<li>{_html(t('twin.no_entities', language))}</li>"
        cards.append(
            f"""
            <article class="tm-hall-card">
              <div class="tm-hall-head">
                <h3 class="tm-hall-name">{_html(hall.name)}</h3>
                <span class="tm-hall-count">{_html(len(hall.entity_ids))}</span>
              </div>
              <p class="tm-panel-copy">{_html(hall.description)}</p>
              <div class="tm-chip-row" style="margin-top: 10px;">{type_chips}</div>
              <ul class="tm-entity-list">{entity_items}</ul>
            </article>
            """
        )
    _render_html(
        f"""
        <section class="tm-panel">
          <p class="tm-panel-title">{_html(t("twin.archive_halls", language))}</p>
          <p class="tm-panel-copy">{_html(t("twin.archive_halls_copy", language))}</p>
          <div class="tm-hall-grid" style="margin-top: 12px;">
            {''.join(cards)}
          </div>
        </section>
        """
    )


def _render_star_map(draft: ProjectArchiveDraft, language: str) -> None:
    rows = _relation_rows(draft)
    if rows:
        relation_html = "\n".join(
            f"""
            <div class="tm-relation">
              <div class="tm-relation-label">{_html(row["relation"])}</div>
              <div class="tm-relation-path">{_html(row["source"])} → {_html(row["target"])}</div>
            </div>
            """
            for row in rows[:6]
        )
        _render_html(
            f"""
            <section class="tm-panel">
              <p class="tm-panel-title">{_html(t("twin.star_map", language))}</p>
              <p class="tm-panel-copy">{_html(t("twin.star_map_copy", language))}</p>
              <div class="tm-star-stage" style="margin-top: 12px;">
                <div class="tm-relation-orbit">{relation_html}</div>
              </div>
            </section>
            """
        )
        display_rows = [
            {
                t("table.source", language): row["source"],
                t("table.relation", language): row["relation"],
                t("table.target", language): row["target"],
            }
            for row in rows
        ]
        st.caption(t("twin.relation_browser", language))
        st.dataframe(display_rows[:16], use_container_width=True, hide_index=True)
    else:
        st.info(t("twin.no_relations", language))


def _render_evidence_drawer(draft: ProjectArchiveDraft, language: str) -> None:
    evidence_preview = draft.evidence_cards[:5]
    evidence_html = "\n".join(
        f"""
        <div class="tm-evidence-card">
          <p class="tm-evidence-title tm-clamp">{_html(card.title)}</p>
          <div class="tm-codepath tm-clamp">{_html(card.source_path)}</div>
          <p class="tm-panel-copy tm-clamp">{_html(card.snippet.strip()[:220])}</p>
        </div>
        """
        for card in evidence_preview
    ) or f'<p class="tm-panel-copy">{_html(t("twin.no_evidence_preview", language))}</p>'

    _render_html(
        f"""
        <aside class="tm-panel">
          <p class="tm-panel-title">{_html(t("twin.evidence_drawer_preview", language))}</p>
          <p class="tm-panel-copy">{_html(t("twin.evidence_drawer_copy", language))}</p>
          {evidence_html}
        </aside>
        """
    )


def _render_compact_type_stats(draft: ProjectArchiveDraft, language: str) -> None:
    entity_rows = _top_type_rows((entity.type for entity in draft.entities), limit=4)
    relation_rows = _top_type_rows(
        (relation.type for relation in draft.relations),
        limit=4,
    )
    entity_html = "\n".join(
        f'<div class="tm-mini-stat"><span>{_html(row["type"])}</span><strong>{_html(row["count"])}</strong></div>'
        for row in entity_rows
    )
    relation_html = "\n".join(
        f'<div class="tm-mini-stat"><span>{_html(row["type"])}</span><strong>{_html(row["count"])}</strong></div>'
        for row in relation_rows
    )
    _render_html(
        f"""
        <section class="tm-panel">
          <p class="tm-panel-title">{_html(t("twin.archive_stats", language))}</p>
          <p class="tm-workbench-label">{_html(t("twin.entity_types", language))}</p>
          {entity_html}
          <p class="tm-workbench-label" style="margin-top: 12px;">{_html(t("twin.relation_types", language))}</p>
          {relation_html}
        </section>
        """
    )


def _render_type_tables(draft: ProjectArchiveDraft, language: str) -> None:
    _render_html(
        f"""
        <div class="tm-panel">
          <p class="tm-panel-title">{_html(t("twin.archive_stats", language))}</p>
          <p class="tm-panel-copy">{_html(t("twin.archive_stats_copy", language))}</p>
        </div>
        """
    )
    col_entities, col_relations = st.columns(2)
    with col_entities:
        st.subheader(t("twin.entity_types", language))
        rows = _top_type_rows(entity.type for entity in draft.entities)
        rows = [
            {
                t("table.type", language): row["type"],
                t("table.count", language): row["count"],
            }
            for row in rows
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    with col_relations:
        st.subheader(t("twin.relation_types", language))
        rows = _top_type_rows(relation.type for relation in draft.relations)
        rows = [
            {
                t("table.type", language): row["type"],
                t("table.count", language): row["count"],
            }
            for row in rows
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_query_panel(
    service: ProjectArchiveService,
    project_id: str,
    language: str,
    draft: ProjectArchiveDraft,
) -> None:
    _render_html(
        f"""
        <section class="tm-panel">
          <p class="tm-panel-title">{_html(t("twin.agent_query", language))}</p>
          <p class="tm-panel-copy">{_html(t("twin.agent_query_copy", language))}</p>
        </section>
        """
    )
    mode = st.selectbox(
        t("twin.mode", language),
        options=list(QueryMode),
        format_func=lambda item: _mode_label(item, language),
        index=list(QueryMode).index(QueryMode.EVIDENCE_QA),
    )
    question = st.text_area(
        t("twin.question", language),
        value=t("twin.default_question", language),
        height=96,
    )
    if st.button(t("twin.run_query", language), key="twinmind_query"):
        try:
            with st.spinner(t("twin.tracing_evidence", language)):
                result = service.query_project(
                    project_id=project_id,
                    question=question.strip() or t("twin.fallback_question", language),
                    mode=mode,
                )
            _render_html(
                f'<div class="tm-agent-report">{_html(_format_agent_result(result, language, draft))}</div>',
            )
        except Exception as exc:
            st.error(t("twin.query_failed", language, error=exc))


def _render_ingestion_panel(service: ProjectArchiveService, language: str) -> None:
    _render_html(
        f"""
        <section class="tm-panel">
          <p class="tm-panel-title">{_html(t("twin.ingest_project", language))}</p>
          <p class="tm-panel-copy">{_html(t("twin.upload_intro", language))}</p>
        </section>
        """
    )
    scan_profile = st.selectbox(
        t("twin.scan_profile", language),
        options=SCAN_PROFILE_OPTIONS,
        format_func=lambda item: _scan_profile_label(item, language),
        index=SCAN_PROFILE_OPTIONS.index(SCAN_PROFILE_ARCHITECTURE),
        key="twinmind_scan_profile",
    )
    st.caption(
        t(
            SCAN_PROFILE_HELP_KEYS.get(
                scan_profile,
                SCAN_PROFILE_HELP_KEYS[SCAN_PROFILE_ARCHITECTURE],
            ),
            language,
        )
    )

    uploaded_zip = st.file_uploader(
        t("twin.project_zip", language),
        type=["zip"],
        max_upload_size=MAX_PROJECT_ZIP_UPLOAD_MB,
        key="twinmind_project_zip",
    )
    st.caption(t("twin.zip_upload_limit", language, size=MAX_PROJECT_ZIP_UPLOAD_MB))
    upload_project_id = st.text_input(
        t("twin.project_id_optional", language),
        value="",
        help=t("twin.auto_id_help", language),
        key="twinmind_upload_project_id",
    )

    if st.button(t("twin.build_uploaded_archive", language), key="twinmind_upload_ingest"):
        try:
            if uploaded_zip is not None:
                project_id = _project_id_from_upload(
                    upload_project_id,
                    zip_name=uploaded_zip.name,
                )
                project_root = _extract_project_zip(uploaded_zip, project_id, scan_profile)
            else:
                st.warning(t("twin.no_upload", language))
                return

            st.caption(t("twin.upload_saved", language, path=project_root))
            with st.spinner(t("twin.building_archive", language)):
                draft = service.ingest_project(
                    project_root=str(project_root),
                    project_id=project_id,
                    scan_profile=scan_profile,
                )
            st.success(
                t(
                    "twin.archive_built",
                    language,
                    entities=len(draft.entities),
                    relations=len(draft.relations),
                    evidence=len(draft.evidence_cards),
                )
            )
            st.session_state["twinmind_selected_project"] = draft.project_id
            st.rerun()
        except Exception as exc:
            st.error(t("twin.archive_build_failed", language, error=exc))

    with st.expander(t("twin.folder_upload_mode", language), expanded=False):
        st.caption(t("twin.folder_upload_intro", language))
        uploaded_folder = st.file_uploader(
            t("twin.project_folder", language),
            accept_multiple_files="directory",
            key="twinmind_project_folder",
        )
        folder_project_id = st.text_input(
            t("twin.project_id_optional", language),
            value="",
            help=t("twin.auto_id_help", language),
            key="twinmind_folder_project_id",
        )
        if st.button(t("twin.build_folder_archive", language), key="twinmind_folder_ingest"):
            try:
                folder_files = list(uploaded_folder or [])
                if not folder_files:
                    st.warning(t("twin.no_folder_upload", language))
                    return
                project_id = _project_id_from_upload(
                    folder_project_id,
                    folder_files=folder_files,
                )
                project_root = _save_project_folder_upload(
                    folder_files,
                    project_id,
                    scan_profile,
                )
                st.caption(t("twin.upload_saved", language, path=project_root))
                with st.spinner(t("twin.building_archive", language)):
                    draft = service.ingest_project(
                        project_root=str(project_root),
                        project_id=project_id,
                        scan_profile=scan_profile,
                    )
                st.success(
                    t(
                        "twin.archive_built",
                        language,
                        entities=len(draft.entities),
                        relations=len(draft.relations),
                        evidence=len(draft.evidence_cards),
                    )
                )
                st.session_state["twinmind_selected_project"] = draft.project_id
                st.rerun()
            except Exception as exc:
                st.error(t("twin.archive_build_failed", language, error=exc))

    with st.expander(t("twin.example_flow", language), expanded=False):
        st.caption(t("twin.example_intro", language))
        st.markdown(t("twin.example_steps", language))
        if st.button(t("twin.use_sample", language), key="twinmind_use_sample"):
            try:
                with st.spinner(t("twin.building_archive", language)):
                    draft = service.ingest_project(
                        project_root=SAMPLE_PROJECT_PATH,
                        project_id=SAMPLE_PROJECT_ID,
                        scan_profile=scan_profile,
                    )
                st.success(t("twin.sample_ready", language))
                st.session_state["twinmind_selected_project"] = draft.project_id
                st.rerun()
            except Exception as exc:
                st.error(t("twin.archive_build_failed", language, error=exc))

    with st.expander(t("twin.local_path_mode", language), expanded=False):
        st.caption(t("twin.local_path_intro", language))
        col_path, col_id = st.columns([3, 1])
        with col_path:
            project_path = st.text_input(
                t("twin.project_path", language),
                value=".",
                key="twinmind_project_path",
            )
        with col_id:
            project_id = st.text_input(
                t("twin.project_id_optional", language),
                value="",
                help=t("twin.auto_id_help", language),
                key="twinmind_project_id",
            )

        if st.button(t("twin.build_archive", language), key="twinmind_ingest"):
            try:
                resolved_project_id = _project_id_from_upload(
                    project_id,
                    fallback=Path(project_path).name,
                )
                with st.spinner(t("twin.building_archive", language)):
                    draft = service.ingest_project(
                        project_root=project_path,
                        project_id=resolved_project_id,
                        scan_profile=scan_profile,
                    )
                st.success(
                    t(
                        "twin.archive_built",
                        language,
                        entities=len(draft.entities),
                        relations=len(draft.relations),
                        evidence=len(draft.evidence_cards),
                    )
                )
                st.session_state["twinmind_selected_project"] = draft.project_id
                st.rerun()
            except Exception as exc:
                st.error(t("twin.archive_build_failed", language, error=exc))


def render() -> None:
    """Render the TwinMind Archive page."""
    language = current_language()
    _inject_archive_observatory_css()
    _render_archive_header(language)

    with st.sidebar.expander(t("twin.storage_settings", language), expanded=False):
        storage_dir = Path(
            st.text_input(
                t("twin.archive_storage", language),
                value=str(ARCHIVE_STORAGE_DIR),
            )
        )
    service = ProjectArchiveService(storage_dir=storage_dir)

    _render_ingestion_panel(service, language)
    st.divider()

    project_ids = _list_archived_project_ids(storage_dir)
    if not project_ids:
        _render_empty_archive_notice(language)
        return

    selected_default = st.session_state.get("twinmind_selected_project")
    default_index = (
        project_ids.index(selected_default)
        if selected_default in project_ids
        else 0
    )
    project_id = st.selectbox(
        t("twin.project_archive", language),
        options=project_ids,
        index=default_index,
    )

    try:
        draft = service.load_draft(project_id)
    except Exception as exc:
        st.error(t("twin.load_failed", language, error=exc))
        return

    _render_project_passport(draft, project_id, language)
    left_col, center_col, right_col = st.columns([0.9, 1.55, 0.95], gap="medium")
    with left_col:
        _render_halls(draft, language)
    with center_col:
        _render_star_map(draft, language)
    with right_col:
        _render_evidence_drawer(draft, language)
        _render_compact_type_stats(draft, language)
    _render_query_panel(service, project_id, language, draft)
