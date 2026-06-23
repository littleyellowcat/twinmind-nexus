"""Graph store contracts and SQLite fallback for project archives."""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Iterable, Optional

from src.project_archive.types import (
    EvidenceCard,
    GraphPath,
    ProjectEntity,
    ProjectRelation,
)


class BaseGraphStore(ABC):
    """Abstract graph persistence contract for project archives."""

    @abstractmethod
    def upsert_entities(self, entities: Iterable[ProjectEntity]) -> None:
        """Insert or replace project entities."""

    @abstractmethod
    def upsert_relations(self, relations: Iterable[ProjectRelation]) -> None:
        """Insert or replace project relations."""

    @abstractmethod
    def upsert_evidence(self, evidence_cards: Iterable[EvidenceCard]) -> None:
        """Insert or replace evidence cards."""

    @abstractmethod
    def get_entity(self, entity_id: str) -> Optional[ProjectEntity]:
        """Return a project entity by id."""

    @abstractmethod
    def list_entities(self, type: Optional[str] = None) -> list[ProjectEntity]:
        """List project entities, optionally filtered by type."""

    @abstractmethod
    def list_relations(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        type: Optional[str] = None,
    ) -> list[ProjectRelation]:
        """List project relations, optionally filtered by fields."""

    @abstractmethod
    def list_evidence(self) -> list[EvidenceCard]:
        """List stored evidence cards."""

    @abstractmethod
    def find_paths(self, source_name: str, target_name: str) -> list[GraphPath]:
        """Find graph paths between entities by display name."""


