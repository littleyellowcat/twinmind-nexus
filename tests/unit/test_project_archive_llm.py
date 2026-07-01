"""Tests for TwinMind Archive LLM-enhanced agent reports."""

from __future__ import annotations

from types import SimpleNamespace

from src.libs.llm import ChatResponse
from src.project_archive.agents import AgentWorkflow
from src.project_archive.llm import ArchiveLLMEnhancer, create_archive_llm_enhancer_from_config
from src.project_archive.multi_agent import MultiAgentPipeline
from src.project_archive.types import (
    ArchiveHall,
    EvidenceCard,
    ProjectArchiveDraft,
    ProjectEntity,
    ProjectRelation,
    QueryMode,
)


class _FakeLLM:
    def chat(self, messages, trace=None, **kwargs):  # noqa: ANN001, ANN201
        return ChatResponse(
            content=(
                '{"summary":"DeepSeek-style architecture report.",'
                '"risks":["Check module coupling."],'
                '"next_actions":["Open cited files."],'
                '"evidence_card_ids":["ev:1"],'
                '"confidence":0.91}'
            ),
            model="deepseek-test",
            usage={"total_tokens": 42},
        )


class _CapturingJSONModeLLM:
    model = "deepseek-test"

    def __init__(self) -> None:
        self.kwargs: list[dict] = []

    def chat(self, messages, trace=None, **kwargs):  # noqa: ANN001, ANN201
        self.kwargs.append(dict(kwargs))
        return ChatResponse(
            content=(
                '{"summary":"JSON mode report.",'
                '"risks":[],"next_actions":[],"evidence_card_ids":["ev:1"],'
                '"confidence":0.9}'
            ),
            model=self.model,
            usage={"total_tokens": 24},
        )


class _CapturingRoleJSONModeLLM:
    model = "deepseek-test"

    def __init__(self) -> None:
        self.kwargs: list[dict] = []

    def chat(self, messages, trace=None, **kwargs):  # noqa: ANN001, ANN201
        self.kwargs.append(dict(kwargs))
        return ChatResponse(
            content=(
                '{"summary":"角色 JSON mode 输出。",'
                '"findings":[{"title":"入口","detail":"app.py 是入口。","evidence_ids":["ev:1"]}],'
                '"risks":[],"next_actions":["查看 app.py。"],'
                '"evidence_card_ids":["ev:1"],"confidence":0.86}'
            ),
            model=self.model,
            usage={"total_tokens": 32},
        )


class _NarrativeLLM:
    model = "deepseek-test"

    def chat(self, messages, trace=None, **kwargs):  # noqa: ANN001, ANN201
        return ChatResponse(
            content="这个项目的入口和配置已经可以作为架构导览起点。",
            model="deepseek-test",
            usage={"total_tokens": 18},
        )


class _RepairingLLM:
    model = "deepseek-test"

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages, trace=None, **kwargs):  # noqa: ANN001, ANN201
        self.calls += 1
        system = messages[0].content if messages else ""
        if "JSON repair" in system:
            return ChatResponse(
                content=(
                    '{"summary":"修复后的结构化架构报告。",'
                    '"risks":["确认入口模块边界。"],'
                    '"next_actions":["查看 app.py。"],'
                    '"evidence_card_ids":["ev:1"],'
                    '"confidence":0.82}'
                ),
                model="deepseek-test",
                usage={"total_tokens": 31},
            )
        return ChatResponse(
            content="这个项目可以从 app.py 开始理解，但我这次没有按 JSON 输出。",
            model="deepseek-test",
            usage={"total_tokens": 19},
        )


class _RepairingRoleLLM:
    model = "deepseek-test"

    def chat(self, messages, trace=None, **kwargs):  # noqa: ANN001, ANN201
        system = messages[0].content if messages else ""
        if "JSON repair" in system:
            return ChatResponse(
                content=(
                    '{"summary":"角色输出已被修复成结构化 JSON。",'
                    '"findings":[{"title":"入口","detail":"app.py 是入口候选。","evidence_ids":["ev:1"]}],'
                    '"risks":[],"next_actions":["检查入口调用链。"],'
                    '"evidence_card_ids":["ev:1"],"confidence":0.8}'
                ),
                model="deepseek-test",
                usage={"total_tokens": 37},
            )
        return ChatResponse(
            content="app.py 是入口候选，但这不是 JSON。",
            model="deepseek-test",
            usage={"total_tokens": 13},
        )


