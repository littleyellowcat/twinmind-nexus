import {
  Archive,
  Boxes,
  Braces,
  ChevronDown,
  CircleDot,
  Command,
  FileArchive,
  FolderInput,
  GitBranch,
  Layers3,
  Network,
  PanelLeft,
  PanelRight,
  Search,
  ShieldCheck,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import type { CSSProperties, KeyboardEvent, ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  fetchAgentMission,
  fetchAgentStatus,
  fetchAgentMissionTrace,
  fetchArchiveDraft,
  fetchGraphNeighborhood,
  fetchGraphSummary,
  fetchHybridRagStatus,
  fetchMissionGraphOverlay,
  fetchProjectAgentReport,
  fetchProjectArchive,
  runArchiveQuery,
  runProjectAgentReportJob,
  searchGraphEntities,
  startAgentMission,
  startArchitectureMission,
  updateAgentMissionStatus,
  updateMissionStatus,
  uploadProjectArchive,
} from "./api";
import type {
  AgentMission,
  AgentReport,
  AgentStatus,
  AgentTraceEvent,
  ArchiveDraft,
  ArchiveHall,
  ArchiveRelation,
  AutonomousMission,
  EvidenceCard,
  GraphExplorerNode,
  GraphExplorerRelation,
  GraphNeighborhood,
  GraphSearchResult,
  GraphSummary,
  HybridRagStatus,
  MissionGraphOverlay,
  MissionTask,
  ProjectAgentReport,
} from "./types";

type Locale = "zh" | "en";
type ScopeMode = "architecture_tour" | "impact_analysis" | "risk_audit" | "evidence_qa";
type ScanProfile = "architecture" | "full" | "docs" | "tests";
type AppPage = "overview" | "graph" | "agents";
type GraphTone = "accent" | "blue" | "amber" | "violet";
type MissionAction = "start" | "pause" | "resume" | "stop" | null;
type JobHistoryItem = {
  id: string;
  label: string;
  progress: number;
  message: string;
};
type JobHistoryByProjectId = Record<string, JobHistoryItem[]>;

const copy = {
  zh: {
    subtitle: "项目档案观测台",
    searchGraph: "搜索图谱",
    createArchive: "生成档案",
    loadingArchive: "正在连接档案 API",
    loadingSelectedArchive: "正在切换档案",
    archiveSelector: "项目档案",
    archiveSelectorPlaceholder: "选择项目档案",
    overviewPage: "档案总览",
    graphPage: "图谱探索",
    agentPage: "Agent 分析",
    expandGraph: "放大图谱",
    graphExplorer: "图谱探索",
    allGraph: "全部图谱",
    searchEntities: "搜索实体",
    graphSearchPlaceholder: "搜索全档案实体、文件或配置",
    graphSearchEmpty: "没有匹配的实体",
    graphSearchHint: "输入关键词后按 Enter 聚焦第一个结果",
    graphStartScore: "分",
    missionControl: "自主任务",
    recommendedStarts: "推荐起点",
    entityDetails: "实体详情",
    closeDrawer: "关闭面板",
    openDrawer: "打开面板",
    agentStatus: "Agent",
    checkingAgent: "检查 Agent",
    archiveSwitched: "已切换档案",
    archiveSwitchFailed: "档案切换失败",
    liveArchive: "真实档案",
    fallbackArchive: "离线示例",
    archiveObservatory: "档案观测台",
    passportSummary:
      "为架构探索、风险追踪和 Agent 项目分析构建有证据链的 GraphRAG 档案。",
    scope: "架构优先",
    metrics: {
      halls: "展厅",
      entities: "实体",
      relations: "关系",
      evidence: "证据",
    },
    intake: "项目入口",
    intakeCopy: "选择项目 ZIP，点击生成档案后才会解析和展示内容。",
    cleanStartTitle: "还没有打开项目档案",
    cleanStartCopy: "这里会保持干净状态。你可以上传 ZIP 生成新档案，或从右上角选择一个已有项目档案查看。",
    noArchiveSelected: "请先上传生成档案，或选择一个已有项目档案。",
    chooseZip: "选择 ZIP",
    uploadLabel: "上传项目 ZIP",
    architectureFirst: "架构优先",
    fullAudit: "完整审计",
    docsFirst: "文档优先",
    testsQuality: "测试质量",
    impactAnalysis: "影响分析",
    riskAudit: "风险审计",
    evidenceQa: "证据问答",
    zipSelected: "已选择",
    uploadPending: "点击生成档案后会上传到后端并开始摄取。",
    searchPlaceholder: "搜索实体、关系或证据路径",
    searchOpened: "搜索框已打开，可以按实体、关系或文件路径过滤当前图谱。",
    createNeedsZip: "请先选择一个项目 ZIP，然后再生成档案。",
    createPending: "正在上传并生成项目档案，这一步会解析代码、文档和配置。",
    processingArchive: "上传完成，后端正在解析项目。",
    creatingArchive: "生成中",
    archiveCreated: "档案已生成",
    agentPipeline: "Agent 流水线",
    autonomousMission: "自主架构任务",
    startMission: "启动架构任务",
    missionStarting: "任务启动中",
    missionPausing: "正在暂停",
    missionResuming: "正在继续",
    missionStopping: "正在停止",
    missionReady: "任务已完成",
    missionRunning: "任务运行中",
    missionPaused: "任务已暂停",
    missionStopped: "任务已停止",
    noMission: "还没有自主任务。启动后会显示真实任务队列、校验状态和图谱覆盖层。",
    missionError: "自主任务失败",
    missionId: "任务 ID",
    missionGoal: "目标",
    stopReason: "停止原因",
    maxSteps: "最大步数",
    completedTasks: "完成任务",
    missionTimeline: "任务时间线",
    pauseMission: "暂停",
    resumeMission: "继续",
    stopMission: "停止",
    openAgentMission: "到 Agent 页启动",
    viewMission: "查看自主任务",
    overlayActive: "任务覆盖层",
    riskOverlay: "风险高亮",
    noAgentReport: "当前档案还没有自动 Agent 报告。上传新档案或重新运行分析后会显示。",
    curatorSummary: "策展总结",
    rerunAnalysis: "运行分析",
    agentReportRunning: "分析中",
    jobProgress: "任务进度",
    uploadFailed: "上传摄取失败",
    relationSelected: "已定位关系",
    evidenceSelected: "已定位证据",
    reportReady: "Agent 报告已生成",
    reportFailed: "Agent 查询失败，请确认后端 API 正在运行。",
    complete: "完成",
    fallback: "降级",
    pending: "等待",
    partial: "部分完成",
    archiveHalls: "Archive Halls",
    hallNav: "展厅导航",
    starMap: "Star Map",
    graphAria: "知识图谱预览",
    relationGraph: "关系图谱",
    graphCaptionPrefix: "当前聚焦",
    graphCaptionSuffix: "选择其他展厅会切换图谱邻域。",
    hideGraphHint: "关闭说明",
    showGraphHint: "显示说明",
    source: "来源",
    relation: "关系",
    target: "目标",
    evidenceDrawer: "Evidence Drawer",
    evidenceTitle: "证据抽屉",
    currentFocus: "当前焦点",
    sourceTypes: {
      code: "代码",
      config: "配置",
      markdown: "文档",
    },
    lineRanges: {
      Config: "配置项",
      Module: "模块",
    },
    agentCommand: "Agent 指令",
    agentPromptPrefix: "解释",
    agentPromptSuffix: "追踪影响，并引用证据。",
    runReport: "生成报告",
    reportRunning: "生成中",
    confidence: "置信度",
    nextActions: "下一步",
    llmSource: "模型",
    deterministicSource: "规则 Agent",
    modelStatus: "模型状态",
    hybridRag: "Hybrid RAG",
    multimodal: "多模态",
    agentProof: "Agent 工作证明",
    taskHistory: "任务历史",
    noTaskHistory: "还没有任务记录。运行分析或生成档案后会出现。",
    evidenceUsed: "证据",
    entitiesUsed: "实体",
    relationsUsed: "关系",
    findings: "发现",
    risks: "风险",
    modelEnhanced: "模型增强",
    ruleCompleted: "规则完成",
    modelFallback: "模型增强未采纳",
    toolsUsed: "工具",
    validation: "验证",
    workLog: "工作记录",
  },
  en: {
    subtitle: "Project archive observatory",
    searchGraph: "Search graph",
    createArchive: "Create Archive",
    loadingArchive: "Connecting archive API",
    loadingSelectedArchive: "Switching archive",
    archiveSelector: "Project archive",
    archiveSelectorPlaceholder: "Select archive",
    overviewPage: "Archive overview",
    graphPage: "Graph Explorer",
    agentPage: "Agent analysis",
    expandGraph: "Expand graph",
    graphExplorer: "Graph Explorer",
    allGraph: "All graph",
    searchEntities: "Search entities",
    graphSearchPlaceholder: "Search archive entities, files, or config",
    graphSearchEmpty: "No matching entities",
    graphSearchHint: "Type a keyword and press Enter to focus the first result",
    graphStartScore: "pts",
    missionControl: "Mission control",
    recommendedStarts: "Recommended starts",
    entityDetails: "Entity details",
    closeDrawer: "Close panel",
    openDrawer: "Open panel",
    agentStatus: "Agent",
    checkingAgent: "Checking Agent",
    archiveSwitched: "Archive switched",
    archiveSwitchFailed: "Archive switch failed",
    liveArchive: "Live archive",
    fallbackArchive: "Offline sample",
    archiveObservatory: "Archive Observatory",
    passportSummary:
      "Evidence-backed GraphRAG archive for architecture exploration, risk tracing, and Agent-assisted project analysis.",
    scope: "Architecture First",
    metrics: {
      halls: "Halls",
      entities: "Entities",
      relations: "Relations",
      evidence: "Evidence",
    },
    intake: "Project intake",
    intakeCopy: "Choose a repository ZIP. Nothing is parsed or shown until you create an archive.",
    cleanStartTitle: "No project archive is open",
    cleanStartCopy: "This page stays clean until you upload a ZIP or select an existing archive from the top-right switcher.",
    noArchiveSelected: "Upload a ZIP or select an existing project archive first.",
    chooseZip: "Choose ZIP",
    uploadLabel: "Upload project ZIP",
    architectureFirst: "Architecture first",
    fullAudit: "Full audit",
    docsFirst: "Docs first",
    testsQuality: "Test quality",
    impactAnalysis: "Impact analysis",
    riskAudit: "Risk audit",
    evidenceQa: "Evidence Q&A",
    zipSelected: "Selected",
    uploadPending: "Click Create Archive to upload and ingest it.",
    searchPlaceholder: "Search entities, relations, or evidence paths",
    searchOpened: "Search is open. Filter the graph by entity, relation, or file path.",
    createNeedsZip: "Choose a project ZIP before creating an archive.",
    createPending: "Uploading and creating the archive from code, docs, and config.",
    processingArchive: "Upload complete. Backend is parsing the project.",
    creatingArchive: "Creating",
    archiveCreated: "Archive created",
    agentPipeline: "Agent pipeline",
    autonomousMission: "Autonomous architecture mission",
    startMission: "Start architecture mission",
    missionStarting: "Starting mission",
    missionPausing: "Pausing",
    missionResuming: "Resuming",
    missionStopping: "Stopping",
    missionReady: "Mission complete",
    missionRunning: "Mission running",
    missionPaused: "Mission paused",
    missionStopped: "Mission stopped",
    noMission: "No autonomous mission yet. Start one to see the real task queue, verifier state, and graph overlay.",
    missionError: "Mission failed",
    missionId: "Mission ID",
    missionGoal: "Goal",
    stopReason: "Stop reason",
    maxSteps: "Max steps",
    completedTasks: "Completed tasks",
    missionTimeline: "Task timeline",
    pauseMission: "Pause",
    resumeMission: "Resume",
    stopMission: "Stop",
    openAgentMission: "Open Agent to start",
    viewMission: "View mission",
    overlayActive: "Mission overlay",
    riskOverlay: "Risk highlight",
    noAgentReport: "No automatic Agent report exists for this archive yet.",
    curatorSummary: "Curator summary",
    rerunAnalysis: "Run analysis",
    agentReportRunning: "Running",
    jobProgress: "Job progress",
    uploadFailed: "Upload ingestion failed",
    relationSelected: "Relation selected",
    evidenceSelected: "Evidence selected",
    reportReady: "Agent report generated",
    reportFailed: "Agent query failed. Check that the backend API is running.",
    complete: "Complete",
    fallback: "Fallback",
    pending: "Pending",
    partial: "Partial",
    archiveHalls: "Archive Halls",
    hallNav: "Hall navigation",
    starMap: "Star Map",
    graphAria: "Knowledge graph preview",
    relationGraph: "relation graph",
    graphCaptionPrefix: "Focused on",
    graphCaptionSuffix: "Select another hall to shift the graph neighborhood.",
    hideGraphHint: "Hide hint",
    showGraphHint: "Show hint",
    source: "Source",
    relation: "Relation",
    target: "Target",
    evidenceDrawer: "Evidence Drawer",
    evidenceTitle: "Evidence drawer",
    currentFocus: "Current focus",
    sourceTypes: {
      code: "code",
      config: "config",
      markdown: "markdown",
    },
    lineRanges: {
      Config: "Config",
      Module: "Module",
    },
    agentCommand: "Agent Command",
    agentPromptPrefix: "Explain",
    agentPromptSuffix: "trace impact, and cite evidence.",
    runReport: "Run report",
    reportRunning: "Running",
    confidence: "Confidence",
    nextActions: "Next actions",
    llmSource: "Model",
    deterministicSource: "Rule Agent",
    modelStatus: "Model status",
    hybridRag: "Hybrid RAG",
    multimodal: "Multimodal",
    agentProof: "Agent work proof",
    taskHistory: "Task history",
    noTaskHistory: "No task history yet. Run analysis or create an archive to populate it.",
    evidenceUsed: "Evidence",
    entitiesUsed: "Entities",
    relationsUsed: "Relations",
    findings: "Findings",
    risks: "Risks",
    modelEnhanced: "Model enhanced",
    ruleCompleted: "Rules completed",
    modelFallback: "Model enhancement not adopted",
    toolsUsed: "Tools",
    validation: "Validation",
    workLog: "Work log",
  },
} satisfies Record<Locale, Record<string, unknown>>;

const scopeOptions = [
  { profile: "architecture", labelKey: "architectureFirst" },
  { profile: "full", labelKey: "fullAudit" },
  { profile: "docs", labelKey: "docsFirst" },
  { profile: "tests", labelKey: "testsQuality" },
] satisfies { profile: ScanProfile; labelKey: keyof typeof copy.zh }[];

const agentModeOptions = [
  { mode: "architecture_tour", labelKey: "architectureFirst" },
  { mode: "impact_analysis", labelKey: "impactAnalysis" },
  { mode: "risk_audit", labelKey: "riskAudit" },
  { mode: "evidence_qa", labelKey: "evidenceQa" },
] satisfies { mode: ScopeMode; labelKey: keyof typeof copy.zh }[];

const formatNumber = (value: number) => new Intl.NumberFormat("en-US").format(value);

const hallTitle = (hall: ArchiveHall, locale: Locale) =>
  locale === "zh" ? hall.label : hall.name;

const hallDescription = (hall: ArchiveHall, locale: Locale) =>
  locale === "zh" ? hall.descriptionZh : hall.description;

const hallRisk = (hall: ArchiveHall, locale: Locale) =>
  locale === "zh" ? hall.riskZh : hall.risk;

const evidenceTitle = (card: EvidenceCard, locale: Locale) =>
  locale === "zh" ? card.titleZh : card.title;

const evidenceSnippet = (card: EvidenceCard, locale: Locale) =>
  locale === "zh" ? card.snippetZh : card.snippet;

const evidenceSourceType = (card: EvidenceCard, locale: Locale) => {
  const sourceTypes = copy[locale].sourceTypes as Record<string, string>;
  return sourceTypes[card.sourceType] ?? card.sourceType;
};

const evidenceLineRange = (card: EvidenceCard, locale: Locale) => {
  if (card.lineRange.startsWith("L")) return card.lineRange;
  const lineRanges = copy[locale].lineRanges as Record<string, string>;
  return lineRanges[card.lineRange] ?? card.lineRange;
};

const typeLabel = (type: string, locale: Locale) => {
  if (locale === "en") return type;
  const labels: Record<string, string> = {
    Class: "类",
    Concept: "概念",
    Config: "配置",
    File: "文件",
    Function: "函数",
    Import: "导入",
    Markdown: "文档",
    Package: "包",
    Retriever: "检索器",
    YAML: "YAML",
  };
  return labels[type] ?? type;
};

const graphToneCycle: GraphTone[] = ["blue", "amber", "violet", "accent"];
const maxGraphNodes = 18;
const maxGraphEdges = 34;

type VisibleGraphNode = {
  id: string;
  label: string;
  x: number;
  y: number;
  tone: GraphTone;
  isSelected: boolean;
  isDimmed: boolean;
  isSearchMatch: boolean;
};

type VisibleGraphEdge = ArchiveRelation & {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  isSelected: boolean;
  isContextEdge: boolean;
  isDimmed: boolean;
};

const compactGraphLabel = (label: string, maxLength = 24) => {
  const clean = label.replace(/\s+/g, " ").trim();
  if (clean.length <= maxLength) return clean;
  const headLength = Math.max(8, Math.floor(maxLength * 0.58));
  const tailLength = Math.max(6, maxLength - headLength - 3);
  return `${clean.slice(0, headLength)}...${clean.slice(-tailLength)}`;
};

const rankRelations = (relations: ArchiveRelation[], selectedRelationId: string) => {
  const degree = new Map<string, number>();
  relations.forEach((relation) => {
    degree.set(relation.source, (degree.get(relation.source) ?? 0) + 1);
    degree.set(relation.target, (degree.get(relation.target) ?? 0) + 1);
  });

  return [...relations].sort((left, right) => {
    if (left.id === selectedRelationId) return -1;
    if (right.id === selectedRelationId) return 1;
    const leftDegree = (degree.get(left.source) ?? 0) + (degree.get(left.target) ?? 0);
    const rightDegree = (degree.get(right.source) ?? 0) + (degree.get(right.target) ?? 0);
    if (leftDegree !== rightDegree) return rightDegree - leftDegree;
    return left.id.localeCompare(right.id);
  });
};

const relationBelongsToHall = (relation: ArchiveRelation, hallId: string) =>
  relation.hall === hallId;

const evidenceBelongsToHall = (card: EvidenceCard, hallId: string) =>
  card.hall === hallId;

const relationMatchesSearch = (
  relation: ArchiveRelation,
  query: string,
  evidenceById: Map<string, EvidenceCard>,
) => {
  const relatedEvidence = relation.evidenceIds
    .map((evidenceId) => evidenceById.get(evidenceId))
    .filter((card): card is EvidenceCard => Boolean(card));
  return [
    relation.source,
    relation.type,
    relation.target,
    ...relatedEvidence.flatMap((card) => [
      card.title,
      card.titleZh,
      card.sourcePath,
      card.sourceType,
      card.snippet,
      card.snippetZh,
    ]),
  ].some((value) => value.toLowerCase().includes(query));
};

const evidenceMatchesSearch = (card: EvidenceCard, query: string) =>
  [
    card.title,
    card.titleZh,
    card.sourcePath,
    card.sourceType,
    card.snippet,
    card.snippetZh,
    card.lineRange,
  ].some((value) => value.toLowerCase().includes(query));

const buildVisibleGraph = (
  relations: ArchiveRelation[],
  selectedRelationId: string,
  searchMatchedNodeLabels: Set<string>,
) => {
  const usableRelations = relations.filter((relation) => relation.source && relation.target);
  const rankedRelations = rankRelations(usableRelations, selectedRelationId);
  const nodeLabels = new Map<string, string>();
  const edgeRelations: ArchiveRelation[] = [];

  rankedRelations.forEach((relation) => {
    if (edgeRelations.length >= maxGraphEdges) return;
    const nextNodes = [relation.source, relation.target].filter((node) => !nodeLabels.has(node));
    const hasRoomForNodes = nodeLabels.size + nextNodes.length <= maxGraphNodes;
    const connectsVisibleNodes = nodeLabels.has(relation.source) && nodeLabels.has(relation.target);

    if (!hasRoomForNodes && !connectsVisibleNodes) return;

    nodeLabels.set(relation.source, relation.source);
    nodeLabels.set(relation.target, relation.target);
    edgeRelations.push(relation);
  });

  const selectedRelation = usableRelations.find((relation) => relation.id === selectedRelationId);
  const selectedNodeNames = new Set<string>();
  if (selectedRelation) {
    selectedNodeNames.add(selectedRelation.source);
    selectedNodeNames.add(selectedRelation.target);
  }
  const hasSelection = Boolean(selectedRelation);

  const nodes = Array.from(nodeLabels.entries()).map(([id, label], index, allNodes) => {
    const nodeCount = allNodes.length;
    const centerX = 380;
    const centerY = 215;
    const isSingle = nodeCount <= 1;
    const angle = -Math.PI / 2 + (index / Math.max(nodeCount, 1)) * Math.PI * 2 + (nodeCount > 9 ? (index % 2) * 0.16 : 0);
    const radiusScale = nodeCount > 10 && index % 2 ? 0.72 : 1;
    let x = isSingle ? centerX : centerX + Math.cos(angle) * 270 * radiusScale;
    let y = isSingle ? centerY : centerY + Math.sin(angle) * 150 * radiusScale;

    if (selectedRelation?.source === id) {
      x = centerX - 92;
      y = centerY;
    } else if (selectedRelation?.target === id) {
      x = centerX + 92;
      y = centerY;
    }

    return {
      id,
      label,
      x: Math.min(690, Math.max(70, x)),
      y: Math.min(370, Math.max(60, y)),
      tone: selectedNodeNames.has(id) ? "accent" : graphToneCycle[index % graphToneCycle.length],
      isSelected: selectedNodeNames.has(id),
      isDimmed: hasSelection && !selectedNodeNames.has(id),
      isSearchMatch: searchMatchedNodeLabels.has(id),
    };
  });

  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const edges = edgeRelations
    .map((relation) => {
      const source = nodeById.get(relation.source);
      const target = nodeById.get(relation.target);
      if (!source || !target) return null;
      const isSelected = relation.id === selectedRelationId;
      const isContextEdge =
        Boolean(selectedRelation) &&
        !isSelected &&
        (selectedNodeNames.has(relation.source) || selectedNodeNames.has(relation.target));
      return {
        ...relation,
        x1: source.x,
        y1: source.y,
        x2: target.x,
        y2: target.y,
        isSelected,
        isContextEdge,
        isDimmed: hasSelection && !isSelected && !isContextEdge,
      };
    })
    .filter((relation): relation is VisibleGraphEdge => Boolean(relation))
    .sort((left, right) => Number(left.isSelected) - Number(right.isSelected));

  return { nodes, edges, selectedRelation, totalRelations: usableRelations.length };
};

function AppHeader({
  agentStatus,
  archiveIds,
  isCreatingArchive,
  isLoading,
  isSwitchingArchive,
  locale,
  onCreateArchive,
  onArchiveChange,
  onLocaleChange,
  onSearchGraph,
  selectedArchiveId,
}: {
  agentStatus: AgentStatus | null;
  archiveIds: string[];
  isCreatingArchive: boolean;
  isLoading: boolean;
  isSwitchingArchive: boolean;
  locale: Locale;
  onCreateArchive: () => void;
  onArchiveChange: (projectId: string) => void;
  onLocaleChange: (locale: Locale) => void;
  onSearchGraph: () => void;
  selectedArchiveId: string;
}) {
  const t = copy[locale];
  const agentLabel = agentStatus
    ? agentStatus.llm_enabled
      ? `${agentStatus.provider} · ${agentStatus.model ?? "model"}`
      : String(t.deterministicSource)
    : String(t.checkingAgent);
  return (
    <header className="topbar">
      <div className="brand-mark" aria-hidden="true">
        <Archive size={20} />
      </div>
      <div className="brand-copy">
        <span className="product-name">TwinMind Archive</span>
        <span className="product-subtitle">{t.subtitle}</span>
      </div>
      <div className="topbar-actions">
        {isLoading ? <span className="api-status">{t.loadingArchive}</span> : null}
        {isSwitchingArchive ? <span className="api-status">{t.loadingSelectedArchive}</span> : null}
        <div className={`agent-status ${agentStatus?.llm_enabled ? "is-llm" : ""}`}>
          <span>{t.agentStatus}</span>
          <strong>{agentLabel}</strong>
        </div>
        <label className="archive-select">
          <span>{t.archiveSelector}</span>
          <select
            aria-label={String(t.archiveSelector)}
            disabled={isLoading || isSwitchingArchive}
            value={selectedArchiveId}
            onChange={(event) => onArchiveChange(event.currentTarget.value)}
          >
            <option value="">{String(t.archiveSelectorPlaceholder)}</option>
            {archiveIds.map((projectId) => (
              <option key={projectId} value={projectId}>
                {projectId}
              </option>
            ))}
          </select>
          <ChevronDown size={16} />
        </label>
        <div className="language-toggle" aria-label="Language switcher">
          <button
            className={locale === "zh" ? "is-selected" : ""}
            onClick={() => onLocaleChange("zh")}
            type="button"
          >
            中文
          </button>
          <button
            className={locale === "en" ? "is-selected" : ""}
            onClick={() => onLocaleChange("en")}
            type="button"
          >
            EN
          </button>
        </div>
        <button className="ghost-button" onClick={onSearchGraph} type="button">
          <Search size={16} />
          {t.searchGraph}
        </button>
        <button
          className="primary-button"
          disabled={isCreatingArchive}
          onClick={onCreateArchive}
          type="button"
        >
          <FolderInput size={16} />
          {isCreatingArchive ? t.creatingArchive : t.createArchive}
        </button>
      </div>
    </header>
  );
}

function ProjectPassport({
  archiveDraft,
  isFallback,
  locale,
}: {
  archiveDraft: ArchiveDraft;
  isFallback: boolean;
  locale: Locale;
}) {
  const t = copy[locale];
  return (
    <section className="passport" aria-label="Project passport">
      <div className="passport-main">
        <div className="eyebrow">{t.archiveObservatory}</div>
        <h1>{archiveDraft.projectId}</h1>
        <p>{t.passportSummary}</p>
        <div className="language-row">
          <span className="pill strong">{t.scope}</span>
          <span className="pill">{isFallback ? t.fallbackArchive : t.liveArchive}</span>
          {archiveDraft.languages.map((language) => (
            <span className="pill" key={language.name}>
              {language.name} · {language.count}
            </span>
          ))}
        </div>
      </div>
      <div className="metric-strip" aria-label="Archive metrics">
        <Metric label={t.metrics.halls} value={archiveDraft.metrics.halls} icon={<Layers3 />} />
        <Metric label={t.metrics.entities} value={archiveDraft.metrics.entities} icon={<Boxes />} />
        <Metric label={t.metrics.relations} value={archiveDraft.metrics.relations} icon={<GitBranch />} />
        <Metric label={t.metrics.evidence} value={archiveDraft.metrics.evidence} icon={<ShieldCheck />} />
      </div>
    </section>
  );
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: number }) {
  return (
    <div className="metric">
      <span className="metric-icon">{icon}</span>
      <span className="metric-value">{formatNumber(value)}</span>
      <span className="metric-label">{label}</span>
    </div>
  );
}

