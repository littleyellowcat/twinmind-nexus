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
import type { KeyboardEvent, ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import {
  fetchAgentStatus,
  fetchArchiveDraft,
  fetchGraphNeighborhood,
  fetchGraphSummary,
  fetchProjectAgentReport,
  fetchProjectArchive,
  runArchiveQuery,
  runProjectAgentReportJob,
  uploadProjectArchive,
} from "./api";
import { archiveDraft as fallbackArchiveDraft } from "./archiveData";
import type {
  AgentReport,
  AgentStatus,
  ArchiveDraft,
  ArchiveHall,
  ArchiveRelation,
  EvidenceCard,
  GraphExplorerNode,
  GraphExplorerRelation,
  GraphNeighborhood,
  GraphSummary,
  ProjectAgentReport,
} from "./types";

type Locale = "zh" | "en";
type ScopeMode = "architecture_tour" | "impact_analysis" | "risk_audit" | "evidence_qa";
type ScanProfile = "architecture" | "full" | "docs" | "tests";
type AppPage = "overview" | "graph" | "agents";
type GraphTone = "accent" | "blue" | "amber" | "violet";
type JobHistoryItem = {
  id: string;
  label: string;
  progress: number;
  message: string;
};

const copy = {
  zh: {
    subtitle: "项目档案观测台",
    searchGraph: "搜索图谱",
    createArchive: "生成档案",
    loadingArchive: "正在连接档案 API",
    loadingSelectedArchive: "正在切换档案",
    archiveSelector: "项目档案",
    overviewPage: "档案总览",
    graphPage: "图谱探索",
    agentPage: "Agent 分析",
    expandGraph: "放大图谱",
    graphExplorer: "图谱探索",
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
    intakeCopy: "拖入项目 ZIP。文件夹上传和后端 API 摄取会在下一步接入。",
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
  },
  en: {
    subtitle: "Project archive observatory",
    searchGraph: "Search graph",
    createArchive: "Create Archive",
    loadingArchive: "Connecting archive API",
    loadingSelectedArchive: "Switching archive",
    archiveSelector: "Project archive",
    overviewPage: "Archive overview",
    graphPage: "Graph Explorer",
    agentPage: "Agent analysis",
    expandGraph: "Expand graph",
    graphExplorer: "Graph Explorer",
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
    intakeCopy: "Drop a repository ZIP here. Local folder upload and API ingestion come next.",
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
  },
} satisfies Record<Locale, Record<string, unknown>>;

const scopeOptions = [
  { profile: "architecture", labelKey: "architectureFirst" },
  { profile: "full", labelKey: "fullAudit" },
  { profile: "docs", labelKey: "docsFirst" },
  { profile: "tests", labelKey: "testsQuality" },
] satisfies { profile: ScanProfile; labelKey: keyof typeof copy.zh }[];

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
};