class _RegeneratingRoleLLM:
    model = "deepseek-test"

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages, trace=None, **kwargs):  # noqa: ANN001, ANN201
        self.calls += 1
        system = messages[0].content if messages else ""
        if "Regenerate" in system:
            return ChatResponse(
                content=(
                    '{"summary":"严格再生成后的角色 JSON。",'
                    '"findings":[{"title":"入口","detail":"app.py 是入口。","evidence_ids":["ev:1"]}],'
                    '"risks":[],"next_actions":["查看 app.py。"],'
                    '"evidence_card_ids":["ev:1"],"confidence":0.83}'
                ),
                model=self.model,
                usage={"total_tokens": 34},
            )
        return ChatResponse(
            content='{"summary":',
            model=self.model,
            usage={"total_tokens": 2200},
        )


class _NestedSummaryRoleLLM:
    model = "deepseek-test"

    def chat(self, messages, trace=None, **kwargs):  # noqa: ANN001, ANN201
        return ChatResponse(
            content=(
                '{"summary":"{\\"summary\\":\\"嵌套摘要已展开。\\",'
                '\\"findings\\":[{\\"title\\":\\"入口\\",\\"detail\\":\\"app.py 是入口。\\",'
                '\\"evidence_ids\\":[\\"ev:1\\"]}],'
                '\\"risks\\":[],\\"next_actions\\":[\\"查看 app.py。\\"],'
                '\\"evidence_card_ids\\":[\\"ev:1\\"],\\"confidence\\":0.84}"}'
            ),
            model="deepseek-test",
            usage={"total_tokens": 29},
        )


class _FailingEnhancer:
    provider = "deepseek"

    def enhance(self, result, *, evidence_cards, entities, relations):  # noqa: ANN001, ANN201
        raise RuntimeError("boom")


def test_agent_workflow_can_enhance_report_with_llm() -> None:
    workflow = AgentWorkflow(
        entities=[ProjectEntity(id="file:app", type="File", name="app.py")],
        relations=[],
        evidence_cards=[
            EvidenceCard(
                id="ev:1",
                source_type="code",
                source_path="app.py",
                title="app",
                snippet="def run(): pass",
            )
        ],
        enhancer=ArchiveLLMEnhancer(_FakeLLM()),
    )

    result = workflow.run("解释这个项目", QueryMode.ARCHITECTURE_TOUR)

    assert result.summary == "DeepSeek-style architecture report."
    assert result.risks == ["Check module coupling."]
    assert result.next_actions == ["Open cited files."]
    assert result.evidence_card_ids == ["ev:1"]
    assert result.confidence == 0.91
    assert result.metadata["llm"]["provider"] == "deepseek"
    assert result.metadata["llm"]["model"] == "deepseek-test"


def test_agent_workflow_requests_json_mode_for_structured_llm() -> None:
    llm = _CapturingJSONModeLLM()
    workflow = AgentWorkflow(
        entities=[ProjectEntity(id="file:app", type="File", name="app.py")],
        relations=[],
        evidence_cards=[
            EvidenceCard(
                id="ev:1",
                source_type="code",
                source_path="app.py",
                title="app",
                snippet="def run(): pass",
            )
        ],
        enhancer=ArchiveLLMEnhancer(llm),
    )

    result = workflow.run("解释这个项目", QueryMode.ARCHITECTURE_TOUR)

    assert result.summary == "JSON mode report."
    assert llm.kwargs[0]["response_format"] == {"type": "json_object"}
    assert llm.kwargs[0]["temperature"] == 0.0
    assert llm.kwargs[0]["max_tokens"] >= 1200


