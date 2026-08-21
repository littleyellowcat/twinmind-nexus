import type {
  AgentMission,
  AgentTaskPlan,
  AgentMissionVisualization,
  AgentEvalReport,
  AgentMemory,
  AgentReport,
  AgentStatus,
  AgentTraceEvent,
  AgentTrustReport,
  ArchiveEvaluationReport,
  ArchiveJob,
  ArchiveDraft,
  ArchiveHall,
  ArchiveRelation,
  AutonomousMission,
  EvidenceCard,
  EvaluationHistory,
  GraphCurationState,
  GraphNeighborhood,
  GraphSearchResult,
  GraphSummary,
  GraphStoreStatus,
  GraphWorkspaceReport,
  HarnessRunSummary,
  HarnessArtifactManifest,
  HarnessArtifactCleanup,
  HarnessCommand,
  HarnessCommandDryRun,
  HarnessTimeline,
  HybridRagStatus,
  IngestionDiagnostics,
  MissionGraphOverlay,
  MissionTask,
  MultimodalInsights,
  ProjectArchitectureDiffReport,
  ProjectAgentReport,
  ProjectIntelligenceReport,
  ProjectKnowledgeUniverse,
  StressTestReport,
  SystemConfigCheck,
  UniverseAgentTask,
  UniverseExplorationPath,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_TWINMIND_API_URL ?? "http://127.0.0.1:8000";

type RawArchiveDraft = {
  project_id: string;
  halls?: RawHall[];
  entities?: RawEntity[];
  relations?: RawRelation[];
  evidence_cards?: RawEvidenceCard[];
};

type RawHall = {
  id: string;
  name: string;
  description: string;
  entity_ids?: string[];
};

type RawEntity = {
  id: string;
  type: string;
  name: string;
  source_path?: string | null;
  properties?: Record<string, unknown>;
};

type RawRelation = {
  id: string;
  source_id: string;
  target_id: string;
  type: string;
  evidence_ids?: string[];
};

type RawEvidenceCard = {
  id: string;
  source_type: string;
  source_path: string;
  title: string;
  snippet: string;
  line_start?: number | null;
  line_end?: number | null;
  confidence?: number;
  linked_entities?: string[];
  metadata?: Record<string, unknown>;
};

export type ArchiveDraftResult = {
  archiveIds: string[];
  draft: ArchiveDraft | null;
  source: "api" | "unavailable";
};

type UploadArchiveJobResult = {
  archive?: RawArchiveDraft;
  project_id?: string;
  metrics?: Record<string, number>;
};

type AgentReportJobResult = {
  agent_report?: ProjectAgentReport;
};

type RawGraphMergeCandidate = {
  id: string;
  label: string;
  entity_ids?: string[];
  created_at?: string;
};

type RawGraphCurationState = {
  project_id: string;
  important_entity_ids?: string[];
  hidden_relation_ids?: string[];
  merge_candidates?: RawGraphMergeCandidate[];
  updated_at?: string;
};

const DEFAULT_JOB_POLL_TIMEOUT_MS = 1000 * 60 * 6;
const ARCHIVE_UPLOAD_POLL_TIMEOUT_MS = 1000 * 60 * 30;
const AGENT_REPORT_POLL_TIMEOUT_MS = 1000 * 60 * 45;
const RAG_REBUILD_POLL_TIMEOUT_MS = 1000 * 60 * 30;

export type UploadArchiveResult = {
  draft: ArchiveDraft;
};

export async function fetchArchiveDraft(): Promise<ArchiveDraftResult> {
  try {
    const archiveIds = await listArchiveIds();
    return { archiveIds, draft: null, source: "api" };
  } catch (error) {
    console.warn("Archive API is unavailable.", error);
    return { archiveIds: [], draft: null, source: "unavailable" };
  }
}

export async function listArchiveIds(): Promise<string[]> {
  const archivesResponse = await fetch(`${API_BASE_URL}/api/archives`);
  if (!archivesResponse.ok) {
    throw new Error(`Archive list failed: ${archivesResponse.status}`);
  }
  const archivesPayload = (await archivesResponse.json()) as { archives?: string[] };
  return archivesPayload.archives ?? [];
}

export async function fetchKnowledgeUniverse(projectIds: string[] = []): Promise<ProjectKnowledgeUniverse> {
  const params = new URLSearchParams({
    link_limit: "80",
    cluster_limit: "24",
  });
  projectIds.forEach((projectId) => params.append("project_ids", projectId));
  const response = await fetch(`${API_BASE_URL}/api/universe?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Knowledge universe failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as ProjectKnowledgeUniverse;
}

export async function fetchUniversePaths(): Promise<UniverseExplorationPath[]> {
  const response = await fetch(`${API_BASE_URL}/api/universe/paths`);
  if (!response.ok) {
    throw new Error(`Universe paths failed: ${await readErrorDetail(response)}`);
  }
  const payload = (await response.json()) as { paths?: UniverseExplorationPath[] };
  return payload.paths ?? [];
}

export async function saveUniversePath(payload: {
  name: string;
  project_ids: string[];
  cluster_ids?: string[];
  link_ids?: string[];
  notes?: string;
}): Promise<UniverseExplorationPath> {
  const response = await fetch(`${API_BASE_URL}/api/universe/paths`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Universe path save failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as UniverseExplorationPath;
}

export async function fetchUniverseAgentTasks(): Promise<UniverseAgentTask[]> {
  const response = await fetch(`${API_BASE_URL}/api/universe/agent-tasks`);
  if (!response.ok) {
    throw new Error(`Universe agent tasks failed: ${await readErrorDetail(response)}`);
  }
  const payload = (await response.json()) as { tasks?: UniverseAgentTask[] };
  return payload.tasks ?? [];
}

export async function runUniverseAgentTasks(payload: {
  project_ids: string[];
  max_tasks?: number;
}): Promise<UniverseAgentTask[]> {
  const response = await fetch(`${API_BASE_URL}/api/universe/agent-tasks/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Universe agent tasks run failed: ${await readErrorDetail(response)}`);
  }
  const result = (await response.json()) as { tasks?: UniverseAgentTask[] };
  return result.tasks ?? [];
}

export async function compareUniverseProjects(
  leftProjectId: string,
  rightProjectId: string,
): Promise<ProjectArchitectureDiffReport> {
  const response = await fetch(`${API_BASE_URL}/api/universe/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      left_project_id: leftProjectId,
      right_project_id: rightProjectId,
    }),
  });
  if (!response.ok) {
    throw new Error(`Universe compare failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as ProjectArchitectureDiffReport;
}

export async function fetchProjectArchive(projectId: string): Promise<ArchiveDraft> {
  const draftResponse = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}`);
  if (!draftResponse.ok) {
    throw new Error(`Archive load failed: ${draftResponse.status}`);
  }
  return transformArchiveDraft((await draftResponse.json()) as RawArchiveDraft);
}

