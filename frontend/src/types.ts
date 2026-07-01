export type MetricSet = {
  halls: number;
  entities: number;
  relations: number;
  evidence: number;
};

export type LanguageStat = {
  name: string;
  count: number;
};

export type ArchiveHall = {
  id: string;
  name: string;
  label: string;
  descriptionZh: string;
  count: number;
  description: string;
  dominantTypes: string[];
  sampleEntities: string[];
  risk: string;
  riskZh: string;
};

export type ArchiveRelation = {
  id: string;
  source: string;
  target: string;
  type: string;
  hall: string;
  hallIds?: string[];
  evidenceIds: string[];
};

export type EvidenceCard = {
  id: string;
  title: string;
  titleZh: string;
  sourcePath: string;
  sourceType: string;
  assetUrl?: string | null;
  modality?: string;
  snippet: string;
  snippetZh: string;
  lineRange: string;
  confidence: number;
  hall: string;
  hallIds?: string[];
  metadata?: Record<string, unknown>;
};

export type ArchiveDraft = {
  projectId: string;
  scope: string;
  languages: LanguageStat[];
  metrics: MetricSet;
  halls: ArchiveHall[];
  relations: ArchiveRelation[];
  evidenceCards: EvidenceCard[];
};

export type AgentReport = {
  mode: string;
  question: string;
  summary: string;
  affected_entities: string[];
  graph_paths?: {
    nodes: string[];
    relations: string[];
    evidence_ids: string[];
  }[];
  evidence_card_ids: string[];
  risks: string[];
  next_actions: string[];
  confidence: number;
  metadata?: {
    llm?: {
      enabled?: boolean;
      provider?: string;
      model?: string;
      fallback?: boolean;
      error?: string;
    };
    hybrid_rag?: {
      enabled?: boolean;
      result_count?: number;
      text_chunks?: number;
      image_chunks?: number;
      indexed_chunks?: number;
      fallback_reasons?: string[];
      error?: string;
    };
    evidence_modalities?: Record<string, number>;
    cited_image_evidence_count?: number;
  };
};

export type AgentStatus = {
  llm_enabled: boolean;
  provider: string;
  mode: string;
  model: string | null;
};

export type GraphStoreStatus = {
  provider: string;
  mode: string;
  database: string | null;
  uri: string | null;
  project_isolation: boolean;
};

export type SystemConfigComponent = {
  id: string;
  label: string;
  status: "working" | "warning" | "disabled" | "error" | string;
  provider: string;
  model: string | null;
  configured: boolean;
  working: boolean;
  details: Record<string, unknown>;
  warnings: string[];
  last_success: Record<string, unknown> | null;
};

export type SystemConfigCheck = {
  status: "working" | "warning" | "partial" | "error" | string;
  summary: string;
  components: SystemConfigComponent[];
  metadata: Record<string, unknown>;
};

export type AgentRoleResult = {
  agent: string;
  status: string;
  summary: string;
  evidence_card_ids: string[];
  entity_ids: string[];
  relation_ids: string[];
  findings: Record<string, unknown>[];
  risks: Record<string, unknown>[];
  next_actions: string[];
  confidence: number;
  metadata?: {
    agent_sdk?: {
      spec_version?: string;
      name?: string;
      title?: string;
      mission?: string;
      depends_on?: string[];
      expected_inputs?: string[];
      expected_outputs?: string[];
      tools?: string[];
      started_at?: string;
      completed_at?: string;
      input_counts?: Record<string, number>;
      handoffs?: Record<string, {
        status?: string;
        confidence?: number;
        summary?: string;
        evidence_card_ids?: string[];
        entity_ids?: string[];
        relation_ids?: string[];
      }>;
      work_log?: {
        step?: string;
        detail?: string;
        tools?: string[];
      }[];
      validation?: {
        status?: string;
        notes?: string[];
        missing_dependencies?: string[];
        missing_outputs?: string[];
      };
    };
    llm?: {
      enabled?: boolean;
      provider?: string;
      model?: string;
      fallback?: boolean;
      error?: string;
    };
  };
};

export type ProjectAgentReport = {
  project_id: string;
  status: string;
  provider: string;
  model: string | null;
  created_at: string;
  scan_profile: string;
  agents: Record<string, AgentRoleResult>;
  errors: string[];
  metrics: MetricSet;
};

export type ProjectIntelligenceReport = {
  project_id: string;
  created_at: string;
  summary: string;
  architecture_layers: Array<Record<string, unknown>>;
  core_modules: Array<Record<string, unknown>>;
  entry_points: Array<Record<string, unknown>>;
  config_dependencies: Array<Record<string, unknown>>;
  call_chains: Array<Record<string, unknown>>;
  risks: Array<Record<string, unknown>>;
  evidence_chain: Array<Record<string, unknown>>;
  rag_citations: Record<string, unknown>;
  multimodal_evidence: Record<string, unknown>;
  next_actions: string[];
  sections?: Array<Record<string, unknown>>;
  risk_index?: Record<string, unknown>;
  evidence_index?: Record<string, unknown>;
  coverage: Record<string, number | string>;
  metadata: Record<string, unknown>;
};

