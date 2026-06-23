"""Ingestion Manager page – upload files, trigger ingestion, delete documents.

Layout:
1. File uploader + collection selector
2. Ingest button → progress bar (using on_progress callback)
3. Document list with delete buttons
"""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import streamlit as st

from src.observability.dashboard.i18n import current_language, t
from src.observability.dashboard.services.data_service import DataService


def _run_ingestion(
    uploaded_file: st.runtime.uploaded_file_manager.UploadedFile,
    collection: str,
    progress_bar: st.delta_generator.DeltaGenerator,
    status_text: st.delta_generator.DeltaGenerator,
    language: str,
) -> None:
    """Save the uploaded file to a temp location and run the pipeline."""
    from src.core.settings import load_settings
    from src.core.trace import TraceCollector, TraceContext
    from src.ingestion.pipeline import IngestionPipeline

    settings = load_settings()

    # Write uploaded file to a temp location
    suffix = Path(uploaded_file.name).suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name

    stage_labels = {
        "integrity": f"🔍 {t('ingest.stage.integrity', language)}",
        "load": f"📄 {t('ingest.stage.load', language)}",
        "split": f"✂️ {t('ingest.stage.split', language)}",
        "transform": f"🔄 {t('ingest.stage.transform', language)}",
        "embed": f"🔢 {t('ingest.stage.embed', language)}",
        "upsert": f"💾 {t('ingest.stage.upsert', language)}",
    }

    def on_progress(stage: str, current: int, total: int) -> None:
        frac = (current - 1) / total  # stage just started, show partial progress
        label = stage_labels.get(stage, stage)
        progress_bar.progress(frac, text=f"[{current}/{total}] {label}")
        status_text.caption(label)

    trace = TraceContext(trace_type="ingestion")
    trace.metadata["source_path"] = uploaded_file.name
    trace.metadata["collection"] = collection
    trace.metadata["source"] = "dashboard"

    try:
        pipeline = IngestionPipeline(settings, collection=collection)
        pipeline.run(
            file_path=tmp_path,
            trace=trace,
            on_progress=on_progress,
        )
        progress_bar.progress(1.0, text=f"✅ {t('ingest.complete', language)}")
        status_text.success(
            t("ingest.success", language, file=uploaded_file.name, collection=collection)
        )
    except Exception as exc:
        status_text.error(t("ingest.failed", language, error=exc))
    finally:
        TraceCollector().collect(trace)
        # Clean up temp file
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


def render() -> None:
    """Render the Ingestion Manager page."""
    language = current_language()
    st.header(f"📥 {t('ingest.header', language)}")

    # ── Upload section ─────────────────────────────────────────────
    st.subheader(f"📤 {t('ingest.upload', language)}")

    col1, col2 = st.columns([3, 1])
    with col1:
        uploaded = st.file_uploader(
            t("ingest.select_file", language),
            type=["pdf", "txt", "md", "docx"],
            key="ingest_uploader",
        )
    with col2:
        collection = st.text_input(
            t("ingest.collection", language),
            value="default",
            key="ingest_collection",
        )

    if uploaded is not None:
        if st.button(f"🚀 {t('ingest.start', language)}", key="btn_ingest"):
            progress_bar = st.progress(0, text=t("ingest.preparing", language))
            status_text = st.empty()
            _run_ingestion(
                uploaded,
                collection.strip() or "default",
                progress_bar,
                status_text,
                language,
            )

    st.divider()

    # ── Document management section ────────────────────────────────
    st.subheader(f"🗑️ {t('ingest.manage', language)}")

    try:
        svc = DataService()
        docs = svc.list_documents()
    except Exception as exc:
        st.error(t("ingest.load_docs_failed", language, error=exc))
        return

    if not docs:
        st.info(t("ingest.no_docs", language))
        return

    for idx, doc in enumerate(docs):
        col_info, col_btn = st.columns([4, 1])
        with col_info:
            st.markdown(
                f"**{doc['source_path']}** — "
                f"{t('ingest.collection', language)}: `{doc.get('collection', '—')}` | "
                f"{t('data.chunks', language)}: {doc['chunk_count']} | "
                f"{t('data.images', language)}: {doc['image_count']}"
            )
        with col_btn:
            if st.button(f"🗑️ {t('ingest.delete', language)}", key=f"del_{idx}"):
                try:
                    result = svc.delete_document(
                        source_path=doc["source_path"],
                        collection=doc.get("collection", "default"),
                        source_hash=doc.get("source_hash"),
                    )
                    if result.success:
                        st.success(
                            t(
                                "ingest.deleted",
                                language,
                                chunks=result.chunks_deleted,
                                images=result.images_deleted,
                            )
                        )
                        st.rerun()
                    else:
                        st.warning(
                            t("ingest.partial_delete", language, errors=result.errors)
                        )
                except Exception as exc:
                    st.error(t("ingest.delete_failed", language, error=exc))