export async function runArchiveQuery(
  projectId: string,
  question: string,
  mode = "evidence_qa",
  hallId?: string,
): Promise<AgentReport> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question, mode, hall_id: hallId }),
  });
  if (!response.ok) {
    throw new Error(`Archive query failed: ${response.status}`);
  }
  return (await response.json()) as AgentReport;
}

export async function fetchAgentStatus(): Promise<AgentStatus> {
  const response = await fetch(`${API_BASE_URL}/api/agent/status`);
  if (!response.ok) {
    throw new Error(`Agent status failed: ${response.status}`);
  }
  return (await response.json()) as AgentStatus;
}

export async function fetchGraphStoreStatus(): Promise<GraphStoreStatus> {
  const response = await fetch(`${API_BASE_URL}/api/graph-store/status`);
  if (!response.ok) {
    throw new Error(`Graph store status failed: ${response.status}`);
  }
  return (await response.json()) as GraphStoreStatus;
}

export async function fetchSystemConfigCheck(): Promise<SystemConfigCheck> {
  const response = await fetch(`${API_BASE_URL}/api/system/config-check`);
  if (!response.ok) {
    throw new Error(`System config check failed: ${response.status}`);
  }
  return (await response.json()) as SystemConfigCheck;
}

export async function fetchProjectAgentReport(projectId: string): Promise<ProjectAgentReport | null> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/agent-report`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Agent report failed: ${response.status}`);
  }
  return (await response.json()) as ProjectAgentReport;
}

export async function fetchProjectIntelligenceReport(projectId: string): Promise<ProjectIntelligenceReport | null> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/intelligence-report`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Project intelligence report failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as ProjectIntelligenceReport;
}

export async function fetchAgentTaskPlan(projectId: string): Promise<AgentTaskPlan | null> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/agent-task-plan`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Agent task plan failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as AgentTaskPlan;
}

export async function runProjectIntelligenceReport(projectId: string): Promise<ProjectIntelligenceReport> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/intelligence-report/run`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Project intelligence report run failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as ProjectIntelligenceReport;
}

export async function downloadProjectIntelligenceMarkdown(projectId: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/intelligence-report/markdown`);
  if (!response.ok) {
    throw new Error(`Project intelligence markdown failed: ${await readErrorDetail(response)}`);
  }
  return response.text();
}

