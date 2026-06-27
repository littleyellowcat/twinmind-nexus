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
  snippet: string;
  snippetZh: string;
  lineRange: string;
  confidence: number;
  hall: string;
  hallIds?: string[];
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
  };
};

export type AgentStatus = {
  llm_enabled: boolean;
  provider: string;
  mode: string;
  model: string | null;
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
      title?: string;
      mission?: string;
      depends_on?: string[];
      tools?: string[];
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

export type HybridRagStatus = {
  project_id: string;
  indexed_chunks: number;
  text_chunks: number;
  image_chunks: number;
  dense_provider: string;
  dense_dimension: number;
  vision_provider: string;
  vision_enabled: boolean;
  fallback_reasons: string[];
  collection_name?: string;
  bm25_collection?: string;
};

export type ArchiveJob = {
  id: string;
  kind: string;
  status: "queued" | "running" | "complete" | "failed";
  progress: number;
  message: string;
  project_id: string | null;
  result?: Record<string, unknown> | null;
  error?: string | null;
  steps: { progress: number; message: string }[];
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
