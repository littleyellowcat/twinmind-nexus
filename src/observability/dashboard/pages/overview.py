"""Overview page – system configuration and data statistics.

Displays:
- Component configuration cards (LLM, Embedding, VectorStore …)
- Collection statistics (document count, chunk count, image count)
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from src.observability.dashboard.i18n import current_language, t
from src.observability.dashboard.services.config_service import ConfigService


def _safe_collection_stats() -> dict[str, Any]:
    """Attempt to load collection statistics from ChromaDB.

    Returns empty dict on failure so the page still renders.
    """
    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        from src.core.settings import load_settings, resolve_path

        settings = load_settings()
        persist_dir = str(
            resolve_path(settings.vector_store.persist_directory)
        )
        client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        stats: dict[str, Any] = {}
        for col in client.list_collections():
            name = col.name if hasattr(col, "name") else str(col)
            collection = client.get_collection(name)
            stats[name] = {"chunk_count": collection.count()}
        return stats
    except Exception:
        return {}


def render() -> None:
    """Render the Overview page."""
    language = current_language()
    st.header(f"📊 {t('overview.header', language)}")

    # ── Component configuration cards ──────────────────────────────
    st.subheader(f"🔧 {t('overview.components', language)}")

    try:
        config_service = ConfigService()
        cards = config_service.get_component_cards()
    except Exception as exc:
        st.error(t("overview.load_failed", language, error=exc))
        return

    cols = st.columns(min(len(cards), 3))
    for idx, card in enumerate(cards):
        with cols[idx % len(cols)]:
            st.markdown(f"**{t(f'component.{card.name}', language)}**")
            st.caption(
                f"{t('overview.provider', language)}: `{card.provider}`  \n"
                f"{t('overview.model', language)}: `{card.model}`"
            )
            with st.expander(t("overview.details", language)):
                for k, v in card.extra.items():
                    st.text(f"{k}: {v}")

    # ── Collection statistics ──────────────────────────────────────
    st.subheader(f"📁 {t('overview.collections', language)}")

    stats = _safe_collection_stats()
    if stats:
        stat_cols = st.columns(min(len(stats), 4))
        for idx, (name, info) in enumerate(sorted(stats.items())):
            with stat_cols[idx % len(stat_cols)]:
                count = info.get("chunk_count", "?")
                st.metric(label=name, value=count)
                if count == 0 or count == "?":
                    st.caption(f"⚠️ {t('overview.empty', language)}")
    else:
        st.warning(t("overview.no_collections", language))

    # ── Trace file statistics ──────────────────────────────────────
    st.subheader(f"📈 {t('overview.traces', language)}")

    from src.core.settings import resolve_path
    traces_path = resolve_path("logs/traces.jsonl")
    if traces_path.exists():
        line_count = sum(1 for _ in traces_path.open(encoding="utf-8"))
        if line_count > 0:
            st.metric(t("overview.total_traces", language), line_count)
        else:
            st.info(t("overview.no_traces", language))
    else:
        st.info(t("overview.no_traces", language))