export type HybridRagStatus = {
  project_id: string;
  indexed_chunks: number;
  text_chunks: number;
  image_chunks: number;
  candidate_chunks?: number;
  coverage_ratio?: number;
  coverage_percent?: number;
  indexing_policy?: string;
  stale?: boolean;
  health?: string;
  health_warnings?: string[];
  dense_provider: string;
  dense_dimension: number;
  vision_provider: string;
  vision_enabled: boolean;
  fallback_reasons: string[];
  collection_name?: string;
  bm25_collection?: string;
};

export type IngestionDiagnostics = {
  project_id: string;
  created_at: string;
  scan_profile: string;
  upload: Record<string, unknown>;
  scan: Record<string, unknown>;
  extraction: Record<string, unknown>;
  graph: Record<string, unknown>;
  images: Record<string, unknown>;
  hybrid_rag: Record<string, unknown>;
  health: {
    score?: number;
    status?: string;
    warnings?: string[];
  };
  recommendations: string[];
};

export type ArchiveEvaluationCaseResult = {
  question_id: string;
  question: string;
  category: string;
  mode: string;
  expected_entity_ids: string[];
  expected_relation_ids: string[];
  expected_evidence_ids: string[];
  matched_entity_ids: string[];
  matched_relation_ids: string[];
  matched_evidence_ids: string[];
  metrics: Record<string, number>;
  summary: string;
  metadata: Record<string, unknown>;
};

export type ArchiveEvaluationReport = {
  project_id: string;
  created_at: string;
  golden_question_count: number;
  aggregate_metrics: Record<string, number>;
  case_results: ArchiveEvaluationCaseResult[];
  metadata: Record<string, unknown>;
};

export type EvaluationHistory = {
  project_id: string | null;
  runs: Array<Record<string, unknown>>;
  metrics: Record<string, number>;
};

export type StressTestProjectReport = {
  project_id: string;
  status: "pass" | "warn" | "fail" | string;
  quality_score: number;
  quality_grade: string;
  evaluation_available: boolean;
  evaluation_score: number;
  evaluation_metrics: Record<string, number>;
  evaluation_error: string;
  hybrid_rag_ready: boolean;
  hybrid_rag: Record<string, unknown>;
  multimodal_ready: boolean;
  multimodal: Record<string, unknown>;
  metrics: Record<string, number>;
  top_entity_types: Array<[string, number]>;
  warnings: string[];
  recommendations: string[];
};

export type StressTestReport = {
  id: string;
  created_at: string;
  project_ids: string[];
  summary: Record<string, number>;
  projects: StressTestProjectReport[];
  regression_matrix?: Array<Record<string, unknown>>;
  language_coverage?: Record<string, unknown>;
  blocking_failures?: Array<Record<string, unknown>>;
  recommendations: string[];
  metadata: Record<string, unknown>;
};

export type GraphWorkspaceReport = {
  project_id: string;
  created_at: string;
  summary: GraphSummary;
  quality?: {
    score: number;
    grade: string;
    component_scores: Record<string, number>;
    weights: Record<string, number>;
    signals: Record<string, number>;
    warnings: string[];
    recommendations: string[];
  };
  entry_points?: Array<Record<string, unknown>>;
  entity_quality?: {
    score?: number;
    grade?: string;
    duplicate_candidates?: Array<Record<string, unknown>>;
    noisy_entities?: Array<Record<string, unknown>>;
    important_entities?: Array<Record<string, unknown>>;
    unsupported_relations?: Array<Record<string, unknown>>;
    metrics?: Record<string, number>;
    recommendations?: string[];
  };
  language_structure?: Record<string, unknown>;
  module_clusters: Array<Record<string, unknown>>;
  module_boundaries: Array<Record<string, unknown>>;
  relation_confidence: Array<Record<string, unknown>>;
  weak_relations: Array<Record<string, unknown>>;
  curation: Record<string, unknown>;
  saved_viewpoints: Record<string, unknown>;
  snapshot: Record<string, unknown>;
  snapshot_diff: Record<string, unknown>;
  metadata: Record<string, unknown>;
};

export type AgentTrustReport = {
  project_id: string;
  created_at: string;
  claims: Array<Record<string, unknown>>;
  warnings: string[];
  metrics: Record<string, number>;
  metadata: Record<string, unknown>;
};

export type AgentEvalGate = {
  id: string;
  label: string;
  status: "pass" | "warn" | "fail" | string;
  score: number;
  warn_threshold: number;
  fail_threshold: number;
  summary: string;
};