export async function downloadProjectIntelligencePdf(projectId: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/intelligence-report/pdf`);
  if (!response.ok) {
    throw new Error(`Project intelligence PDF failed: ${await readErrorDetail(response)}`);
  }
  return response.blob();
}

export async function fetchHybridRagStatus(projectId: string): Promise<HybridRagStatus | null> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/rag-status`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Hybrid RAG status failed: ${response.status}`);
  }
  return (await response.json()) as HybridRagStatus;
}

export async function rebuildHybridRagIndexJob(
  projectId: string,
  onProgress?: (progress: number, message: string, projectId?: string | null) => void,
): Promise<HybridRagStatus | null> {
  const response = await fetch(
    `${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/rag-status/rebuild-job`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw new Error(`Hybrid RAG rebuild failed: ${await readErrorDetail(response)}`);
  }
  const queuedJob = (await response.json()) as ArchiveJob;
  await pollArchiveJob(queuedJob.id, onProgress, {
    timeoutMs: RAG_REBUILD_POLL_TIMEOUT_MS,
    timeoutMessage: "Hybrid RAG rebuild is still running in the background.",
  });
  return fetchHybridRagStatus(projectId);
}

export async function fetchIngestionDiagnostics(projectId: string): Promise<IngestionDiagnostics | null> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/diagnostics`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Ingestion diagnostics failed: ${response.status}`);
  }
  return (await response.json()) as IngestionDiagnostics;
}

export async function fetchGraphWorkspaceReport(projectId: string): Promise<GraphWorkspaceReport | null> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/graph/workspace`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Graph workspace report failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as GraphWorkspaceReport;
}

export async function fetchAgentTrustReport(projectId: string): Promise<AgentTrustReport | null> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/agent-trust`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Agent trust report failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as AgentTrustReport;
}

export async function fetchAgentEvalReport(projectId: string): Promise<AgentEvalReport | null> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/agent-eval`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`AgentEval report failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as AgentEvalReport;
}

export async function fetchHarnessRunSummary(projectId: string): Promise<HarnessRunSummary | null> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/harness/summary`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Harness summary failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as HarnessRunSummary;
}

export async function fetchHarnessCommands(): Promise<HarnessCommand[]> {
  const response = await fetch(`${API_BASE_URL}/api/harness/commands`);
  if (!response.ok) {
    throw new Error(`Harness commands failed: ${await readErrorDetail(response)}`);
  }
  const payload = (await response.json()) as { commands?: HarnessCommand[] };
  return payload.commands ?? [];
}

export async function dryRunHarnessCommand(
  commandId: string,
  parameters: Record<string, unknown>,
): Promise<HarnessCommandDryRun> {
  const response = await fetch(`${API_BASE_URL}/api/harness/commands/${encodeURIComponent(commandId)}/dry-run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ parameters }),
  });
  if (!response.ok) {
    throw new Error(`Harness command dry-run failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as HarnessCommandDryRun;
}

export async function fetchHarnessTimeline(projectId: string): Promise<HarnessTimeline | null> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/harness/timeline`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Harness timeline failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as HarnessTimeline;
}

export async function fetchHarnessExport(projectId: string): Promise<Record<string, unknown> | null> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/harness/export`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Harness export failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as Record<string, unknown>;
}

export async function fetchHarnessArtifactManifest(projectId: string): Promise<HarnessArtifactManifest | null> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/harness/artifacts`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Harness artifacts failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as HarnessArtifactManifest;
}

export async function dryRunHarnessArtifactCleanup(projectId: string): Promise<HarnessArtifactCleanup | null> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/harness/artifacts/cleanup-dry-run`, {
    method: "POST",
  });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Harness artifact cleanup dry-run failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as HarnessArtifactCleanup;
}

export async function runAgentEvalHarness(
  projectId: string,
  payload: {
    run_evaluation?: boolean;
    evaluation_limit?: number;
    run_agent_report?: boolean;
    agent_llm_mode?: string;
  } = {},
): Promise<AgentEvalReport> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/agent-eval/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`AgentEval harness failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as AgentEvalReport;
}

export async function fetchAgentMemory(projectId: string): Promise<AgentMemory | null> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/agent-memory`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Agent memory failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as AgentMemory;
}

export async function fetchMultimodalInsights(projectId: string): Promise<MultimodalInsights | null> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/multimodal`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Multimodal insights failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as MultimodalInsights;
}

export async function fetchArchiveEvaluation(projectId: string): Promise<ArchiveEvaluationReport | null> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/evaluation`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Archive evaluation failed: ${response.status}`);
  }
  return (await response.json()) as ArchiveEvaluationReport;
}

export async function fetchEvaluationHistory(projectId?: string): Promise<EvaluationHistory> {
  const params = new URLSearchParams();
  if (projectId) params.set("project_id", projectId);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(`${API_BASE_URL}/api/evaluation/history${suffix}`);
  if (!response.ok) {
    throw new Error(`Evaluation history failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as EvaluationHistory;
}

