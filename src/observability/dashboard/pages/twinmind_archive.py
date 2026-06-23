"""TwinMind Archive dashboard page.

Provides a lightweight project-archive workbench for ingesting local projects,
inspecting archive halls, viewing graph relationships, and querying the
deterministic TwinMind agent workflows.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import streamlit as st

from src.project_archive.service import ProjectArchiveService
from src.project_archive.types import AgentResult, ProjectArchiveDraft, QueryMode

ARCHIVE_STORAGE_DIR = Path("data/project_archive")

MODE_LABELS = {
    QueryMode.ARCHITECTURE_TOUR: "Architecture Tour",
    QueryMode.IMPACT_ANALYSIS: "Impact Analysis",
    QueryMode.RISK_AUDIT: "Risk Audit",
    QueryMode.EVIDENCE_QA: "Evidence Q&A",
}


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


def _top_type_rows(values: Iterable[str], limit: int = 8) -> list[dict[str, Any]]:
    """Build rows for compact type distribution tables."""
    return [
        {"type": item_type, "count": count}
        for item_type, count in Counter(values).most_common(limit)
    ]


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


def _format_agent_result(result: AgentResult) -> str:
    """Format a deterministic agent result for display."""
    lines = [
        f"Mode: {MODE_LABELS.get(result.mode, result.mode.value)}",
        f"Confidence: {result.confidence:.2f}",
        "",
        result.summary,
    ]
    if result.affected_entities:
        lines.extend(["", "Affected entities:", *_bullet_lines(result.affected_entities)])
    if result.evidence_card_ids:
        lines.extend(["", "Evidence cards:", *_bullet_lines(result.evidence_card_ids)])
    if result.risks:
        lines.extend(["", "Risks:", *_bullet_lines(result.risks)])
    if result.next_actions:
        lines.extend(["", "Next actions:", *_bullet_lines(result.next_actions)])
    return "\n".join(lines)


def _bullet_lines(values: Iterable[str]) -> list[str]:
    return [f"- {value}" for value in values]


def _render_metrics(draft: ProjectArchiveDraft) -> None:
    metrics = _archive_metrics(draft)
    cols = st.columns(4)
    cols[0].metric("Halls", metrics["halls"])
    cols[1].metric("Entities", metrics["entities"])
    cols[2].metric("Relations", metrics["relations"])
    cols[3].metric("Evidence", metrics["evidence"])


def _render_halls(draft: ProjectArchiveDraft) -> None:
    st.subheader("Archive Halls")
    cols = st.columns(2)
    for idx, hall in enumerate(draft.halls):
        with cols[idx % 2]:
            with st.expander(f"{hall.name} ({len(hall.entity_ids)})"):
                st.caption(hall.description)
                if hall.entity_ids:
                    st.write(", ".join(hall.entity_ids[:12]))
                else:
                    st.write("No entities assigned yet.")


def _render_star_map(draft: ProjectArchiveDraft) -> None:
    st.subheader("Star Map")
    rows = _relation_rows(draft)
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No archive relations were extracted yet.")


def _render_type_tables(draft: ProjectArchiveDraft) -> None:
    col_entities, col_relations = st.columns(2)
    with col_entities:
        st.subheader("Entity Types")
        rows = _top_type_rows(entity.type for entity in draft.entities)
        st.dataframe(rows, use_container_width=True, hide_index=True)
    with col_relations:
        st.subheader("Relation Types")
        rows = _top_type_rows(relation.type for relation in draft.relations)
        st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_query_panel(service: ProjectArchiveService, project_id: str) -> None:
    st.subheader("Agent Query")
    mode = st.selectbox(
        "Mode",
        options=list(QueryMode),
        format_func=lambda item: MODE_LABELS[item],
        index=list(QueryMode).index(QueryMode.EVIDENCE_QA),
    )
    question = st.text_area(
        "Question",
        value="What should I understand first about this project?",
        height=96,
    )
    if st.button("Run Query", key="twinmind_query"):
        try:
            with st.spinner("Tracing archive evidence..."):
                result = service.query_project(
                    project_id=project_id,
                    question=question.strip() or "Summarize this project archive.",
                    mode=mode,
                )
            st.markdown(_format_agent_result(result))
        except Exception as exc:
            st.error(f"Query failed: {exc}")


def _render_ingestion_panel(service: ProjectArchiveService) -> None:
    st.subheader("Ingest Project")
    col_path, col_id = st.columns([3, 1])
    with col_path:
        project_path = st.text_input("Project path", value=".")
    with col_id:
        project_id = st.text_input("Project ID", value="current-project")

    if st.button("Build Archive", key="twinmind_ingest"):
        try:
            with st.spinner("Building TwinMind archive..."):
                draft = service.ingest_project(
                    project_root=project_path,
                    project_id=project_id.strip() or "current-project",
                )
            st.success(
                "Archive built: "
                f"{len(draft.entities)} entities, "
                f"{len(draft.relations)} relations, "
                f"{len(draft.evidence_cards)} evidence cards."
            )
            st.session_state["twinmind_selected_project"] = draft.project_id
            st.rerun()
        except Exception as exc:
            st.error(f"Archive build failed: {exc}")


def render() -> None:
    """Render the TwinMind Archive page."""
    st.header("TwinMind Archive")

    storage_dir = Path(
        st.text_input("Archive storage", value=str(ARCHIVE_STORAGE_DIR))
    )
    service = ProjectArchiveService(storage_dir=storage_dir)

    _render_ingestion_panel(service)
    st.divider()

    project_ids = _list_archived_project_ids(storage_dir)
    if not project_ids:
        st.info("No project archives found yet.")
        return

    selected_default = st.session_state.get("twinmind_selected_project")
    default_index = (
        project_ids.index(selected_default)
        if selected_default in project_ids
        else 0
    )
    project_id = st.selectbox(
        "Project archive",
        options=project_ids,
        index=default_index,
    )

    try:
        draft = service.load_draft(project_id)
    except Exception as exc:
        st.error(f"Failed to load project archive: {exc}")
        return

    _render_metrics(draft)
    _render_halls(draft)
    _render_star_map(draft)
    _render_type_tables(draft)
    _render_query_panel(service, project_id)