function PageTabs({
  activePage,
  locale,
  onPageChange,
}: {
  activePage: AppPage;
  locale: Locale;
  onPageChange: (page: AppPage) => void;
}) {
  const tabs = [
    { id: "overview" as AppPage, label: copy[locale].overviewPage, icon: Archive },
    { id: "graph" as AppPage, label: copy[locale].graphPage, icon: Network },
    { id: "agents" as AppPage, label: copy[locale].agentPage, icon: Sparkles },
  ];
  return (
    <nav className="page-tabs" aria-label="TwinMind Archive sections">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        return (
          <button
            aria-current={activePage === tab.id ? "page" : undefined}
            className={activePage === tab.id ? "is-active" : ""}
            key={tab.id}
            onClick={() => onPageChange(tab.id)}
            type="button"
          >
            <Icon size={16} />
            {String(tab.label)}
          </button>
        );
      })}
    </nav>
  );
}

function UploadDock({
  isCreatingArchive,
  locale,
  onScanProfileChange,
  onZipSelected,
  scanProfile,
  selectedFileName,
  uploadProgress,
  uploadProgressMessage,
}: {
  isCreatingArchive: boolean;
  locale: Locale;
  onScanProfileChange: (scanProfile: ScanProfile) => void;
  onZipSelected: (file: File) => void;
  scanProfile: ScanProfile;
  selectedFileName: string;
  uploadProgress: number;
  uploadProgressMessage: string;
}) {
  const t = copy[locale];
  const showProgress = isCreatingArchive || uploadProgress > 0;
  return (
    <section className="upload-dock" aria-label="Create archive" id="project-intake">
      <div>
        <div className="panel-title">
          <FileArchive size={16} />
          {t.intake}
        </div>
        <p>
          {selectedFileName
            ? `${t.zipSelected}: ${selectedFileName}. ${t.uploadPending}`
            : t.intakeCopy}
        </p>
        {showProgress ? (
          <div className="upload-progress" aria-label="Archive creation progress">
            <div>
              <span>
                {uploadProgressMessage ||
                  (uploadProgress >= 80 && uploadProgress < 100 ? t.processingArchive : t.createPending)}
              </span>
              <strong>{uploadProgress}%</strong>
            </div>
            <progress max="100" value={uploadProgress} />
          </div>
        ) : null}
      </div>
      <label className="upload-target">
        <Upload size={18} />
        <span>{t.chooseZip}</span>
        <input
          aria-label={t.uploadLabel as string}
          type="file"
          accept=".zip"
          onChange={(event) => {
            const file = event.currentTarget.files?.[0];
            if (file) onZipSelected(file);
          }}
        />
      </label>
      <label className="scope-select">
        <select
          aria-label={String(t.scope)}
          value={scanProfile}
          onChange={(event) => onScanProfileChange(event.currentTarget.value as ScanProfile)}
        >
          {scopeOptions.map((option) => (
            <option key={option.profile} value={option.profile}>
              {String(t[option.labelKey])}
            </option>
          ))}
        </select>
        <ChevronDown size={16} />
      </label>
    </section>
  );
}