def test_agent_workflow_falls_back_when_llm_enhancement_fails() -> None:
    workflow = AgentWorkflow(
        entities=[ProjectEntity(id="file:app", type="File", name="app.py")],
        relations=[],
        evidence_cards=[],
        enhancer=_FailingEnhancer(),
    )

    result = workflow.run("解释这个项目", QueryMode.ARCHITECTURE_TOUR)

    assert result.summary == "Architecture tour assembled from archive structure."
    assert result.metadata["llm"]["fallback"] is True
    assert result.metadata["llm"]["provider"] == "deepseek"


def test_agent_workflow_uses_plain_text_llm_response_as_fallback_summary() -> None:
    workflow = AgentWorkflow(
        entities=[ProjectEntity(id="file:app", type="File", name="app.py")],
        relations=[],
        evidence_cards=[
            EvidenceCard(
                id="ev:1",
                source_type="code",
                source_path="app.py",
                title="app",
                snippet="def run(): pass",
            )
        ],
        enhancer=ArchiveLLMEnhancer(_NarrativeLLM()),
    )

    result = workflow.run("解释这个项目", QueryMode.ARCHITECTURE_TOUR)

    assert "架构导览起点" in result.summary
    assert result.metadata["llm"]["fallback"] is True
    assert "JSON" in result.metadata["llm"]["error"]


def test_agent_workflow_repairs_non_json_llm_response_before_fallback() -> None:
    llm = _RepairingLLM()
    workflow = AgentWorkflow(
        entities=[ProjectEntity(id="file:app", type="File", name="app.py")],
        relations=[],
        evidence_cards=[
            EvidenceCard(
                id="ev:1",
                source_type="code",
                source_path="app.py",
                title="app",
                snippet="def run(): pass",
            )
        ],
        enhancer=ArchiveLLMEnhancer(llm),
    )

    result = workflow.run("解释这个项目", QueryMode.ARCHITECTURE_TOUR)

    assert result.summary == "修复后的结构化架构报告。"
    assert result.evidence_card_ids == ["ev:1"]
    assert result.metadata["llm"]["json_repaired"] is True
    assert "fallback" not in result.metadata["llm"]
    assert llm.calls == 2


def test_llm_enhancer_factory_reads_deepseek_key_from_settings(
    monkeypatch,
) -> None:
    settings = SimpleNamespace(
        llm=SimpleNamespace(
            provider="deepseek",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
            api_key="config-key",
            temperature=0.2,
            max_tokens=1200,
            timeout_seconds=60.0,
        )
    )
    captured = {}

    def fake_create(settings, **kwargs):  # noqa: ANN001, ANN202
        captured["settings"] = settings
        captured["kwargs"] = kwargs
        return _FakeLLM()

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("src.project_archive.llm.load_settings", lambda: settings)
    monkeypatch.setattr("src.project_archive.llm.LLMFactory.create", fake_create)

    enhancer = create_archive_llm_enhancer_from_config()

    assert enhancer is not None
    assert captured["kwargs"]["api_key"] == "config-key"
    assert captured["kwargs"]["base_url"] == "https://api.deepseek.com"
    assert captured["kwargs"]["timeout"] == 60.0
    assert captured["settings"].llm.model == "deepseek-v4-flash"


def test_llm_enhancer_factory_allows_deepseek_timeout_override(
    monkeypatch,
) -> None:
    settings = SimpleNamespace(
        llm=SimpleNamespace(
            provider="deepseek",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
            api_key="config-key",
            temperature=0.2,
            max_tokens=1200,
            timeout_seconds=60.0,
        )
    )
    captured = {}

    def fake_create(settings, **kwargs):  # noqa: ANN001, ANN202
        captured["kwargs"] = kwargs
        return _FakeLLM()

    monkeypatch.setenv("TWINMIND_DEEPSEEK_TIMEOUT_SECONDS", "3.5")
    monkeypatch.setattr("src.project_archive.llm.load_settings", lambda: settings)
    monkeypatch.setattr("src.project_archive.llm.LLMFactory.create", fake_create)

    enhancer = create_archive_llm_enhancer_from_config()

    assert enhancer is not None
    assert captured["kwargs"]["timeout"] == 3.5


