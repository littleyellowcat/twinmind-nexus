from pathlib import Path

import pytest

from src.mcp_server.tools.ingest_project_archive import IngestProjectArchiveTool
from src.mcp_server.tools.query_project_twin import QueryProjectTwinTool


@pytest.mark.asyncio
async def test_query_project_twin_tool_returns_agent_result(tmp_path):
    project_root = Path("tests/fixtures/project_archive_sample")
    ingest_tool = IngestProjectArchiveTool(storage_dir=tmp_path)
    query_tool = QueryProjectTwinTool(storage_dir=tmp_path)
    await ingest_tool.execute(project_path=str(project_root), project_id="sample")

    result = await query_tool.execute(
        project_id="sample",
        question="What is the architecture?",
        mode="architecture_tour",
    )

    assert "architecture_tour" in result
    assert "evidence" in result.lower()