export async function runArchiveEvaluation(projectId: string): Promise<ArchiveEvaluationReport> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/evaluation/run`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Archive evaluation run failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as ArchiveEvaluationReport;
}

export async function fetchStressTestReport(): Promise<StressTestReport | null> {
  const response = await fetch(`${API_BASE_URL}/api/stress-test/latest`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Stress test report failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as StressTestReport;
}

export async function runStressTest(projectIds: string[]): Promise<StressTestReport> {
  const response = await fetch(`${API_BASE_URL}/api/stress-test/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_ids: projectIds,
      run_evaluation: false,
      evaluation_limit: 6,
    }),
  });
  if (!response.ok) {
    throw new Error(`Stress test run failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as StressTestReport;
}

export async function fetchGraphCuration(projectId: string): Promise<GraphCurationState> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/graph-curation`);
  if (!response.ok) {
    throw new Error(`Graph curation load failed: ${response.status}`);
  }
  return transformGraphCuration((await response.json()) as RawGraphCurationState);
}

export async function saveGraphCuration(
  projectId: string,
  state: GraphCurationState,
): Promise<GraphCurationState> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/graph-curation`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      important_entity_ids: state.importantEntityIds,
      hidden_relation_ids: state.hiddenRelationIds,
      merge_candidates: state.mergeCandidates.map((candidate) => ({
        id: candidate.id,
        label: candidate.label,
        entity_ids: candidate.entityIds,
        created_at: candidate.createdAt,
      })),
    }),
  });
  if (!response.ok) {
    throw new Error(`Graph curation save failed: ${response.status}`);
  }
  return transformGraphCuration((await response.json()) as RawGraphCurationState);
}

export async function applyGraphCurationSuggestions(projectId: string): Promise<GraphCurationState> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/graph-curation/apply-suggestions`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Graph curation suggestions failed: ${await readErrorDetail(response)}`);
  }
  return transformGraphCuration((await response.json()) as RawGraphCurationState);
}

export async function fetchProjectVersionHistory(projectId: string): Promise<{ events: Array<Record<string, unknown>>; metrics: Record<string, number> }> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/versions`);
  if (!response.ok) {
    throw new Error(`Version history failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as { events: Array<Record<string, unknown>>; metrics: Record<string, number> };
}

export async function runProjectAgentReport(
  projectId: string,
  scanProfile: string,
): Promise<ProjectAgentReport> {
  const params = new URLSearchParams({ scan_profile: scanProfile });
  const response = await fetch(
    `${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/agent-report/run?${params.toString()}`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw new Error(`Agent report run failed: ${response.status}`);
  }
  return (await response.json()) as ProjectAgentReport;
}

export async function runProjectAgentReportJob(
  projectId: string,
  scanProfile: string,
  onProgress?: (progress: number, message: string, projectId?: string | null) => void,
): Promise<ProjectAgentReport> {
  const params = new URLSearchParams({ scan_profile: scanProfile, llm_mode: "fast" });
  const response = await fetch(
    `${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/agent-report/run-job?${params.toString()}`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw new Error(`Agent report job failed: ${response.status}`);
  }
  const queuedJob = (await response.json()) as ArchiveJob;
  const job = await pollArchiveJob(queuedJob.id, onProgress, {
    timeoutMs: AGENT_REPORT_POLL_TIMEOUT_MS,
    timeoutMessage: "Agent report is still running in the background.",
  });
  const result = (job.result ?? {}) as AgentReportJobResult;
  if (!result.agent_report) {
    const savedReport = await fetchProjectAgentReport(projectId);
    if (savedReport) return savedReport;
    throw new Error(job.error ?? "Agent report job finished without a report.");
  }
  return result.agent_report;
}

export async function uploadProjectArchive(
  file: File,
  scanProfile: string,
  onProgress?: (progress: number, message: string, projectId?: string | null) => void,
): Promise<UploadArchiveResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("scan_profile", scanProfile);

  const job = await new Promise<ArchiveJob>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE_URL}/api/archives/upload-job`);
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress?.(
          Math.min(18, Math.round((event.loaded / event.total) * 18)),
          "Uploading project ZIP.",
        );
      }
    };
    request.onload = () => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(request.responseText);
      } catch {
        parsed = undefined;
      }
      if (request.status >= 200 && request.status < 300) {
        resolve(parsed as ArchiveJob);
        return;
      }
      const detail =
        parsed && typeof parsed === "object" && "detail" in parsed
          ? String((parsed as { detail?: unknown }).detail)
          : `Archive upload failed: ${request.status}`;
      reject(new Error(detail));
    };
    request.onerror = () => reject(new Error("Archive upload failed: network error"));
    request.send(formData);
  });

  const finishedJob = await pollArchiveJob(job.id, onProgress, {
    timeoutMs: ARCHIVE_UPLOAD_POLL_TIMEOUT_MS,
    timeoutMessage:
      "Archive job is still running after 30 minutes. It may finish on the backend; check the archive switcher later.",
  });
  const payload = (finishedJob.result ?? {}) as UploadArchiveJobResult;
  if (payload.archive) {
    return {
      draft: transformArchiveDraft(payload.archive),
    };
  }
  const projectId = payload.project_id ?? finishedJob.project_id;
  if (!projectId) {
    throw new Error(finishedJob.error ?? "Archive job finished without an archive id.");
  }
  return {
    draft: await fetchProjectArchive(projectId),
  };
}