def test_multi_agent_pipeline_uses_narrative_llm_output_as_summary() -> None:
    draft = ProjectArchiveDraft(
        project_id="demo",
        halls=[
            ArchiveHall(
                id="hall:architecture",
                name="Architecture",
                description="Architecture hall",
                entity_ids=["file:app"],
            )
        ],
        entities=[ProjectEntity(id="file:app", type="File", name="app.py")],
        evidence_cards=[
            EvidenceCard(
                id="ev:1",
                source_type="code",
                source_path="app.py",
                title="app",
                snippet="def run(): pass",
                linked_entities=["file:app"],
            )
        ],
    )

    report = MultiAgentPipeline(llm=_NarrativeLLM(), provider="deepseek").run(
        draft=draft,
        scan_profile="architecture",
    )

    assert report.agents["curator"].status == "complete"
    assert "架构导览起点" in report.agents["curator"].summary
    assert report.agents["curator"].metadata["llm"]["model"] == "deepseek-test"


def test_multi_agent_pipeline_repairs_role_json_before_plain_text_fallback() -> None:
    draft = ProjectArchiveDraft(
        project_id="demo",
        halls=[
            ArchiveHall(
                id="hall:architecture",
                name="Architecture",
                description="Architecture hall",
                entity_ids=["file:app"],
            )
        ],
        entities=[ProjectEntity(id="file:app", type="File", name="app.py")],
        evidence_cards=[
            EvidenceCard(
                id="ev:1",
                source_type="code",
                source_path="app.py",
                title="app",
                snippet="def run(): pass",
                linked_entities=["file:app"],
            )
        ],
    )

    report = MultiAgentPipeline(llm=_RepairingRoleLLM(), provider="deepseek").run(
        draft=draft,
        scan_profile="architecture",
    )

    assert report.agents["curator"].summary == "角色输出已被修复成结构化 JSON。"
    assert report.agents["curator"].metadata["llm"]["json_repaired"] is True
    assert "fallback" not in report.agents["curator"].metadata["llm"]


def test_multi_agent_pipeline_regenerates_invalid_role_json_before_repair() -> None:
    draft = ProjectArchiveDraft(
        project_id="demo",
        halls=[
            ArchiveHall(
                id="hall:architecture",
                name="Architecture",
                description="Architecture hall",
                entity_ids=["file:app"],
            )
        ],
        entities=[ProjectEntity(id="file:app", type="File", name="app.py")],
        evidence_cards=[
            EvidenceCard(
                id="ev:1",
                source_type="code",
                source_path="app.py",
                title="app",
                snippet="def run(): pass",
                linked_entities=["file:app"],
            )
        ],
    )
    llm = _RegeneratingRoleLLM()

    report = MultiAgentPipeline(llm=llm, provider="deepseek").run(
        draft=draft,
        scan_profile="architecture",
    )

    assert report.agents["curator"].summary == "严格再生成后的角色 JSON。"
    assert report.agents["curator"].metadata["llm"]["json_regenerated"] is True
    assert "json_repaired" not in report.agents["curator"].metadata["llm"]
    assert llm.calls == 10


def test_multi_agent_pipeline_requests_json_mode_for_role_llm() -> None:
    draft = ProjectArchiveDraft(
        project_id="demo",
        halls=[
            ArchiveHall(
                id="hall:architecture",
                name="Architecture",
                description="Architecture hall",
                entity_ids=["file:app"],
            )
        ],
        entities=[ProjectEntity(id="file:app", type="File", name="app.py")],
        evidence_cards=[
            EvidenceCard(
                id="ev:1",
                source_type="code",
                source_path="app.py",
                title="app",
                snippet="def run(): pass",
                linked_entities=["file:app"],
            )
        ],
    )
    llm = _CapturingRoleJSONModeLLM()

    report = MultiAgentPipeline(llm=llm, provider="deepseek").run(
        draft=draft,
        scan_profile="architecture",
    )

    assert report.agents["curator"].summary == "角色 JSON mode 输出。"
    assert llm.kwargs
    assert all(kwargs["response_format"] == {"type": "json_object"} for kwargs in llm.kwargs)
    assert all(kwargs["temperature"] == 0.0 for kwargs in llm.kwargs)
    assert all(kwargs["max_tokens"] >= 1200 for kwargs in llm.kwargs)


