"""MCP Tool: ingest_project_archive.

This tool ingests a local project into the TwinMind Archive graph and stores
the generated archive draft for later queries.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.project_archive.service import ProjectArchiveService

if TYPE_CHECKING:
    from src.mcp_server.protocol_handler import ProtocolHandler

logger = logging.getLogger(__name__)


TOOL_NAME = "ingest_project_archive"
TOOL_DESCRIPTION = """Ingest a project directory into the TwinMind Archive.

Scans source files and project metadata, builds archive halls, entities,
relations, and evidence cards, then persists the archive under the supplied
project_id for later query_project_twin calls.
"""

TOOL_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "project_path": {
            "type": "string",
            "description": "Path to the project directory to ingest.",
        },
        "project_id": {
            "type": "string",
            "description": "Stable identifier used to store and query the archive.",
        },
    },
    "required": ["project_path", "project_id"],
}


class IngestProjectArchiveTool:
    """MCP tool for TwinMind Archive ingestion."""

    def __init__(self, storage_dir: Path | str = "data/project_archive") -> None:
        self.service = ProjectArchiveService(storage_dir=storage_dir)

    async def execute(self, project_path: str, project_id: str) -> str:
        """Ingest a project and return a concise archive summary."""
        draft = await asyncio.to_thread(
            self.service.ingest_project,
            project_path,
            project_id,
        )

        return (
            f"Project archive ingested for '{draft.project_id}'.\n"
            f"- halls: {len(draft.halls)}\n"
            f"- entities: {len(draft.entities)}\n"
            f"- relations: {len(draft.relations)}\n"
            f"- evidence cards: {len(draft.evidence_cards)}"
        )


_tool = IngestProjectArchiveTool()


async def handle_tool(project_path: str, project_id: str) -> str:
    """Handle ingest_project_archive MCP calls."""
    return await _tool.execute(project_path=project_path, project_id=project_id)


def register_tool(protocol_handler: ProtocolHandler) -> None:
    """Register ingest_project_archive with the protocol handler."""
    protocol_handler.register_tool(
        name=TOOL_NAME,
        description=TOOL_DESCRIPTION,
        input_schema=TOOL_INPUT_SCHEMA,
        handler=handle_tool,
    )
    logger.info("Registered MCP tool: %s", TOOL_NAME)
