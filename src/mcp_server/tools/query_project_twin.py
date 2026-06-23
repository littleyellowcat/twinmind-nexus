"""MCP Tool: query_project_twin.

This tool queries a previously ingested TwinMind Archive project using the
deterministic archive agent workflow.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, TYPE_CHECKING

from src.project_archive.service import ProjectArchiveService
from src.project_archive.types import QueryMode

if TYPE_CHECKING:
    from src.mcp_server.protocol_handler import ProtocolHandler
    from src.project_archive.types import AgentResult

logger = logging.getLogger(__name__)


TOOL_NAME = "query_project_twin"
TOOL_DESCRIPTION = """Query an ingested TwinMind Archive project.

Answers questions about a project archive in modes such as evidence_qa,
architecture_tour, impact_analysis, and risk_audit, returning summaries with
entities, evidence cards, risks, and suggested next actions.
"""

TOOL_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "project_id": {
            "type": "string",
            "description": "Identifier of a previously ingested project archive.",
        },
        "question": {
            "type": "string",
            "description": "Question to ask about the project twin.",
        },
        "mode": {
            "type": "string",
            "description": "Query mode to use.",
            "default": QueryMode.EVIDENCE_QA.value,
            "enum": [mode.value for mode in QueryMode],
        },
    },
    "required": ["project_id", "question"],
}


class QueryProjectTwinTool:
    """MCP tool for querying TwinMind Archive projects."""

    def __init__(self, storage_dir: Path | str = "data/project_archive") -> None:
        self.service = ProjectArchiveService(storage_dir=storage_dir)

    async def execute(
        self,
        project_id: str,
        question: str,
        mode: str = QueryMode.EVIDENCE_QA.value,
    ) -> str:
        """Query an ingested project and return a formatted agent result."""
        query_mode = QueryMode(mode)
        result = await asyncio.to_thread(
            self.service.query_project,
            project_id,
            question,
            query_mode,
        )
        return self._format_result(result)

    def _format_result(self, result: "AgentResult") -> str:
        return "\n".join(
            [
                f"Mode: {result.mode.value}",
                f"Summary: {result.summary}",
                f"Affected entities: {self._format_list(result.affected_entities)}",
                f"Evidence cards: {self._format_list(result.evidence_card_ids)}",
                f"Risks: {self._format_list(result.risks)}",
                f"Next actions: {self._format_list(result.next_actions)}",
            ]
        )

    def _format_list(self, values: Iterable[str]) -> str:
        items = list(values)
        if not items:
            return "None"
        return ", ".join(items)


_tool = QueryProjectTwinTool()


async def handle_tool(
    project_id: str,
    question: str,
    mode: str = QueryMode.EVIDENCE_QA.value,
) -> str:
    """Handle query_project_twin MCP calls."""
    return await _tool.execute(project_id=project_id, question=question, mode=mode)


def register_tool(protocol_handler: "ProtocolHandler") -> None:
    """Register query_project_twin with the protocol handler."""
    protocol_handler.register_tool(
        name=TOOL_NAME,
        description=TOOL_DESCRIPTION,
        input_schema=TOOL_INPUT_SCHEMA,
        handler=handle_tool,
    )
    logger.info("Registered MCP tool: %s", TOOL_NAME)