class SQLiteGraphStore(BaseGraphStore):
    """SQLite-backed graph store using JSON columns for flexible fields."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def upsert_entities(self, entities: Iterable[ProjectEntity]) -> None:
        rows = [
            (
                entity.id,
                entity.type,
                entity.name,
                entity.source_path,
                _json_dumps(entity.properties),
                _json_dumps(entity.evidence_ids),
            )
            for entity in entities
        ]
        if not rows:
            return

        with self._connection() as conn:
            conn.executemany(
                """
                INSERT INTO entities (
                    id, type, name, source_path, properties_json, evidence_ids_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    type = excluded.type,
                    name = excluded.name,
                    source_path = excluded.source_path,
                    properties_json = excluded.properties_json,
                    evidence_ids_json = excluded.evidence_ids_json
                """,
                rows,
            )

    def upsert_relations(self, relations: Iterable[ProjectRelation]) -> None:
        rows = [
            (
                relation.id,
                relation.source_id,
                relation.target_id,
                relation.type,
                _json_dumps(relation.evidence_ids),
                _json_dumps(relation.properties),
            )
            for relation in relations
        ]
        if not rows:
            return

        with self._connection() as conn:
            conn.executemany(
                """
                INSERT INTO relations (
                    id, source_id, target_id, type, evidence_ids_json, properties_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_id = excluded.source_id,
                    target_id = excluded.target_id,
                    type = excluded.type,
                    evidence_ids_json = excluded.evidence_ids_json,
                    properties_json = excluded.properties_json
                """,
                rows,
            )

    def upsert_evidence(self, evidence_cards: Iterable[EvidenceCard]) -> None:
        rows = [
            (evidence.id, _json_dumps(evidence.to_dict()))
            for evidence in evidence_cards
        ]
        if not rows:
            return

        with self._connection() as conn:
            conn.executemany(
                """
                INSERT INTO evidence (id, payload_json)
                VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload_json = excluded.payload_json
                """,
                rows,
            )

    def get_entity(self, entity_id: str) -> Optional[ProjectEntity]:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT id, type, name, source_path, properties_json, evidence_ids_json
                FROM entities
                WHERE id = ?
                """,
                (entity_id,),
            ).fetchone()
        return _entity_from_row(row) if row else None

    def list_entities(self, type: Optional[str] = None) -> list[ProjectEntity]:
        sql = """
            SELECT id, type, name, source_path, properties_json, evidence_ids_json
            FROM entities
        """
        params: list[str] = []
        if type is not None:
            sql += " WHERE type = ?"
            params.append(type)
        sql += " ORDER BY id"

        with self._connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_entity_from_row(row) for row in rows]

    def list_relations(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        type: Optional[str] = None,
    ) -> list[ProjectRelation]:
        sql = """
            SELECT id, source_id, target_id, type, evidence_ids_json, properties_json
            FROM relations
        """
        filters: list[str] = []
        params: list[str] = []
        if source_id is not None:
            filters.append("source_id = ?")
            params.append(source_id)
        if target_id is not None:
            filters.append("target_id = ?")
            params.append(target_id)
        if type is not None:
            filters.append("type = ?")
            params.append(type)
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        sql += " ORDER BY id"

        with self._connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_relation_from_row(row) for row in rows]

    def list_evidence(self) -> list[EvidenceCard]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM evidence ORDER BY id"
            ).fetchall()
        return [
            EvidenceCard.from_dict(json.loads(row["payload_json"]))
            for row in rows
        ]

    def find_paths(self, source_name: str, target_name: str) -> list[GraphPath]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    source.id AS source_id,
                    target.id AS target_id,
                    relations.type AS relation_type,
                    relations.evidence_ids_json AS evidence_ids_json
                FROM relations
                JOIN entities AS source ON source.id = relations.source_id
                JOIN entities AS target ON target.id = relations.target_id
                WHERE lower(source.name) = lower(?)
                  AND lower(target.name) = lower(?)
                ORDER BY relations.id
                """,
                (source_name, target_name),
            ).fetchall()

        return [
            GraphPath(
                nodes=[row["source_id"], row["target_id"]],
                relations=[row["relation_type"]],
                evidence_ids=json.loads(row["evidence_ids_json"]),
            )
            for row in rows
        ]

    def _initialize(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    source_path TEXT,
                    properties_json TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS relations (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    properties_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evidence (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()


class KuzuGraphStore(BaseGraphStore):
    """Placeholder for the Phase 1-disabled Kuzu graph store."""

    def __init__(self, path: str | Path) -> None:
        try:
            import kuzu  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "Kuzu graph store requires the optional 'kuzu' package to be installed."
            ) from exc
        raise RuntimeError(
            "Kuzu graph store is not enabled in Phase 1; use provider='sqlite'."
        )

    def upsert_entities(self, entities: Iterable[ProjectEntity]) -> None:
        raise NotImplementedError

    def upsert_relations(self, relations: Iterable[ProjectRelation]) -> None:
        raise NotImplementedError

    def upsert_evidence(self, evidence_cards: Iterable[EvidenceCard]) -> None:
        raise NotImplementedError

    def get_entity(self, entity_id: str) -> Optional[ProjectEntity]:
        raise NotImplementedError

    def list_entities(self, type: Optional[str] = None) -> list[ProjectEntity]:
        raise NotImplementedError

    def list_relations(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        type: Optional[str] = None,
    ) -> list[ProjectRelation]:
        raise NotImplementedError

    def list_evidence(self) -> list[EvidenceCard]:
        raise NotImplementedError

    def find_paths(self, source_name: str, target_name: str) -> list[GraphPath]:
        raise NotImplementedError


class GraphStoreFactory:
    """Factory for graph store providers."""

    @staticmethod
    def create(provider: str, path: str | Path) -> BaseGraphStore:
        normalized_provider = provider.lower()
        if normalized_provider == "sqlite":
            return SQLiteGraphStore(path)
        if normalized_provider == "kuzu":
            return KuzuGraphStore(path)
        raise ValueError(f"Unsupported graph store provider: {provider}")


def _json_dumps(value: object) -> str:
    return json.dumps(value, sort_keys=True)


def _entity_from_row(row: sqlite3.Row) -> ProjectEntity:
    return ProjectEntity(
        id=row["id"],
        type=row["type"],
        name=row["name"],
        source_path=row["source_path"],
        properties=json.loads(row["properties_json"]),
        evidence_ids=json.loads(row["evidence_ids_json"]),
    )


def _relation_from_row(row: sqlite3.Row) -> ProjectRelation:
    return ProjectRelation(
        id=row["id"],
        source_id=row["source_id"],
        target_id=row["target_id"],
        type=row["type"],
        evidence_ids=json.loads(row["evidence_ids_json"]),
        properties=json.loads(row["properties_json"]),
    )