export type AgentEvalRegression = {
  status: "baseline" | "pass" | "warn" | "fail" | string;
  summary: string;
  previous_run_id?: string;
  previous_created_at?: string;
  checks: Array<Record<string, unknown>>;
};

export type AgentEvalReport = {
  id: string;
  project_id: string;
  created_at: string;
  status: "pass" | "warn" | "fail" | string;
  duration_seconds: number;
  metrics: Record<string, unknown>;
  quality_gates: AgentEvalGate[];
  regression: AgentEvalRegression;
  recommendations: string[];
  artifacts: Record<string, string>;
  metadata: Record<string, unknown>;
  memory_update?: Record<string, unknown>;
};

export type AgentMemoryItem = {
  title?: string;
  text?: string;
  severity?: string;
  source?: string;
  created_at?: string;
  metadata?: Record<string, unknown>;
};

export type AgentMemory = {
  project_id: string;
  updated_at: string;
  facts: AgentMemoryItem[];
  entities: string[];
  evidence: string[];
  relations: string[];
  risks: AgentMemoryItem[];
  harness_runs: Array<Record<string, unknown>>;
  recommendations: string[];
  metadata: Record<string, unknown>;
};

export type MultimodalInsights = {
  project_id: string;
  created_at: string;
  image_count: number;
  vision_supported: number;
  ocr_supported: number;
  average_quality: number;
  method_counts?: Record<string, number>;
  entity_alignment?: {
    aligned_image_count?: number;
    alignment_count?: number;
    items?: Array<Record<string, unknown>>;
  };
  evidence_support?: Record<string, unknown>;
  images: Array<Record<string, unknown>>;
  graph_contributions: Record<string, unknown>;
  metadata: Record<string, unknown>;
};

export type ProjectUniverseProject = {
  project_id: string;
  metrics: Record<string, number>;
  top_entity_types: { type: string; count: number }[];
  evidence_modalities: Record<string, number>;
  hall_names: string[];
};

export type ProjectUniverseEntityRef = {
  project_id: string;
  entity_id: string;
  label: string;
  type: string;
  source_path: string | null;
  degree: number;
  evidence_count: number;
  hall_ids: string[];
};

export type ProjectUniverseLink = {
  id: string;
  type: string;
  source: ProjectUniverseEntityRef;
  target: ProjectUniverseEntityRef;
  score: number;
  reason: string;
  shared_key: string;
};

export type ProjectUniverseCluster = {
  id: string;
  label: string;
  type: string;
  project_ids: string[];
  entity_refs: ProjectUniverseEntityRef[];
  score: number;
};

export type ProjectKnowledgeUniverse = {
  created_at: string;
  project_ids: string[];
  metrics: Record<string, number>;
  projects: ProjectUniverseProject[];
  links: ProjectUniverseLink[];
  clusters: ProjectUniverseCluster[];
  metadata: Record<string, unknown>;
};

export type UniverseExplorationPath = {
  id: string;
  name: string;
  project_ids: string[];
  cluster_ids: string[];
  link_ids: string[];
  notes: string;
  created_at: string;
  metadata: Record<string, unknown>;
};

export type UniverseAgentTask = {
  id: string;
  status: string;
  objective: string;
  project_ids: string[];
  cluster_ids: string[];
  link_ids: string[];
  findings: Array<Record<string, unknown>>;
  evidence: Array<Record<string, unknown>>;
  next_actions: string[];
  created_at: string;
  completed_at: string;
  metadata: Record<string, unknown>;
};

export type ProjectArchitectureDiffReport = {
  id: string;
  left_project_id: string;
  right_project_id: string;
  created_at: string;
  summary: string;
  shared_clusters: ProjectUniverseCluster[];
  shared_links: ProjectUniverseLink[];
  only_left: ProjectUniverseEntityRef[];
  only_right: ProjectUniverseEntityRef[];
  metric_delta: Record<string, number>;
  findings: Array<Record<string, unknown>>;
  recommendations: string[];
  sections: Array<Record<string, unknown>>;
  evidence_chain: Array<Record<string, unknown>>;
  component_delta: Record<string, unknown>;
  risk_points: Array<Record<string, unknown>>;
  migration_notes: string[];
  metadata: Record<string, unknown>;
};

