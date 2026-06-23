"""Dashboard internationalization helpers."""

from __future__ import annotations

from typing import Any

DEFAULT_LANGUAGE = "zh"
LANGUAGE_STATE_KEY = "dashboard_language"

LANGUAGE_OPTIONS = {
    "zh": "中文",
    "en": "English",
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "app.page_title": "TwinMind Archive Dashboard",
        "language.label": "Language",
        "language.zh": "中文",
        "language.en": "English",
        "nav.overview": "Overview",
        "nav.data_browser": "Data Browser",
        "nav.ingestion_manager": "Ingestion Manager",
        "nav.ingestion_traces": "Ingestion Traces",
        "nav.query_traces": "Query Traces",
        "nav.evaluation_panel": "Evaluation Panel",
        "nav.twinmind_archive": "TwinMind Archive",
        "twin.header": "TwinMind Archive",
        "twin.archive_storage": "Archive storage",
        "twin.ingest_project": "Ingest Project",
        "twin.project_path": "Project path",
        "twin.project_id": "Project ID",
        "twin.build_archive": "Build Archive",
        "twin.building_archive": "Building TwinMind archive...",
        "twin.archive_built": "Archive built: {entities} entities, {relations} relations, {evidence} evidence cards.",
        "twin.archive_build_failed": "Archive build failed: {error}",
        "twin.no_archives": "No project archives found yet.",
        "twin.project_archive": "Project archive",
        "twin.load_failed": "Failed to load project archive: {error}",
        "twin.metric.halls": "Halls",
        "twin.metric.entities": "Entities",
        "twin.metric.relations": "Relations",
        "twin.metric.evidence": "Evidence",
        "twin.archive_halls": "Archive Halls",
        "twin.no_entities": "No entities assigned yet.",
        "twin.star_map": "Star Map",
        "twin.no_relations": "No archive relations were extracted yet.",
        "twin.entity_types": "Entity Types",
        "twin.relation_types": "Relation Types",
        "twin.agent_query": "Agent Query",
        "twin.mode": "Mode",
        "twin.question": "Question",
        "twin.default_question": "What should I understand first about this project?",
        "twin.run_query": "Run Query",
        "twin.tracing_evidence": "Tracing archive evidence...",
        "twin.fallback_question": "Summarize this project archive.",
        "twin.query_failed": "Query failed: {error}",
        "twin.mode.architecture_tour": "Architecture Tour",
        "twin.mode.impact_analysis": "Impact Analysis",
        "twin.mode.risk_audit": "Risk Audit",
        "twin.mode.evidence_qa": "Evidence Q&A",
        "twin.result.mode": "Mode",
        "twin.result.confidence": "Confidence",
        "twin.result.affected_entities": "Affected entities",
        "twin.result.evidence_cards": "Evidence cards",
        "twin.result.risks": "Risks",
        "twin.result.next_actions": "Next actions",
        "table.type": "type",
        "table.count": "count",
        "table.source": "source",
        "table.relation": "relation",
        "table.target": "target",
    },
    "zh": {
        "app.page_title": "TwinMind Archive 控制台",
        "language.label": "语言",
        "language.zh": "中文",
        "language.en": "English",
        "nav.overview": "总览",
        "nav.data_browser": "数据浏览",
        "nav.ingestion_manager": "摄取管理",
        "nav.ingestion_traces": "摄取追踪",
        "nav.query_traces": "查询追踪",
        "nav.evaluation_panel": "评估面板",
        "nav.twinmind_archive": "TwinMind 档案馆",
        "twin.header": "TwinMind 档案馆",
        "twin.archive_storage": "档案存储位置",
        "twin.ingest_project": "摄取项目",
        "twin.project_path": "项目路径",
        "twin.project_id": "项目 ID",
        "twin.build_archive": "构建档案",
        "twin.building_archive": "正在构建 TwinMind 档案...",
        "twin.archive_built": "档案已构建：{entities} 个实体，{relations} 条关系，{evidence} 张证据卡。",
        "twin.archive_build_failed": "档案构建失败：{error}",
        "twin.no_archives": "还没有找到项目档案。",
        "twin.project_archive": "项目档案",
        "twin.load_failed": "项目档案加载失败：{error}",
        "twin.metric.halls": "展厅",
        "twin.metric.entities": "实体",
        "twin.metric.relations": "关系",
        "twin.metric.evidence": "证据",
        "twin.archive_halls": "档案展厅",
        "twin.no_entities": "暂时没有分配实体。",
        "twin.star_map": "星图",
        "twin.no_relations": "暂时没有抽取到档案关系。",
        "twin.entity_types": "实体类型",
        "twin.relation_types": "关系类型",
        "twin.agent_query": "Agent 查询",
        "twin.mode": "模式",
        "twin.question": "问题",
        "twin.default_question": "我应该先理解这个项目的哪些部分？",
        "twin.run_query": "运行查询",
        "twin.tracing_evidence": "正在追踪档案证据...",
        "twin.fallback_question": "总结这个项目档案。",
        "twin.query_failed": "查询失败：{error}",
        "twin.mode.architecture_tour": "架构导览",
        "twin.mode.impact_analysis": "影响分析",
        "twin.mode.risk_audit": "风险审计",
        "twin.mode.evidence_qa": "证据问答",
        "twin.result.mode": "模式",
        "twin.result.confidence": "置信度",
        "twin.result.affected_entities": "受影响实体",
        "twin.result.evidence_cards": "证据卡",
        "twin.result.risks": "风险",
        "twin.result.next_actions": "下一步行动",
        "table.type": "类型",
        "table.count": "数量",
        "table.source": "来源",
        "table.relation": "关系",
        "table.target": "目标",
    },
}


def normalize_language(language: str | None) -> str:
    """Return a supported language code."""
    if language in LANGUAGE_OPTIONS:
        return language
    return DEFAULT_LANGUAGE


def t(key: str, language: str | None = None, **kwargs: Any) -> str:
    """Translate a text key and format it with optional keyword values."""
    normalized = normalize_language(language)
    text = TRANSLATIONS.get(normalized, {}).get(key)
    if text is None:
        text = TRANSLATIONS["en"].get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text


def current_language() -> str:
    """Read the current Streamlit language, falling back outside Streamlit."""
    try:
        import streamlit as st

        return normalize_language(st.session_state.get(LANGUAGE_STATE_KEY))
    except Exception:
        return DEFAULT_LANGUAGE
