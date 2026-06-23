from pathlib import Path

import pytest

from src.mcp_server.tools.ingest_project_archive import IngestProjectArchiveTool


@pytest.mark.asyncio
async def test_ingest_project_archive_tool_returns_summary(tmp_path):
    project_root = Path("tests/fixtures/project_archive_sample")
    tool = IngestProjectArchiveTool(storage_dir=tmp_path)

    result = await tool.execute(project_path=str(project_root), project_id="sample")

    assert "sample" in result
    assert "halls" in result
    assert "entities" in result
