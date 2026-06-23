from src.project_archive.agents import AgentWorkflow
from src.project_archive.types import EvidenceCard, ProjectEntity, ProjectRelation, QueryMode


def _fixture_archive_parts():
    entities = [
        ProjectEntity(id="module_ingestion", type="Module", name="IngestionPipeline"),
        ProjectEntity(id="module_query", type="Module", name="QueryKnowledgeHubTool"),
        ProjectEntity(id="risk_main", type="Risk", name="main.py placeholder entry"),
    ]
    relations = [
        ProjectRelation(
            id="rel_impact",
            source_id="module_ingestion",
            target_id="module_query",
            type="AFFECTS",
            evidence_ids=["ev_pipeline"],
        )
    ]
    evidence = [
        EvidenceCard(
            id="ev_pipeline",
            source_type="code",
            source_path="src/ingestion/pipeline.py",
            title="Ingestion pipeline",
            snippet="class IngestionPipeline:",
        ),
        EvidenceCard(
            id="ev_main",
            source_type="code",
            source_path="main.py",
            title="Placeholder main",
            snippet="MCP Server will be implemented in Phase E.",
        ),
    ]
    return entities, relations, evidence


def test_impact_analysis_returns_affected_entities_and_evidence():
    entities, relations, evidence = _fixture_archive_parts()
    workflow = AgentWorkflow(entities=entities, relations=relations, evidence_cards=evidence)

    result = workflow.run(
        question="If I add a knowledge graph layer, which modules are affected?",
        mode=QueryMode.IMPACT_ANALYSIS,
    )

    assert result.mode == QueryMode.IMPACT_ANALYSIS
    assert "module_ingestion" in result.affected_entities
    assert "module_query" in result.affected_entities
    assert "ev_pipeline" in result.evidence_card_ids
    assert result.next_actions


def test_risk_audit_mentions_placeholder_entry_risk():
    entities, relations, evidence = _fixture_archive_parts()
    workflow = AgentWorkflow(entities=entities, relations=relations, evidence_cards=evidence)

    result = workflow.run(question="Does README match implementation?", mode=QueryMode.RISK_AUDIT)

    assert result.mode == QueryMode.RISK_AUDIT
    assert result.risks
    assert "ev_main" in result.evidence_card_ids


def test_architecture_tour_limits_affected_entities_to_first_twelve_matches():
    entities = [
        ProjectEntity(id=f"module_{index}", type="Module", name=f"Module{index}")
        for index in range(13)
    ]
    entities.append(ProjectEntity(id="risk_main", type="Risk", name="Placeholder risk"))
    workflow = AgentWorkflow(entities=entities, relations=[], evidence_cards=[])

    result = workflow.run(question="Show me the architecture.", mode=QueryMode.ARCHITECTURE_TOUR)

    assert result.mode == QueryMode.ARCHITECTURE_TOUR
    assert result.affected_entities == [f"module_{index}" for index in range(12)]
    assert len(result.affected_entities) == 12