export type ArchiveJob = {
  id: string;
  kind: string;
  status: "queued" | "running" | "complete" | "failed" | "cancelled";
  progress: number;
  message: string;
  project_id: string | null;
  result?: Record<string, unknown> | null;
  error?: string | null;
  steps: { progress: number; message: string }[];
  cancel_requested?: boolean;
  retry_count?: number;
  retry_of?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type GraphExplorerNode = {
  id: string;
  label: string;
  type: string;
  hall_ids: string[];
  source_path: string | null;
  evidence_ids: string[];
  degree: number;
  importance: number;
  tags: string[];
};

export type GraphExplorerRelation = {
  id: string;
  source_id: string;
  target_id: string;
  type: string;
  evidence_ids: string[];
  hall_ids: string[];
  weight: number;
};

export type RecommendedGraphStart = {
  entity_id: string;
  label: string;
  group: string;
  reason: string;
  score: number;
  hall_ids: string[];
};

export type GraphSummary = {
  project_id: string;
  metrics: {
    entities: number;
    relations: number;
    evidence: number;
  };
  recommended_starts: RecommendedGraphStart[];
};

export type GraphNeighborhood = {
  project_id: string;
  hall_id: string | null;
  focus_entity_id: string | null;
  depth: number;
  nodes: GraphExplorerNode[];
  relations: GraphExplorerRelation[];
  evidence_ids: string[];
  is_sparse: boolean;
  sparse_reason: string | null;
};

export type GraphSearchResult = {
  entity_id: string;
  label: string;
  type: string;
  source_path: string | null;
  hall_ids: string[];
  evidence_ids: string[];
  degree: number;
  score: number;
  matched_fields: string[];
};

export type GraphMergeCandidate = {
  id: string;
  label: string;
  entityIds: string[];
  createdAt: string;
};

export type GraphCurationState = {
  projectId: string;
  importantEntityIds: string[];
  hiddenRelationIds: string[];
  mergeCandidates: GraphMergeCandidate[];
  updatedAt: string;
};

export type MissionGraphOverlay = {
  mission_id: string;
  explored_node_ids: string[];
  explored_relation_ids: string[];
  risk_node_ids: string[];
  risk_relation_ids: string[];
  annotations: Record<string, unknown>[];
};

export type MissionTask = {
  id: string;
  mission_id: string;
  status: string;
  agent: string;
  task_type: string;
  title: string;
  input_entity_ids: string[];
  input_relation_ids: string[];
  evidence_ids: string[];
  findings: Record<string, unknown>[];
  risks: Record<string, unknown>[];
  confidence: number;
  verifier_status: string;
  created_at: string;
  completed_at: string;
};

export type AutonomousMission = {
  id: string;
  project_id: string;
  goal: string;
  status: string;
  max_steps: number;
  stop_reason: string;
  created_at: string;
  completed_at: string;
  tasks: MissionTask[];
  graph_overlay: MissionGraphOverlay | null;
};

export type AgentMissionBudget = {
  max_tasks: number;
  max_steps_per_task: number;
  max_tool_calls: number;
  timeout_seconds: number;
};

export type AgentMissionTask = {
  id: string;
  mission_id: string;
  task_type: string;
  objective: string;
  status: string;
  allowed_tools: string[];
  max_steps: number;
  steps_used: number;
  input_entity_ids: string[];
  output_entity_ids: string[];
  evidence_ids: string[];
  findings: Array<Record<string, unknown>>;
  risks: Array<Record<string, unknown>>;
  confidence: number;
  created_at: string;
  completed_at: string;
  metadata: Record<string, unknown>;
};

export type AgentTraceEvent = {
  id: string;
  mission_id: string;
  task_id: string;
  sequence: number;
  event_type: "plan" | "action" | "observation" | "verification" | "final" | string;
  tool_name?: string | null;
  tool_input: Record<string, unknown>;
  observation_summary: string;
  evidence_ids: string[];
  entity_ids: string[];
  relation_ids: string[];
  started_at: string;
  completed_at: string;
  error?: string | null;
  metadata: Record<string, unknown>;
};

export type AgentMissionVerifierResult = {
  status: string;
  supported_finding_count: number;
  uncertain_finding_count: number;
  warnings: string[];
};

export type AgentMissionFinalReport = {
  summary: string;
  findings: Array<Record<string, unknown>>;
  evidence_ids: string[];
  confidence: number;
};

export type AgentMission = {
  id: string;
  project_id: string;
  goal: string;
  status: string;
  created_at: string;
  completed_at: string;
  budget: AgentMissionBudget;
  tasks: AgentMissionTask[];
  trace_events: AgentTraceEvent[];
  verifier_result?: AgentMissionVerifierResult | null;
  final_report?: AgentMissionFinalReport | null;
  metadata: Record<string, unknown>;
};

export type AgentMissionVisualization = {
  mission_id: string;
  project_id: string;
  created_at: string;
  status: string;
  goal: string;
  loop_phases: Array<Record<string, unknown>>;
  task_cards: Array<Record<string, unknown>>;
  tool_timeline: Array<Record<string, unknown>>;
  audit: Record<string, unknown>;
  warnings: string[];
  metadata: Record<string, unknown>;
};

export type AgentTaskPlan = {
  project_id: string;
  created_at: string;
  summary: string;
  tasks: Array<Record<string, unknown>>;
  metadata: Record<string, unknown>;
};