type VisibleGraphEdge = ArchiveRelation & {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  isSelected: boolean;
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

const buildVisibleGraph = (relations: ArchiveRelation[], selectedRelationId: string) => {
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

  const nodes = Array.from(nodeLabels.entries()).map(([id, label], index, allNodes) => {
    const nodeCount = allNodes.length;
    const centerX = 380;
    const centerY = 215;
    const isSingle = nodeCount <= 1;
    const angle = -Math.PI / 2 + (index / Math.max(nodeCount, 1)) * Math.PI * 2 + (nodeCount > 9 ? (index % 2) * 0.16 : 0);
    const radiusScale = nodeCount > 10 && index % 2 ? 0.72 : 1;
    const x = isSingle ? centerX : centerX + Math.cos(angle) * 270 * radiusScale;
    const y = isSingle ? centerY : centerY + Math.sin(angle) * 150 * radiusScale;

    return {
      id,
      label,
      x: Math.min(690, Math.max(70, x)),
      y: Math.min(370, Math.max(60, y)),
      tone: selectedNodeNames.has(id) ? "accent" : graphToneCycle[index % graphToneCycle.length],
      isSelected: selectedNodeNames.has(id),
    };
  });

  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const edges = edgeRelations
    .map((relation) => {
      const source = nodeById.get(relation.source);
      const target = nodeById.get(relation.target);
      if (!source || !target) return null;
      return {
        ...relation,
        x1: source.x,
        y1: source.y,
        x2: target.x,
        y2: target.y,
        isSelected: relation.id === selectedRelationId,
      };
    })
    .filter((relation): relation is VisibleGraphEdge => Boolean(relation));

  return { nodes, edges, totalRelations: usableRelations.length };
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
  hall,
  isGraphHintVisible,
  relations,
  locale,
  onExpandGraph,
  onGraphHintClose,
  onGraphHintShow,
  onRelationSelect,
  searchQuery,
  searchVisible,
  selectedRelationId,
  onSearchChange,
}: {
  hall: ArchiveHall;
  isGraphHintVisible: boolean;
  relations: ArchiveRelation[];
  locale: Locale;
  onExpandGraph: () => void;
  onGraphHintClose: () => void;
  onGraphHintShow: () => void;
  onRelationSelect: (relation: ArchiveRelation) => void;
  searchQuery: string;
  searchVisible: boolean;
  selectedRelationId: string;
  onSearchChange: (query: string) => void;
}) {
  const t = copy[locale];
  const visibleRelations = relations.filter((relation) => relation.hall === hall.id);
  const fallbackRelations = visibleRelations.length ? visibleRelations : relations.slice(0, 12);
  const normalizedQuery = searchQuery.trim().toLowerCase();
  const filteredRelations = normalizedQuery
    ? fallbackRelations.filter((relation) =>
        [relation.source, relation.type, relation.target].some((value) =>
          value.toLowerCase().includes(normalizedQuery),
        ),
      )
    : fallbackRelations;
  const visibleGraph = useMemo(
    () => buildVisibleGraph(filteredRelations, selectedRelationId),
    [filteredRelations, selectedRelationId],
  );
  const graphCounter =
    locale === "zh"
      ? `显示 ${formatNumber(visibleGraph.nodes.length)} 个节点 / ${formatNumber(visibleGraph.edges.length)} 条关系，当前匹配 ${formatNumber(visibleGraph.totalRelations)} 条`
      : `Showing ${formatNumber(visibleGraph.nodes.length)} nodes / ${formatNumber(visibleGraph.edges.length)} relations from ${formatNumber(visibleGraph.totalRelations)} matches`;
  const emptyGraphText =
    locale === "zh"
      ? "当前展厅还没有可展示的关系。换一个展厅或清空搜索试试。"
      : "No relations are available for this hall. Try another hall or clear search.";

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
        <label className="graph-search">
          <Search size={16} />
          <input
            autoFocus={searchVisible}
            value={searchQuery}
            placeholder={String(t.searchPlaceholder)}
            onChange={(event) => onSearchChange(event.currentTarget.value)}
          />
        </label>
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
                className={`graph-edge ${edge.isSelected ? "is-selected" : ""}`}
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
  isSelected,
  label,
  tone,
  x,
  y,
}: {
  isSelected: boolean;
  label: string;
  tone: GraphTone;
  x: number;
  y: number;
}) {
  const displayLabel = compactGraphLabel(label);
  return (
    <g className={`graph-node ${tone} ${isSelected ? "is-selected" : ""}`}>
      <title>{label}</title>
      <circle className="node-glow" cx={x} cy={y} r="42" />
      <circle cx={x} cy={y} r="14" />
      <text textAnchor="middle" x={x} y={y + 34}>
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
  const visibleCards = cards.filter((card) => card.hall === hall.id);
  const fallbackCards = visibleCards.length ? visibleCards : cards;

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
        {fallbackCards.slice(0, 4).map((card) => (
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
        ))}
      </div>
    </aside>
  );
}

