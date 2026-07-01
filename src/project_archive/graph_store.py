"""Graph store contracts and providers for project archives."""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from typing import Any
from pathlib import Path

from src.project_archive.types import (
    EvidenceCard,
    GraphPath,
    ProjectEntity,
    ProjectRelation,
    ProjectUniverseEntityRef,
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
    def get_entity(self, entity_id: str) -> ProjectEntity | None:
        """Return a project entity by id."""

    @abstractmethod
    def list_entities(self, type: str | None = None) -> list[ProjectEntity]:
        """List project entities, optionally filtered by type."""

    @abstractmethod
    def list_relations(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        type: str | None = None,
    ) -> list[ProjectRelation]:
        """List project relations, optionally filtered by fields."""

    @abstractmethod
    def list_evidence(self) -> list[EvidenceCard]:
        """List stored evidence cards."""

    @abstractmethod
    def find_paths(self, source_name: str, target_name: str) -> list[GraphPath]:
        """Find graph paths between entities by display name."""

    def list_universe_entity_refs(
        self,
        project_ids: list[str],
        *,
        limit_per_project: int = 180,
    ) -> list[ProjectUniverseEntityRef]:
        """Return cross-project entity refs for global universe queries."""
        return []


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

    def get_entity(self, entity_id: str) -> ProjectEntity | None:
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

    def list_entities(self, type: str | None = None) -> list[ProjectEntity]:
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
        source_id: str | None = None,
        target_id: str | None = None,
        type: str | None = None,
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
    """Kuzu-backed graph store for project archives."""

    def __init__(self, path: str | Path) -> None:
        try:
            import kuzu
        except ImportError as exc:
            raise RuntimeError(
                "Kuzu graph store requires the optional 'kuzu' package to be installed."
            ) from exc

        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.database = kuzu.Database(str(self.path))
        self.connection = kuzu.Connection(self.database)
        self._initialize()

    def upsert_entities(self, entities: Iterable[ProjectEntity]) -> None:
        for entity in entities:
            self.connection.execute(
                """
                MERGE (entity:Entity {id: $id})
                SET
                    entity.type = $type,
                    entity.name = $name,
                    entity.source_path = $source_path,
                    entity.properties_json = $properties_json,
                    entity.evidence_ids_json = $evidence_ids_json
                """,
                {
                    "id": entity.id,
                    "type": entity.type,
                    "name": entity.name,
                    "source_path": entity.source_path,
                    "properties_json": _json_dumps(entity.properties),
                    "evidence_ids_json": _json_dumps(entity.evidence_ids),
                },
            )

    def upsert_relations(self, relations: Iterable[ProjectRelation]) -> None:
        for relation in relations:
            self.connection.execute(
                """
                MATCH (:Entity)-[relation:ArchiveRelation]->(:Entity)
                WHERE relation.id = $id
                DELETE relation
                """,
                {"id": relation.id},
            )
            self.connection.execute(
                """
                MATCH
                    (source:Entity {id: $source_id}),
                    (target:Entity {id: $target_id})
                CREATE (source)-[:ArchiveRelation {
                    id: $id,
                    type: $type,
                    evidence_ids_json: $evidence_ids_json,
                    properties_json: $properties_json
                }]->(target)
                """,
                {
                    "id": relation.id,
                    "source_id": relation.source_id,
                    "target_id": relation.target_id,
                    "type": relation.type,
                    "evidence_ids_json": _json_dumps(relation.evidence_ids),
                    "properties_json": _json_dumps(relation.properties),
                },
            )

    def upsert_evidence(self, evidence_cards: Iterable[EvidenceCard]) -> None:
        for evidence in evidence_cards:
            self.connection.execute(
                """
                MERGE (evidence:Evidence {id: $id})
                SET evidence.payload_json = $payload_json
                """,
                {
                    "id": evidence.id,
                    "payload_json": _json_dumps(evidence.to_dict()),
                },
            )

    def get_entity(self, entity_id: str) -> ProjectEntity | None:
        result = self.connection.execute(
            """
            MATCH (entity:Entity {id: $id})
            RETURN
                entity.id,
                entity.type,
                entity.name,
                entity.source_path,
                entity.properties_json,
                entity.evidence_ids_json
            """,
            {"id": entity_id},
        )
        rows = list(result)
        return _entity_from_kuzu_row(rows[0]) if rows else None

    def list_entities(self, type: str | None = None) -> list[ProjectEntity]:
        if type is None:
            result = self.connection.execute(
                """
                MATCH (entity:Entity)
                RETURN
                    entity.id,
                    entity.type,
                    entity.name,
                    entity.source_path,
                    entity.properties_json,
                    entity.evidence_ids_json
                ORDER BY entity.id
                """
            )
        else:
            result = self.connection.execute(
                """
                MATCH (entity:Entity)
                WHERE entity.type = $type
                RETURN
                    entity.id,
                    entity.type,
                    entity.name,
                    entity.source_path,
                    entity.properties_json,
                    entity.evidence_ids_json
                ORDER BY entity.id
                """,
                {"type": type},
            )
        return [_entity_from_kuzu_row(row) for row in result]

    def list_relations(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        type: str | None = None,
    ) -> list[ProjectRelation]:
        filters = []
        params = {}
        if source_id is not None:
            filters.append("source.id = $source_id")
            params["source_id"] = source_id
        if target_id is not None:
            filters.append("target.id = $target_id")
            params["target_id"] = target_id
        if type is not None:
            filters.append("relation.type = $type")
            params["type"] = type

        query = """
            MATCH (source:Entity)-[relation:ArchiveRelation]->(target:Entity)
        """
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += """
            RETURN
                relation.id,
                source.id,
                target.id,
                relation.type,
                relation.evidence_ids_json,
                relation.properties_json
            ORDER BY relation.id
        """

        result = self.connection.execute(query, params)
        return [_relation_from_kuzu_row(row) for row in result]

    def list_evidence(self) -> list[EvidenceCard]:
        result = self.connection.execute(
            """
            MATCH (evidence:Evidence)
            RETURN evidence.payload_json
            ORDER BY evidence.id
            """
        )
        return [EvidenceCard.from_dict(json.loads(row[0])) for row in result]

    def find_paths(self, source_name: str, target_name: str) -> list[GraphPath]:
        result = self.connection.execute(
            """
            MATCH (source:Entity)-[relation:ArchiveRelation]->(target:Entity)
            WHERE lower(source.name) = lower($source_name)
              AND lower(target.name) = lower($target_name)
            RETURN
                source.id,
                target.id,
                relation.type,
                relation.evidence_ids_json
            ORDER BY relation.id
            """,
            {"source_name": source_name, "target_name": target_name},
        )

        return [
            GraphPath(
                nodes=[row[0], row[1]],
                relations=[row[2]],
                evidence_ids=json.loads(row[3]),
            )
            for row in result
        ]

    def _initialize(self) -> None:
        self.connection.execute(
            """
            CREATE NODE TABLE IF NOT EXISTS Entity(
                id STRING,
                type STRING,
                name STRING,
                source_path STRING,
                properties_json STRING,
                evidence_ids_json STRING,
                PRIMARY KEY(id)
            )
            """
        )
        self.connection.execute(
            """
            CREATE NODE TABLE IF NOT EXISTS Evidence(
                id STRING,
                payload_json STRING,
                PRIMARY KEY(id)
            )
            """
        )
        self.connection.execute(
            """
            CREATE REL TABLE IF NOT EXISTS ArchiveRelation(
                FROM Entity TO Entity,
                id STRING,
                type STRING,
                evidence_ids_json STRING,
                properties_json STRING
            )
            """
        )


class Neo4jGraphStore(BaseGraphStore):
    """Neo4j-backed graph store for production project archives."""

    def __init__(
        self,
        *,
        uri: str,
        username: str,
        password: str,
        database: str = "neo4j",
        project_id: str,
    ) -> None:
        try:
            from neo4j import GraphDatabase
        except ImportError as exc:
            raise RuntimeError(
                "Neo4j graph store requires the optional 'neo4j' package to be installed."
            ) from exc

        if not project_id:
            raise ValueError("Neo4j graph store requires a project_id for isolation.")
        if not uri:
            raise ValueError("Neo4j graph store requires a uri.")
        if not username:
            raise ValueError("Neo4j graph store requires a username.")

        self.project_id = project_id
        self.database = database or "neo4j"
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self._initialize()

    def upsert_entities(self, entities: Iterable[ProjectEntity]) -> None:
        rows = [
            {
                "id": entity.id,
                "project_id": self.project_id,
                "type": entity.type,
                "name": entity.name,
                "source_path": entity.source_path,
                "properties_json": _json_dumps(entity.properties),
                "evidence_ids_json": _json_dumps(entity.evidence_ids),
            }
            for entity in entities
        ]
        if not rows:
            return

        self._execute_write(
            """
            UNWIND $rows AS row
            MERGE (entity:ProjectEntity {project_id: row.project_id, id: row.id})
            SET
                entity.type = row.type,
                entity.name = row.name,
                entity.source_path = row.source_path,
                entity.properties_json = row.properties_json,
                entity.evidence_ids_json = row.evidence_ids_json
            """,
            rows=rows,
        )

    def upsert_relations(self, relations: Iterable[ProjectRelation]) -> None:
        rows = [
            {
                "id": relation.id,
                "project_id": self.project_id,
                "source_id": relation.source_id,
                "target_id": relation.target_id,
                "type": relation.type,
                "evidence_ids_json": _json_dumps(relation.evidence_ids),
                "properties_json": _json_dumps(relation.properties),
            }
            for relation in relations
        ]
        if not rows:
            return

        self._execute_write(
            """
            UNWIND $rows AS row
            MERGE (source:ProjectEntity {project_id: row.project_id, id: row.source_id})
            ON CREATE SET
                source.type = 'Unknown',
                source.name = row.source_id,
                source.source_path = null,
                source.properties_json = '{}',
                source.evidence_ids_json = '[]'
            MERGE (target:ProjectEntity {project_id: row.project_id, id: row.target_id})
            ON CREATE SET
                target.type = 'Unknown',
                target.name = row.target_id,
                target.source_path = null,
                target.properties_json = '{}',
                target.evidence_ids_json = '[]'
            MERGE (source)-[relation:ARCHIVE_RELATION {project_id: row.project_id, id: row.id}]->(target)
            SET
                relation.type = row.type,
                relation.evidence_ids_json = row.evidence_ids_json,
                relation.properties_json = row.properties_json
            """,
            rows=rows,
        )

    def upsert_evidence(self, evidence_cards: Iterable[EvidenceCard]) -> None:
        rows = [
            {
                "id": evidence.id,
                "project_id": self.project_id,
                "payload_json": _json_dumps(evidence.to_dict()),
            }
            for evidence in evidence_cards
        ]
        if not rows:
            return

        self._execute_write(
            """
            UNWIND $rows AS row
            MERGE (evidence:ProjectEvidence {project_id: row.project_id, id: row.id})
            SET evidence.payload_json = row.payload_json
            """,
            rows=rows,
        )

    def get_entity(self, entity_id: str) -> ProjectEntity | None:
        rows = self._execute_read(
            """
            MATCH (entity:ProjectEntity {project_id: $project_id, id: $entity_id})
            RETURN
                entity.id AS id,
                entity.type AS type,
                entity.name AS name,
                entity.source_path AS source_path,
                entity.properties_json AS properties_json,
                entity.evidence_ids_json AS evidence_ids_json
            """,
            project_id=self.project_id,
            entity_id=entity_id,
        )
        return _entity_from_mapping(rows[0]) if rows else None

    def list_entities(self, type: str | None = None) -> list[ProjectEntity]:
        filters = ["entity.project_id = $project_id"]
        params: dict[str, Any] = {"project_id": self.project_id}
        if type is not None:
            filters.append("entity.type = $type")
            params["type"] = type
        rows = self._execute_read(
            f"""
            MATCH (entity:ProjectEntity)
            WHERE {" AND ".join(filters)}
            RETURN
                entity.id AS id,
                entity.type AS type,
                entity.name AS name,
                entity.source_path AS source_path,
                entity.properties_json AS properties_json,
                entity.evidence_ids_json AS evidence_ids_json
            ORDER BY entity.id
            """,
            **params,
        )
        return [_entity_from_mapping(row) for row in rows]

    def list_relations(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        type: str | None = None,
    ) -> list[ProjectRelation]:
        filters = ["relation.project_id = $project_id"]
        params: dict[str, Any] = {"project_id": self.project_id}
        if source_id is not None:
            filters.append("source.id = $source_id")
            params["source_id"] = source_id
        if target_id is not None:
            filters.append("target.id = $target_id")
            params["target_id"] = target_id
        if type is not None:
            filters.append("relation.type = $type")
            params["type"] = type

        rows = self._execute_read(
            f"""
            MATCH (source:ProjectEntity)-[relation:ARCHIVE_RELATION]->(target:ProjectEntity)
            WHERE {" AND ".join(filters)}
            RETURN
                relation.id AS id,
                source.id AS source_id,
                target.id AS target_id,
                relation.type AS type,
                relation.evidence_ids_json AS evidence_ids_json,
                relation.properties_json AS properties_json
            ORDER BY relation.id
            """,
            **params,
        )
        return [_relation_from_mapping(row) for row in rows]

    def list_evidence(self) -> list[EvidenceCard]:
        rows = self._execute_read(
            """
            MATCH (evidence:ProjectEvidence)
            WHERE evidence.project_id = $project_id
            RETURN evidence.payload_json AS payload_json
            ORDER BY evidence.id
            """,
            project_id=self.project_id,
        )
        return [
            EvidenceCard.from_dict(json.loads(str(row["payload_json"])))
            for row in rows
        ]

    def find_paths(self, source_name: str, target_name: str) -> list[GraphPath]:
        rows = self._execute_read(
            """
            MATCH (source:ProjectEntity)-[relation:ARCHIVE_RELATION]->(target:ProjectEntity)
            WHERE relation.project_id = $project_id
              AND source.project_id = $project_id
              AND target.project_id = $project_id
              AND toLower(source.name) = toLower($source_name)
              AND toLower(target.name) = toLower($target_name)
            RETURN
                source.id AS source_id,
                target.id AS target_id,
                relation.type AS relation_type,
                relation.evidence_ids_json AS evidence_ids_json
            ORDER BY relation.id
            """,
            project_id=self.project_id,
            source_name=source_name,
            target_name=target_name,
        )

        return [
            GraphPath(
                nodes=[str(row["source_id"]), str(row["target_id"])],
                relations=[str(row["relation_type"])],
                evidence_ids=json.loads(str(row["evidence_ids_json"])),
            )
            for row in rows
        ]

    def close(self) -> None:
        self.driver.close()

    def list_universe_entity_refs(
        self,
        project_ids: list[str],
        *,
        limit_per_project: int = 180,
    ) -> list[ProjectUniverseEntityRef]:
        selected_project_ids = [project_id for project_id in project_ids if project_id]
        if not selected_project_ids:
            return []

        rows = self._execute_read(
            """
            MATCH (entity:ProjectEntity)
            WHERE entity.project_id IN $project_ids
            OPTIONAL MATCH (entity)-[relation:ARCHIVE_RELATION]-()
            WITH entity, count(relation) AS degree
            ORDER BY entity.project_id, degree DESC, size(entity.evidence_ids_json) DESC, entity.name
            WITH entity.project_id AS project_id, collect({
                id: entity.id,
                type: entity.type,
                name: entity.name,
                source_path: entity.source_path,
                evidence_ids_json: entity.evidence_ids_json,
                degree: degree
            })[..$limit_per_project] AS refs
            UNWIND refs AS ref
            RETURN
                project_id AS project_id,
                ref.id AS entity_id,
                ref.type AS type,
                ref.name AS label,
                ref.source_path AS source_path,
                ref.evidence_ids_json AS evidence_ids_json,
                ref.degree AS degree
            """,
            project_ids=selected_project_ids,
            limit_per_project=max(1, min(limit_per_project, 500)),
        )
        refs: list[ProjectUniverseEntityRef] = []
        for row in rows:
            evidence_ids = _safe_json_list(row.get("evidence_ids_json"))
            refs.append(
                ProjectUniverseEntityRef(
                    project_id=str(row["project_id"]),
                    entity_id=str(row["entity_id"]),
                    label=str(row["label"]),
                    type=str(row["type"]),
                    source_path=str(row["source_path"]) if row.get("source_path") else None,
                    degree=int(row.get("degree", 0) or 0),
                    evidence_count=len(evidence_ids),
                    hall_ids=[],
                )
            )
        return refs

    def _initialize(self) -> None:
        self._execute_write(
            """
            CREATE CONSTRAINT project_entity_identity IF NOT EXISTS
            FOR (entity:ProjectEntity)
            REQUIRE (entity.project_id, entity.id) IS UNIQUE
            """
        )
        self._execute_write(
            """
            CREATE CONSTRAINT project_evidence_identity IF NOT EXISTS
            FOR (evidence:ProjectEvidence)
            REQUIRE (evidence.project_id, evidence.id) IS UNIQUE
            """
        )
        self._execute_write(
            """
            CREATE INDEX archive_relation_identity IF NOT EXISTS
            FOR ()-[relation:ARCHIVE_RELATION]-()
            ON (relation.project_id, relation.id)
            """
        )

    def _execute_write(self, query: str, **params: Any) -> None:
        with self.driver.session(database=self.database) as session:
            session.execute_write(lambda tx: tx.run(query, **params).consume())

    def _execute_read(self, query: str, **params: Any) -> list[dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            result = session.execute_read(
                lambda tx: [dict(record) for record in tx.run(query, **params)]
            )
        return list(result)


class GraphStoreFactory:
    """Factory for graph store providers."""

    @staticmethod
    def create(
        provider: str,
        path: str | Path,
        *,
        project_id: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> BaseGraphStore:
        normalized_provider = provider.lower()
        if normalized_provider == "sqlite":
            return SQLiteGraphStore(path)
        if normalized_provider == "kuzu":
            return KuzuGraphStore(path)
        if normalized_provider == "neo4j":
            config = config or {}
            return Neo4jGraphStore(
                uri=str(config.get("uri") or "bolt://localhost:7687"),
                username=str(config.get("username") or "neo4j"),
                password=str(config.get("password") or ""),
                database=str(config.get("database") or "neo4j"),
                project_id=project_id or "",
            )
        raise ValueError(f"Unsupported graph store provider: {provider}")


def create_graph_store(
    path: str | Path,
    preferred_provider: str = "sqlite",
    *,
    project_id: str | None = None,
    config: dict[str, Any] | None = None,
) -> BaseGraphStore:
    """Create a graph store for the requested provider."""
    return GraphStoreFactory.create(
        provider=preferred_provider,
        path=path,
        project_id=project_id,
        config=config,
    )


def _json_dumps(value: object) -> str:
    return json.dumps(value, sort_keys=True)


def _safe_json_list(value: object) -> list[str]:
    try:
        payload = json.loads(str(value or "[]"))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload]


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


def _entity_from_kuzu_row(row: list[object]) -> ProjectEntity:
    return ProjectEntity(
        id=str(row[0]),
        type=str(row[1]),
        name=str(row[2]),
        source_path=str(row[3]) if row[3] is not None else None,
        properties=json.loads(str(row[4])),
        evidence_ids=json.loads(str(row[5])),
    )


def _relation_from_kuzu_row(row: list[object]) -> ProjectRelation:
    return ProjectRelation(
        id=str(row[0]),
        source_id=str(row[1]),
        target_id=str(row[2]),
        type=str(row[3]),
        evidence_ids=json.loads(str(row[4])),
        properties=json.loads(str(row[5])),
    )


def _entity_from_mapping(row: dict[str, Any]) -> ProjectEntity:
    return ProjectEntity(
        id=str(row["id"]),
        type=str(row["type"]),
        name=str(row["name"]),
        source_path=str(row["source_path"]) if row.get("source_path") is not None else None,
        properties=json.loads(str(row["properties_json"])),
        evidence_ids=json.loads(str(row["evidence_ids_json"])),
    )


def _relation_from_mapping(row: dict[str, Any]) -> ProjectRelation:
    return ProjectRelation(
        id=str(row["id"]),
        source_id=str(row["source_id"]),
        target_id=str(row["target_id"]),
        type=str(row["type"]),
        evidence_ids=json.loads(str(row["evidence_ids_json"])),
        properties=json.loads(str(row["properties_json"])),
    )