def test_multi_agent_pipeline_unwraps_nested_json_summary() -> None:
    draft = ProjectArchiveDraft(
        project_id="demo",
        halls=[
            ArchiveHall(
                id="hall:architecture",
                name="Architecture",
                description="Architecture hall",
                entity_ids=["file:app"],
            )
        ],
        entities=[ProjectEntity(id="file:app", type="File", name="app.py")],
        evidence_cards=[
            EvidenceCard(
                id="ev:1",
                source_type="code",
                source_path="app.py",
                title="app",
                snippet="def run(): pass",
                linked_entities=["file:app"],
            )
        ],
    )

    report = MultiAgentPipeline(llm=_NestedSummaryRoleLLM(), provider="deepseek").run(
        draft=draft,
        scan_profile="architecture",
    )

    assert report.agents["curator"].summary == "嵌套摘要已展开。"
    assert report.agents["curator"].findings[0]["title"] == "入口"


def test_multi_agent_pipeline_records_agent_contracts_handoffs_and_validation() -> None:
    draft = ProjectArchiveDraft(
        project_id="demo",
        halls=[
            ArchiveHall(
                id="hall:architecture",
                name="Architecture",
                description="Architecture hall",
                entity_ids=["file:app", "config:settings"],
            ),
            ArchiveHall(
                id="hall:config",
                name="Configuration",
                description="Configuration hall",
                entity_ids=["config:settings"],
            ),
        ],
        entities=[
            ProjectEntity(id="file:app", type="File", name="app.py", evidence_ids=["ev:1"]),
            ProjectEntity(
                id="config:settings",
                type="Config",
                name="settings.yaml",
                evidence_ids=["ev:2"],
            ),
        ],
        relations=[
            ProjectRelation(
                id="rel:app-settings",
                source_id="file:app",
                target_id="config:settings",
                type="CONFIGURES",
                evidence_ids=["ev:2"],
            )
        ],
        evidence_cards=[
            EvidenceCard(
                id="ev:1",
                source_type="code",
                source_path="app.py",
                title="app",
                snippet="def run(): pass",
                linked_entities=["file:app"],
            ),
            EvidenceCard(
                id="ev:2",
                source_type="config",
                source_path="settings.yaml",
                title="settings",
                snippet="llm: deepseek",
                linked_entities=["config:settings"],
            ),
        ],
    )

    report = MultiAgentPipeline().run(draft=draft, scan_profile="architecture")

    assert set(report.agents) == {
        "archivist",
        "cartographer",
        "detective",
        "skeptic",
        "curator",
    }
    cartographer_runtime = report.agents["cartographer"].metadata["agent_sdk"]
    detective_runtime = report.agents["detective"].metadata["agent_sdk"]
    curator_runtime = report.agents["curator"].metadata["agent_sdk"]

    assert cartographer_runtime["spec_version"] == "twinmind-agent-spec-v1"
    assert cartographer_runtime["depends_on"] == ["archivist"]
    assert "archivist" in cartographer_runtime["handoffs"]
    assert cartographer_runtime["work_log"]
    assert cartographer_runtime["validation"]["status"] == "accepted"
    assert "cartographer" in detective_runtime["handoffs"]
    assert "skeptic" in curator_runtime["handoffs"]


def test_llm_enhancer_factory_ignores_placeholder_key(monkeypatch) -> None:
    settings = SimpleNamespace(
        llm=SimpleNamespace(
            provider="deepseek",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
            api_key="YOUR_DEEPSEEK_API_KEY_HERE",
            temperature=0.2,
            max_tokens=1200,
        )
    )
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("src.project_archive.llm.load_settings", lambda: settings)

    assert create_archive_llm_enhancer_from_config() is None
