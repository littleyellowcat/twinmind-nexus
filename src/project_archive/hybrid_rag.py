"""Project-scoped multimodal Hybrid RAG index for TwinMind Archive."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.query_engine.dense_retriever import DenseRetriever
from src.core.query_engine.fusion import RRFFusion
from src.core.query_engine.hybrid_search import HybridSearch, HybridSearchConfig
from src.core.query_engine.query_processor import QueryProcessor
from src.core.query_engine.sparse_retriever import SparseRetriever
from src.core.settings import load_settings
from src.core.types import Chunk, RetrievalResult
from src.ingestion.embedding.sparse_encoder import SparseEncoder
from src.ingestion.storage.bm25_indexer import BM25Indexer
from src.libs.embedding.base_embedding import BaseEmbedding
from src.libs.embedding.embedding_factory import EmbeddingFactory
from src.libs.llm import LLMFactory
from src.libs.llm.base_vision_llm import ImageInput
from src.libs.vector_store.chroma_store import ChromaStore
from src.project_archive.types import (
    EvidenceCard,
    ProjectArchiveDraft,
)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
MAX_IMAGE_BYTES = 6 * 1024 * 1024
MAX_IMAGES_PER_PROJECT = 16
DEFAULT_COLLECTION_PREFIX = "twinmind_project_chunks"


@dataclass(frozen=True)
class HybridRAGBuildResult:
    project_id: str
    indexed_chunks: int
    text_chunks: int
    image_chunks: int
    image_evidence_cards: list[EvidenceCard]
    dense_provider: str
    dense_dimension: int
    vision_provider: str
    vision_enabled: bool
    fallback_reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "indexed_chunks": self.indexed_chunks,
            "text_chunks": self.text_chunks,
            "image_chunks": self.image_chunks,
            "image_evidence_cards": [card.to_dict() for card in self.image_evidence_cards],
            "dense_provider": self.dense_provider,
            "dense_dimension": self.dense_dimension,
            "vision_provider": self.vision_provider,
            "vision_enabled": self.vision_enabled,
            "fallback_reasons": list(self.fallback_reasons),
        }


@dataclass(frozen=True)
class HybridRAGSearchResult:
    project_id: str
    query: str
    results: list[RetrievalResult]
    dense_count: int
    sparse_count: int
    used_fallback: bool
    dense_error: str | None
    sparse_error: str | None
    dense_provider: str
    dense_dimension: int
    collection_name: str

    def to_metadata(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "query": self.query,
            "result_count": len(self.results),
            "dense_count": self.dense_count,
            "sparse_count": self.sparse_count,
            "used_fallback": self.used_fallback,
            "dense_error": self.dense_error,
            "sparse_error": self.sparse_error,
            "dense_provider": self.dense_provider,
            "dense_dimension": self.dense_dimension,
            "collection_name": self.collection_name,
            "chunk_ids": [result.chunk_id for result in self.results],
        }


class ProjectHybridRAGIndex:
    """Build and query project archive chunks through Chroma + BM25 + RRF."""

    def __init__(self, storage_dir: Path | str = "data/project_archive") -> None:
        self.storage_dir = Path(storage_dir)

    def build(
        self,
        *,
        project_root: Path | str,
        draft: ProjectArchiveDraft,
    ) -> HybridRAGBuildResult:
        project_root = Path(project_root)
        project_dir = self._project_dir(draft.project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        fallback_reasons: list[str] = []

        image_cards = self._build_image_evidence(project_root, draft.project_id)
        chunks = self._build_chunks(draft=draft, image_cards=image_cards)
        if not chunks:
            result = HybridRAGBuildResult(
                project_id=draft.project_id,
                indexed_chunks=0,
                text_chunks=0,
                image_chunks=0,
                image_evidence_cards=image_cards,
                dense_provider="none",
                dense_dimension=0,
                vision_provider="none",
                vision_enabled=False,
                fallback_reasons=["No chunks were available for Hybrid RAG indexing."],
            )
            self._status_path(draft.project_id).write_text(
                json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return result

        embedding, dense_provider, dense_dimension, reason = self._create_embedding()
        if reason:
            fallback_reasons.append(reason)

        try:
            vectors = embedding.embed([chunk.text for chunk in chunks])
        except Exception as exc:
            fallback_reasons.append(f"Configured embedding failed; using local hash embedding: {exc}")
            embedding = LocalHashEmbedding()
            dense_provider = embedding.provider
            dense_dimension = embedding.dimension
            vectors = embedding.embed([chunk.text for chunk in chunks])

        vector_store = self._create_vector_store(
            dense_provider=dense_provider,
            dense_dimension=dense_dimension,
        )
        vector_store.delete_by_metadata({"project_id": draft.project_id})
        vector_store.upsert(
            [
                {
                    "id": chunk.id,
                    "vector": vector,
                    "metadata": {**chunk.metadata, "text": chunk.text},
                }
                for chunk, vector in zip(chunks, vectors, strict=True)
            ]
        )

        sparse_stats = SparseEncoder().encode(chunks)
        BM25Indexer(index_dir=str(self._bm25_dir())).rebuild(
            sparse_stats,
            collection=self._project_collection(draft.project_id),
        )

        vision_status = self._vision_status(image_cards)
        result = HybridRAGBuildResult(
            project_id=draft.project_id,
            indexed_chunks=len(chunks),
            text_chunks=sum(1 for chunk in chunks if chunk.metadata.get("modality") == "text"),
            image_chunks=sum(1 for chunk in chunks if chunk.metadata.get("modality") == "image"),
            image_evidence_cards=image_cards,
            dense_provider=dense_provider,
            dense_dimension=dense_dimension,
            vision_provider=vision_status["provider"],
            vision_enabled=vision_status["enabled"],
            fallback_reasons=fallback_reasons
            + [
                str(card.metadata.get("vision_error"))
                for card in image_cards
                if card.metadata.get("vision_error")
            ],
        )
        self._status_path(draft.project_id).write_text(
            json.dumps(
                {
                    **result.to_dict(),
                    "collection_name": self._collection_name(dense_provider, dense_dimension),
                    "bm25_collection": self._project_collection(draft.project_id),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return result

    def search(
        self,
        *,
        project_id: str,
        query: str,
        hall_id: str | None = None,
        top_k: int = 8,
    ) -> HybridRAGSearchResult | None:
        status = self.load_status(project_id)
        if not status or int(status.get("indexed_chunks", 0)) <= 0:
            return None

        dense_provider = str(status.get("dense_provider", "local_hash"))
        dense_dimension = int(status.get("dense_dimension", LocalHashEmbedding.dimension))
        collection_name = str(
            status.get("collection_name")
            or self._collection_name(dense_provider, dense_dimension)
        )
        vector_store = self._create_vector_store(
            dense_provider=dense_provider,
            dense_dimension=dense_dimension,
            collection_name=collection_name,
        )

        embedding: BaseEmbedding | None
        dense_error: str | None = None
        if dense_provider == LocalHashEmbedding.provider:
            embedding = LocalHashEmbedding(dimension=dense_dimension)
        else:
            try:
                embedding = self._create_configured_embedding()[0]
            except Exception as exc:
                embedding = None
                dense_error = f"Configured embedding unavailable for dense search: {exc}"

        dense_retriever = (
            DenseRetriever(embedding_client=embedding, vector_store=vector_store)
            if embedding is not None
            else None
        )
        sparse_retriever = SparseRetriever(
            bm25_indexer=BM25Indexer(index_dir=str(self._bm25_dir())),
            vector_store=vector_store,
            default_collection=self._project_collection(project_id),
        )
        hybrid = HybridSearch(
            query_processor=QueryProcessor(),
            dense_retriever=dense_retriever,
            sparse_retriever=sparse_retriever,
            fusion=RRFFusion(k=60),
            config=HybridSearchConfig(
                dense_top_k=max(top_k * 2, 10),
                sparse_top_k=max(top_k * 2, 10),
                fusion_top_k=top_k,
                enable_dense=dense_retriever is not None,
                enable_sparse=True,
                parallel_retrieval=dense_retriever is not None,
                metadata_filter_post=True,
            ),
        )
        details = hybrid.search(
            query,
            top_k=max(top_k * 2, 10),
            filters={"project_id": project_id},
            return_details=True,
        )
        results = details.results
        if hall_id:
            results = [
                result for result in results if _metadata_contains_hall(result.metadata, hall_id)
            ]
        results = results[:top_k]
        return HybridRAGSearchResult(
            project_id=project_id,
            query=query,
            results=results,
            dense_count=len(details.dense_results or []),
            sparse_count=len(details.sparse_results or []),
            used_fallback=details.used_fallback or bool(dense_error),
            dense_error=dense_error or details.dense_error,
            sparse_error=details.sparse_error,
            dense_provider=dense_provider,
            dense_dimension=dense_dimension,
            collection_name=collection_name,
        )

    def load_status(self, project_id: str) -> dict[str, Any] | None:
        path = self._status_path(project_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _build_chunks(
        self,
        *,
        draft: ProjectArchiveDraft,
        image_cards: list[EvidenceCard],
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        hall_ids_by_entity = _hall_ids_by_entity(draft)
        for index, card in enumerate([*draft.evidence_cards, *image_cards]):
            hall_ids = sorted(
                {
                    hall_id
                    for entity_id in card.linked_entities
                    for hall_id in hall_ids_by_entity.get(entity_id, [])
                }
            )
            chunks.append(
                Chunk(
                    id=_chunk_id(draft.project_id, "evidence", card.id),
                    text=(
                        f"Evidence: {card.title}\n"
                        f"Source: {card.source_path}\n"
                        f"Type: {card.source_type}\n"
                        f"Content:\n{card.snippet}"
                    ),
                    metadata={
                        "project_id": draft.project_id,
                        "chunk_kind": "evidence",
                        "evidence_id": card.id,
                        "source_path": card.source_path,
                        "source_type": card.source_type,
                        "modality": "image" if card.source_type == "image" else "text",
                        "hall_ids": ",".join(hall_ids),
                        "chunk_index": index,
                    },
                )
            )

        entity_lookup = {entity.id: entity for entity in draft.entities}
        for index, entity in enumerate(draft.entities):
            related_relations = [
                relation
                for relation in draft.relations
                if relation.source_id == entity.id or relation.target_id == entity.id
            ][:12]
            chunks.append(
                Chunk(
                    id=_chunk_id(draft.project_id, "entity", entity.id),
                    text=(
                        f"Entity: {entity.name}\n"
                        f"Type: {entity.type}\n"
                        f"Path: {entity.source_path or ''}\n"
                        f"Relations: "
                        + "; ".join(
                            f"{relation.source_id} {relation.type} {relation.target_id}"
                            for relation in related_relations
                        )
                    ),
                    metadata={
                        "project_id": draft.project_id,
                        "chunk_kind": "entity",
                        "entity_id": entity.id,
                        "source_path": entity.source_path or entity.name,
                        "source_type": entity.type,
                        "modality": "text",
                        "hall_ids": ",".join(hall_ids_by_entity.get(entity.id, [])),
                        "chunk_index": index,
                    },
                )
            )

        for index, relation in enumerate(draft.relations):
            source = entity_lookup.get(relation.source_id)
            target = entity_lookup.get(relation.target_id)
            source_halls = set(hall_ids_by_entity.get(relation.source_id, []))
            target_halls = set(hall_ids_by_entity.get(relation.target_id, []))
            chunks.append(
                Chunk(
                    id=_chunk_id(draft.project_id, "relation", relation.id),
                    text=(
                        f"Relation: {relation.type}\n"
                        f"Source: {source.name if source else relation.source_id}\n"
                        f"Target: {target.name if target else relation.target_id}\n"
                        f"Evidence IDs: {', '.join(relation.evidence_ids)}"
                    ),
                    metadata={
                        "project_id": draft.project_id,
                        "chunk_kind": "relation",
                        "relation_id": relation.id,
                        "source_path": source.source_path if source else relation.id,
                        "source_type": relation.type,
                        "modality": "text",
                        "hall_ids": ",".join(sorted(source_halls | target_halls)),
                        "chunk_index": index,
                    },
                )
            )
        return [chunk for chunk in chunks if chunk.text.strip()]

    def _build_image_evidence(
        self,
        project_root: Path,
        project_id: str,
    ) -> list[EvidenceCard]:
        images = [
            path
            for path in project_root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in IMAGE_SUFFIXES
            and path.stat().st_size <= MAX_IMAGE_BYTES
            and not _is_ignored_image_path(path, project_root)
        ][:MAX_IMAGES_PER_PROJECT]
        if not images:
            return []

        vision_llm, provider, disabled_reason = self._create_vision_llm()
        cards: list[EvidenceCard] = []
        for index, image_path in enumerate(images):
            relative_path = image_path.relative_to(project_root).as_posix()
            metadata: dict[str, Any] = {
                "modality": "image",
                "vision_provider": provider,
                "vision_enabled": vision_llm is not None,
                "file_size": image_path.stat().st_size,
            }
            if disabled_reason:
                metadata["vision_error"] = disabled_reason
            caption = self._fallback_image_caption(image_path, relative_path)
            if vision_llm is not None:
                try:
                    response = vision_llm.chat_with_image(
                        text=(
                            "Describe this project image for a software architecture RAG index. "
                            "Mention visible UI, diagrams, text, architecture components, and risks. "
                            "Answer in concise Chinese if possible."
                        ),
                        image=ImageInput(path=image_path, mime_type=_image_mime_type(image_path)),
                    )
                    if response.content.strip():
                        caption = response.content.strip()
                        metadata["vision_model"] = response.model
                        metadata["vision_usage"] = response.usage
                except Exception as exc:
                    metadata["vision_enabled"] = False
                    metadata["vision_error"] = f"Vision caption failed for {relative_path}: {exc}"

            cards.append(
                EvidenceCard(
                    id=f"image:{project_id}:{index}:{_stable_hash(relative_path)[:10]}",
                    source_type="image",
                    source_path=relative_path,
                    title=f"Image: {Path(relative_path).name}",
                    snippet=caption,
                    confidence=0.72 if metadata.get("vision_enabled") else 0.42,
                    metadata=metadata,
                )
            )
        return cards

    def _create_embedding(self) -> tuple[BaseEmbedding, str, int, str | None]:
        try:
            embedding, provider, dimension = self._create_configured_embedding()
            return embedding, provider, dimension, None
        except Exception as exc:
            embedding = LocalHashEmbedding()
            return (
                embedding,
                embedding.provider,
                embedding.dimension,
                f"Configured embedding unavailable; using local hash embedding: {exc}",
            )

    def _create_configured_embedding(self) -> tuple[BaseEmbedding, str, int]:
        settings = load_settings()
        provider = getattr(settings.embedding, "provider", "unknown")
        api_key = getattr(settings.embedding, "api_key", None)
        if provider.lower() != "ollama" and _looks_like_placeholder(api_key):
            raise ValueError("embedding.api_key is missing or still a placeholder")
        embedding = EmbeddingFactory.create(settings)
        try:
            dimension = int(embedding.get_dimension())
        except Exception:
            dimension = int(getattr(settings.embedding, "dimensions", 1536))
        return embedding, provider, dimension

    def _create_vision_llm(self) -> tuple[Any | None, str, str | None]:
        try:
            settings = load_settings()
        except Exception as exc:
            return None, "none", f"Vision settings unavailable: {exc}"

        vision_settings = getattr(settings, "vision_llm", None)
        if vision_settings is None or not getattr(vision_settings, "enabled", False):
            return None, "none", "Vision LLM is disabled."

        provider = getattr(vision_settings, "provider", "unknown")
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY") or getattr(vision_settings, "api_key", None)
        if provider.lower() != "ollama" and _looks_like_placeholder(api_key):
            return None, provider, "Vision API key is missing or still a placeholder."

        try:
            return LLMFactory.create_vision_llm(settings), provider, None
        except Exception as exc:
            return None, provider, f"Vision LLM unavailable: {exc}"

    def _create_vector_store(
        self,
        *,
        dense_provider: str,
        dense_dimension: int,
        collection_name: str | None = None,
    ) -> ChromaStore:
        settings = load_settings()
        return ChromaStore(
            settings=settings,
            persist_directory=str(self.storage_dir / "rag" / "chroma"),
            collection_name=collection_name or self._collection_name(dense_provider, dense_dimension),
        )

    def _vision_status(self, cards: list[EvidenceCard]) -> dict[str, Any]:
        if not cards:
            return {"provider": "none", "enabled": False}
        provider = str(cards[0].metadata.get("vision_provider", "none"))
        enabled = any(bool(card.metadata.get("vision_enabled")) for card in cards)
        return {"provider": provider, "enabled": enabled}

    def _project_dir(self, project_id: str) -> Path:
        return self.storage_dir / project_id.replace("/", "_").replace(" ", "_")

    def _status_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "hybrid_rag_status.json"

    def _bm25_dir(self) -> Path:
        return self.storage_dir / "rag" / "bm25"

    def _project_collection(self, project_id: str) -> str:
        return _sanitize_collection_name(f"project_{project_id}")[:63]

    def _collection_name(self, dense_provider: str, dense_dimension: int) -> str:
        return _sanitize_collection_name(
            f"{DEFAULT_COLLECTION_PREFIX}_{dense_provider}_{dense_dimension}"
        )[:63]

    @staticmethod
    def _fallback_image_caption(image_path: Path, relative_path: str) -> str:
        return (
            f"Project image file {relative_path}. "
            f"Suffix: {image_path.suffix.lower()}. "
            f"Size: {image_path.stat().st_size} bytes. "
            "Vision caption was not available, so this image is indexed by file metadata."
        )


class LocalHashEmbedding(BaseEmbedding):
    """Deterministic local embedding used when configured embeddings are unavailable."""

    provider = "local_hash"
    dimension = 384

    def __init__(self, dimension: int | None = None) -> None:
        self.dimension = int(dimension or self.dimension)

    def embed(
        self,
        texts: list[str],
        trace: Any | None = None,
        **kwargs: Any,
    ) -> list[list[float]]:
        self.validate_texts(texts)
        return [self._embed_one(text) for text in texts]

    def get_dimension(self) -> int:
        return self.dimension

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


def retrieval_results_to_evidence_cards(
    results: list[RetrievalResult],
) -> list[EvidenceCard]:
    cards: list[EvidenceCard] = []
    for index, result in enumerate(results):
        metadata = dict(result.metadata)
        evidence_id = str(metadata.get("evidence_id") or result.chunk_id)
        source_path = str(metadata.get("source_path") or "hybrid-rag")
        source_type = str(metadata.get("source_type") or metadata.get("chunk_kind") or "retrieval")
        cards.append(
            EvidenceCard(
                id=f"rag:{evidence_id}:{index}",
                source_type=source_type,
                source_path=source_path,
                title=f"Hybrid RAG: {source_path}",
                snippet=result.text[:1400],
                confidence=min(1.0, max(0.2, float(result.score) * 12)),
                linked_entities=[],
                metadata={
                    **metadata,
                    "hybrid_rag": True,
                    "chunk_id": result.chunk_id,
                    "rrf_score": result.score,
                },
            )
        )
    return cards


def _metadata_contains_hall(metadata: dict[str, Any], hall_id: str) -> bool:
    hall_ids = str(metadata.get("hall_ids", ""))
    return hall_id in {item.strip() for item in hall_ids.split(",") if item.strip()}


def _hall_ids_by_entity(draft: ProjectArchiveDraft) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for hall in draft.halls:
        for entity_id in hall.entity_ids:
            rows.setdefault(entity_id, []).append(hall.id)
    return rows


def _chunk_id(project_id: str, kind: str, item_id: str) -> str:
    return f"{_stable_hash(project_id)[:10]}:{kind}:{_stable_hash(item_id)[:16]}"


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sanitize_collection_name(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_-]+", "_", value)
    sanitized = sanitized.strip("_-") or "project"
    if len(sanitized) < 3:
        sanitized = f"{sanitized}_idx"
    return sanitized[:63].strip("_-") or "project_idx"


def _looks_like_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    return (
        not stripped
        or stripped.startswith("YOUR_")
        or stripped in {"YOUR_API_KEY_HERE", "YOUR_DEEPSEEK_API_KEY_HERE", "sk-xxxxxxxx"}
    )


def _is_ignored_image_path(path: Path, root: Path) -> bool:
    ignored = {
        ".git",
        ".hg",
        ".svn",
        "__MACOSX",
        "node_modules",
        "dist",
        "build",
        "target",
        ".venv",
        "__pycache__",
    }
    try:
        relative_parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in ignored for part in relative_parts)


def _image_mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    if suffix == ".bmp":
        return "image/bmp"
    return "image/png"
