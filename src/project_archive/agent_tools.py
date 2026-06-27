"""Bounded tool registry for graph-grounded Agent missions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.project_archive.types import AgentRoleResult, EvidenceCard, ProjectArchiveDraft

MAX_GRAPH_SEARCH_LIMIT = 20
MAX_NEIGHBORHOOD_DEPTH = 3
MAX_NEIGHBORHOOD_NODES = 80
MAX_NEIGHBORHOOD_RELATIONS = 120
MAX_HYBRID_TOP_K = 12
MAX_EVIDENCE_CARDS = 20
MAX_ENTITY_RELATIONS = 50
SPECIALIST_ROLES = {"archivist", "cartographer", "detective", "skeptic", "curator"}


class ToolExecutionError(ValueError):
    """Raised when an Agent tool call is not approved or has invalid input."""


@dataclass(frozen=True)
class AgentToolResult:
    tool_name: str
    summary: str
    payload: dict[str, Any]
    evidence_ids: list[str]
    entity_ids: list[str]
    relation_ids: list[str]


class AgentToolRegistry:
    """Dispatch only approved graph-grounded tools to existing archive services."""

    def __init__(self, service: Any) -> None:
        self.service = service
        self._handlers = {
            "get_evidence": self._get_evidence,
            "graph_neighborhood": self._graph_neighborhood,
            "graph_search": self._graph_search,
            "graph_summary": self._graph_summary,
            "hybrid_search": self._hybrid_search,
            "inspect_entity": self._inspect_entity,
            "list_halls": self._list_halls,
            "run_specialist_agent": self._run_specialist_agent,
        }

    def tool_names(self) -> list[str]:
        return sorted(self._handlers)

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> AgentToolResult:
        handler = self._handlers.get(tool_name)
        if handler is None:
            raise ToolExecutionError(f"Unknown Agent tool: {tool_name}")
        if not isinstance(tool_input, dict):
            raise ToolExecutionError("Agent tool input must be a dictionary.")
        return handler(tool_input)

    def _list_halls(self, tool_input: dict[str, Any]) -> AgentToolResult:
        project_id = _required_str(tool_input, "project_id")
        draft = self.service.load_draft(project_id)
        halls = [
            {
                "id": hall.id,
                "name": hall.name,
                "description": hall.description,
                "entity_count": len(hall.entity_ids),
            }
            for hall in draft.halls
        ]
        return AgentToolResult(
            tool_name="list_halls",
            summary=f"Listed {len(halls)} archive halls.",
            payload={"project_id": project_id, "halls": halls},
            evidence_ids=[],
            entity_ids=[],
            relation_ids=[],
        )

    def _graph_summary(self, tool_input: dict[str, Any]) -> AgentToolResult:
        project_id = _required_str(tool_input, "project_id")
        payload = self.service.graph_summary(project_id).to_dict()
        metrics = payload.get("metrics", {})
        entities = int(metrics.get("entities", 0))
        relations = int(metrics.get("relations", 0))
        return AgentToolResult(
            tool_name="graph_summary",
            summary=f"Graph summary returned {entities} entities and {relations} relations.",
            payload=payload,
            evidence_ids=[],
            entity_ids=[],
            relation_ids=[],
        )

    def _graph_search(self, tool_input: dict[str, Any]) -> AgentToolResult:
        project_id = _required_str(tool_input, "project_id")
        query = _required_str(tool_input, "query")
        requested_limit = _positive_int(
            tool_input.get("limit", MAX_GRAPH_SEARCH_LIMIT),
            "limit",
        )
        effective_limit = min(requested_limit, MAX_GRAPH_SEARCH_LIMIT)
        results = self.service.search_graph_entities(
            project_id,
            query=query,
            limit=effective_limit,
        )
        rows = [result.to_dict() for result in results[:effective_limit]]
        return AgentToolResult(
            tool_name="graph_search",
            summary=f"Graph search returned {len(rows)} entities.",
            payload={
                "project_id": project_id,
                "query": query,
                "results": rows,
                "metadata": {
                    "requested_limit": requested_limit,
                    "effective_limit": effective_limit,
                    "truncated": requested_limit > effective_limit
                    or len(results) > effective_limit,
                },
            },
            evidence_ids=_unique_id_list(
                evidence_id
                for result in results[:effective_limit]
                for evidence_id in getattr(result, "evidence_ids", [])
            )[:MAX_EVIDENCE_CARDS],
            entity_ids=_unique_id_list(
                getattr(result, "entity_id", "") for result in results[:effective_limit]
            ),
            relation_ids=[],
        )

    def _graph_neighborhood(self, tool_input: dict[str, Any]) -> AgentToolResult:
        project_id = _required_str(tool_input, "project_id")
        requested_depth = _positive_int(tool_input.get("depth", 1), "depth")
        requested_node_limit = _positive_int(
            tool_input.get("node_limit", MAX_NEIGHBORHOOD_NODES),
            "node_limit",
        )
        requested_relation_limit = _positive_int(
            tool_input.get("relation_limit", MAX_NEIGHBORHOOD_RELATIONS),
            "relation_limit",
        )
        effective_depth = min(requested_depth, MAX_NEIGHBORHOOD_DEPTH)
        effective_node_limit = min(requested_node_limit, MAX_NEIGHBORHOOD_NODES)
        effective_relation_limit = min(
            requested_relation_limit,
            MAX_NEIGHBORHOOD_RELATIONS,
        )
        neighborhood = self.service.graph_neighborhood(
            project_id,
            hall_id=_optional_str(tool_input.get("hall_id"), "hall_id"),
            focus_entity_id=_optional_str(
                tool_input.get("focus_entity_id"),
                "focus_entity_id",
            ),
            depth=effective_depth,
            relation_types=_string_list(
                tool_input.get("relation_types", []),
                "relation_types",
            ),
            node_limit=effective_node_limit,
            relation_limit=effective_relation_limit,
        )
        payload = neighborhood.to_dict()
        raw_nodes = payload.get("nodes", [])
        raw_relations = payload.get("relations", [])
        raw_evidence_ids = _string_list(payload.get("evidence_ids", []), "evidence_ids")
        nodes = raw_nodes[:effective_node_limit] if isinstance(raw_nodes, list) else []
        relations = (
            raw_relations[:effective_relation_limit]
            if isinstance(raw_relations, list)
            else []
        )
        evidence_ids = _unique_id_list(raw_evidence_ids)[:MAX_EVIDENCE_CARDS]
        payload = {
            **payload,
            "nodes": nodes,
            "relations": relations,
            "evidence_ids": evidence_ids,
            "metadata": {
                "requested_depth": requested_depth,
                "effective_depth": effective_depth,
                "requested_node_limit": requested_node_limit,
                "effective_node_limit": effective_node_limit,
                "requested_relation_limit": requested_relation_limit,
                "effective_relation_limit": effective_relation_limit,
                "truncated": requested_depth > effective_depth
                or requested_node_limit > effective_node_limit
                or requested_relation_limit > effective_relation_limit
                or len(raw_nodes) > effective_node_limit
                or len(raw_relations) > effective_relation_limit
                or len(raw_evidence_ids) > MAX_EVIDENCE_CARDS,
            },
        }
        return AgentToolResult(
            tool_name="graph_neighborhood",
            summary=(
                f"Graph neighborhood returned {len(nodes)} nodes and "
                f"{len(relations)} relations."
            ),
            payload=payload,
            evidence_ids=evidence_ids,
            entity_ids=_unique_id_list(node.get("id") for node in nodes if isinstance(node, dict)),
            relation_ids=_unique_id_list(
                relation.get("id") for relation in relations if isinstance(relation, dict)
            ),
        )

    def _hybrid_search(self, tool_input: dict[str, Any]) -> AgentToolResult:
        from src.project_archive.hybrid_rag import ProjectHybridRAGIndex

        project_id = _required_str(tool_input, "project_id")
        query = _required_str(tool_input, "query")
        requested_top_k = _positive_int(tool_input.get("top_k", MAX_HYBRID_TOP_K), "top_k")
        effective_top_k = min(requested_top_k, MAX_HYBRID_TOP_K)
        hall_id = _optional_str(tool_input.get("hall_id"), "hall_id")
        storage_dir = getattr(self.service, "storage_dir", "data/project_archive")
        result = ProjectHybridRAGIndex(storage_dir).search(
            project_id=project_id,
            query=query,
            hall_id=hall_id,
            top_k=effective_top_k,
        )
        if result is None:
            return AgentToolResult(
                tool_name="hybrid_search",
                summary="Hybrid search index is unavailable for this project.",
                payload={
                    "project_id": project_id,
                    "query": query,
                    "results": [],
                    "metadata": {
                        "enabled": False,
                        "result_count": 0,
                        "requested_top_k": requested_top_k,
                        "effective_top_k": effective_top_k,
                        "truncated": requested_top_k > effective_top_k,
                    },
                },
                evidence_ids=[],
                entity_ids=[],
                relation_ids=[],
            )

        result_rows = result.results[:effective_top_k]
        rows = [row.to_dict() for row in result_rows]
        metadata = result.to_metadata()
        return AgentToolResult(
            tool_name="hybrid_search",
            summary=f"Hybrid search returned {len(rows)} results.",
            payload={
                "project_id": project_id,
                "query": query,
                "results": rows,
                "metadata": {
                    **metadata,
                    "requested_top_k": requested_top_k,
                    "effective_top_k": effective_top_k,
                    "truncated": requested_top_k > effective_top_k
                    or len(result.results) > effective_top_k,
                },
            },
            evidence_ids=_unique_id_list(
                row.metadata.get("evidence_id") for row in result_rows
            )[:MAX_EVIDENCE_CARDS],
            entity_ids=_unique_id_list(row.metadata.get("entity_id") for row in result_rows),
            relation_ids=_unique_id_list(
                row.metadata.get("relation_id") for row in result_rows
            ),
        )

    def _get_evidence(self, tool_input: dict[str, Any]) -> AgentToolResult:
        project_id = _required_str(tool_input, "project_id")
        requested_evidence_ids = _string_list(
            tool_input.get("evidence_ids", []),
            "evidence_ids",
        )
        evidence_ids = _unique_id_list(requested_evidence_ids)[:MAX_EVIDENCE_CARDS]
        draft = self.service.load_draft(project_id)
        cards = _evidence_by_ids(draft, evidence_ids)
        found_ids = [card.id for card in cards]
        return AgentToolResult(
            tool_name="get_evidence",
            summary=f"Returned {len(cards)} evidence cards.",
            payload={
                "project_id": project_id,
                "evidence_cards": [card.to_dict() for card in cards],
                "metadata": {
                    "requested_count": len(requested_evidence_ids),
                    "effective_count": len(evidence_ids),
                    "truncated": len(requested_evidence_ids) > len(evidence_ids),
                },
            },
            evidence_ids=found_ids,
            entity_ids=_unique_id_list(
                entity_id for card in cards for entity_id in card.linked_entities
            ),
            relation_ids=[],
        )

    def _inspect_entity(self, tool_input: dict[str, Any]) -> AgentToolResult:
        project_id = _required_str(tool_input, "project_id")
        entity_id = _required_str(tool_input, "entity_id")
        draft = self.service.load_draft(project_id)
        entity = next((item for item in draft.entities if item.id == entity_id), None)
        if entity is None:
            raise ToolExecutionError(f"Entity not found: {entity_id}")

        relations = [
            relation
            for relation in draft.relations
            if relation.source_id == entity_id or relation.target_id == entity_id
        ]
        total_relation_count = len(relations)
        relations = relations[:MAX_ENTITY_RELATIONS]
        neighbor_ids = _unique_id_list(
            relation.target_id if relation.source_id == entity_id else relation.source_id
            for relation in relations
        )
        neighbors = [item for item in draft.entities if item.id in set(neighbor_ids)]
        all_evidence_ids = _unique_id_list(
            [
                *entity.evidence_ids,
                *[
                    evidence_id
                    for relation in relations
                    for evidence_id in relation.evidence_ids
                ],
            ]
        )
        evidence_ids = all_evidence_ids[:MAX_EVIDENCE_CARDS]
        cards = _evidence_by_ids(draft, evidence_ids)
        found_evidence_ids = [card.id for card in cards]
        return AgentToolResult(
            tool_name="inspect_entity",
            summary=(
                f"Inspected entity {entity_id} with {len(relations)} connected relations."
            ),
            payload={
                "project_id": project_id,
                "entity": entity.to_dict(),
                "relations": [relation.to_dict() for relation in relations],
                "neighbor_entities": [neighbor.to_dict() for neighbor in neighbors],
                "evidence_cards": [card.to_dict() for card in cards],
                "metadata": {
                    "total_relation_count": total_relation_count,
                    "returned_relation_count": len(relations),
                    "returned_evidence_count": len(cards),
                    "truncated": total_relation_count > len(relations)
                    or len(all_evidence_ids) > len(evidence_ids),
                },
            },
            evidence_ids=found_evidence_ids,
            entity_ids=[entity_id],
            relation_ids=[relation.id for relation in relations],
        )

    def _run_specialist_agent(self, tool_input: dict[str, Any]) -> AgentToolResult:
        project_id = _required_str(tool_input, "project_id")
        role = _required_str(tool_input, "role")
        if role not in SPECIALIST_ROLES:
            raise ToolExecutionError(f"Unknown specialist role: {role}")

        from src.project_archive.multi_agent import run_specialist_role

        draft = self.service.load_draft(project_id)
        prior_agents = _prior_agents(tool_input.get("prior_agents"))
        try:
            result = run_specialist_role(
                draft=draft,
                role=role,
                prior_agents=prior_agents,
            )
        except ValueError as exc:
            raise ToolExecutionError(str(exc)) from exc
        return AgentToolResult(
            tool_name="run_specialist_agent",
            summary=result.summary,
            payload={"project_id": project_id, "agent": result.to_dict()},
            evidence_ids=list(result.evidence_card_ids),
            entity_ids=list(result.entity_ids),
            relation_ids=list(result.relation_ids),
        )


def _required_str(tool_input: dict[str, Any], key: str) -> str:
    value = tool_input.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolExecutionError(f"Agent tool input requires string field: {key}")
    return value.strip()


def _evidence_by_ids(
    draft: ProjectArchiveDraft,
    evidence_ids: list[str],
) -> list[EvidenceCard]:
    cards_by_id = {card.id: card for card in draft.evidence_cards}
    return [cards_by_id[evidence_id] for evidence_id in evidence_ids if evidence_id in cards_by_id]


def _unique_id_list(values: Any) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        if not isinstance(value, str) or not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _optional_str(value: Any, key: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ToolExecutionError(f"Agent tool input field must be a string: {key}")
    return value.strip() or None


def _string_list(value: Any, key: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ToolExecutionError(f"Agent tool input field must be a list of strings: {key}")
    rows: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ToolExecutionError(
                f"Agent tool input field must be a list of strings: {key}"
            )
        stripped = item.strip()
        if not stripped:
            raise ToolExecutionError(
                f"Agent tool input field must not contain blank strings: {key}"
            )
        rows.append(stripped)
    return rows


def _positive_int(value: Any, key: str) -> int:
    if isinstance(value, bool):
        raise ToolExecutionError(f"Agent tool input requires integer field: {key}")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float) and value.is_integer():
        parsed = int(value)
    elif isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
    else:
        raise ToolExecutionError(f"Agent tool input requires integer field: {key}")
    if parsed < 1:
        raise ToolExecutionError(f"Agent tool input field must be positive: {key}")
    return parsed


def _prior_agents(value: Any) -> dict[str, AgentRoleResult] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ToolExecutionError("prior_agents must be a dictionary when provided.")
    agents: dict[str, AgentRoleResult] = {}
    for name, result in value.items():
        if isinstance(result, AgentRoleResult):
            agents[str(name)] = result
        elif isinstance(result, dict):
            _validate_prior_agent_payload(str(name), result)
            try:
                agents[str(name)] = AgentRoleResult.from_dict(result)
            except (TypeError, ValueError) as exc:
                raise ToolExecutionError(
                    f"prior_agents contains malformed AgentRoleResult payload: {name}"
                ) from exc
        else:
            raise ToolExecutionError("prior_agents values must be AgentRoleResult payloads.")
    return agents


def _validate_prior_agent_payload(name: str, payload: dict[str, Any]) -> None:
    string_fields = ("agent", "status", "summary")
    list_fields = (
        "findings",
        "risks",
        "next_actions",
        "evidence_card_ids",
        "entity_ids",
        "relation_ids",
    )
    for field in string_fields:
        if not isinstance(payload.get(field), str):
            raise ToolExecutionError(
                f"prior_agents contains invalid AgentRoleResult payload for {name}: "
                f"{field} must be a string"
            )
    for field in list_fields:
        if field in payload and not isinstance(payload[field], list):
            raise ToolExecutionError(
                f"prior_agents contains invalid AgentRoleResult payload for {name}: "
                f"{field} must be a list"
            )
    if "metadata" in payload and not isinstance(payload["metadata"], dict):
        raise ToolExecutionError(
            f"prior_agents contains invalid AgentRoleResult payload for {name}: "
            "metadata must be a dictionary"
        )
    confidence = payload.get("confidence")
    if (
        confidence is not None
        and (isinstance(confidence, bool) or not isinstance(confidence, (int, float)))
    ):
        raise ToolExecutionError(
            f"prior_agents contains invalid AgentRoleResult payload for {name}: "
            "confidence must be numeric"
        )