export async function fetchGraphSummary(projectId: string): Promise<GraphSummary> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/graph`);
  if (!response.ok) {
    throw new Error(`Graph summary failed: ${response.status}`);
  }
  return (await response.json()) as GraphSummary;
}

export async function fetchGraphNeighborhood({
  projectId,
  hallId,
  focusEntityId,
  depth,
  relationTypes,
  nodeLimit = 80,
  relationLimit = 120,
}: {
  projectId: string;
  hallId?: string | null;
  focusEntityId?: string | null;
  depth: number;
  relationTypes: string[];
  nodeLimit?: number;
  relationLimit?: number;
}): Promise<GraphNeighborhood> {
  const params = new URLSearchParams({
    depth: String(depth),
    node_limit: String(nodeLimit),
    relation_limit: String(relationLimit),
  });
  if (hallId) params.set("hall_id", hallId);
  if (focusEntityId) params.set("focus_entity_id", focusEntityId);
  relationTypes.forEach((type) => params.append("relation_types", type));
  const response = await fetch(
    `${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/graph/neighborhood?${params.toString()}`,
  );
  if (!response.ok) {
    throw new Error(`Graph neighborhood failed: ${response.status}`);
  }
  return (await response.json()) as GraphNeighborhood;
}

export async function searchGraphEntities(
  projectId: string,
  query: string,
  limit = 20,
): Promise<GraphSearchResult[]> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
  });
  const response = await fetch(
    `${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/graph/search?${params.toString()}`,
  );
  if (!response.ok) {
    throw new Error(`Graph search failed: ${response.status}`);
  }
  const payload = (await response.json()) as { results?: GraphSearchResult[] };
  return payload.results ?? [];
}

export async function startArchitectureMission(
  projectId: string,
  maxSteps = 12,
): Promise<AutonomousMission> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/missions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      goal: "understand_project_architecture",
      max_steps: maxSteps,
    }),
  });
  if (!response.ok) {
    throw new Error(`Mission start failed: ${response.status}`);
  }
  return (await response.json()) as AutonomousMission;
}

export async function fetchMission(missionId: string): Promise<AutonomousMission> {
  const response = await fetch(`${API_BASE_URL}/api/missions/${encodeURIComponent(missionId)}`);
  if (!response.ok) {
    throw new Error(`Mission load failed: ${response.status}`);
  }
  return (await response.json()) as AutonomousMission;
}

export async function fetchMissionTasks(missionId: string): Promise<MissionTask[]> {
  const response = await fetch(`${API_BASE_URL}/api/missions/${encodeURIComponent(missionId)}/tasks`);
  if (!response.ok) {
    throw new Error(`Mission tasks failed: ${response.status}`);
  }
  const payload = (await response.json()) as { tasks?: MissionTask[] };
  return payload.tasks ?? [];
}

export async function fetchMissionGraphOverlay(missionId: string): Promise<MissionGraphOverlay> {
  const response = await fetch(`${API_BASE_URL}/api/missions/${encodeURIComponent(missionId)}/graph-overlay`);
  if (!response.ok) {
    throw new Error(`Mission overlay failed: ${response.status}`);
  }
  return (await response.json()) as MissionGraphOverlay;
}

export async function updateMissionStatus(
  missionId: string,
  action: "pause" | "resume" | "stop",
): Promise<AutonomousMission> {
  const response = await fetch(`${API_BASE_URL}/api/missions/${encodeURIComponent(missionId)}/${action}`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Mission ${action} failed: ${response.status}`);
  }
  return (await response.json()) as AutonomousMission;
}

export async function startAgentMission(
  projectId: string,
  payload: { goal: string; max_tasks?: number; max_steps_per_task?: number },
): Promise<AgentMission> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/agent-missions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Agent mission start failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as AgentMission;
}