function EmptyArchiveState({
  archiveCount,
  locale,
}: {
  archiveCount: number;
  locale: Locale;
}) {
  const t = copy[locale];
  return (
    <section className="empty-archive panel" aria-label={String(t.cleanStartTitle)}>
      <div className="empty-archive-icon" aria-hidden="true">
        <Archive size={22} />
      </div>
      <div>
        <span className="eyebrow">{t.archiveObservatory}</span>
        <h2>{String(t.cleanStartTitle)}</h2>
        <p>{String(t.cleanStartCopy)}</p>
        <div className="empty-archive-actions">
          <span className="pill strong">{archiveCount ? `${archiveCount} ${String(t.archiveSelector)}` : String(t.noArchiveSelected)}</span>
        </div>
      </div>
    </section>
  );
}

function HallRail({
  archiveDraft,
  selectedHallId,
  onSelect,
  locale,
}: {
  archiveDraft: ArchiveDraft;
  selectedHallId: string;
  onSelect: (hall: ArchiveHall) => void;
  locale: Locale;
}) {
  const t = copy[locale];
  return (
    <aside className="rail panel" aria-label="Archive halls">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{t.archiveHalls}</span>
          <h2>{t.hallNav}</h2>
        </div>
        <Layers3 size={18} />
      </div>
      <div className="hall-list">
        {archiveDraft.halls.map((hall) => (
          <button
            className={`hall-item ${hall.id === selectedHallId ? "is-active" : ""}`}
            key={hall.id}
            onClick={() => onSelect(hall)}
            type="button"
          >
            <span className="hall-count">{hall.count}</span>
            <span className="hall-name">{hallTitle(hall, locale)}</span>
            <span className="hall-description">{hallDescription(hall, locale)}</span>
            <span className="type-row">
              {hall.dominantTypes.map((type) => (
                <span className="mini-pill" key={type}>
                  {typeLabel(type, locale)}
                </span>
              ))}
            </span>
          </button>
        ))}
      </div>
    </aside>
  );
}