function AgentCommandBar({
  hall,
  locale,
  onNotify,
  projectId,
  scopeMode,
}: {
  hall: ArchiveHall;
  locale: Locale;
  onNotify: (message: string) => void;
  projectId: string;
  scopeMode: ScopeMode;
}) {
  const t = copy[locale];
  const defaultQuestion = `${t.agentPromptPrefix} ${hallTitle(hall, locale)}, ${t.agentPromptSuffix}`;
  const [question, setQuestion] = useState(defaultQuestion);
  const [report, setReport] = useState<AgentReport | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  useEffect(() => {
    setQuestion(defaultQuestion);
  }, [defaultQuestion]);

  const handleRunReport = async () => {
    setIsRunning(true);
    try {
      const nextReport = await runArchiveQuery(projectId, question.trim() || defaultQuestion, scopeMode);
      setReport(nextReport);
      onNotify(String(t.reportReady));
    } catch {
      onNotify(String(t.reportFailed));
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <section className="agent-bar" aria-label="Agent command bar">
      <div className="agent-mode">
        <Command size={18} />
        {t.agentCommand}
      </div>
      <label className="agent-input">
        <Sparkles size={16} />
        <input
          value={question}
          onChange={(event) => setQuestion(event.currentTarget.value)}
        />
      </label>
      <button className="primary-button" disabled={isRunning} onClick={handleRunReport} type="button">
        <Braces size={16} />
        {isRunning ? t.reportRunning : t.runReport}
      </button>
      {report ? (
        <div className="agent-report">
          <strong>{report.summary}</strong>
          <span>
            {t.confidence}: {Math.round(report.confidence * 100)}%
          </span>
          <span>
            {t.llmSource}:{" "}
            {report.metadata?.llm?.enabled && !report.metadata.llm.fallback
              ? `${report.metadata.llm.provider ?? "llm"} · ${report.metadata.llm.model ?? ""}`
              : t.deterministicSource}
          </span>
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

function GraphExplorerPage({
  archiveDraft,
  locale,
}: {
  archiveDraft: ArchiveDraft;
  locale: Locale;
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
  const [error, setError] = useState("");

  useEffect(() => {
    setSelectedHallId(archiveDraft.halls[0]?.id ?? null);
    setFocusedEntityId(null);
    setSelectedRelationId(null);
  }, [archiveDraft.projectId, archiveDraft.halls]);

  useEffect(() => {
    let isMounted = true;
    setSummary(null);
    setIsSummaryLoading(true);

    fetchGraphSummary(archiveDraft.projectId)
      .then((nextSummary) => {
        if (!isMounted) return;
        setSummary(nextSummary);
        setError("");
      })
      .catch((nextError) => {
        if (!isMounted) return;
        setSummary(null);
        setError(nextError instanceof Error ? nextError.message : String(nextError));
      })
      .finally(() => {
        if (isMounted) setIsSummaryLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [archiveDraft.projectId]);

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
        setError("");
      })
      .catch((nextError) => {
        if (!isMounted) return;
        setNeighborhood(null);
        setError(nextError instanceof Error ? nextError.message : String(nextError));
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
  const visibleNodeCount = neighborhood?.nodes.length ?? 0;
  const visibleRelationCount = neighborhood?.relations.length ?? 0;
  const statusText = error
    ? error
    : locale === "zh"
      ? `显示 ${formatNumber(visibleNodeCount)} 个节点 / ${formatNumber(visibleRelationCount)} 条关系`
      : `Showing ${formatNumber(visibleNodeCount)} nodes / ${formatNumber(visibleRelationCount)} relations`;

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
              {archiveDraft.halls.map((hall) => (
                <option key={hall.id} value={hall.id}>
                  {hallTitle(hall, locale)}
                </option>
              ))}
            </select>
            <ChevronDown size={15} />
          </label>
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
          selectedRelationId={selectedRelationId}
        />
        {isRightOpen ? (
          <GraphEntityDrawer
            focusedNode={focusedNode}
            locale={locale}
            nodeById={nodeById}
            selectedRelation={selectedRelation}
          />
        ) : null}
      </div>
      <div className={`graph-explorer-status ${error ? "is-error" : ""}`} role="status">
        {statusText}
      </div>
    </section>
  );
}

function GraphStartsDrawer({
  focusedEntityId,
  isLoading,
  locale,
  onStartSelect,
  selectedHallId,
  summary,
}: {
  focusedEntityId: string | null;
  isLoading: boolean;
  locale: Locale;
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
        <PanelLeft size={18} />
      </div>
      <div className="graph-start-list">
        {starts.length ? (
          starts.map((start) => (
            <button
              className={`graph-start-item ${start.entity_id === focusedEntityId ? "is-active" : ""}`}
              key={start.entity_id}
              onClick={() => onStartSelect(start.entity_id)}
              type="button"
            >
              <span className="graph-start-group">{start.group}</span>
              <strong>{start.label}</strong>
              <span>{start.reason}</span>
              <small>{Math.round(start.score * 100)}%</small>
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
  selectedRelation,
}: {
  focusedNode: GraphExplorerNode | null;
  locale: Locale;
  nodeById: Map<string, GraphExplorerNode>;
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
        <PanelRight size={18} />
      </div>
      <div className="entity-detail-stack">
        {focusedNode ? (
          <section className="entity-detail-card">
            <span className="entity-label">{t.currentFocus}</span>
            <h3>{focusedNode.label}</h3>
            <div className="entity-meta-grid">
              <span>Type</span>
              <strong>{typeLabel(focusedNode.type, locale)}</strong>
              <span>Degree</span>
              <strong>{focusedNode.degree}</strong>
              <span>Importance</span>
              <strong>{Math.round(focusedNode.importance * 100)}%</strong>
              <span>Evidence</span>
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
              <span>Weight</span>
              <strong>{selectedRelation.weight}</strong>
              <span>Evidence</span>
              <strong>{selectedRelation.evidence_ids.length}</strong>
              <span>Halls</span>
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
  neighborhood,
  onNodeFocus,
  onRelationSelect,
  selectedRelationId,
}: {
  focusedEntityId: string | null;
  isLoading: boolean;
  locale: Locale;
  neighborhood: GraphNeighborhood | null;
  onNodeFocus: (entityId: string) => void;
  onRelationSelect: (relationId: string) => void;
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
                } ${relation.isDimmed ? "is-dimmed" : ""}`}
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
        {layout.nodes.map((node) => (
          <g
            aria-label={node.label}
            className={`explorer-node ${node.tone} ${node.isFocused ? "is-focused" : ""} ${
              node.isDimmed ? "is-dimmed" : ""
            }`}
            key={node.id}
            onClick={() => onNodeFocus(node.id)}
            onKeyDown={(event) => handleNodeKeyDown(event, node.id)}
            role="button"
            tabIndex={0}
          >
            <title>{node.label}</title>
            <circle className="node-glow" cx={node.x} cy={node.y} r={node.isFocused ? 54 : 42} />
            <circle cx={node.x} cy={node.y} r={node.isFocused ? 20 : 15} />
            <text textAnchor="middle" x={node.x} y={node.y + (node.isFocused ? 42 : 35)}>
              {compactGraphLabel(node.label, 26)}
            </text>
          </g>
        ))}
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
  const sourceNodes = neighborhood.nodes;
  if (!sourceNodes.length) return { nodes: [], relations: [] };

  const nodeIds = new Set(sourceNodes.map((node) => node.id));
  const visibleRelations = neighborhood.relations.filter(
    (relation) => nodeIds.has(relation.source_id) && nodeIds.has(relation.target_id),
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
  locale,
  report,
}: {
  agentStatus: AgentStatus | null;
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
              </div>
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

export function App() {
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [archiveDraft, setArchiveDraft] = useState<ArchiveDraft>(fallbackArchiveDraft);
  const [agentReport, setAgentReport] = useState<ProjectAgentReport | null>(null);
  const [archiveIds, setArchiveIds] = useState<string[]>([fallbackArchiveDraft.projectId]);
  const [isFallbackArchive, setIsFallbackArchive] = useState(true);
  const [isLoadingArchive, setIsLoadingArchive] = useState(true);
  const [isSwitchingArchive, setIsSwitchingArchive] = useState(false);
  const [selectedHallId, setSelectedHallId] = useState(fallbackArchiveDraft.halls[0].id);
  const [selectedArchiveId, setSelectedArchiveId] = useState(fallbackArchiveDraft.projectId);
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
  const [jobHistory, setJobHistory] = useState<JobHistoryItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearchVisible, setIsSearchVisible] = useState(false);
  const [isGraphHintVisible, setIsGraphHintVisible] = useState(false);
  const [selectedRelationId, setSelectedRelationId] = useState("");
  const [selectedEvidenceId, setSelectedEvidenceId] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let isMounted = true;

    fetchArchiveDraft().then(({ archiveIds: nextArchiveIds, draft, source }) => {
      if (!isMounted) return;
      setArchiveIds(nextArchiveIds.length ? nextArchiveIds : [draft.projectId]);
      setArchiveDraft(draft);
      setSelectedArchiveId(draft.projectId);
      setSelectedHallId(draft.halls[0]?.id ?? fallbackArchiveDraft.halls[0].id);
      setIsFallbackArchive(source === "fallback");
      setIsLoadingArchive(false);
      fetchProjectAgentReport(draft.projectId)
        .then((report) => {
          if (isMounted) setAgentReport(report);
        })
        .catch(() => {
          if (isMounted) setAgentReport(null);
        });
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
    () => archiveDraft.halls.find((hall) => hall.id === selectedHallId) ?? archiveDraft.halls[0],
    [archiveDraft.halls, selectedHallId],
  );

  const notify = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 3200);
  };

  const recordJobProgress = (label: string, progress: number, message: string) => {
    setJobHistory((current) => [
      ...current.slice(-20),
      {
        id: `${Date.now()}-${label}-${progress}`,
        label,
        progress,
        message,
      },
    ]);
  };

  const resetArchiveView = (draft: ArchiveDraft, report: ProjectAgentReport | null = null) => {
    setArchiveDraft(draft);
    setAgentReport(report);
    setSelectedArchiveId(draft.projectId);
    setSelectedHallId(draft.halls[0]?.id ?? fallbackArchiveDraft.halls[0].id);
    setSelectedRelationId("");
    setSelectedEvidenceId("");
    setSearchQuery("");
  };

  const handleArchiveChange = async (projectId: string) => {
    if (!projectId || projectId === archiveDraft.projectId) return;
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
      const { draft, agentReport } = await uploadProjectArchive(
        selectedFile,
        scanProfile,
        (progress, message) => {
          setUploadProgress(progress);
          setUploadProgressMessage(message);
          recordJobProgress(String(copy[locale].createArchive), progress, message);
        },
      );
      resetArchiveView(draft, agentReport);
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
    setIsSearchVisible(true);
    notify(String(copy[locale].searchOpened));
  };

  const handleRunAgentReport = async () => {
    setIsRunningAgentReport(true);
    setAgentJobProgress(1);
    setAgentJobMessage(String(copy[locale].agentReportRunning));
    notify(String(copy[locale].agentReportRunning));
    try {
      const report = await runProjectAgentReportJob(
        archiveDraft.projectId,
        scanProfile,
        (progress, message) => {
          setAgentJobProgress(progress);
          setAgentJobMessage(message);
          recordJobProgress(String(copy[locale].rerunAnalysis), progress, message);
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
          <ProjectPassport
            archiveDraft={archiveDraft}
            isFallback={isFallbackArchive}
            locale={locale}
          />
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
          <div className="workbench">
            <HallRail
              archiveDraft={archiveDraft}
              locale={locale}
              selectedHallId={selectedHallId}
              onSelect={(hall) => {
                setSelectedHallId(hall.id);
                setSelectedRelationId("");
                setSelectedEvidenceId("");
              }}
            />
            <StarMap
              hall={selectedHall}
              isGraphHintVisible={isGraphHintVisible}
              locale={locale}
              onExpandGraph={() => setActivePage("graph")}
              onGraphHintClose={() => setIsGraphHintVisible(false)}
              onGraphHintShow={() => setIsGraphHintVisible(true)}
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
      ) : activePage === "graph" ? (
        <GraphExplorerPage archiveDraft={archiveDraft} locale={locale} />
      ) : (
        <div className="agent-analysis-page">
          <div className="agent-analysis-main">
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
              hall={selectedHall}
              locale={locale}
              onNotify={notify}
              projectId={archiveDraft.projectId}
              scopeMode={queryMode}
            />
          </div>
          <aside className="agent-analysis-side">
            <ModelStatusPanel agentStatus={agentStatus} locale={locale} report={agentReport} />
            <TaskHistoryPanel history={jobHistory} locale={locale} />
          </aside>
        </div>
      )}
    </div>
  );
}
