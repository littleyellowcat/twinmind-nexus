"""Modular RAG Dashboard – multi-page Streamlit application.

Entry-point: ``streamlit run src/observability/dashboard/app.py``

Pages are registered via ``st.navigation()`` and rendered by their
respective modules under ``pages/``.  Pages not yet implemented show
a placeholder message.
"""

from __future__ import annotations

import streamlit as st

from src.observability.dashboard.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGE_OPTIONS,
    LANGUAGE_STATE_KEY,
    normalize_language,
    t,
)

# ── Page definitions ─────────────────────────────────────────────────

def _page_overview() -> None:
    from src.observability.dashboard.pages.overview import render
    render()


def _page_data_browser() -> None:
    from src.observability.dashboard.pages.data_browser import render
    render()


def _page_ingestion_manager() -> None:
    from src.observability.dashboard.pages.ingestion_manager import render
    render()


def _page_ingestion_traces() -> None:
    from src.observability.dashboard.pages.ingestion_traces import render
    render()


def _page_query_traces() -> None:
    from src.observability.dashboard.pages.query_traces import render
    render()


def _page_evaluation_panel() -> None:
    from src.observability.dashboard.pages.evaluation_panel import render
    render()


def _page_twinmind_archive() -> None:
    from src.observability.dashboard.pages.twinmind_archive import render
    render()


# ── Navigation ───────────────────────────────────────────────────────


def _current_language() -> str:
    language = normalize_language(st.session_state.get(LANGUAGE_STATE_KEY))
    st.session_state[LANGUAGE_STATE_KEY] = language
    return language


def _render_language_switcher(language: str) -> str:
    selected = st.sidebar.radio(
        t("language.label", language),
        options=list(LANGUAGE_OPTIONS),
        index=list(LANGUAGE_OPTIONS).index(language),
        format_func=lambda code: t(f"language.{code}", language),
        horizontal=True,
        key="dashboard_language_selector",
    )
    selected = normalize_language(selected)
    if selected != language:
        st.session_state[LANGUAGE_STATE_KEY] = selected
        st.rerun()
    return selected


def _build_pages(language: str) -> list[st.Page]:
    return [
        st.Page(
            _page_overview,
            title=t("nav.overview", language),
            icon="📊",
            default=True,
        ),
        st.Page(_page_data_browser, title=t("nav.data_browser", language), icon="🔍"),
        st.Page(
            _page_ingestion_manager,
            title=t("nav.ingestion_manager", language),
            icon="📥",
        ),
        st.Page(
            _page_ingestion_traces,
            title=t("nav.ingestion_traces", language),
            icon="🔬",
        ),
        st.Page(_page_query_traces, title=t("nav.query_traces", language), icon="🔎"),
        st.Page(
            _page_evaluation_panel,
            title=t("nav.evaluation_panel", language),
            icon="📏",
        ),
        st.Page(
            _page_twinmind_archive,
            title=t("nav.twinmind_archive", language),
            icon="🗂️",
        ),
    ]


def main() -> None:
    st.set_page_config(
        page_title=t("app.page_title", DEFAULT_LANGUAGE),
        page_icon="📊",
        layout="wide",
    )

    language = _render_language_switcher(_current_language())
    nav = st.navigation(_build_pages(language))
    nav.run()


if __name__ == "__main__":
    main()
else:
    # When run directly via `streamlit run app.py`
    main()