function StarMap({
  evidenceCards,
  hall,
  isGraphHintVisible,
  relations,
  locale,
  onExpandGraph,
  onGraphHintClose,
  onGraphHintShow,
  onEvidenceSelect,
  onRelationClear,
  onRelationSelect,
  searchQuery,
  searchVisible,
  selectedRelationId,
  onSearchChange,
}: {
  evidenceCards: EvidenceCard[];
  hall: ArchiveHall;
  isGraphHintVisible: boolean;
  relations: ArchiveRelation[];
  locale: Locale;
  onExpandGraph: () => void;
  onGraphHintClose: () => void;
  onGraphHintShow: () => void;
  onEvidenceSelect: (card: EvidenceCard) => void;
  onRelationClear: () => void;
  onRelationSelect: (relation: ArchiveRelation) => void;
  searchQuery: string;
  searchVisible: boolean;
  selectedRelationId: string;
  onSearchChange: (query: string) => void;
}) {
  const t = copy[locale];
  const visibleRelations = relations.filter((relation) => relationBelongsToHall(relation, hall.id));
  const visibleEvidenceCards = evidenceCards.filter((card) => evidenceBelongsToHall(card, hall.id));
  const evidenceById = useMemo(
    () => new Map(evidenceCards.map((card) => [card.id, card])),
    [evidenceCards],
  );
  const normalizedQuery = searchQuery.trim().toLowerCase();
  const filteredRelations = normalizedQuery
    ? visibleRelations.filter((relation) =>
        relationMatchesSearch(relation, normalizedQuery, evidenceById),
      )
    : visibleRelations;
  const matchedEvidenceCards = normalizedQuery
    ? visibleEvidenceCards.filter((card) => evidenceMatchesSearch(card, normalizedQuery))
    : [];
  const searchMatchedNodeLabels = useMemo(() => {
    if (!normalizedQuery) return new Set<string>();
    const labels = new Set<string>();
    filteredRelations.forEach((relation) => {
      if (relation.source.toLowerCase().includes(normalizedQuery)) labels.add(relation.source);
      if (relation.target.toLowerCase().includes(normalizedQuery)) labels.add(relation.target);
    });
    return labels;
  }, [filteredRelations, normalizedQuery]);
  const visibleGraph = useMemo(
    () => buildVisibleGraph(filteredRelations, selectedRelationId, searchMatchedNodeLabels),
    [filteredRelations, searchMatchedNodeLabels, selectedRelationId],
  );
  const graphCounter =
    locale === "zh"
      ? `显示 ${formatNumber(visibleGraph.nodes.length)} 个节点 / ${formatNumber(visibleGraph.edges.length)} 条关系，当前匹配 ${formatNumber(visibleGraph.totalRelations)} 条`
      : `Showing ${formatNumber(visibleGraph.nodes.length)} nodes / ${formatNumber(visibleGraph.edges.length)} relations from ${formatNumber(visibleGraph.totalRelations)} matches`;
  const emptyGraphText =
    locale === "zh"
      ? "当前展厅还没有可展示的关系。换一个展厅或清空搜索试试。"
      : "No relations are available for this hall. Try another hall or clear search.";
  const searchResultText =
    locale === "zh"
      ? `匹配 ${formatNumber(filteredRelations.length)} 条关系 / ${formatNumber(matchedEvidenceCards.length)} 张证据`
      : `${formatNumber(filteredRelations.length)} relations / ${formatNumber(matchedEvidenceCards.length)} evidence cards`;
  const clearSearchText = locale === "zh" ? "清空搜索" : "Clear search";
  const handleSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    if (filteredRelations[0]) {
      onRelationSelect(filteredRelations[0]);
      return;
    }
    if (matchedEvidenceCards[0]) {
      onEvidenceSelect(matchedEvidenceCards[0]);
    }
  };
  const handleClearSearch = () => {
    onSearchChange("");
    onRelationClear();
  };

  return (
    <main className="star-workspace panel" aria-label="Star map workspace">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{t.starMap}</span>
          <h2>{hallTitle(hall, locale)}</h2>
        </div>
        <div className="panel-tools">
          <button className="secondary-action" onClick={onExpandGraph} type="button">
            <Network size={15} />
            {t.expandGraph}
          </button>
          {!isGraphHintVisible ? (
            <button className="icon-button" onClick={onGraphHintShow} type="button" title={String(t.showGraphHint)}>
              <CircleDot size={16} />
            </button>
          ) : null}
        </div>
      </div>
      {(searchVisible || searchQuery) ? (
        <div className="graph-search-wrap">
          <label className="graph-search">
            <Search size={16} />
            <input
              autoFocus={searchVisible}
              value={searchQuery}
              placeholder={String(t.searchPlaceholder)}
              onChange={(event) => onSearchChange(event.currentTarget.value)}
              onKeyDown={handleSearchKeyDown}
            />
            {searchQuery ? (
              <button className="icon-button subtle" onClick={handleClearSearch} type="button" title={clearSearchText}>
                <X size={14} />
              </button>
            ) : null}
          </label>
          {searchQuery ? (
            <div className="graph-search-results">
              <span>{searchResultText}</span>
              {matchedEvidenceCards.slice(0, 3).map((card) => (
                <button key={card.id} onClick={() => onEvidenceSelect(card)} type="button">
                  {compactGraphLabel(card.sourcePath, 32)}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
      <div className="graph-stage" aria-label={t.graphAria as string}>
        {visibleGraph.nodes.length ? (
          <svg viewBox="0 0 760 430" role="img" aria-label={`${hallTitle(hall, locale)} ${t.relationGraph}`}>
            <defs>
              <radialGradient id="nodeGlow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#35d0ba" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#35d0ba" stopOpacity="0" />
              </radialGradient>
              <marker id="graphArrow" markerHeight="7" markerWidth="7" orient="auto" refX="6" refY="3.5">
                <path d="M0,0 L7,3.5 L0,7 Z" />
              </marker>
              <marker id="graphArrowSelected" markerHeight="7" markerWidth="7" orient="auto" refX="6" refY="3.5">
                <path d="M0,0 L7,3.5 L0,7 Z" />
              </marker>
            </defs>
            <path className="orbit orbit-a" d="M98 219 C184 72 579 72 674 216 C562 356 231 367 98 219Z" />
            <path className="orbit orbit-b" d="M161 290 C211 134 482 75 612 184 C547 333 298 367 161 290Z" />
            {visibleGraph.edges.map((edge) => (
              <line
                className={`graph-edge ${edge.isSelected ? "is-selected" : ""} ${
                  edge.isContextEdge ? "is-context" : ""
                } ${edge.isDimmed ? "is-dimmed" : ""}`}
                key={edge.id}
                markerEnd={edge.isSelected ? "url(#graphArrowSelected)" : "url(#graphArrow)"}
                x1={edge.x1}
                x2={edge.x2}
                y1={edge.y1}
                y2={edge.y2}
              >
                <title>{`${edge.source} ${edge.type} ${edge.target}`}</title>
              </line>
            ))}
            {visibleGraph.nodes.map((node) => (
              <GraphNode
                isDimmed={node.isDimmed}
                isSearchMatch={node.isSearchMatch}
                isSelected={node.isSelected}
                key={node.id}
                label={node.label}
                tone={node.tone}
                x={node.x}
                y={node.y}
              />
            ))}
          </svg>
        ) : (
          <div className="graph-empty">{emptyGraphText}</div>
        )}
        <div className="graph-counter">{graphCounter}</div>
        {isGraphHintVisible ? (
          <div className="graph-caption">
            <CircleDot size={14} />
            <span>
              {t.graphCaptionPrefix} {hallTitle(hall, locale)}. {t.graphCaptionSuffix}
            </span>
            <button className="icon-button subtle" onClick={onGraphHintClose} type="button" title={String(t.hideGraphHint)}>
              <X size={14} />
            </button>
          </div>
        ) : null}
      </div>
      {visibleGraph.selectedRelation ? (
        <button
          className="relation-focus-card"
          onClick={onRelationClear}
          type="button"
          aria-label={locale === "zh" ? "关闭当前关系聚焦" : "Close focused relation"}
        >
          <span>{locale === "zh" ? "当前关系" : "Focused relation"}</span>
          <strong>{compactGraphLabel(visibleGraph.selectedRelation.source, 38)}</strong>
          <code>{visibleGraph.selectedRelation.type}</code>
          <strong>{compactGraphLabel(visibleGraph.selectedRelation.target, 38)}</strong>
          <X size={15} />
        </button>
      ) : null}
      <div className="relation-table" aria-label="Relation browser">
        <div className="table-head">
          <span>{t.source}</span>
          <span>{t.relation}</span>
          <span>{t.target}</span>
        </div>
        <div className="relation-table-body">
          {filteredRelations.length ? (
            filteredRelations.slice(0, 60).map((relation) => (
              <button
                className={`table-row ${relation.id === selectedRelationId ? "is-active" : ""}`}
                key={relation.id}
                onClick={() => onRelationSelect(relation)}
                type="button"
              >
                <span>{relation.source}</span>
                <span className="relation-type">{relation.type}</span>
                <span>{relation.target}</span>
              </button>
            ))
          ) : (
            <div className="empty-row">{emptyGraphText}</div>
          )}
        </div>
      </div>
    </main>
  );
}

function GraphNode({
  isDimmed,
  isSearchMatch,
  isSelected,
  label,
  tone,
  x,
  y,
}: {
  isDimmed: boolean;
  isSearchMatch: boolean;
  isSelected: boolean;
  label: string;
  tone: GraphTone;
  x: number;
  y: number;
}) {
  const displayLabel = compactGraphLabel(label);
  return (
    <g className={`graph-node ${tone} ${isSelected ? "is-selected" : ""} ${isSearchMatch ? "is-search-match" : ""} ${isDimmed ? "is-dimmed" : ""}`}>
      <title>{label}</title>
      <circle className="node-glow" cx={x} cy={y} r={isSelected ? 62 : 42} />
      <circle cx={x} cy={y} r={isSelected ? 20 : 14} />
      <text textAnchor="middle" x={x} y={y + (isSelected ? 42 : 34)}>
        {displayLabel}
      </text>
    </g>
  );
}

function EvidenceDrawer({
  hall,
  cards,
  locale,
  onEvidenceSelect,
  selectedEvidenceId,
}: {
  hall: ArchiveHall;
  cards: EvidenceCard[];
  locale: Locale;
  onEvidenceSelect: (card: EvidenceCard) => void;
  selectedEvidenceId: string;
}) {
  const t = copy[locale];
  const visibleCards = cards.filter((card) => evidenceBelongsToHall(card, hall.id));
  const emptyText =
    locale === "zh"
      ? "当前展厅还没有直接绑定的证据。可以到图谱探索页查看实体级证据链。"
      : "No evidence is directly bound to this hall yet. Open Graph Explorer for entity-level evidence.";

  return (
    <aside className="evidence panel" aria-label="Evidence drawer">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{t.evidenceDrawer}</span>
          <h2>{t.evidenceTitle}</h2>
        </div>
        <PanelRight size={18} />
      </div>
      <div className="selected-entity">
        <span className="entity-label">{t.currentFocus}</span>
        <strong>{hallTitle(hall, locale)}</strong>
        <p>{hallRisk(hall, locale)}</p>
      </div>
      <div className="evidence-list">
        {visibleCards.length ? (
          visibleCards.slice(0, 4).map((card) => (
            <button
              className={`evidence-card ${card.id === selectedEvidenceId ? "is-active" : ""}`}
              key={card.id}
              onClick={() => onEvidenceSelect(card)}
              type="button"
            >
              <div className="evidence-meta">
                <span>{evidenceSourceType(card, locale)}</span>
                <span>{evidenceLineRange(card, locale)}</span>
              </div>
              <h3>{evidenceTitle(card, locale)}</h3>
              <code>{card.sourcePath}</code>
              <p>{evidenceSnippet(card, locale)}</p>
            </button>
          ))
        ) : (
          <div className="evidence-empty">{emptyText}</div>
        )}
      </div>
    </aside>
  );
}

function AgentCommandBar({
  evidenceCards,
  hall,
  locale,
  onNotify,
  projectId,
  scopeMode,
}: {
  evidenceCards: EvidenceCard[];
  hall: ArchiveHall;
  locale: Locale;
  onNotify: (message: string) => void;
  projectId: string;
  scopeMode: ScopeMode;
}) {
  const t = copy[locale];
  const hallSamples = hall.sampleEntities.slice(0, 5).join(", ");
  const defaultQuestion =
    locale === "zh"
      ? `基于当前展厅的实体、关系和证据分析「${hallTitle(hall, locale)}」。展厅说明：${hallDescription(hall, locale)}。代表实体：${hallSamples || "暂无"}。请追踪影响，并引用证据。`
      : `Analyze "${hallTitle(hall, locale)}" using the current hall's entities, relations, and evidence. Hall description: ${hallDescription(hall, locale)}. Representative entities: ${hallSamples || "none"}. Trace impact and cite evidence.`;
  const [question, setQuestion] = useState(defaultQuestion);
  const [mode, setMode] = useState<ScopeMode>(scopeMode);
  const [report, setReport] = useState<AgentReport | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState("");
  const evidenceById = useMemo(
    () => new Map(evidenceCards.map((card) => [card.id, card])),
    [evidenceCards],
  );
  const citedEvidence = report?.evidence_card_ids
    .map((id) => evidenceById.get(id))
    .filter((card): card is EvidenceCard => Boolean(card)) ?? [];

  useEffect(() => {
    setQuestion(defaultQuestion);
    setReport(null);
    setError("");
  }, [defaultQuestion]);

  const handleRunReport = async () => {
    if (isRunning) return;
    setIsRunning(true);
    setError("");
    try {
      const nextReport = await runArchiveQuery(projectId, question.trim() || defaultQuestion, mode, hall.id);
      setReport(nextReport);
      onNotify(String(t.reportReady));
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : String(t.reportFailed);
      setError(message);
      onNotify(`${t.reportFailed}: ${message}`);
    } finally {
      setIsRunning(false);
    }
  };
  const handleQuestionKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    void handleRunReport();
  };

  return (
    <section className="agent-bar" aria-label="Agent command bar">
      <div className="agent-mode">
        <Command size={18} />
        {t.agentCommand}
      </div>
      <label className="agent-mode-select">
        <select value={mode} onChange={(event) => setMode(event.currentTarget.value as ScopeMode)}>
          {agentModeOptions.map((option) => (
            <option key={option.mode} value={option.mode}>
              {String(t[option.labelKey])}
            </option>
          ))}
        </select>
        <ChevronDown size={15} />
      </label>
      <label className="agent-input">
        <Sparkles size={16} />
        <input
          value={question}
          onChange={(event) => setQuestion(event.currentTarget.value)}
          onKeyDown={handleQuestionKeyDown}
        />
      </label>
      <button className="primary-button" disabled={isRunning} onClick={handleRunReport} type="button">
        <Braces size={16} />
        {isRunning ? t.reportRunning : t.runReport}
      </button>
      {error ? <div className="agent-report-error">{error}</div> : null}
      {report ? (
        <div className="agent-report">
          <div className="agent-report-head">
            <strong>{report.summary}</strong>
            <span>
              {t.confidence}: {Math.round(report.confidence * 100)}%
            </span>
            <span>
              {t.llmSource}:{" "}
              {report.metadata?.llm?.enabled && !report.metadata.llm.fallback
                ? `${report.metadata.llm.provider ?? "llm"} · ${report.metadata.llm.model ?? ""}`
                : report.metadata?.llm?.fallback
                  ? t.modelFallback
                  : t.deterministicSource}
            </span>
          </div>
          <div className="agent-report-metrics">
            <span>{t.evidenceUsed}: {report.evidence_card_ids.length}</span>
            <span>{t.entitiesUsed}: {report.affected_entities.length}</span>
            <span>{t.relationsUsed}: {report.graph_paths?.reduce((count, path) => count + path.relations.length, 0) ?? 0}</span>
          </div>
          {citedEvidence.length ? (
            <div className="agent-report-evidence">
              {citedEvidence.slice(0, 4).map((card) => (
                <article key={card.id}>
                  <span>{evidenceSourceType(card, locale)} · {evidenceLineRange(card, locale)}</span>
                  <strong>{evidenceTitle(card, locale)}</strong>
                  <code>{card.sourcePath}</code>
                </article>
              ))}
            </div>
          ) : null}
          {report.risks.length ? (
            <p>
              {t.risks}: {report.risks.slice(0, 3).join(" · ")}
            </p>
          ) : null}
          {report.next_actions.length ? (
            <p>
              {t.nextActions}: {report.next_actions.slice(0, 2).join(" · ")}
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

const agentRoleOrder = ["archivist", "cartographer", "detective", "skeptic", "curator"] as const;

type AgentRole = (typeof agentRoleOrder)[number];

const agentRoleLabels = {
  zh: {
    archivist: "档案员",
    cartographer: "制图师",
    detective: "侦探",
    skeptic: "质疑者",
    curator: "策展人",
  },
  en: {
    archivist: "Archivist",
    cartographer: "Cartographer",
    detective: "Detective",
    skeptic: "Skeptic",
    curator: "Curator",
  },
} satisfies Record<Locale, Record<AgentRole, string>>;

const statusLabel = (status: string, locale: Locale) => {
  const labels = copy[locale] as Record<string, unknown>;
  return String(labels[status] ?? status);
};

const missionStatusLabel = (status: string, locale: Locale) => {
  const labels: Record<string, Record<string, string>> = {
    zh: {
      completed: "已完成",
      complete: "已完成",
      cancelled: "已取消",
      failed: "失败",
      paused: "已暂停",
      partial: "部分完成",
      pending: "等待",
      running: "运行中",
      stopped: "已停止",
    },
    en: {
      completed: "Completed",
      complete: "Completed",
      cancelled: "Cancelled",
      failed: "Failed",
      paused: "Paused",
      partial: "Partial",
      pending: "Pending",
      running: "Running",
      stopped: "Stopped",
    },
  };
  return labels[locale][status] ?? status;
};

const isMissionTerminal = (mission: { status: string } | null) =>
  Boolean(mission && ["completed", "complete", "partial", "failed", "stopped", "cancelled"].includes(mission.status));

const wait = (delayMs: number) => new Promise<void>((resolve) => window.setTimeout(resolve, delayMs));

const summarizeMissionItems = (items: Record<string, unknown>[], locale: Locale) => {
  if (!items.length) return locale === "zh" ? "无" : "None";
  return items
    .slice(0, 2)
    .map((item) => String(item.title ?? item.summary ?? item.detail ?? item.description ?? JSON.stringify(item)))
    .join(" · ");
};

function GraphExplorerPage({
  archiveDraft,
  locale,
  missionOverlay,
  onOpenMission,
}: {
  archiveDraft: ArchiveDraft;
  locale: Locale;
  missionOverlay: MissionGraphOverlay | null;
  onOpenMission: () => void;
}) {
  const t = copy[locale];
  const initialHallId = archiveDraft.halls[0]?.id ?? null;
  const [summary, setSummary] = useState<GraphSummary | null>(null);
  const [neighborhood, setNeighborhood] = useState<GraphNeighborhood | null>(null);
  const [focusedEntityId, setFocusedEntityId] = useState<string | null>(null);
  const [selectedRelationId, setSelectedRelationId] = useState<string | null>(null);
  const [selectedHallId, setSelectedHallId] = useState<string | null>(initialHallId);
  const [depth, setDepth] = useState(1);
  const [isLeftOpen, setIsLeftOpen] = useState(true);
  const [isRightOpen, setIsRightOpen] = useState(true);
  const [isSummaryLoading, setIsSummaryLoading] = useState(false);
  const [isNeighborhoodLoading, setIsNeighborhoodLoading] = useState(false);
  const [graphSearchQuery, setGraphSearchQuery] = useState("");
  const [graphSearchResults, setGraphSearchResults] = useState<GraphSearchResult[]>([]);
  const [isGraphSearchLoading, setIsGraphSearchLoading] = useState(false);
  const graphSearchAnchorRef = useRef<HTMLLabelElement | null>(null);
  const [graphSearchMenuStyle, setGraphSearchMenuStyle] = useState<CSSProperties | undefined>();
  const [graphSearchError, setGraphSearchError] = useState("");
  const [summaryError, setSummaryError] = useState("");
  const [neighborhoodError, setNeighborhoodError] = useState("");

  useEffect(() => {
    setSelectedHallId(archiveDraft.halls[0]?.id ?? null);
    setFocusedEntityId(null);
    setSelectedRelationId(null);
    setGraphSearchQuery("");
    setGraphSearchResults([]);
    setGraphSearchError("");
  }, [archiveDraft.projectId, archiveDraft.halls]);

  useEffect(() => {
    let isMounted = true;
    setSummary(null);
    setIsSummaryLoading(true);

    fetchGraphSummary(archiveDraft.projectId)
      .then((nextSummary) => {
        if (!isMounted) return;
        setSummary(nextSummary);
        setSummaryError("");
      })
      .catch((nextError) => {
        if (!isMounted) return;
        setSummary(null);
        setSummaryError(nextError instanceof Error ? nextError.message : String(nextError));
      })
      .finally(() => {
        if (isMounted) setIsSummaryLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [archiveDraft.projectId]);

  useEffect(() => {
    const normalizedQuery = graphSearchQuery.trim();
    if (normalizedQuery.length < 2) {
      setGraphSearchResults([]);
      setGraphSearchError("");
      setIsGraphSearchLoading(false);
      return;
    }

    let isMounted = true;
    setIsGraphSearchLoading(true);
    const timerId = window.setTimeout(() => {
      searchGraphEntities(archiveDraft.projectId, normalizedQuery, 12)
        .then((results) => {
          if (!isMounted) return;
          setGraphSearchResults(results);
          setGraphSearchError("");
        })
        .catch((nextError) => {
          if (!isMounted) return;
          setGraphSearchResults([]);
          setGraphSearchError(nextError instanceof Error ? nextError.message : String(nextError));
        })
        .finally(() => {
          if (isMounted) setIsGraphSearchLoading(false);
        });
    }, 220);

    return () => {
      isMounted = false;
      window.clearTimeout(timerId);
    };
  }, [archiveDraft.projectId, graphSearchQuery]);

  useEffect(() => {
    let isMounted = true;
    setNeighborhood(null);
    setIsNeighborhoodLoading(true);

    fetchGraphNeighborhood({
      projectId: archiveDraft.projectId,
      hallId: selectedHallId,
      focusEntityId: focusedEntityId,
      depth,
      relationTypes: [],
    })
      .then((nextNeighborhood) => {
        if (!isMounted) return;
        setNeighborhood(nextNeighborhood);
        setNeighborhoodError("");
      })
      .catch((nextError) => {
        if (!isMounted) return;
        setNeighborhood(null);
        setNeighborhoodError(nextError instanceof Error ? nextError.message : String(nextError));
      })
      .finally(() => {
        if (isMounted) setIsNeighborhoodLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [archiveDraft.projectId, selectedHallId, focusedEntityId, depth]);

  const selectedRelation =
    neighborhood?.relations.find((relation) => relation.id === selectedRelationId) ?? null;
  const focusedNode =
    neighborhood?.nodes.find((node) => node.id === focusedEntityId) ?? null;
  const nodeById = useMemo(
    () => new Map(neighborhood?.nodes.map((node) => [node.id, node]) ?? []),
    [neighborhood],
  );
  const graphSearchMatchedEntityIds = useMemo(
    () => new Set(graphSearchResults.map((result) => result.entity_id)),
    [graphSearchResults],
  );
  const visibleNodeCount = neighborhood?.nodes.length ?? 0;
  const visibleRelationCount = neighborhood?.relations.length ?? 0;
  const visibleError = neighborhoodError || summaryError;
  const statusText = visibleError
    ? visibleError
    : locale === "zh"
      ? `显示 ${formatNumber(visibleNodeCount)} 个节点 / ${formatNumber(visibleRelationCount)} 条关系`
      : `Showing ${formatNumber(visibleNodeCount)} nodes / ${formatNumber(visibleRelationCount)} relations`;
  const selectGraphSearchResult = (result: GraphSearchResult) => {
    if (result.hall_ids.length && !result.hall_ids.includes(selectedHallId ?? "")) {
      setSelectedHallId(result.hall_ids[0]);
    } else if (!result.hall_ids.length) {
      setSelectedHallId(null);
    }
    setFocusedEntityId(result.entity_id);
    setSelectedRelationId(null);
    setIsRightOpen(true);
  };
  const handleGraphSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    if (graphSearchResults[0]) selectGraphSearchResult(graphSearchResults[0]);
  };
  const updateGraphSearchMenuPosition = () => {
    const rect = graphSearchAnchorRef.current?.getBoundingClientRect();
    if (!rect) {
      setGraphSearchMenuStyle(undefined);
      return;
    }
    const width = Math.min(420, Math.max(320, rect.width));
    const viewportPadding = 12;
    setGraphSearchMenuStyle({
      top: rect.bottom + 8,
      left: Math.min(
        Math.max(viewportPadding, rect.right - width),
        window.innerWidth - width - viewportPadding,
      ),
      width,
    });
  };

  useEffect(() => {
    if (graphSearchQuery.trim().length < 2) {
      setGraphSearchMenuStyle(undefined);
      return;
    }
    updateGraphSearchMenuPosition();
    window.addEventListener("resize", updateGraphSearchMenuPosition);
    window.addEventListener("scroll", updateGraphSearchMenuPosition, true);
    return () => {
      window.removeEventListener("resize", updateGraphSearchMenuPosition);
      window.removeEventListener("scroll", updateGraphSearchMenuPosition, true);
    };
  }, [graphSearchQuery]);

  return (
    <section className="graph-explorer-page">
      <div className="graph-explorer-toolbar panel">
        <div>
          <span className="eyebrow">{t.graphExplorer}</span>
          <h2>{archiveDraft.projectId}</h2>
        </div>
        <div className="toolbar-actions">
          <label className="graph-toolbar-select">
            <span>{t.archiveHalls}</span>
            <select
              aria-label={String(t.archiveHalls)}
              value={selectedHallId ?? ""}
              onChange={(event) => {
                setSelectedHallId(event.currentTarget.value || null);
                setFocusedEntityId(null);
                setSelectedRelationId(null);
              }}
            >
              <option value="">{String(t.allGraph)}</option>
              {archiveDraft.halls.map((hall) => (
                <option key={hall.id} value={hall.id}>
                  {hallTitle(hall, locale)}
                </option>
              ))}
            </select>
            <ChevronDown size={15} />
          </label>
          <div className="graph-search-popover">
            <label className="graph-toolbar-search" ref={graphSearchAnchorRef}>
              <Search size={15} />
              <input
                aria-label={String(t.searchEntities)}
                value={graphSearchQuery}
                placeholder={String(t.graphSearchPlaceholder)}
                onChange={(event) => setGraphSearchQuery(event.currentTarget.value)}
                onKeyDown={handleGraphSearchKeyDown}
              />
              {graphSearchQuery ? (
                <button
                  className="icon-button subtle"
                  onClick={() => {
                    setGraphSearchQuery("");
                    setGraphSearchResults([]);
                    setGraphSearchError("");
                  }}
                  type="button"
                  title={locale === "zh" ? "清空搜索" : "Clear search"}
                >
                  <X size={14} />
                </button>
              ) : null}
            </label>
            {graphSearchQuery.trim().length >= 2 ? (
              <div className="graph-search-menu" style={graphSearchMenuStyle}>
                <div className={`graph-search-state ${graphSearchError ? "is-error" : ""}`}>
                  {graphSearchError
                    ? graphSearchError
                    : isGraphSearchLoading
                      ? locale === "zh" ? "搜索中..." : "Searching..."
                      : graphSearchResults.length
                        ? locale === "zh"
                          ? `${formatNumber(graphSearchResults.length)} 个实体结果`
                          : `${formatNumber(graphSearchResults.length)} entity results`
                        : String(t.graphSearchEmpty)}
                </div>
                {graphSearchResults.map((result) => (
                  <button
                    className={result.entity_id === focusedEntityId ? "is-active" : ""}
                    key={result.entity_id}
                    onClick={() => selectGraphSearchResult(result)}
                    type="button"
                  >
                    <span>{typeLabel(result.type, locale)} · {result.degree}</span>
                    <strong>{result.label}</strong>
                    <code>{result.source_path ?? result.entity_id}</code>
                  </button>
                ))}
                {!graphSearchResults.length && !isGraphSearchLoading && !graphSearchError ? (
                  <p>{String(t.graphSearchHint)}</p>
                ) : null}
              </div>
            ) : null}
          </div>
          <button
            aria-pressed={depth === 2}
            className="secondary-action"
            onClick={() => {
              setDepth((currentDepth) => (currentDepth === 1 ? 2 : 1));
              setSelectedRelationId(null);
            }}
            type="button"
          >
            <GitBranch size={15} />
            {locale === "zh" ? `深度 ${depth}` : `Depth ${depth}`}
          </button>
          <button
            aria-pressed={isLeftOpen}
            className="secondary-action"
            onClick={() => setIsLeftOpen((current) => !current)}
            type="button"
          >
            <PanelLeft size={15} />
            {isLeftOpen ? t.closeDrawer : t.recommendedStarts}
          </button>
          <button
            aria-pressed={isRightOpen}
            className="secondary-action"
            onClick={() => setIsRightOpen((current) => !current)}
            type="button"
          >
            <PanelRight size={15} />
            {isRightOpen ? t.closeDrawer : t.entityDetails}
          </button>
          <button className="secondary-action mission-jump" onClick={onOpenMission} type="button">
            <Sparkles size={15} />
            {missionOverlay ? t.viewMission : t.openAgentMission}
          </button>
          {missionOverlay ? (
            <span className="mission-overlay-pill">
              {t.overlayActive}: {missionOverlay.explored_node_ids.length} / {t.riskOverlay}: {missionOverlay.risk_node_ids.length}
            </span>
          ) : null}
        </div>
      </div>
      <div
        className={`graph-explorer-shell panel ${isLeftOpen ? "has-left" : "is-left-closed"} ${
          isRightOpen ? "has-right" : "is-right-closed"
        }`}
      >
        {isLeftOpen ? (
          <GraphStartsDrawer
            focusedEntityId={focusedEntityId}
            isLoading={isSummaryLoading}
            locale={locale}
            onClose={() => setIsLeftOpen(false)}
            onStartSelect={(entityId) => {
              setFocusedEntityId(entityId);
              setSelectedRelationId(null);
              setIsRightOpen(true);
            }}
            selectedHallId={selectedHallId}
            summary={summary}
          />
        ) : null}
        <GraphExplorerCanvas
          focusedEntityId={focusedEntityId}
          isLoading={isNeighborhoodLoading}
          locale={locale}
          missionOverlay={missionOverlay}
          neighborhood={neighborhood}
          onNodeFocus={(entityId) => {
            setFocusedEntityId(entityId);
            setSelectedRelationId(null);
            setIsRightOpen(true);
          }}
          onRelationSelect={(relationId) => {
            setSelectedRelationId(relationId);
            setIsRightOpen(true);
          }}
          searchMatchedEntityIds={graphSearchMatchedEntityIds}
          selectedRelationId={selectedRelationId}
        />
        {isRightOpen ? (
          <GraphEntityDrawer
            focusedNode={focusedNode}
            locale={locale}
            nodeById={nodeById}
            onClose={() => setIsRightOpen(false)}
            selectedRelation={selectedRelation}
          />
        ) : null}
      </div>
      <div className={`graph-explorer-status ${visibleError ? "is-error" : ""}`} role="status">
        {statusText}
      </div>
    </section>
  );
}

function GraphStartsDrawer({
  focusedEntityId,
  isLoading,
  locale,
  onClose,
  onStartSelect,
  selectedHallId,
  summary,
}: {
  focusedEntityId: string | null;
  isLoading: boolean;
  locale: Locale;
  onClose: () => void;
  onStartSelect: (entityId: string) => void;
  selectedHallId: string | null;
  summary: GraphSummary | null;
}) {
  const t = copy[locale];
  const starts = useMemo(() => {
    const recommendedStarts = summary?.recommended_starts ?? [];
    if (!selectedHallId) return recommendedStarts;
    const hallStarts = recommendedStarts.filter((start) => start.hall_ids.includes(selectedHallId));
    return hallStarts.length ? hallStarts : recommendedStarts;
  }, [selectedHallId, summary]);
  const emptyText = isLoading
    ? locale === "zh"
      ? "正在加载推荐起点..."
      : "Loading recommended starts..."
    : locale === "zh"
      ? "暂无推荐起点。"
      : "No recommended starts yet.";

  return (
    <aside className="graph-drawer graph-drawer-left" aria-label={String(t.recommendedStarts)}>
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{t.graphExplorer}</span>
          <h2>{t.recommendedStarts}</h2>
        </div>
        <button className="icon-button drawer-close-button" onClick={onClose} type="button" title={String(t.closeDrawer)}>
          <PanelLeft size={18} />
        </button>
      </div>
      <div className="graph-start-list">
        {starts.length ? (
          starts.map((start, index) => (
            <button
              className={`graph-start-item ${start.entity_id === focusedEntityId ? "is-active" : ""}`}
              key={`${start.group}-${start.entity_id}-${index}`}
              onClick={() => onStartSelect(start.entity_id)}
              type="button"
            >
              <span className="graph-start-group">{start.group}</span>
              <strong>{start.label}</strong>
              <span>{start.reason}</span>
              <small>
                {formatNumber(Math.round(start.score))} {String(t.graphStartScore)}
              </small>
            </button>
          ))
        ) : (
          <p className="empty-note">{emptyText}</p>
        )}
      </div>
    </aside>
  );
}

function GraphEntityDrawer({
  focusedNode,
  locale,
  nodeById,
  onClose,
  selectedRelation,
}: {
  focusedNode: GraphExplorerNode | null;
  locale: Locale;
  nodeById: Map<string, GraphExplorerNode>;
  onClose: () => void;
  selectedRelation: GraphExplorerRelation | null;
}) {
  const t = copy[locale];
  const sourceNode = selectedRelation ? nodeById.get(selectedRelation.source_id) : null;
  const targetNode = selectedRelation ? nodeById.get(selectedRelation.target_id) : null;
  const emptyText =
    locale === "zh" ? "选择一个节点或关系查看详情。" : "Select a node or relation to inspect details.";
  const sourcePathFallback = locale === "zh" ? "未提供来源路径" : "No source path provided";

  return (
    <aside className="graph-drawer graph-drawer-right" aria-label={String(t.entityDetails)}>
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{t.graphExplorer}</span>
          <h2>{t.entityDetails}</h2>
        </div>
        <button className="icon-button drawer-close-button" onClick={onClose} type="button" title={String(t.closeDrawer)}>
          <PanelRight size={18} />
        </button>
      </div>
      <div className="entity-detail-stack">
        {focusedNode ? (
          <section className="entity-detail-card">
            <span className="entity-label">{t.currentFocus}</span>
            <h3>{focusedNode.label}</h3>
            <div className="entity-meta-grid">
              <span>{locale === "zh" ? "类型" : "Type"}</span>
              <strong>{typeLabel(focusedNode.type, locale)}</strong>
              <span>{locale === "zh" ? "连接数" : "Degree"}</span>
              <strong>{focusedNode.degree}</strong>
              <span>{locale === "zh" ? "重要度" : "Importance"}</span>
              <strong>{Math.round(focusedNode.importance * 100)}%</strong>
              <span>{t.evidenceUsed}</span>
              <strong>{focusedNode.evidence_ids.length}</strong>
            </div>
            <code>{focusedNode.source_path ?? sourcePathFallback}</code>
            {focusedNode.tags.length ? (
              <div className="type-row">
                {focusedNode.tags.slice(0, 6).map((tag) => (
                  <span className="mini-pill" key={tag}>
                    {tag}
                  </span>
                ))}
              </div>
            ) : null}
          </section>
        ) : (
          <p className="empty-note">{emptyText}</p>
        )}
        {selectedRelation ? (
          <section className="entity-detail-card relation-detail">
            <span className="entity-label">{t.relation}</span>
            <h3>{typeLabel(selectedRelation.type, locale)}</h3>
            <div className="relation-path">
              <strong>{sourceNode?.label ?? selectedRelation.source_id}</strong>
              <span>{selectedRelation.type}</span>
              <strong>{targetNode?.label ?? selectedRelation.target_id}</strong>
            </div>
            <div className="entity-meta-grid">
              <span>{locale === "zh" ? "权重" : "Weight"}</span>
              <strong>{selectedRelation.weight}</strong>
              <span>{t.evidenceUsed}</span>
              <strong>{selectedRelation.evidence_ids.length}</strong>
              <span>{locale === "zh" ? "展厅" : "Halls"}</span>
              <strong>{selectedRelation.hall_ids.length}</strong>
            </div>
          </section>
        ) : null}
      </div>
    </aside>
  );
}

function GraphExplorerCanvas({
  focusedEntityId,
  isLoading,
  locale,
  missionOverlay,
  neighborhood,
  onNodeFocus,
  onRelationSelect,
  searchMatchedEntityIds,
  selectedRelationId,
}: {
  focusedEntityId: string | null;
  isLoading: boolean;
  locale: Locale;
  missionOverlay: MissionGraphOverlay | null;
  neighborhood: GraphNeighborhood | null;
  onNodeFocus: (entityId: string) => void;
  onRelationSelect: (relationId: string) => void;
  searchMatchedEntityIds: Set<string>;
  selectedRelationId: string | null;
}) {
  const layout = useMemo(
    () => (neighborhood ? layoutGraph(neighborhood, focusedEntityId) : { nodes: [], relations: [] }),
    [focusedEntityId, neighborhood],
  );
  const handleNodeKeyDown = (event: KeyboardEvent<SVGGElement>, entityId: string) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    onNodeFocus(entityId);
  };
  const handleRelationKeyDown = (event: KeyboardEvent<SVGGElement>, relationId: string) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    onRelationSelect(relationId);
  };

  if (isLoading) {
    return (
      <div className="graph-explorer-canvas">
        <div className="graph-canvas-message">
          <Network size={28} />
          <strong>{locale === "zh" ? "正在加载图谱邻域" : "Loading graph neighborhood"}</strong>
        </div>
      </div>
    );
  }

  if (!neighborhood) {
    return (
      <div className="graph-explorer-canvas">
        <div className="graph-canvas-message">
          <Network size={28} />
          <strong>{locale === "zh" ? "暂无图谱数据" : "No graph data loaded"}</strong>
        </div>
      </div>
    );
  }

  if (neighborhood.is_sparse) {
    const sparseText =
      neighborhood.sparse_reason ??
      (locale === "zh"
        ? "当前筛选下图谱较稀疏，请尝试其他展厅或推荐起点。"
        : "This graph is sparse for the current filters. Try another hall or recommended start.");
    return (
      <div className="graph-explorer-canvas">
        <div className="graph-canvas-message">
          <Network size={28} />
          <strong>{locale === "zh" ? "图谱数据较少" : "Sparse graph"}</strong>
          <span>{sparseText}</span>
        </div>
      </div>
    );
  }

  if (!layout.nodes.length) {
    return (
      <div className="graph-explorer-canvas">
        <div className="graph-canvas-message">
          <Network size={28} />
          <strong>{locale === "zh" ? "没有可展示的节点" : "No visible nodes"}</strong>
        </div>
      </div>
    );
  }

  return (
    <div className="graph-explorer-canvas">
      <svg viewBox="0 0 840 520" role="img" aria-label={locale === "zh" ? "知识图谱邻域" : "Knowledge graph neighborhood"}>
        <defs>
          <marker id="explorerArrow" markerHeight="7" markerWidth="7" orient="auto" refX="6" refY="3.5">
            <path d="M0,0 L7,3.5 L0,7 Z" />
          </marker>
          <marker id="explorerArrowSelected" markerHeight="8" markerWidth="8" orient="auto" refX="7" refY="4">
            <path d="M0,0 L8,4 L0,8 Z" />
          </marker>
        </defs>
        {layout.relations.map((relation) => {
          const isSelected = relation.id === selectedRelationId;
          const isExplored = missionOverlay?.explored_relation_ids.includes(relation.id) ?? false;
          const isRisk = missionOverlay?.risk_relation_ids.includes(relation.id) ?? false;
          const relationLabel = `${relation.sourceLabel} ${relation.type} ${relation.targetLabel}`;
          return (
            <g
              aria-label={relationLabel}
              className={`explorer-edge-hit ${isSelected ? "is-selected" : ""}`}
              key={relation.id}
              onClick={() => onRelationSelect(relation.id)}
              onKeyDown={(event) => handleRelationKeyDown(event, relation.id)}
              role="button"
              tabIndex={0}
            >
              <line className="explorer-edge-target" x1={relation.x1} x2={relation.x2} y1={relation.y1} y2={relation.y2} />
              <line
                className={`explorer-edge ${relation.isFocusEdge ? "is-focus-edge" : ""} ${
                  isSelected ? "is-selected" : ""
                } ${relation.isDimmed ? "is-dimmed" : ""} ${isExplored ? "is-agent-explored" : ""} ${
                  isRisk ? "is-agent-risk" : ""
                }`}
                markerEnd={isSelected ? "url(#explorerArrowSelected)" : "url(#explorerArrow)"}
                x1={relation.x1}
                x2={relation.x2}
                y1={relation.y1}
                y2={relation.y2}
              />
              <title>{relationLabel}</title>
            </g>
          );
        })}
        {layout.nodes.map((node) => {
          const isExplored = missionOverlay?.explored_node_ids.includes(node.id) ?? false;
          const isRisk = missionOverlay?.risk_node_ids.includes(node.id) ?? false;
          const isSearchMatch = searchMatchedEntityIds.has(node.id);
          return (
            <g
              aria-label={node.label}
              className={`explorer-node ${node.tone} ${node.isFocused ? "is-focused" : ""} ${
                node.isDimmed ? "is-dimmed" : ""
              } ${isSearchMatch ? "is-search-match" : ""} ${isExplored ? "is-agent-explored" : ""} ${isRisk ? "is-agent-risk" : ""}`}
              key={node.id}
              onClick={() => onNodeFocus(node.id)}
              onKeyDown={(event) => handleNodeKeyDown(event, node.id)}
              role="button"
              tabIndex={0}
            >
              <title>{node.label}</title>
              <circle className="node-glow" cx={node.x} cy={node.y} r={node.isFocused ? 54 : 42} />
              <circle cx={node.x} cy={node.y} r={node.isFocused ? 20 : 15} />
              {isRisk ? <circle className="risk-ring" cx={node.x} cy={node.y} r={node.isFocused ? 28 : 23} /> : null}
              <text textAnchor="middle" x={node.x} y={node.y + (node.isFocused ? 42 : 35)}>
                {compactGraphLabel(node.label, 26)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

type ExplorerLayoutNode = GraphExplorerNode & {
  x: number;
  y: number;
  tone: GraphTone;
  isFocused: boolean;
  isDimmed: boolean;
};

type ExplorerLayoutRelation = GraphExplorerRelation & {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  sourceLabel: string;
  targetLabel: string;
  isFocusEdge: boolean;
  isDimmed: boolean;
};

function layoutGraph(
  neighborhood: GraphNeighborhood,
  focusedEntityId: string | null,
): { nodes: ExplorerLayoutNode[]; relations: ExplorerLayoutRelation[] } {
  const centerX = 420;
  const centerY = 260;
  const sourceNodes = Array.from(new Map(neighborhood.nodes.map((node) => [node.id, node])).values());
  if (!sourceNodes.length) return { nodes: [], relations: [] };

  const nodeIds = new Set(sourceNodes.map((node) => node.id));
  const visibleRelations = Array.from(
    new Map(
      neighborhood.relations
        .filter((relation) => nodeIds.has(relation.source_id) && nodeIds.has(relation.target_id))
        .map((relation) => [relation.id, relation]),
    ).values(),
  );
  const requestedFocus = focusedEntityId && nodeIds.has(focusedEntityId) ? focusedEntityId : null;
  const centerNodeId = requestedFocus ?? sourceNodes[0].id;
  const focusEdgeIds = new Set<string>();
  const focusConnectedIds = new Set<string>();
  visibleRelations.forEach((relation) => {
    if (requestedFocus && (relation.source_id === centerNodeId || relation.target_id === centerNodeId)) {
      focusEdgeIds.add(relation.id);
      focusConnectedIds.add(relation.source_id === centerNodeId ? relation.target_id : relation.source_id);
    }
  });

  const orderedNodes = [...sourceNodes].sort((left, right) => {
    if (left.id === centerNodeId) return -1;
    if (right.id === centerNodeId) return 1;
    const leftConnected = focusConnectedIds.has(left.id) ? 0 : 1;
    const rightConnected = focusConnectedIds.has(right.id) ? 0 : 1;
    if (leftConnected !== rightConnected) return leftConnected - rightConnected;
    return right.importance - left.importance;
  });
  const outerNodes = orderedNodes.filter((node) => node.id !== centerNodeId);
  const positionedNodes = new Map<string, ExplorerLayoutNode>();

  orderedNodes.forEach((node, index) => {
    const isCenter = node.id === centerNodeId;
    const outerIndex = Math.max(0, index - 1);
    const outerCount = Math.max(outerNodes.length, 1);
    const connected = focusConnectedIds.has(node.id);
    const angle = -Math.PI / 2 + (outerIndex / outerCount) * Math.PI * 2 + (outerCount > 14 ? (outerIndex % 2) * 0.1 : 0);
    const radiusX = connected || !requestedFocus ? 255 : 315;
    const radiusY = connected || !requestedFocus ? 155 : 205;
    const x = isCenter ? centerX : centerX + Math.cos(angle) * radiusX;
    const y = isCenter ? centerY : centerY + Math.sin(angle) * radiusY;
    positionedNodes.set(node.id, {
      ...node,
      x: Math.min(790, Math.max(50, x)),
      y: Math.min(475, Math.max(55, y)),
      tone: isCenter ? "accent" : graphToneCycle[index % graphToneCycle.length],
      isFocused: Boolean(requestedFocus && isCenter),
      isDimmed: Boolean(requestedFocus && !isCenter && !connected),
    });
  });

  const nodes = Array.from(positionedNodes.values());
  const relations = visibleRelations
    .map((relation) => {
      const source = positionedNodes.get(relation.source_id);
      const target = positionedNodes.get(relation.target_id);
      if (!source || !target) return null;
      const isFocusEdge = focusEdgeIds.has(relation.id);
      return {
        ...relation,
        x1: source.x,
        y1: source.y,
        x2: target.x,
        y2: target.y,
        sourceLabel: source.label,
        targetLabel: target.label,
        isFocusEdge,
        isDimmed: Boolean(requestedFocus && !isFocusEdge),
      };
    })
    .filter((relation): relation is ExplorerLayoutRelation => Boolean(relation));

  return { nodes, relations };
}

function AgentPipelinePanel({
  jobMessage,
  jobProgress,
  isRunning,
  locale,
  onRun,
  report,
}: {
  jobMessage: string;
  jobProgress: number;
  isRunning: boolean;
  locale: Locale;
  onRun: () => void;
  report: ProjectAgentReport | null;
}) {
  const t = copy[locale];
  const curator = report?.agents.curator;
  return (
    <section className="agent-pipeline" aria-label="Agent pipeline">
      <div className="agent-pipeline-head">
        <div>
          <span className="eyebrow">{t.agentPipeline}</span>
          <strong>
            {report
              ? `${report.provider}${report.model ? ` · ${report.model}` : ""}`
              : t.deterministicSource}
          </strong>
        </div>
        <div className="pipeline-actions">
          {report ? <span className="pipeline-status">{statusLabel(report.status, locale)}</span> : null}
          <button className="ghost-button compact" disabled={isRunning} onClick={onRun} type="button">
            <Sparkles size={14} />
            {isRunning ? t.agentReportRunning : t.rerunAnalysis}
          </button>
        </div>
        {isRunning ? (
          <div className="pipeline-progress">
            <div>
              <span>{jobMessage || String(t.jobProgress)}</span>
              <strong>{jobProgress}%</strong>
            </div>
            <progress max="100" value={jobProgress} />
          </div>
        ) : null}
      </div>
      <div className="agent-steps">
        {agentRoleOrder.map((role) => {
          const result = report?.agents[role];
          return (
            <div className={`agent-step ${result?.status ?? "pending"}`} key={role}>
              <span>{agentRoleLabels[locale][role]}</span>
              <strong>{statusLabel(result?.status ?? "pending", locale)}</strong>
            </div>
          );
        })}
      </div>
      <div className="curator-summary">
        <span>{t.curatorSummary}</span>
        <p>{curator?.summary ?? String(t.noAgentReport)}</p>
        {curator?.next_actions?.length ? (
          <ul>
            {curator.next_actions.slice(0, 3).map((action) => (
              <li key={action}>{action}</li>
            ))}
          </ul>
        ) : null}
      </div>
    </section>
  );
}

const agentDisplayStatus = (result: ProjectAgentReport["agents"][string] | undefined, locale: Locale) => {
  const t = copy[locale];
  if (!result) return String(t.pending);
  const llm = result.metadata?.llm;
  if (llm?.enabled && !llm.fallback) return String(t.modelEnhanced);
  if (llm?.fallback) return String(t.modelFallback);
  return String(t.ruleCompleted);
};

function ModelStatusPanel({
  agentStatus,
  hybridRagStatus,
  locale,
  report,
}: {
  agentStatus: AgentStatus | null;
  hybridRagStatus: HybridRagStatus | null;
  locale: Locale;
  report: ProjectAgentReport | null;
}) {
  const t = copy[locale];
  return (
    <section className="agent-side-panel">
      <div className="panel-title">
        <ShieldCheck size={16} />
        {t.modelStatus}
      </div>
      <div className="model-grid">
        <span>{t.llmSource}</span>
        <strong>
          {agentStatus?.llm_enabled
            ? `${agentStatus.provider} · ${agentStatus.model ?? "model"}`
            : t.deterministicSource}
        </strong>
        <span>{t.agentPipeline}</span>
        <strong>{report ? statusLabel(report.status, locale) : t.pending}</strong>
        <span>{t.scope}</span>
        <strong>{report?.scan_profile ?? "architecture"}</strong>
        <span>{t.hybridRag}</span>
        <strong>
          {hybridRagStatus
            ? `${formatNumber(hybridRagStatus.indexed_chunks)} chunks · ${hybridRagStatus.dense_provider}`
            : t.pending}
        </strong>
        <span>{t.multimodal}</span>
        <strong>
          {hybridRagStatus
            ? `${formatNumber(hybridRagStatus.image_chunks)} image chunks · ${
                hybridRagStatus.vision_enabled ? hybridRagStatus.vision_provider : t.fallback
              }`
            : t.pending}
        </strong>
      </div>
    </section>
  );
}

function AgentWorkProofPanel({
  locale,
  report,
}: {
  locale: Locale;
  report: ProjectAgentReport | null;
}) {
  const t = copy[locale];
  return (
    <section className="agent-proof panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{t.agentProof}</span>
          <h2>{t.agentPage}</h2>
        </div>
        <Sparkles size={18} />
      </div>
      <div className="agent-proof-list">
        {agentRoleOrder.map((role) => {
          const result = report?.agents[role];
          const llm = result?.metadata?.llm;
          const agentSdk = result?.metadata?.agent_sdk;
          const llmError = typeof llm === "object" && llm && "error" in llm ? String((llm as Record<string, unknown>).error) : "";
          return (
            <article className="agent-proof-card" key={role}>
              <div className="agent-proof-head">
                <div>
                  <span className="eyebrow">{agentRoleLabels[locale][role]}</span>
                  <h3>{agentDisplayStatus(result, locale)}</h3>
                </div>
                <span className={`pipeline-status ${result?.status ?? "pending"}`}>
                  {statusLabel(result?.status ?? "pending", locale)}
                </span>
              </div>
              <p>{result?.summary ?? String(t.noAgentReport)}</p>
              <div className="proof-metrics">
                <span>{t.evidenceUsed}: {result?.evidence_card_ids.length ?? 0}</span>
                <span>{t.entitiesUsed}: {result?.entity_ids.length ?? 0}</span>
                <span>{t.relationsUsed}: {result?.relation_ids.length ?? 0}</span>
                <span>{t.confidence}: {Math.round((result?.confidence ?? 0) * 100)}%</span>
                {agentSdk?.tools?.length ? <span>{t.toolsUsed}: {agentSdk.tools.length}</span> : null}
                {agentSdk?.validation?.status ? <span>{t.validation}: {agentSdk.validation.status}</span> : null}
              </div>
              {agentSdk?.work_log?.length ? (
                <div className="proof-block">
                  <strong>{t.workLog}</strong>
                  <ul>
                    {agentSdk.work_log.slice(0, 3).map((item, index) => (
                      <li key={`${role}-work-${index}`}>{String(item.detail ?? item.step ?? "")}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {result?.findings.length ? (
                <div className="proof-block">
                  <strong>{t.findings}</strong>
                  <ul>
                    {result.findings.slice(0, 3).map((finding, index) => (
                      <li key={`${role}-finding-${index}`}>{String(finding.title ?? finding.detail ?? JSON.stringify(finding))}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {result?.risks.length ? (
                <div className="proof-block">
                  <strong>{t.risks}</strong>
                  <ul>
                    {result.risks.slice(0, 3).map((risk, index) => (
                      <li key={`${role}-risk-${index}`}>{String(risk.title ?? risk.detail ?? JSON.stringify(risk))}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {llmError ? <code className="proof-error">{llmError}</code> : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function TaskHistoryPanel({
  history,
  locale,
}: {
  history: JobHistoryItem[];
  locale: Locale;
}) {
  const t = copy[locale];
  return (
    <section className="agent-side-panel">
      <div className="panel-title">
        <Command size={16} />
        {t.taskHistory}
      </div>
      {history.length ? (
        <div className="task-history">
          {history.slice(-8).reverse().map((item) => (
            <div className="task-history-item" key={item.id}>
              <span>{item.label}</span>
              <strong>{item.progress}%</strong>
              <p>{item.message}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="empty-note">{t.noTaskHistory}</p>
      )}
    </section>
  );
}

function ReactAgentMissionPanel({
  error,
  isStarting,
  locale,
  mission,
  onAction,
  onStart,
  trace,
}: {
  error: string;
  isStarting: boolean;
  locale: Locale;
  mission: AgentMission | null;
  onAction: (action: "pause" | "resume" | "stop") => void;
  onStart: () => void;
  trace: AgentTraceEvent[];
}) {
  const t = copy[locale];
  const completedCount = mission?.tasks.filter((task) => ["completed", "complete"].includes(task.status)).length ?? 0;
  const terminal = isMissionTerminal(mission);
  const canStop = Boolean(mission && !terminal && !isStarting);
  const statusText = mission
    ? missionStatusLabel(mission.status, locale)
    : locale === "zh"
      ? "未启动"
      : "Not started";
  const traceEvents = trace.length ? trace : mission?.trace_events ?? [];
  const verifierStatus = mission?.verifier_result?.status
    ? missionStatusLabel(mission.verifier_result.status, locale)
    : locale === "zh"
      ? "未校验"
      : "Not verified";

  return (
    <section className="react-agent-panel panel" aria-label={locale === "zh" ? "ReAct Agent 任务" : "ReAct Agent mission"}>
      <div className="mission-control-head">
        <div>
          <span className="eyebrow">{locale === "zh" ? "Graph-grounded ReAct" : "Graph-grounded ReAct"}</span>
          <h2>{locale === "zh" ? "Agent 任务追踪" : "Agent mission trace"}</h2>
        </div>
        <div className="mission-actions">
          <span className={`pipeline-status ${mission?.status ?? "pending"}`}>{statusText}</span>
          <button className="primary-button compact" disabled={isStarting} onClick={onStart} type="button">
            <Sparkles size={14} />
            {isStarting ? t.missionStarting : locale === "zh" ? "启动 ReAct" : "Start ReAct"}
          </button>
          <button className="secondary-action compact danger" disabled={!canStop} onClick={() => onAction("stop")} type="button">
            <X size={14} />
            {t.stopMission}
          </button>
        </div>
      </div>
      {error ? (
        <div className="mission-error" role="alert">
          <strong>{t.missionError}</strong>
          <span>{error}</span>
        </div>
      ) : null}
      {mission ? (
        <>
          <div className="mission-meta-grid react-plan-grid">
            <span>{t.missionId}</span>
            <strong>{mission.id}</strong>
            <span>{t.missionGoal}</span>
            <strong>{mission.goal}</strong>
            <span>{locale === "zh" ? "任务预算" : "Task budget"}</span>
            <strong>{completedCount} / {mission.budget.max_tasks}</strong>
            <span>{t.maxSteps}</span>
            <strong>{mission.budget.max_steps_per_task}</strong>
            <span>{t.toolsUsed}</span>
            <strong>{mission.budget.max_tool_calls}</strong>
            <span>{t.validation}</span>
            <strong>{verifierStatus}</strong>
          </div>
          <div className="mission-task-list">
            {mission.tasks.length ? (
              mission.tasks.map((task) => (
                <article className={`mission-task ${task.status}`} key={task.id}>
                  <div className="mission-task-head">
                    <div>
                      <span className="eyebrow">{task.task_type}</span>
                      <h3>{task.objective}</h3>
                    </div>
                    <span className={`pipeline-status ${task.status}`}>{missionStatusLabel(task.status, locale)}</span>
                  </div>
                  <div className="mission-task-metrics">
                    <span>{locale === "zh" ? "步骤" : "Steps"}: {task.steps_used} / {task.max_steps}</span>
                    <span>{t.toolsUsed}: {task.allowed_tools.length}</span>
                    <span>{t.evidenceUsed}: {task.evidence_ids.length}</span>
                    <span>{t.entitiesUsed}: {task.output_entity_ids.length || task.input_entity_ids.length}</span>
                    <span>{t.confidence}: {Math.round(task.confidence * 100)}%</span>
                  </div>
                  <div className="mission-task-notes">
                    <p><strong>{t.findings}</strong> {summarizeMissionItems(task.findings, locale)}</p>
                    <p><strong>{t.risks}</strong> {summarizeMissionItems(task.risks, locale)}</p>
                  </div>
                </article>
              ))
            ) : (
              <p className="empty-note">{locale === "zh" ? "任务已创建，尚无计划记录。" : "Mission created, but no task plan records yet."}</p>
            )}
          </div>
          <div className="mission-timeline-head">
            <strong>{locale === "zh" ? "工具时间线" : "Tool timeline"}</strong>
            <span>{traceEvents.length} {locale === "zh" ? "条事件" : "events"}</span>
          </div>
          <div className="react-trace-list">
            {traceEvents.length ? (
              traceEvents.map((event) => (
                <article className={`react-trace-event ${event.event_type}`} key={event.id}>
                  <div>
                    <span className="eyebrow">#{event.sequence} · {event.event_type}</span>
                    <strong>{event.tool_name || (locale === "zh" ? "无工具调用" : "No tool call")}</strong>
                  </div>
                  <p>{event.observation_summary || (locale === "zh" ? "无观察摘要" : "No observation summary")}</p>
                  <div className="mission-task-metrics">
                    <span>{t.evidenceUsed}: {event.evidence_ids.length}</span>
                    <span>{t.entitiesUsed}: {event.entity_ids.length}</span>
                    <span>{t.relationsUsed}: {event.relation_ids.length}</span>
                    {event.error ? <span>{locale === "zh" ? "错误" : "Error"}: {event.error}</span> : null}
                  </div>
                </article>
              ))
            ) : (
              <p className="empty-note">{locale === "zh" ? "暂无工具事件。" : "No tool events yet."}</p>
            )}
          </div>
          {mission.final_report ? (
            <div className="react-final-report">
              <div>
                <span className="eyebrow">{locale === "zh" ? "最终报告" : "Final report"}</span>
                <strong>{t.confidence}: {Math.round(mission.final_report.confidence * 100)}%</strong>
              </div>
              <p>{mission.final_report.summary}</p>
              <div className="mission-task-metrics">
                <span>{t.findings}: {mission.final_report.findings.length}</span>
                <span>{t.evidenceUsed}: {mission.final_report.evidence_ids.length}</span>
              </div>
            </div>
          ) : null}
        </>
      ) : (
        <p className="empty-note mission-empty">
          {locale === "zh"
            ? "还没有 ReAct Agent 任务。启动后会显示任务卡、工具调用摘要和最终报告。"
            : "No ReAct Agent mission yet. Start one to see task cards, tool-call summaries, and the final report."}
        </p>
      )}
    </section>
  );
}

function MissionControlPanel({
  error,
  locale,
  mission,
  missionAction,
  onPause,
  onResume,
  onStart,
  onStop,
}: {
  error: string;
  locale: Locale;
  mission: AutonomousMission | null;
  missionAction: MissionAction;
  onPause: () => void;
  onResume: () => void;
  onStart: () => void;
  onStop: () => void;
}) {
  const t = copy[locale];
  const isBusy = Boolean(missionAction);
  const completedCount = mission?.tasks.filter((task) => ["completed", "complete"].includes(task.status)).length ?? 0;
  const terminal = isMissionTerminal(mission);
  const canPause = Boolean(mission && !terminal && mission.status !== "paused" && !isBusy);
  const canResume = Boolean(mission && mission.status === "paused" && !isBusy);
  const canStop = Boolean(mission && !terminal && !isBusy);
  const statusText = mission
    ? missionStatusLabel(mission.status, locale)
    : locale === "zh"
      ? "未启动"
      : "Not started";

  return (
    <section className="mission-control panel" aria-label={String(t.autonomousMission)}>
      <div className="mission-control-head">
        <div>
          <span className="eyebrow">{t.autonomousMission}</span>
          <h2>{t.agentPage}</h2>
        </div>
        <div className="mission-actions">
          <span className={`pipeline-status ${mission?.status ?? "pending"}`}>{statusText}</span>
          <button className="primary-button compact" disabled={isBusy} onClick={onStart} type="button">
            <Sparkles size={14} />
            {missionAction === "start" ? t.missionStarting : t.startMission}
          </button>
          <button className="secondary-action compact" disabled={!canPause} onClick={onPause} type="button">
            <CircleDot size={14} />
            {missionAction === "pause" ? t.missionPausing : t.pauseMission}
          </button>
          <button className="secondary-action compact" disabled={!canResume} onClick={onResume} type="button">
            <Sparkles size={14} />
            {missionAction === "resume" ? t.missionResuming : t.resumeMission}
          </button>
          <button className="secondary-action compact danger" disabled={!canStop} onClick={onStop} type="button">
            <X size={14} />
            {missionAction === "stop" ? t.missionStopping : t.stopMission}
          </button>
        </div>
      </div>
      {error ? (
        <div className="mission-error" role="alert">
          <strong>{t.missionError}</strong>
          <span>{error}</span>
        </div>
      ) : null}
      {mission ? (
        <>
          <div className="mission-meta-grid">
            <span>{t.missionId}</span>
            <strong>{mission.id}</strong>
            <span>{t.missionGoal}</span>
            <strong>{mission.goal}</strong>
            <span>{t.stopReason}</span>
            <strong>{mission.stop_reason || (locale === "zh" ? "未提供" : "Not provided")}</strong>
            <span>{t.maxSteps}</span>
            <strong>{mission.max_steps}</strong>
            <span>{t.completedTasks}</span>
            <strong>{completedCount} / {mission.tasks.length}</strong>
          </div>
          <div className="mission-timeline-head">
            <strong>{t.missionTimeline}</strong>
            <span>{mission.graph_overlay ? `${t.overlayActive}: ${mission.graph_overlay.explored_node_ids.length}` : ""}</span>
          </div>
          <div className="mission-task-list">
            {mission.tasks.length ? (
              mission.tasks.map((task) => (
                <MissionTaskCard key={task.id} locale={locale} task={task} />
              ))
            ) : (
              <p className="empty-note">{locale === "zh" ? "任务已创建，尚无队列记录。" : "Mission created, but no task records yet."}</p>
            )}
          </div>
        </>
      ) : (
        <p className="empty-note mission-empty">{t.noMission}</p>
      )}
    </section>
  );
}

function MissionTaskCard({ locale, task }: { locale: Locale; task: MissionTask }) {
  const t = copy[locale];
  return (
    <article className={`mission-task ${task.status}`}>
      <div className="mission-task-head">
        <div>
          <span className="eyebrow">{task.agent} · {task.task_type}</span>
          <h3>{task.title}</h3>
        </div>
        <span className={`pipeline-status ${task.status}`}>{missionStatusLabel(task.status, locale)}</span>
      </div>
      <div className="mission-task-metrics">
        <span>{locale === "zh" ? "校验" : "Verifier"}: {missionStatusLabel(task.verifier_status, locale)}</span>
        <span>{t.confidence}: {Math.round(task.confidence * 100)}%</span>
        <span>{t.evidenceUsed}: {task.evidence_ids.length}</span>
        <span>{t.entitiesUsed}: {task.input_entity_ids.length}</span>
      </div>
      <div className="mission-task-notes">
        <p><strong>{t.findings}</strong> {summarizeMissionItems(task.findings, locale)}</p>
        <p><strong>{t.risks}</strong> {summarizeMissionItems(task.risks, locale)}</p>
      </div>
    </article>
  );
}

export function App() {
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [archiveDraft, setArchiveDraft] = useState<ArchiveDraft | null>(null);
  const [agentReport, setAgentReport] = useState<ProjectAgentReport | null>(null);
  const [hybridRagStatus, setHybridRagStatus] = useState<HybridRagStatus | null>(null);
  const [mission, setMission] = useState<AutonomousMission | null>(null);
  const [reactMission, setReactMission] = useState<AgentMission | null>(null);
  const [reactTrace, setReactTrace] = useState<AgentTraceEvent[]>([]);
  const [reactMissionError, setReactMissionError] = useState("");
  const [isStartingReactMission, setIsStartingReactMission] = useState(false);
  const [missionOverlay, setMissionOverlay] = useState<MissionGraphOverlay | null>(null);
  const [missionError, setMissionError] = useState("");
  const [missionAction, setMissionAction] = useState<MissionAction>(null);
  const [archiveIds, setArchiveIds] = useState<string[]>([]);
  const [isFallbackArchive, setIsFallbackArchive] = useState(false);
  const [isLoadingArchive, setIsLoadingArchive] = useState(true);
  const [isSwitchingArchive, setIsSwitchingArchive] = useState(false);
  const [selectedHallId, setSelectedHallId] = useState("");
  const [selectedArchiveId, setSelectedArchiveId] = useState("");
  const [locale, setLocale] = useState<Locale>("zh");
  const [activePage, setActivePage] = useState<AppPage>("overview");
  const [queryMode] = useState<ScopeMode>("architecture_tour");
  const [scanProfile, setScanProfile] = useState<ScanProfile>("architecture");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedFileName, setSelectedFileName] = useState("");
  const [isCreatingArchive, setIsCreatingArchive] = useState(false);
  const [isRunningAgentReport, setIsRunningAgentReport] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadProgressMessage, setUploadProgressMessage] = useState("");
  const [agentJobProgress, setAgentJobProgress] = useState(0);
  const [agentJobMessage, setAgentJobMessage] = useState("");
  const [jobHistoryByProjectId, setJobHistoryByProjectId] = useState<JobHistoryByProjectId>({});
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearchVisible, setIsSearchVisible] = useState(false);
  const [isGraphHintVisible, setIsGraphHintVisible] = useState(false);
  const [selectedRelationId, setSelectedRelationId] = useState("");
  const [selectedEvidenceId, setSelectedEvidenceId] = useState("");
  const [notice, setNotice] = useState("");
  const activeProjectIdRef = useRef("");
  const activeMissionIdRef = useRef<string | null>(null);
  const missionActionRef = useRef<MissionAction>(null);
  const missionActionTokenRef = useRef(0);
  const reactMissionRequestTokenRef = useRef(0);

  useEffect(() => {
    activeProjectIdRef.current = archiveDraft?.projectId ?? "";
  }, [archiveDraft?.projectId]);

  useEffect(() => {
    activeMissionIdRef.current = mission?.id ?? null;
  }, [mission?.id]);

  useEffect(() => {
    let isMounted = true;

    fetchArchiveDraft().then(({ archiveIds: nextArchiveIds }) => {
      if (!isMounted) return;
      setArchiveIds(nextArchiveIds);
      setArchiveDraft(null);
      setSelectedArchiveId("");
      setSelectedHallId("");
      setIsFallbackArchive(false);
      setIsLoadingArchive(false);
      setAgentReport(null);
      setHybridRagStatus(null);
      reactMissionRequestTokenRef.current += 1;
      setReactMission(null);
      setReactTrace([]);
      setReactMissionError("");
      setIsStartingReactMission(false);
    });

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    fetchAgentStatus()
      .then((status) => {
        if (isMounted) setAgentStatus(status);
      })
      .catch(() => {
        if (isMounted) {
          setAgentStatus({
            llm_enabled: false,
            provider: "rules",
            mode: "deterministic",
            model: null,
          });
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const selectedHall = useMemo(
    () => archiveDraft?.halls.find((hall) => hall.id === selectedHallId) ?? archiveDraft?.halls[0] ?? null,
    [archiveDraft?.halls, selectedHallId],
  );
  const currentJobHistory = jobHistoryByProjectId[archiveDraft?.projectId ?? selectedArchiveId] ?? [];

  const notify = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 3200);
  };

  const recordJobProgress = (
    label: string,
    progress: number,
    message: string,
    projectId = activeProjectIdRef.current,
  ) => {
    setJobHistoryByProjectId((historyByProject) => {
      const current = historyByProject[projectId] ?? [];
      const last = current[current.length - 1];
      const nextItem = {
        id: `${Date.now()}-${label}-${progress}`,
        label,
        progress,
        message,
      };

      if (last?.label === label && last.progress === progress && last.message === message) {
        return historyByProject;
      }

      if (last?.label === label && last.progress < 100 && progress < 100) {
        return {
          ...historyByProject,
          [projectId]: [...current.slice(0, -1), nextItem],
        };
      }

      return {
        ...historyByProject,
        [projectId]: [...current.slice(-20), nextItem],
      };
    });
  };

  const resetArchiveView = (draft: ArchiveDraft, report: ProjectAgentReport | null = null) => {
    activeProjectIdRef.current = draft.projectId;
    activeMissionIdRef.current = null;
    missionActionTokenRef.current += 1;
    missionActionRef.current = null;
    reactMissionRequestTokenRef.current += 1;
    setArchiveDraft(draft);
    setAgentReport(report);
    fetchHybridRagStatus(draft.projectId)
      .then(setHybridRagStatus)
      .catch(() => setHybridRagStatus(null));
    setMission(null);
    setReactMission(null);
    setReactTrace([]);
    setReactMissionError("");
    setIsStartingReactMission(false);
    setMissionOverlay(null);
    setMissionError("");
    setMissionAction(null);
    setSelectedArchiveId(draft.projectId);
    setSelectedHallId(draft.halls[0]?.id ?? "");
    setSelectedRelationId("");
    setSelectedEvidenceId("");
    setSearchQuery("");
  };

  const handleArchiveChange = async (projectId: string) => {
    if (!projectId) {
      resetArchiveSelection();
      return;
    }
    if (projectId === archiveDraft?.projectId) return;
    setIsSwitchingArchive(true);
    try {
      const draft = await fetchProjectArchive(projectId);
      const report = await fetchProjectAgentReport(projectId).catch(() => null);
      resetArchiveView(draft, report);
      setIsFallbackArchive(false);
      notify(`${copy[locale].archiveSwitched}: ${draft.projectId}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(copy[locale].archiveSwitchFailed);
      notify(`${copy[locale].archiveSwitchFailed}: ${message}`);
    } finally {
      setIsSwitchingArchive(false);
    }
  };

  const resetArchiveSelection = () => {
    activeProjectIdRef.current = "";
    activeMissionIdRef.current = null;
    missionActionTokenRef.current += 1;
    missionActionRef.current = null;
    reactMissionRequestTokenRef.current += 1;
    setArchiveDraft(null);
    setAgentReport(null);
    setHybridRagStatus(null);
    setMission(null);
    setReactMission(null);
    setReactTrace([]);
    setReactMissionError("");
    setIsStartingReactMission(false);
    setMissionOverlay(null);
    setMissionError("");
    setMissionAction(null);
    setSelectedArchiveId("");
    setSelectedHallId("");
    setSelectedRelationId("");
    setSelectedEvidenceId("");
    setSearchQuery("");
    setIsSearchVisible(false);
    setIsFallbackArchive(false);
  };

  const handleCreateArchive = async () => {
    document.getElementById("project-intake")?.scrollIntoView({ behavior: "smooth", block: "center" });
    if (!selectedFile) {
      notify(String(copy[locale].createNeedsZip));
      return;
    }

    setIsCreatingArchive(true);
    setUploadProgress(2);
    setUploadProgressMessage(String(copy[locale].createPending));
    notify(String(copy[locale].createPending));
    try {
      const { draft } = await uploadProjectArchive(
        selectedFile,
        scanProfile,
        (progress, message, projectId) => {
          setUploadProgress(progress);
          setUploadProgressMessage(message);
          recordJobProgress(
            String(copy[locale].createArchive),
            progress,
            message,
            projectId ?? activeProjectIdRef.current,
          );
        },
      );
      resetArchiveView(draft, null);
      setArchiveIds((currentIds) =>
        currentIds.includes(draft.projectId) ? currentIds : [...currentIds, draft.projectId].sort(),
      );
      setIsFallbackArchive(false);
      setSelectedFile(null);
      setSelectedFileName("");
      notify(`${copy[locale].archiveCreated}: ${draft.projectId}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(copy[locale].uploadFailed);
      notify(`${copy[locale].uploadFailed}: ${message}`);
    } finally {
      setIsCreatingArchive(false);
      window.setTimeout(() => {
        setUploadProgress(0);
        setUploadProgressMessage("");
      }, 1200);
    }
  };

  const handleSearchGraph = () => {
    if (!archiveDraft) {
      setActivePage("overview");
      notify(String(copy[locale].noArchiveSelected));
      return;
    }
    setActivePage("overview");
    setIsSearchVisible(true);
    window.setTimeout(() => {
      document.querySelector<HTMLInputElement>(".graph-search input")?.focus();
    }, 0);
    notify(String(copy[locale].searchOpened));
  };

  const handleRunAgentReport = async () => {
    if (!archiveDraft) {
      notify(String(copy[locale].noArchiveSelected));
      return;
    }
    const projectId = archiveDraft.projectId;
    setIsRunningAgentReport(true);
    setAgentJobProgress(1);
    setAgentJobMessage(String(copy[locale].agentReportRunning));
    notify(String(copy[locale].agentReportRunning));
    try {
      const report = await runProjectAgentReportJob(
        projectId,
        scanProfile,
        (progress, message, projectId) => {
          setAgentJobProgress(progress);
          setAgentJobMessage(message);
          recordJobProgress(
            String(copy[locale].rerunAnalysis),
            progress,
            message,
            projectId ?? activeProjectIdRef.current,
          );
        },
      );
      setAgentReport(report);
      notify(String(copy[locale].reportReady));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(copy[locale].reportFailed);
      notify(`${copy[locale].reportFailed}: ${message}`);
    } finally {
      setIsRunningAgentReport(false);
      window.setTimeout(() => {
        setAgentJobProgress(0);
        setAgentJobMessage("");
      }, 1200);
    }
  };

  const handleStartReactMission = async () => {
    if (!archiveDraft || isStartingReactMission) return;
    const projectId = archiveDraft.projectId;
    const token = reactMissionRequestTokenRef.current + 1;
    reactMissionRequestTokenRef.current = token;
    const isCurrentReactRequest = () =>
      reactMissionRequestTokenRef.current === token && activeProjectIdRef.current === projectId;
    setIsStartingReactMission(true);
    setReactMissionError("");
    try {
      const nextMission = await startAgentMission(projectId, {
        goal: "Understand project architecture with graph-grounded evidence",
        max_tasks: 5,
        max_steps_per_task: 4,
      });
      if (!isCurrentReactRequest()) return;
      setReactMission(nextMission);
      setReactTrace(nextMission.trace_events);

      let latestMission = nextMission;
      for (let attempt = 0; attempt < 10; attempt += 1) {
        if (attempt > 0) await wait(500);
        if (!isCurrentReactRequest()) return;
        const [polledMission, latestTrace] = await Promise.all([
          fetchAgentMission(nextMission.id),
          fetchAgentMissionTrace(nextMission.id),
        ]);
        if (!isCurrentReactRequest()) return;
        latestMission = polledMission;
        setReactMission(polledMission);
        setReactTrace(latestTrace);
        if (isMissionTerminal(polledMission)) break;
      }

      if (!isCurrentReactRequest()) return;
      if (isMissionTerminal(latestMission)) {
        notify(locale === "zh" ? "ReAct Agent 任务已完成" : "ReAct Agent mission complete");
      }
    } catch (error) {
      if (!isCurrentReactRequest()) return;
      const message = error instanceof Error ? error.message : String(error);
      setReactMissionError(message);
      notify(`${copy[locale].missionError}: ${message}`);
    } finally {
      if (isCurrentReactRequest()) setIsStartingReactMission(false);
    }
  };

  const handleReactMissionAction = async (action: "pause" | "resume" | "stop") => {
    if (!reactMission) return;
    const projectId = reactMission.project_id;
    setReactMissionError("");
    try {
      const updated = await updateAgentMissionStatus(reactMission.id, action);
      if (activeProjectIdRef.current !== projectId) return;
      setReactMission(updated);
      setReactTrace(updated.trace_events);
    } catch (error) {
      if (activeProjectIdRef.current !== projectId) return;
      const message = error instanceof Error ? error.message : String(error);
      setReactMissionError(message);
    }
  };

  const refreshMissionOverlay = async (nextMission: AutonomousMission) => {
    const requestedMissionId = nextMission.id;
    if (nextMission.project_id !== activeProjectIdRef.current || requestedMissionId !== activeMissionIdRef.current) return;
    if (nextMission.graph_overlay) {
      setMissionOverlay(nextMission.graph_overlay.mission_id === requestedMissionId ? nextMission.graph_overlay : null);
      return;
    }
    try {
      const nextOverlay = await fetchMissionGraphOverlay(requestedMissionId);
      if (
        nextMission.project_id === activeProjectIdRef.current &&
        requestedMissionId === activeMissionIdRef.current &&
        nextOverlay.mission_id === requestedMissionId
      ) {
        setMissionOverlay(nextOverlay);
      }
    } catch (error) {
      if (requestedMissionId !== activeMissionIdRef.current) return;
      setMissionOverlay(null);
      setMissionError(error instanceof Error ? error.message : String(error));
    }
  };

  const handleStartMission = async () => {
    if (!archiveDraft) {
      notify(String(copy[locale].noArchiveSelected));
      return;
    }
    if (missionActionRef.current) return;
    const token = missionActionTokenRef.current + 1;
    missionActionTokenRef.current = token;
    const requestedProjectId = archiveDraft.projectId;
    missionActionRef.current = "start";
    setMissionAction("start");
    activeMissionIdRef.current = null;
    setMissionOverlay(null);
    setMissionError("");
    try {
      const nextMission = await startArchitectureMission(requestedProjectId, 12);
      if (missionActionTokenRef.current !== token || nextMission.project_id !== activeProjectIdRef.current) return;
      activeMissionIdRef.current = nextMission.id;
      setMission(nextMission);
      await refreshMissionOverlay(nextMission);
      notify(String(copy[locale].missionReady));
    } catch (error) {
      if (missionActionTokenRef.current !== token || requestedProjectId !== activeProjectIdRef.current) return;
      const message = error instanceof Error ? error.message : String(error);
      setMissionError(message);
      notify(`${copy[locale].missionError}: ${message}`);
    } finally {
      if (missionActionTokenRef.current === token) {
        missionActionRef.current = null;
        setMissionAction(null);
      }
    }
  };

  const handleMissionStatusChange = async (action: "pause" | "resume" | "stop") => {
    if (missionActionRef.current || !mission || !archiveDraft) return;
    if (action === "pause" && (isMissionTerminal(mission) || mission.status === "paused")) return;
    if (action === "resume" && mission.status !== "paused") return;
    if (action === "stop" && isMissionTerminal(mission)) return;
    const token = missionActionTokenRef.current + 1;
    missionActionTokenRef.current = token;
    const requestedProjectId = archiveDraft.projectId;
    const requestedMissionId = mission.id;
    missionActionRef.current = action;
    setMissionAction(action);
    setMissionError("");
    try {
      const nextMission = await updateMissionStatus(requestedMissionId, action);
      if (missionActionTokenRef.current !== token || nextMission.project_id !== activeProjectIdRef.current) return;
      activeMissionIdRef.current = nextMission.id;
      setMission(nextMission);
      await refreshMissionOverlay(nextMission);
    } catch (error) {
      if (missionActionTokenRef.current !== token || requestedProjectId !== activeProjectIdRef.current) return;
      const message = error instanceof Error ? error.message : String(error);
      setMissionError(message);
      notify(`${copy[locale].missionError}: ${message}`);
    } finally {
      if (missionActionTokenRef.current === token) {
        missionActionRef.current = null;
        setMissionAction(null);
      }
    }
  };

  return (
    <div className="app-shell">
      <AppHeader
        agentStatus={agentStatus}
        archiveIds={archiveIds}
        isCreatingArchive={isCreatingArchive}
        isLoading={isLoadingArchive}
        isSwitchingArchive={isSwitchingArchive}
        locale={locale}
        onArchiveChange={handleArchiveChange}
        onCreateArchive={handleCreateArchive}
        onLocaleChange={setLocale}
        onSearchGraph={handleSearchGraph}
        selectedArchiveId={selectedArchiveId}
      />
      {notice ? <div className="notice-bar" role="status">{notice}</div> : null}
      <PageTabs activePage={activePage} locale={locale} onPageChange={setActivePage} />
      {activePage === "overview" ? (
        <>
          <UploadDock
            isCreatingArchive={isCreatingArchive}
            locale={locale}
            onScanProfileChange={(nextProfile) => {
              setScanProfile(nextProfile);
              notify(String(copy[locale][scopeOptions.find((option) => option.profile === nextProfile)?.labelKey ?? "scope"]));
            }}
            onZipSelected={(file) => {
              setSelectedFile(file);
              setSelectedFileName(file.name);
              notify(`${copy[locale].zipSelected}: ${file.name}`);
            }}
            scanProfile={scanProfile}
            selectedFileName={selectedFileName}
            uploadProgress={uploadProgress}
            uploadProgressMessage={uploadProgressMessage}
          />
          {archiveDraft && selectedHall ? (
            <>
              <ProjectPassport
                archiveDraft={archiveDraft}
                isFallback={isFallbackArchive}
                locale={locale}
              />
              <div className="workbench">
                <HallRail
                  archiveDraft={archiveDraft}
                  locale={locale}
                  selectedHallId={selectedHallId}
                  onSelect={(hall) => {
                    setSelectedHallId(hall.id);
                    setSelectedRelationId("");
                    setSelectedEvidenceId("");
                    setSearchQuery("");
                    setIsSearchVisible(false);
                  }}
                />
                <StarMap
                  evidenceCards={archiveDraft.evidenceCards}
                  hall={selectedHall}
                  isGraphHintVisible={isGraphHintVisible}
                  locale={locale}
                  onExpandGraph={() => setActivePage("graph")}
                  onEvidenceSelect={(card) => {
                    setSelectedEvidenceId(card.id);
                    notify(`${copy[locale].evidenceSelected}: ${evidenceTitle(card, locale)}`);
                  }}
                  onGraphHintClose={() => setIsGraphHintVisible(false)}
                  onGraphHintShow={() => setIsGraphHintVisible(true)}
                  onRelationClear={() => {
                    setSelectedRelationId("");
                    notify(locale === "zh" ? "已返回关系列表" : "Returned to relation list");
                  }}
                  onRelationSelect={(relation) => {
                    setSelectedRelationId(relation.id);
                    notify(`${copy[locale].relationSelected}: ${relation.type}`);
                  }}
                  onSearchChange={setSearchQuery}
                  relations={archiveDraft.relations}
                  searchQuery={searchQuery}
                  searchVisible={isSearchVisible}
                  selectedRelationId={selectedRelationId}
                />
                <EvidenceDrawer
                  cards={archiveDraft.evidenceCards}
                  hall={selectedHall}
                  locale={locale}
                  onEvidenceSelect={(card) => {
                    setSelectedEvidenceId(card.id);
                    notify(`${copy[locale].evidenceSelected}: ${evidenceTitle(card, locale)}`);
                  }}
                  selectedEvidenceId={selectedEvidenceId}
                />
              </div>
            </>
          ) : (
            <EmptyArchiveState archiveCount={archiveIds.length} locale={locale} />
          )}
        </>
      ) : activePage === "graph" && archiveDraft ? (
        <GraphExplorerPage
          archiveDraft={archiveDraft}
          locale={locale}
          missionOverlay={
            mission?.project_id === archiveDraft.projectId && missionOverlay?.mission_id === mission.id
              ? missionOverlay
              : null
          }
          onOpenMission={() => setActivePage("agents")}
        />
      ) : activePage === "graph" ? (
        <EmptyArchiveState archiveCount={archiveIds.length} locale={locale} />
      ) : archiveDraft && selectedHall ? (
        <div className="agent-analysis-page">
          <div className="agent-analysis-main">
            <ReactAgentMissionPanel
              error={reactMissionError}
              isStarting={isStartingReactMission}
              locale={locale}
              mission={reactMission?.project_id === archiveDraft.projectId ? reactMission : null}
              onAction={handleReactMissionAction}
              onStart={handleStartReactMission}
              trace={reactMission?.project_id === archiveDraft.projectId ? reactTrace : []}
            />
            <MissionControlPanel
              error={missionError}
              locale={locale}
              mission={mission?.project_id === archiveDraft.projectId ? mission : null}
              missionAction={missionAction}
              onPause={() => handleMissionStatusChange("pause")}
              onResume={() => handleMissionStatusChange("resume")}
              onStart={handleStartMission}
              onStop={() => handleMissionStatusChange("stop")}
            />
            <AgentPipelinePanel
              jobMessage={agentJobMessage}
              jobProgress={agentJobProgress}
              isRunning={isRunningAgentReport}
              locale={locale}
              onRun={handleRunAgentReport}
              report={agentReport}
            />
            <AgentWorkProofPanel locale={locale} report={agentReport} />
            <AgentCommandBar
              evidenceCards={archiveDraft.evidenceCards}
              hall={selectedHall}
              locale={locale}
              onNotify={notify}
              projectId={archiveDraft.projectId}
              scopeMode={queryMode}
            />
          </div>
          <aside className="agent-analysis-side">
            <ModelStatusPanel
              agentStatus={agentStatus}
              hybridRagStatus={hybridRagStatus}
              locale={locale}
              report={agentReport}
            />
            <TaskHistoryPanel history={currentJobHistory} locale={locale} />
          </aside>
        </div>
      ) : (
        <EmptyArchiveState archiveCount={archiveIds.length} locale={locale} />
      )}
    </div>
  );
}
