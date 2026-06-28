from __future__ import annotations

import base64
from dataclasses import replace

from src.project_archive import hybrid_rag
from src.project_archive.service import ProjectArchiveService
from src.project_archive.types import QueryMode

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def test_project_ingest_builds_hybrid_rag_index_and_image_evidence(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "README.md").write_text(
        "# Demo\n\nThis project contains a visual architecture diagram.",
        encoding="utf-8",
    )
    (project_root / "settings.yaml").write_text(
        "retrieval:\n  fusion_top_k: 5\n",
        encoding="utf-8",
    )
    (project_root / "diagram.png").write_bytes(PNG_1X1)

    service = ProjectArchiveService(storage_dir=tmp_path / "archives")
    draft = service.ingest_project(
        project_root=project_root,
        project_id="demo-hybrid",
        scan_profile="architecture",
    )
    status = service.hybrid_rag_status("demo-hybrid")

    assert status["indexed_chunks"] > 0
    assert status["image_chunks"] == 1
    assert status["dense_provider"] in {"local_hash", "ollama"}
    assert status["dense_dimension"] > 0
    assert any(card.source_type == "image" for card in draft.evidence_cards)


def test_project_ingest_falls_back_to_local_hash_when_embedding_unavailable(
    tmp_path,
    monkeypatch,
):
    settings = hybrid_rag.load_settings()
    monkeypatch.setattr(
        hybrid_rag,
        "load_settings",
        lambda: replace(
            settings,
            embedding=replace(settings.embedding, provider="missing-provider"),
        ),
    )
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "README.md").write_text(
        "# Demo\n\nThis project should still index with fallback embeddings.",
        encoding="utf-8",
    )

    service = ProjectArchiveService(storage_dir=tmp_path / "archives")
    service.ingest_project(
        project_root=project_root,
        project_id="demo-local-hash",
        scan_profile="architecture",
    )
    status = service.hybrid_rag_status("demo-local-hash")

    assert status["indexed_chunks"] > 0
    assert status["dense_provider"] == "local_hash"
    assert status["dense_dimension"] == hybrid_rag.LocalHashEmbedding.dimension
    assert any("Configured embedding unavailable" in reason for reason in status["fallback_reasons"])


def test_project_query_uses_hybrid_rag_context(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "README.md").write_text(
        "# Demo\n\nThe API layer uses Chroma, BM25, and RRF retrieval.",
        encoding="utf-8",
    )
    (project_root / "diagram.png").write_bytes(PNG_1X1)

    service = ProjectArchiveService(storage_dir=tmp_path / "archives")
    service.ingest_project(
        project_root=project_root,
        project_id="demo-query",
        scan_profile="architecture",
    )

    result = service.query_project(
        project_id="demo-query",
        question="Where is BM25 retrieval mentioned?",
        mode=QueryMode.EVIDENCE_QA,
    )

    assert result.metadata["hybrid_rag"]["enabled"] is True
    assert result.metadata["hybrid_rag"]["result_count"] > 0
    assert result.evidence_card_ids
