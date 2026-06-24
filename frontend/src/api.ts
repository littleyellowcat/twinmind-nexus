import { archiveDraft as fallbackArchive } from "./archiveData";
import type {
  AgentReport,
  AgentStatus,
  ArchiveJob,
  ArchiveDraft,
  ArchiveHall,
  ArchiveRelation,
  AutonomousMission,
  EvidenceCard,
  GraphNeighborhood,
  GraphSummary,
  MissionGraphOverlay,
  MissionTask,
  ProjectAgentReport,
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
};

export type ArchiveDraftResult = {
  archiveIds: string[];
  draft: ArchiveDraft;
  source: "api" | "fallback";
};

type UploadArchiveJobResult = {
  archive?: RawArchiveDraft;
  agent_report?: ProjectAgentReport;
};

type AgentReportJobResult = {
  agent_report?: ProjectAgentReport;
};

export type UploadArchiveResult = {
  draft: ArchiveDraft;
  agentReport: ProjectAgentReport | null;
};

export async function fetchArchiveDraft(): Promise<ArchiveDraftResult> {
  try {
    const archiveIds = await listArchiveIds();
    const projectId =
      archiveIds.find((id) => id === fallbackArchive.projectId) ??
      archiveIds[0];
    if (!projectId) {
      return { archiveIds: [fallbackArchive.projectId], draft: fallbackArchive, source: "fallback" };
    }

    return {
      archiveIds,
      draft: await fetchProjectArchive(projectId),
      source: "api",
    };
  } catch (error) {
    console.warn("Using fallback archive data.", error);
    return { archiveIds: [fallbackArchive.projectId], draft: fallbackArchive, source: "fallback" };
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
): Promise<AgentReport> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question, mode }),
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
  onProgress?: (progress: number, message: string) => void,
): Promise<ProjectAgentReport> {
  const params = new URLSearchParams({ scan_profile: scanProfile });
  const response = await fetch(
    `${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/agent-report/run-job?${params.toString()}`,
    { method: "POST" },
  );
  if (!response.ok) {
    throw new Error(`Agent report job failed: ${response.status}`);
  }
  const queuedJob = (await response.json()) as ArchiveJob;
  const job = await pollArchiveJob(queuedJob.id, onProgress);
  const result = (job.result ?? {}) as AgentReportJobResult;
  if (!result.agent_report) {
    throw new Error(job.error ?? "Agent report job finished without a report.");
  }
  return result.agent_report;
}

export async function uploadProjectArchive(
  file: File,
  scanProfile: string,
  onProgress?: (progress: number, message: string) => void,
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

  const finishedJob = await pollArchiveJob(job.id, onProgress);
  const payload = (finishedJob.result ?? {}) as UploadArchiveJobResult;
  if (!payload.archive) {
    throw new Error(finishedJob.error ?? "Archive job finished without an archive.");
  }
  return {
    draft: transformArchiveDraft(payload.archive),
    agentReport: payload.agent_report ?? null,
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

export async function pollArchiveJob(
  jobId: string,
  onProgress?: (progress: number, message: string) => void,
): Promise<ArchiveJob> {
  const startedAt = Date.now();
  while (Date.now() - startedAt < 1000 * 60 * 6) {
    const response = await fetch(`${API_BASE_URL}/api/jobs/${encodeURIComponent(jobId)}`);
    if (!response.ok) {
      throw new Error(`Archive job polling failed: ${response.status}`);
    }
    const job = (await response.json()) as ArchiveJob;
    onProgress?.(job.progress, job.message);
    if (job.status === "complete") return job;
    if (job.status === "failed") {
      throw new Error(job.error || job.message || "Archive job failed.");
    }
    await delay(800);
  }
  throw new Error("Archive job timed out.");
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function transformArchiveDraft(raw: RawArchiveDraft): ArchiveDraft {
  const entities = raw.entities ?? [];
  const relations = raw.relations ?? [];
  const evidenceCards = raw.evidence_cards ?? [];
  const entityById = new Map(entities.map((entity) => [entity.id, entity]));
  const hallByEntityId = new Map<string, string>();
  for (const hall of raw.halls ?? []) {
    for (const entityId of hall.entity_ids ?? []) {
      hallByEntityId.set(entityId, hall.id);
    }
  }

  const halls = (raw.halls ?? []).map((hall) =>
    transformHall(hall, entities, hallByEntityId),
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
    relations: relations.slice(0, 80).map((relation) =>
      transformRelation(relation, entityById, hallByEntityId),
    ),
    evidenceCards: evidenceCards.slice(0, 80).map((card) =>
      transformEvidenceCard(card, hallByEntityId),
    ),
  };
}

function transformHall(
  hall: RawHall,
  entities: RawEntity[],
  hallByEntityId: Map<string, string>,
): ArchiveHall {
  const hallEntities = entities.filter((entity) => hallByEntityId.get(entity.id) === hall.id);
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
  hallByEntityId: Map<string, string>,
): ArchiveRelation {
  return {
    id: relation.id,
    source: displayEntity(entityById.get(relation.source_id), relation.source_id),
    target: displayEntity(entityById.get(relation.target_id), relation.target_id),
    type: relation.type,
    hall: hallByEntityId.get(relation.source_id) ?? hallByEntityId.get(relation.target_id) ?? "architecture",
  };
}

function transformEvidenceCard(
  card: RawEvidenceCard,
  hallByEntityId: Map<string, string>,
): EvidenceCard {
  const hall = card.linked_entities
    ?.map((entityId) => hallByEntityId.get(entityId))
    .find((value): value is string => Boolean(value));
  return {
    id: card.id,
    title: card.title,
    titleZh: translateEvidenceTitle(card.title),
    sourcePath: card.source_path,
    sourceType: card.source_type,
    snippet: card.snippet,
    snippetZh: translateEvidenceSnippet(card.snippet),
    lineRange: lineRange(card),
    confidence: card.confidence ?? 1,
    hall: hall ?? "architecture",
  };
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
  return rows.length ? rows.slice(0, 5) : fallbackArchive.languages;
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