export async function fetchAgentMission(missionId: string): Promise<AgentMission> {
  const response = await fetch(`${API_BASE_URL}/api/agent-missions/${encodeURIComponent(missionId)}`);
  if (!response.ok) {
    throw new Error(`Agent mission fetch failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as AgentMission;
}

export async function fetchAgentMissionTrace(missionId: string): Promise<AgentTraceEvent[]> {
  const response = await fetch(`${API_BASE_URL}/api/agent-missions/${encodeURIComponent(missionId)}/trace`);
  if (!response.ok) {
    throw new Error(`Agent mission trace failed: ${await readErrorDetail(response)}`);
  }
  const payload = (await response.json()) as { trace_events: AgentTraceEvent[] };
  return payload.trace_events;
}

export async function fetchAgentMissionVisualization(missionId: string): Promise<AgentMissionVisualization> {
  const response = await fetch(`${API_BASE_URL}/api/agent-missions/${encodeURIComponent(missionId)}/visualization`);
  if (!response.ok) {
    throw new Error(`Agent mission visualization failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as AgentMissionVisualization;
}

export async function updateAgentMissionStatus(
  missionId: string,
  action: "pause" | "resume" | "stop",
): Promise<AgentMission> {
  const response = await fetch(`${API_BASE_URL}/api/agent-missions/${encodeURIComponent(missionId)}/${action}`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Agent mission ${action} failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as AgentMission;
}

export async function pollArchiveJob(
  jobId: string,
  onProgress?: (progress: number, message: string, projectId?: string | null) => void,
  options: { timeoutMs?: number; timeoutMessage?: string } = {},
): Promise<ArchiveJob> {
  const startedAt = Date.now();
  const timeoutMs = options.timeoutMs ?? DEFAULT_JOB_POLL_TIMEOUT_MS;
  while (Date.now() - startedAt < timeoutMs) {
    const response = await fetch(`${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}`);
    if (!response.ok) {
      throw new Error(`Archive job polling failed: ${response.status}`);
    }
    const job = (await response.json()) as ArchiveJob;
    onProgress?.(job.progress, job.message, job.project_id);
    if (job.status === "complete") return job;
    if (job.status === "cancelled") {
      throw new Error(job.error || job.message || "Archive job was cancelled.");
    }
    if (job.status === "failed") {
      throw new Error(job.error || job.message || "Archive job failed.");
    }
    await delay(800);
  }
  throw new Error(options.timeoutMessage ?? "Archive job timed out.");
}

export async function listArchiveJobs(projectId?: string): Promise<ArchiveJob[]> {
  const params = new URLSearchParams();
  if (projectId) params.set("project_id", projectId);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(`${API_BASE_URL}/api/jobs${suffix}`);
  if (!response.ok) {
    throw new Error(`Archive jobs failed: ${await readErrorDetail(response)}`);
  }
  const payload = (await response.json()) as { jobs?: ArchiveJob[] };
  return payload.jobs ?? [];
}

export async function cancelArchiveJob(jobId: string): Promise<ArchiveJob> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Archive job cancel failed: ${await readErrorDetail(response)}`);
  }
  return (await response.json()) as ArchiveJob;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
  } catch {
    // Ignore malformed or empty error bodies and fall back to the status code.
  }
  return `${response.status}`;
}

function transformArchiveDraft(raw: RawArchiveDraft): ArchiveDraft {
  const entities = raw.entities ?? [];
  const relations = raw.relations ?? [];
  const evidenceCards = raw.evidence_cards ?? [];
  const entityById = new Map(entities.map((entity) => [entity.id, entity]));
  const hallIndex = createHallIndex(raw.halls ?? []);

  const halls = (raw.halls ?? []).map((hall) =>
    transformHall(hall, entities, hallIndex.hallsByEntityId),
  );

  return {
    projectId: raw.project_id,
    scope: "Architecture First",
    languages: languageStats(entities),
    metrics: {
      halls: halls.length,
      entities: entities.length,
      relations: relations.length,
      evidence: evidenceCards.length,
    },
    halls,
    relations: relations.map((relation) =>
      transformRelation(relation, entityById, hallIndex),
    ),
    evidenceCards: evidenceCards.map((card) =>
      transformEvidenceCard(card, hallIndex, raw.project_id),
    ),
  };
}

function transformGraphCuration(raw: RawGraphCurationState): GraphCurationState {
  return {
    projectId: raw.project_id,
    importantEntityIds: raw.important_entity_ids ?? [],
    hiddenRelationIds: raw.hidden_relation_ids ?? [],
    mergeCandidates: (raw.merge_candidates ?? []).map((candidate) => ({
      id: candidate.id,
      label: candidate.label,
      entityIds: candidate.entity_ids ?? [],
      createdAt: candidate.created_at ?? "",
    })),
    updatedAt: raw.updated_at ?? "",
  };
}

function createHallIndex(halls: RawHall[]) {
  const hallsByEntityId = new Map<string, string[]>();
  for (const hall of halls) {
    for (const entityId of hall.entity_ids ?? []) {
      const current = hallsByEntityId.get(entityId) ?? [];
      current.push(hall.id);
      hallsByEntityId.set(entityId, current);
    }
  }

  return {
    allHallIds: halls.map((hall) => hall.id),
    defaultHallId: halls[0]?.id ?? "architecture",
    hallsByEntityId,
  };
}

function transformHall(
  hall: RawHall,
  entities: RawEntity[],
  hallsByEntityId: Map<string, string[]>,
): ArchiveHall {
  const hallEntities = entities.filter((entity) => hallsByEntityId.get(entity.id)?.includes(hall.id));
  const dominantTypes = topCounts(hallEntities.map((entity) => entity.type), 3);
  return {
    id: hall.id,
    name: hall.name,
    label: translateHallName(hall.name),
    description: hall.description,
    descriptionZh: translateHallDescription(hall.name, hall.description),
    count: hall.entity_ids?.length ?? 0,
    dominantTypes,
    sampleEntities: hallEntities.slice(0, 3).map((entity) => displayEntity(entity)),
    risk: inferHallRisk(hall.name),
    riskZh: inferHallRiskZh(hall.name),
  };
}

function transformRelation(
  relation: RawRelation,
  entityById: Map<string, RawEntity>,
  hallIndex: ReturnType<typeof createHallIndex>,
): ArchiveRelation {
  const hallIds = relationHallIds(relation, hallIndex);
  return {
    id: relation.id,
    source: displayEntity(entityById.get(relation.source_id), relation.source_id),
    target: displayEntity(entityById.get(relation.target_id), relation.target_id),
    type: relation.type,
    hall: chooseRelationHall(relation, hallIndex, hallIds),
    hallIds,
    evidenceIds: relation.evidence_ids ?? [],
  };
}

function transformEvidenceCard(
  card: RawEvidenceCard,
  hallIndex: ReturnType<typeof createHallIndex>,
  projectId: string,
): EvidenceCard {
  const candidateHalls = unique(
    card.linked_entities?.flatMap((entityId) => hallIndex.hallsByEntityId.get(entityId) ?? []) ?? [],
  );
  const hall = chooseEvidenceHall(card, candidateHalls, hallIndex);
  const assetId = typeof card.metadata?.asset_id === "string" ? card.metadata.asset_id : "";
  return {
    id: card.id,
    title: card.title,
    titleZh: translateEvidenceTitle(card.title),
    sourcePath: card.source_path,
    sourceType: card.source_type,
    assetUrl: assetId
      ? `${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/evidence-assets/${encodeURIComponent(assetId)}`
      : null,
    modality: typeof card.metadata?.modality === "string" ? card.metadata.modality : card.source_type,
    snippet: card.snippet,
    snippetZh: translateEvidenceSnippet(card.snippet),
    lineRange: lineRange(card),
    confidence: card.confidence ?? 1,
    hall,
    hallIds: candidateHalls.length ? candidateHalls : [hall],
    metadata: card.metadata ?? {},
  };
}

function relationHallIds(
  relation: RawRelation,
  hallIndex: ReturnType<typeof createHallIndex>,
): string[] {
  const hallIds = unique([
    ...(hallIndex.hallsByEntityId.get(relation.source_id) ?? []),
    ...(hallIndex.hallsByEntityId.get(relation.target_id) ?? []),
  ]);
  return hallIds.length ? hallIds : [hallIndex.defaultHallId];
}

function chooseRelationHall(
  relation: RawRelation,
  hallIndex: ReturnType<typeof createHallIndex>,
  candidateHalls: string[],
): string {
  const type = relation.type.toLowerCase();
  const retrievalHall = findHall(candidateHalls, "retriev");
  if (retrievalHall) return retrievalHall;
  if (type.includes("config")) {
    return (
      findHall(candidateHalls, "config") ??
      findHall(hallIndex.allHallIds, "config") ??
      candidateHalls[0] ??
      hallIndex.defaultHallId
    );
  }
  if (type.includes("import") || type.includes("depend")) {
    return (
      findHall(candidateHalls, "depend") ??
      findHall(hallIndex.allHallIds, "depend") ??
      candidateHalls[0] ??
      hallIndex.defaultHallId
    );
  }
  if (type.includes("mention")) {
    return (
      findHall(candidateHalls, "concept") ??
      findHall(hallIndex.allHallIds, "concept") ??
      candidateHalls[0] ??
      hallIndex.defaultHallId
    );
  }
  if (type.includes("retriev")) {
    return (
      findHall(candidateHalls, "retriev") ??
      findHall(hallIndex.allHallIds, "retriev") ??
      candidateHalls[0] ??
      hallIndex.defaultHallId
    );
  }
  return candidateHalls[0] ?? hallIndex.defaultHallId;
}

function chooseEvidenceHall(
  card: RawEvidenceCard,
  candidateHalls: string[],
  hallIndex: ReturnType<typeof createHallIndex>,
): string {
  const source = `${card.source_type} ${card.source_path} ${card.title}`.toLowerCase();
  if (source.includes("config") || source.includes(".yaml") || source.includes(".toml")) {
    return (
      findHall(candidateHalls, "config") ??
      findHall(hallIndex.allHallIds, "config") ??
      candidateHalls[0] ??
      hallIndex.defaultHallId
    );
  }
  if (source.includes("retriev") || source.includes("query")) {
    return (
      findHall(candidateHalls, "retriev") ??
      findHall(hallIndex.allHallIds, "retriev") ??
      candidateHalls[0] ??
      hallIndex.defaultHallId
    );
  }
  if (source.includes("import") || source.includes("depend")) {
    return (
      findHall(candidateHalls, "depend") ??
      findHall(hallIndex.allHallIds, "depend") ??
      candidateHalls[0] ??
      hallIndex.defaultHallId
    );
  }
  if (source.includes("markdown") || source.includes("readme") || source.includes("heading")) {
    return (
      findHall(candidateHalls, "concept") ??
      findHall(hallIndex.allHallIds, "concept") ??
      candidateHalls[0] ??
      hallIndex.defaultHallId
    );
  }
  return candidateHalls[0] ?? hallIndex.defaultHallId;
}

function findHall(hallIds: string[], fragment: string): string | undefined {
  return hallIds.find((hallId) => hallId.toLowerCase().includes(fragment));
}

function unique(values: string[]): string[] {
  return Array.from(new Set(values));
}

function displayEntity(entity: RawEntity | undefined, fallback = ""): string {
  if (!entity) return fallback;
  if (entity.source_path && entity.name !== entity.source_path) {
    return `${entity.name} (${entity.source_path})`;
  }
  return entity.name;
}

function languageStats(entities: RawEntity[]) {
  const counts = new Map<string, number>();
  for (const entity of entities) {
    const language = entity.properties?.language;
    if (typeof language === "string") {
      counts.set(language, (counts.get(language) ?? 0) + 1);
    }
  }
  const rows = Array.from(counts, ([name, count]) => ({ name, count })).sort(
    (a, b) => b.count - a.count,
  );
  return rows.slice(0, 5);
}

function topCounts(values: string[], limit: number): string[] {
  const counts = new Map<string, number>();
  for (const value of values) {
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return Array.from(counts, ([value, count]) => ({ value, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, limit)
    .map((row) => row.value);
}

function lineRange(card: RawEvidenceCard): string {
  if (card.line_start && card.line_end && card.line_start !== card.line_end) {
    return `L${card.line_start}-L${card.line_end}`;
  }
  if (card.line_start) {
    return `L${card.line_start}`;
  }
  return card.source_type === "code" ? "Module" : "Config";
}

function translateHallName(name: string): string {
  const labels: Record<string, string> = {
    "Architecture Hall": "架构展厅",
    "Retrieval Hall": "检索展厅",
    "Configuration Hall": "配置展厅",
    "Concept Hall": "概念展厅",
    "Dependency Hall": "依赖展厅",
  };
  return labels[name] ?? name;
}

function translateHallDescription(name: string, fallback: string): string {
  const labels: Record<string, string> = {
    "Architecture Hall": "定义项目结构的文件、类和函数。",
    "Retrieval Hall": "与检索行为和配置相关的实体。",
    "Configuration Hall": "从项目设置中抽取的配置键和配置文件。",
    "Concept Hall": "项目文档中发现的概念和标题。",
    "Dependency Hall": "源码文件引用的导入依赖。",
  };
  return labels[name] ?? fallback;
}

function inferHallRisk(name: string): string {
  const risks: Record<string, string> = {
    "Architecture Hall": "High coupling surface",
    "Retrieval Hall": "Core behavior path",
    "Configuration Hall": "Environment sensitive",
    "Concept Hall": "Docs drift watch",
    "Dependency Hall": "Upgrade surface",
  };
  return risks[name] ?? "Review evidence before changes";
}

function inferHallRiskZh(name: string): string {
  const risks: Record<string, string> = {
    "Architecture Hall": "高耦合变更面",
    "Retrieval Hall": "核心行为路径",
    "Configuration Hall": "环境敏感区域",
    "Concept Hall": "文档漂移观察点",
    "Dependency Hall": "升级影响面",
  };
  return risks[name] ?? "变更前需要检查证据";
}

function translateEvidenceTitle(title: string): string {
  if (title.startsWith("Heading: ")) {
    return `标题：${title.replace("Heading: ", "")}`;
  }
  const labels: Record<string, string> = {
    "Retrieval configuration": "检索配置",
    "Query engine composition": "查询引擎组合方式",
  };
  return labels[title] ?? title;
}

function translateEvidenceSnippet(snippet: string): string {
  const labels: Record<string, string> = {
    "Dense and sparse retrievers are fused before reranking and response assembly.":
      "密集检索和稀疏检索会先融合，再进入重排和回答组装流程。",
    "retrieval, embedding, vector_store, and reranker settings are loaded before query execution.":
      "查询执行前会加载 retrieval、embedding、vector_store 和 reranker 等设置。",
  };
  return labels[snippet] ?? snippet;
}
