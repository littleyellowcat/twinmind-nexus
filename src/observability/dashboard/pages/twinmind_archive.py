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

from src.observability.dashboard.i18n import current_language, t
from src.project_archive.service import ProjectArchiveService
from src.project_archive.types import AgentResult, ProjectArchiveDraft, QueryMode

ARCHIVE_STORAGE_DIR = Path("data/project_archive")

MODE_LABEL_KEYS = {
    QueryMode.ARCHITECTURE_TOUR: "twin.mode.architecture_tour",
    QueryMode.IMPACT_ANALYSIS: "twin.mode.impact_analysis",
    QueryMode.RISK_AUDIT: "twin.mode.risk_audit",
    QueryMode.EVIDENCE_QA: "twin.mode.evidence_qa",
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


def _mode_label(mode: QueryMode, language: str = "en") -> str:
    return t(MODE_LABEL_KEYS.get(mode, mode.value), language)


def _format_agent_result(result: AgentResult, language: str = "en") -> str:
    """Format a deterministic agent result for display."""
    lines = [
        f"{t('twin.result.mode', language)}: {_mode_label(result.mode, language)}",
        f"{t('twin.result.confidence', language)}: {result.confidence:.2f}",
        "",
        result.summary,
    ]
    if result.affected_entities:
        lines.extend(
            ["", f"{t('twin.result.affected_entities', language)}:", *_bullet_lines(result.affected_entities)]
        )
    if result.evidence_card_ids:
        lines.extend(
            ["", f"{t('twin.result.evidence_cards', language)}:", *_bullet_lines(result.evidence_card_ids)]
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


def _render_metrics(draft: ProjectArchiveDraft, language: str) -> None:
    metrics = _archive_metrics(draft)
    cols = st.columns(4)
    cols[0].metric(t("twin.metric.halls", language), metrics["halls"])
    cols[1].metric(t("twin.metric.entities", language), metrics["entities"])
    cols[2].metric(t("twin.metric.relations", language), metrics["relations"])
    cols[3].metric(t("twin.metric.evidence", language), metrics["evidence"])


def _render_halls(draft: ProjectArchiveDraft, language: str) -> None:
    st.subheader(t("twin.archive_halls", language))
    cols = st.columns(2)
    for idx, hall in enumerate(draft.halls):
        with cols[idx % 2]:
            with st.expander(f"{hall.name} ({len(hall.entity_ids)})"):
                st.caption(hall.description)
                if hall.entity_ids:
                    st.write(", ".join(hall.entity_ids[:12]))
                else:
                    st.write(t("twin.no_entities", language))


def _render_star_map(draft: ProjectArchiveDraft, language: str) -> None:
    st.subheader(t("twin.star_map", language))
    rows = _relation_rows(draft)
    if rows:
        display_rows = [
            {
                t("table.source", language): row["source"],
                t("table.relation", language): row["relation"],
                t("table.target", language): row["target"],
            }
            for row in rows
        ]
        st.dataframe(display_rows, use_container_width=True, hide_index=True)
    else:
        st.info(t("twin.no_relations", language))


def _render_type_tables(draft: ProjectArchiveDraft, language: str) -> None:
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
    service: ProjectArchiveService, project_id: str, language: str
) -> None:
    st.subheader(t("twin.agent_query", language))
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
            st.markdown(_format_agent_result(result, language))
        except Exception as exc:
            st.error(t("twin.query_failed", language, error=exc))


def _render_ingestion_panel(service: ProjectArchiveService, language: str) -> None:
    st.subheader(t("twin.ingest_project", language))
    col_path, col_id = st.columns([3, 1])
    with col_path:
        project_path = st.text_input(t("twin.project_path", language), value=".")
    with col_id:
        project_id = st.text_input(t("twin.project_id", language), value="current-project")

    if st.button(t("twin.build_archive", language), key="twinmind_ingest"):
        try:
            with st.spinner(t("twin.building_archive", language)):
                draft = service.ingest_project(
                    project_root=project_path,
                    project_id=project_id.strip() or "current-project",
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
    st.header(t("twin.header", language))

    storage_dir = Path(
        st.text_input(t("twin.archive_storage", language), value=str(ARCHIVE_STORAGE_DIR))
    )
    service = ProjectArchiveService(storage_dir=storage_dir)

    _render_ingestion_panel(service, language)
    st.divider()

    project_ids = _list_archived_project_ids(storage_dir)
    if not project_ids:
        st.info(t("twin.no_archives", language))
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

    _render_metrics(draft, language)
    _render_halls(draft, language)
    _render_star_map(draft, language)
    _render_type_tables(draft, language)
    _render_query_panel(service, project_id, language)
