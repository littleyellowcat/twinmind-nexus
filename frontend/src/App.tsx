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
  ListTree,
  Network,
  PanelLeft,
  PanelRight,
  Route,
  Save,
  Search,
  ShieldCheck,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, KeyboardEvent, ReactNode } from "react";
import * as THREE from "three";
import {
  compareUniverseProjects,
  cancelArchiveJob,
  dryRunHarnessArtifactCleanup,
  dryRunHarnessCommand,
  fetchAgentTaskPlan,
  fetchAgentEvalReport,
  fetchAgentMemory,
  fetchAgentMission,
  fetchAgentMissionVisualization,
  fetchAgentStatus,
  fetchAgentMissionTrace,
  fetchAgentTrustReport,
  fetchArchiveDraft,
  fetchEvaluationHistory,
  fetchGraphCuration,
  fetchGraphNeighborhood,
  fetchGraphSummary,
  fetchGraphStoreStatus,
  fetchGraphWorkspaceReport,
  fetchHarnessArtifactManifest,
  fetchHarnessCommands,
  fetchHarnessExport,
  fetchHarnessRunSummary,
  fetchHarnessTimeline,
  fetchHybridRagStatus,
  fetchIngestionDiagnostics,
  fetchKnowledgeUniverse,
  fetchMultimodalInsights,
  fetchSystemConfigCheck,
  fetchMissionGraphOverlay,
  fetchProjectAgentReport,
  fetchProjectIntelligenceReport,
  fetchProjectArchive,
  fetchStressTestReport,
  fetchUniverseAgentTasks,
  fetchUniversePaths,
  listArchiveJobs,
  rebuildHybridRagIndexJob,
  runArchiveQuery,
  runAgentEvalHarness,
  runProjectAgentReportJob,
  runUniverseAgentTasks,
  saveGraphCuration,
  saveUniversePath,
  searchGraphEntities,
  startAgentMission,
  startArchitectureMission,
  updateAgentMissionStatus,
  updateMissionStatus,
  uploadProjectArchive,
  fetchArchiveEvaluation,
  runArchiveEvaluation,
  runProjectIntelligenceReport,
  runStressTest,
  downloadProjectIntelligenceMarkdown,
  downloadProjectIntelligencePdf,
} from "./api";
import type {
  AgentMission,
  AgentEvalReport,
  AgentMemory,
  AgentTaskPlan,
  AgentMissionVisualization,
  AgentReport,
  AgentStatus,
  AgentTrustReport,
  AgentTraceEvent,
  ArchiveEvaluationReport,
  ArchiveDraft,
  ArchiveJob,
  ArchiveHall,
  ArchiveRelation,
  AutonomousMission,
  EvidenceCard,
  GraphExplorerNode,
  GraphExplorerRelation,
  GraphNeighborhood,
  GraphSearchResult,
  GraphSummary,
  GraphStoreStatus,
  GraphWorkspaceReport,
  HarnessArtifactManifest,
  HarnessCommand,
  HarnessCommandDryRun,
  HarnessRunSummary,
  HarnessTimeline,
  HybridRagStatus,
  IngestionDiagnostics,
  EvaluationHistory,
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

type Locale = "zh" | "en";
type ScopeMode = "architecture_tour" | "impact_analysis" | "risk_audit" | "evidence_qa";
type ScanProfile = "architecture" | "full" | "docs" | "tests";
type AppPage = "overview" | "graph" | "agents" | "universe" | "tasks" | "system";
type GraphTone = "accent" | "blue" | "amber" | "violet";
type GraphViewMode = "cluster" | "hierarchy";
type GraphPanelMode = "balanced" | "map" | "inspect";
type GraphFocusPreset = "all" | "entry" | "config" | "api" | "dependency";
type GraphClusterItem = {
  label: string;
  count: number;
};
type GraphReviewItem = {
  id: string;
  kind: "duplicate" | "weak_relation" | "thin_evidence";
  title: string;
  reason: string;
  targetEntityId: string | null;
  relationId: string | null;
  relatedEntityIds: string[];
};
type GraphMergeCandidate = {
  id: string;
  label: string;
  entityIds: string[];
  createdAt: string;
};
type GraphCurationState = {
  importantEntityIds: string[];
  hiddenRelationIds: string[];
  mergeCandidates: GraphMergeCandidate[];
};
type GraphWorkspaceState = {
  hallId: string | null;
  focusEntityId: string | null;
  depth: number;
  viewMode: GraphViewMode;
  panelMode: GraphPanelMode;
  searchQuery: string;
  nodeTypes: string[];
  relationTypes: string[];
  focusPreset: GraphFocusPreset;
};
type AgentProofTimelineEvent = {
  id: string;
  phase: "plan" | "action" | "observation" | "verify" | "final";
  role: string;
  title: string;
  detail: string;
  status: "supported" | "review" | "pending";
  evidenceCount: number;
  entityCount: number;
  relationCount: number;
  tools: string[];
};
type MissionAction = "start" | "pause" | "resume" | "stop" | null;
type JobHistoryItem = {
  id: string;
  label: string;
  progress: number;
  message: string;
};
type JobHistoryByProjectId = Record<string, JobHistoryItem[]>;
type SavedGraphRoute = {
  id: string;
  title: string;
  projectId: string;
  hallId: string | null;
  focusEntityId: string | null;
  depth: number;
  viewMode: GraphViewMode;
  panelMode?: GraphPanelMode;
  nodeTypes?: string[];
  relationTypes?: string[];
  focusPreset?: GraphFocusPreset;
  source?: "manual" | "search" | "recommendation";
  createdAt: string;
};

const copy = {
  zh: {
    subtitle: "项目档案观测台",
    searchGraph: "搜索图谱",
    createArchive: "生成项目档案",
    loadingArchive: "正在连接档案 API",
    loadingSelectedArchive: "正在切换档案",
    archiveSelector: "项目档案",
    archiveSelectorPlaceholder: "选择项目档案",
    overviewPage: "档案总览",
    graphPage: "图谱探索",
    agentPage: "Agent 分析",
    universePage: "知识宇宙",
    taskCenterPage: "任务中心",
    systemPage: "系统配置",
    demoFlow: "演示流程",
    demoFlowCopy: "按顺序完成一次完整项目分析。",
    demoProgress: "进度",
    demoNext: "推荐下一步",
    demoStepUpload: "选择 ZIP",
    demoStepArchive: "生成档案",
    demoStepGraph: "图谱探索",
    demoStepAgent: "Agent 分析",
    demoStepUniverse: "知识宇宙",
    demoStepDiff: "A/B 对比",
    demoActionSelectZip: "选择项目 ZIP",
    demoActionCreateArchive: "生成项目档案",
    demoActionOpenGraph: "打开图谱探索",
    demoActionRunAgent: "运行 Agent 分析",
    demoActionOpenUniverse: "打开知识宇宙",
    demoActionRunUniverseAgent: "启动跨项目探索",
    demoActionRunDiff: "生成 A/B 差异报告",
    demoDone: "流程已完成",
    refreshUniverse: "刷新宇宙",
    loadingUniverse: "正在构建知识宇宙",
    universeLoadFailed: "知识宇宙加载失败",
    universeEmpty: "至少需要一个项目档案。上传或选择项目后，这里会显示跨项目共享实体、概念簇和关系。",
    universeSummary: "跨项目知识宇宙会把多个档案中的模块、配置、概念和证据放在同一个比较空间里。",
    selectedProjects: "选择项目",
    allProjects: "全部项目",
    universeProjects: "项目星系",
    sharedClusters: "共享实体簇",
    crossProjectLinks: "跨项目链接",
    metaverseLayer: "知识元宇宙",
    metaverseFocus: "空间焦点",
    metaverseHint: "拖拽旋转，滚轮缩放，点击项目或共享簇查看焦点。",
    saveUniversePath: "保存路径",
    savedPaths: "已保存路径",
    noSavedPaths: "还没有保存的跨项目探索路径。",
    universeAgentTasks: "跨项目 Agent 探索",
    runUniverseAgent: "启动跨项目探索",
    noUniverseTasks: "还没有跨项目 Agent 任务。",
    compareProjects: "项目 A/B 差异报告",
    runCompare: "生成差异报告",
    chooseSecondProject: "请选择两个不同项目。",
    diffReport: "差异报告",
    uniqueLeft: "A 独有",
    uniqueRight: "B 独有",
    noCrossProjectLinks: "当前选择下还没有发现跨项目链接。可以选择更多项目，或重新生成更完整的项目档案。",
    linkScore: "关联分",
    linkReason: "原因",
    expandGraph: "放大图谱",
    graphExplorer: "图谱探索",
    allGraph: "全部图谱",
    searchEntities: "搜索实体",
    graphSearchPlaceholder: "搜索全档案实体、文件或配置",
    graphSearchEmpty: "没有匹配的实体",
    graphSearchHint: "输入关键词后按 Enter 聚焦第一个结果",
    entityTypeFilter: "实体类型",
    allEntityTypes: "全部类型",
    graphFocusPreset: "图谱视角",
    graphPresetAll: "全局",
    graphPresetEntry: "入口点",
    graphPresetConfig: "配置",
    graphPresetApi: "接口",
    graphPresetDependency: "依赖",
    relationTypeFilter: "关系类型",
    allRelationTypes: "全部关系",
    whyRecommended: "推荐原因",
    expandCluster: "展开",
    collapseCluster: "收起",
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
    emptyGeneratedArchiveTitle: "档案已生成，但没有可展示的展厅",
    emptyGeneratedArchiveCopy: "后端已返回这个项目档案，但当前扫描结果没有形成展厅。可以换完整审计模式重新生成，或检查 ZIP 内是否有源码、文档、配置文件。",
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
    startMission: "启动自主架构任务",
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
    rerunAnalysis: "运行五角色分析",
    agentReportRunning: "分析中",
    jobProgress: "任务进度",
    uploadFailed: "上传摄取失败",
    retryUpload: "可以保留当前 ZIP，调整扫描模式后再次点击生成档案。",
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
      image: "图片",
      markdown: "文档",
    },
    lineRanges: {
      Config: "配置项",
      Module: "模块",
    },
    agentCommand: "Agent 指令",
    agentPromptPrefix: "解释",
    agentPromptSuffix: "追踪影响，并引用证据。",
    runReport: "生成问答报告",
    reportRunning: "生成中",
    confidence: "置信度",
    nextActions: "下一步",
    llmSource: "模型",
    deterministicSource: "规则 Agent",
    modelStatus: "模型状态",
    graphStore: "图存储",
    productionGraph: "生产图",
    hybridRag: "Hybrid RAG",
    multimodal: "多模态",
    agentProof: "Agent 工作证明",
    evaluationBenchmark: "评测基准",
    runEvaluation: "运行评测",
    evaluationRunning: "评测中",
    evaluationReady: "评测报告已生成",
    evaluationFailed: "评测失败",
    noEvaluationReport: "当前项目还没有评测报告。运行评测后会生成黄金问题、命中率和证据覆盖结果。",
    goldenQuestions: "黄金问题",
    caseScore: "用例分",
    graphCoverage: "图谱覆盖",
    evidenceCoverage: "证据覆盖",
    entityHitRate: "实体命中",
    relationHitRate: "关系命中",
    evidenceHitRate: "证据命中",
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
    proofPhasePlan: "Plan",
    proofPhaseAction: "Action",
    proofPhaseObservation: "Observation",
    proofPhaseVerify: "Verify",
    proofPhaseFinal: "Final",
    proofTimeline: "工作时间线",
    proofTimelineEmpty: "还没有可检查的 Agent 时间线。运行分析后会从显式工作记录生成。",
    proofSupported: "有证据",
    proofUncertain: "需复核",
  },
  en: {
    subtitle: "Project archive observatory",
    searchGraph: "Search graph",
    createArchive: "Create project archive",
    loadingArchive: "Connecting archive API",
    loadingSelectedArchive: "Switching archive",
    archiveSelector: "Project archive",
    archiveSelectorPlaceholder: "Select archive",
    overviewPage: "Archive overview",
    graphPage: "Graph Explorer",
    agentPage: "Agent analysis",
    universePage: "Knowledge universe",
    taskCenterPage: "Task center",
    systemPage: "System config",
    demoFlow: "Demo flow",
    demoFlowCopy: "Walk through one complete project-analysis loop.",
    demoProgress: "Progress",
    demoNext: "Next best action",
    demoStepUpload: "Choose ZIP",
    demoStepArchive: "Create archive",
    demoStepGraph: "Explore graph",
    demoStepAgent: "Agent analysis",
    demoStepUniverse: "Knowledge universe",
    demoStepDiff: "A/B diff",
    demoActionSelectZip: "Choose project ZIP",
    demoActionCreateArchive: "Create project archive",
    demoActionOpenGraph: "Open graph explorer",
    demoActionRunAgent: "Run Agent analysis",
    demoActionOpenUniverse: "Open knowledge universe",
    demoActionRunUniverseAgent: "Start cross-project exploration",
    demoActionRunDiff: "Generate A/B diff report",
    demoDone: "Flow complete",
    refreshUniverse: "Refresh universe",
    loadingUniverse: "Building knowledge universe",
    universeLoadFailed: "Knowledge universe failed",
    universeEmpty: "Create or select at least one project archive to see shared entities, concept clusters, and cross-project links.",
    universeSummary: "The multi-project universe places modules, config, concepts, and evidence from multiple archives into one comparison space.",
    selectedProjects: "Selected projects",
    allProjects: "All projects",
    universeProjects: "Project constellation",
    sharedClusters: "Shared clusters",
    crossProjectLinks: "Cross-project links",
    metaverseLayer: "Knowledge metaverse",
    metaverseFocus: "Spatial focus",
    metaverseHint: "Drag to rotate, wheel to zoom, and click projects or shared clusters to inspect them.",
    saveUniversePath: "Save path",
    savedPaths: "Saved paths",
    noSavedPaths: "No cross-project exploration paths saved yet.",
    universeAgentTasks: "Cross-project Agent exploration",
    runUniverseAgent: "Start cross-project exploration",
    noUniverseTasks: "No cross-project Agent tasks yet.",
    compareProjects: "Project A/B diff report",
    runCompare: "Generate diff report",
    chooseSecondProject: "Choose two different projects.",
    diffReport: "Diff report",
    uniqueLeft: "A only",
    uniqueRight: "B only",
    noCrossProjectLinks: "No cross-project links found for this selection yet. Select more projects or regenerate richer archives.",
    linkScore: "Score",
    linkReason: "Reason",
    expandGraph: "Expand graph",
    graphExplorer: "Graph Explorer",
    allGraph: "All graph",
    searchEntities: "Search entities",
    graphSearchPlaceholder: "Search archive entities, files, or config",
    graphSearchEmpty: "No matching entities",
    graphSearchHint: "Type a keyword and press Enter to focus the first result",
    entityTypeFilter: "Entity types",
    allEntityTypes: "All types",
    graphFocusPreset: "Graph lens",
    graphPresetAll: "Global",
    graphPresetEntry: "Entry",
    graphPresetConfig: "Config",
    graphPresetApi: "API",
    graphPresetDependency: "Dependency",
    relationTypeFilter: "Relation types",
    allRelationTypes: "All relations",
    whyRecommended: "Why recommended",
    expandCluster: "Expand",
    collapseCluster: "Collapse",
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
    emptyGeneratedArchiveTitle: "Archive generated, but no halls are available",
    emptyGeneratedArchiveCopy: "The backend returned this archive, but the scan did not produce displayable halls. Try Full audit or check that the ZIP contains source, docs, or config files.",
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
    startMission: "Start autonomous architecture mission",
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
    rerunAnalysis: "Run five-role analysis",
    agentReportRunning: "Running",
    jobProgress: "Job progress",
    uploadFailed: "Upload ingestion failed",
    retryUpload: "The current ZIP is still selected. Adjust the scan mode and create the archive again.",
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
      image: "image",
      markdown: "markdown",
    },
    lineRanges: {
      Config: "Config",
      Module: "Module",
    },
    agentCommand: "Agent Command",
    agentPromptPrefix: "Explain",
    agentPromptSuffix: "trace impact, and cite evidence.",
    runReport: "Run QA report",
    reportRunning: "Running",
    confidence: "Confidence",
    nextActions: "Next actions",
    llmSource: "Model",
    deterministicSource: "Rule Agent",
    modelStatus: "Model status",
    graphStore: "Graph store",
    productionGraph: "Production graph",
    hybridRag: "Hybrid RAG",
    multimodal: "Multimodal",
    agentProof: "Agent work proof",
    evaluationBenchmark: "Evaluation benchmark",
    runEvaluation: "Run evaluation",
    evaluationRunning: "Evaluating",
    evaluationReady: "Evaluation report generated",
    evaluationFailed: "Evaluation failed",
    noEvaluationReport: "No evaluation report exists for this project yet. Run evaluation to create golden questions, hit rates, and evidence coverage.",
    goldenQuestions: "Golden questions",
    caseScore: "Case score",
    graphCoverage: "Graph coverage",
    evidenceCoverage: "Evidence coverage",
    entityHitRate: "Entity hit",
    relationHitRate: "Relation hit",
    evidenceHitRate: "Evidence hit",
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
    proofPhasePlan: "Plan",
    proofPhaseAction: "Action",
    proofPhaseObservation: "Observation",
    proofPhaseVerify: "Verify",
    proofPhaseFinal: "Final",
    proofTimeline: "Work timeline",
    proofTimelineEmpty: "No inspectable Agent timeline yet. Run analysis to generate it from explicit work records.",
    proofSupported: "Supported",
    proofUncertain: "Review",
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
const formatPercent = (value: number | undefined) => `${Math.round((value ?? 0) * 100)}%`;

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

type EvidenceModality = "all" | "image" | "code" | "config" | "text";

const evidenceModality = (card: EvidenceCard): Exclude<EvidenceModality, "all"> => {
  const raw = `${card.modality ?? ""} ${card.sourceType} ${card.sourcePath}`.toLowerCase();
  if (raw.includes("image")) return "image";
  if (raw.includes("config") || raw.includes(".yaml") || raw.includes(".yml") || raw.includes(".toml") || raw.includes(".json")) {
    return "config";
  }
  if (raw.includes("code") || /\.(py|java|ts|tsx|js|jsx|go|rs|c|cc|cpp|h|hpp)$/i.test(card.sourcePath)) {
    return "code";
  }
  return "text";
};

const evidenceIsHybrid = (card: EvidenceCard) => Boolean(card.metadata?.hybrid_rag);

const evidenceModalityLabel = (modality: EvidenceModality, locale: Locale) => {
  const labels: Record<Locale, Record<EvidenceModality, string>> = {
    zh: {
      all: "全部",
      image: "图片",
      code: "代码",
      config: "配置",
      text: "文本",
    },
    en: {
      all: "All",
      image: "Images",
      code: "Code",
      config: "Config",
      text: "Text",
    },
  };
  return labels[locale][modality];
};

const evidenceModalityCounts = (cards: EvidenceCard[]) => {
  const counts: Record<EvidenceModality, number> = {
    all: cards.length,
    image: 0,
    code: 0,
    config: 0,
    text: 0,
  };
  cards.forEach((card) => {
    counts[evidenceModality(card)] += 1;
  });
  return counts;
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
  const selectedRelation = usableRelations.find((relation) => relation.id === selectedRelationId);
  const nodeLabels = new Map<string, string>();
  const edgeRelations: ArchiveRelation[] = [];
  const seenNodePairKeys = new Set<string>();

  const addRelation = (
    relation: ArchiveRelation,
    options: { allowRepeatedPair?: boolean; requireNewNode?: boolean } = {},
  ) => {
    if (edgeRelations.length >= maxGraphEdges) return;
    const nodePairKey = `${relation.source}\u0000${relation.target}`;
    if (!options.allowRepeatedPair && seenNodePairKeys.has(nodePairKey)) return;
    const nextNodes = [relation.source, relation.target].filter((node) => !nodeLabels.has(node));
    if (options.requireNewNode && nextNodes.length === 0) return;
    const hasRoomForNodes = nodeLabels.size + nextNodes.length <= maxGraphNodes;
    const connectsVisibleNodes = nodeLabels.has(relation.source) && nodeLabels.has(relation.target);

    if (!hasRoomForNodes && !connectsVisibleNodes) return;

    nodeLabels.set(relation.source, relation.source);
    nodeLabels.set(relation.target, relation.target);
    edgeRelations.push(relation);
    seenNodePairKeys.add(nodePairKey);
  };

  if (selectedRelation) addRelation(selectedRelation, { allowRepeatedPair: true });
  rankedRelations.forEach((relation) => {
    if (relation.id !== selectedRelationId) addRelation(relation, { requireNewNode: true });
  });
  rankedRelations.forEach((relation) => {
    if (relation.id !== selectedRelationId) addRelation(relation);
  });
  rankedRelations.forEach((relation) => {
    if (relation.id !== selectedRelationId) addRelation(relation, { allowRepeatedPair: true });
  });

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
  isLoading,
  isSwitchingArchive,
  locale,
  onArchiveChange,
  onLocaleChange,
  onSearchGraph,
  selectedArchiveId,
}: {
  agentStatus: AgentStatus | null;
  archiveIds: string[];
  isLoading: boolean;
  isSwitchingArchive: boolean;
  locale: Locale;
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

const diagnosticNumber = (source: Record<string, unknown>, key: string) => {
  const value = source[key];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
};

const diagnosticObject = (source: Record<string, unknown>, key: string): Record<string, unknown> => {
  const value = source[key];
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
};

const diagnosticStringList = (value: unknown) =>
  Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];

function IngestionDiagnosticsPanel({
  diagnostics,
  locale,
}: {
  diagnostics: IngestionDiagnostics | null;
  locale: Locale;
}) {
  const labels = locale === "zh"
    ? {
        title: "摄取诊断",
        subtitle: "解释这个档案是怎样从 ZIP、扫描、抽取、多模态和 Hybrid RAG 建出来的。",
        unavailable: "当前档案还没有诊断报告。重新生成档案后会自动写入。",
        health: "健康度",
        upload: "ZIP 过滤",
        scan: "扫描",
        extraction: "结构抽取",
        images: "图片理解",
        hybrid: "Hybrid RAG",
        recommendations: "建议",
        kept: "保留",
        skipped: "跳过",
        total: "发现",
        entities: "实体",
        relations: "关系",
        evidence: "证据",
        treeSitter: "Tree-sitter",
        parsed: "解析",
        unavailableTree: "不可用",
        chunks: "索引块",
        fallback: "兜底",
      }
    : {
        title: "Ingestion diagnostics",
        subtitle: "Explains how this archive was built from ZIP filtering, scanning, extraction, multimodal evidence, and Hybrid RAG.",
        unavailable: "No diagnostics report is available for this archive yet. Regenerate it to write one.",
        health: "Health",
        upload: "ZIP filter",
        scan: "Scan",
        extraction: "Extraction",
        images: "Image understanding",
        hybrid: "Hybrid RAG",
        recommendations: "Recommendations",
        kept: "Kept",
        skipped: "Skipped",
        total: "Discovered",
        entities: "Entities",
        relations: "Relations",
        evidence: "Evidence",
        treeSitter: "Tree-sitter",
        parsed: "Parsed",
        unavailableTree: "Unavailable",
        chunks: "Chunks",
        fallback: "Fallback",
      };
  if (!diagnostics) {
    return (
      <section className="ingestion-diagnostics panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">{labels.health}</span>
            <h2>{labels.title}</h2>
          </div>
          <ShieldCheck size={18} />
        </div>
        <p className="empty-note">{labels.unavailable}</p>
      </section>
    );
  }

  const uploadSkipped = diagnosticObject(diagnostics.upload, "skipped_by_reason");
  const scanSkipped = diagnosticObject(diagnostics.scan, "skipped_by_reason");
  const extractionLanguages = diagnosticObject(diagnostics.extraction, "languages");
  const treeSitter = diagnosticObject(diagnostics.extraction, "tree_sitter");
  const hybridFallbacks = diagnosticStringList(diagnostics.hybrid_rag.fallback_reasons);
  const warnings = diagnostics.health.warnings ?? [];
  const languageRows = Object.entries(extractionLanguages).slice(0, 6);
  const healthScore = diagnostics.health.score ?? 0;

  return (
    <section className="ingestion-diagnostics panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{diagnostics.scan_profile}</span>
          <h2>{labels.title}</h2>
        </div>
        <span className={`diagnostic-score ${diagnostics.health.status ?? "review"}`}>
          {labels.health} {Math.round(healthScore)}
        </span>
      </div>
      <p>{labels.subtitle}</p>
      <div className="diagnostic-grid">
        <article>
          <strong>{labels.upload}</strong>
          <span>{labels.total}: {formatNumber(diagnosticNumber(diagnostics.upload, "total_zip_files"))}</span>
          <span>{labels.kept}: {formatNumber(diagnosticNumber(diagnostics.upload, "kept_files"))}</span>
          <span>{labels.skipped}: {formatNumber(diagnosticNumber(diagnostics.upload, "skipped_files"))}</span>
        </article>
        <article>
          <strong>{labels.scan}</strong>
          <span>{labels.total}: {formatNumber(diagnosticNumber(diagnostics.scan, "total_files_discovered"))}</span>
          <span>{labels.kept}: {formatNumber(diagnosticNumber(diagnostics.scan, "kept_files"))}</span>
          <span>{labels.skipped}: {formatNumber(diagnosticNumber(diagnostics.scan, "skipped_files"))}</span>
        </article>
        <article>
          <strong>{labels.extraction}</strong>
          <span>{labels.entities}: {formatNumber(diagnosticNumber(diagnostics.graph, "entities"))}</span>
          <span>{labels.relations}: {formatNumber(diagnosticNumber(diagnostics.graph, "relations"))}</span>
          <span>{labels.evidence}: {formatNumber(diagnosticNumber(diagnostics.graph, "evidence"))}</span>
        </article>
        <article>
          <strong>{labels.treeSitter}</strong>
          <span>{labels.total}: {formatNumber(diagnosticNumber(treeSitter, "files"))}</span>
          <span>{labels.parsed}: {formatNumber(diagnosticNumber(treeSitter, "parsed"))}</span>
          <span>{labels.unavailableTree}: {formatNumber(diagnosticNumber(treeSitter, "unavailable"))}</span>
        </article>
        <article>
          <strong>{labels.images}</strong>
          <span>{labels.evidence}: {formatNumber(diagnosticNumber(diagnostics.images, "evidence_cards"))}</span>
          <span>Vision: {formatNumber(diagnosticNumber(diagnostics.images, "vision_enabled_cards"))}</span>
          <span>{labels.fallback}: {formatNumber(diagnosticNumber(diagnostics.images, "fallback_cards"))}</span>
        </article>
        <article>
          <strong>{labels.hybrid}</strong>
          <span>{labels.chunks}: {formatNumber(diagnosticNumber(diagnostics.hybrid_rag, "indexed_chunks"))}</span>
          <span>Text: {formatNumber(diagnosticNumber(diagnostics.hybrid_rag, "text_chunks"))}</span>
          <span>Image: {formatNumber(diagnosticNumber(diagnostics.hybrid_rag, "image_chunks"))}</span>
        </article>
      </div>
      <div className="diagnostic-detail-grid">
        <DiagnosticReasonList locale={locale} title={locale === "zh" ? "ZIP 跳过原因" : "ZIP skip reasons"} reasons={uploadSkipped} />
        <DiagnosticReasonList locale={locale} title={locale === "zh" ? "扫描跳过原因" : "Scan skip reasons"} reasons={scanSkipped} />
        <div className="diagnostic-reason-list">
          <strong>{locale === "zh" ? "语言抽取" : "Language extraction"}</strong>
          {languageRows.length ? languageRows.map(([language, rawStats]) => {
            const stats = rawStats && typeof rawStats === "object" ? rawStats as Record<string, unknown> : {};
            return (
              <span key={language}>
                {language}: {formatNumber(diagnosticNumber(stats, "files"))} files / {formatNumber(diagnosticNumber(stats, "entities"))} entities
              </span>
            );
          }) : <span>{locale === "zh" ? "暂无语言统计" : "No language stats"}</span>}
        </div>
      </div>
      {warnings.length || hybridFallbacks.length ? (
        <div className="diagnostic-warning-row">
          {[...warnings, ...hybridFallbacks].slice(0, 5).map((warning) => (
            <span key={warning}>{warning}</span>
          ))}
        </div>
      ) : null}
      <div className="diagnostic-recommendations">
        <strong>{labels.recommendations}</strong>
        <ul>
          {diagnostics.recommendations.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function DiagnosticReasonList({
  locale,
  reasons,
  title,
}: {
  locale: Locale;
  reasons: Record<string, unknown>;
  title: string;
}) {
  const rows = Object.entries(reasons).slice(0, 6);
  return (
    <div className="diagnostic-reason-list">
      <strong>{title}</strong>
      {rows.length ? rows.map(([reason, count]) => (
        <span key={reason}>{reason}: {formatNumber(typeof count === "number" ? count : 0)}</span>
      )) : <span>{locale === "zh" ? "暂无" : "None"}</span>}
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
    { id: "universe" as AppPage, label: copy[locale].universePage, icon: Boxes },
    { id: "tasks" as AppPage, label: copy[locale].taskCenterPage, icon: Command },
    { id: "system" as AppPage, label: copy[locale].systemPage, icon: ShieldCheck },
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

function DemoGuidePanel({
  activePage,
  agentReport,
  archiveDraft,
  archiveIds,
  isCreatingArchive,
  isLoadingUniverse,
  isRunningAgentReport,
  isRunningUniverseAgent,
  isRunningUniverseDiff,
  knowledgeUniverse,
  locale,
  graphVisited,
  onCreateArchive,
  onGoPage,
  onOpenUpload,
  onRunAgentReport,
  onRunFirstDiff,
  onRunUniverseAgent,
  selectedFileName,
  universeDiffReport,
}: {
  activePage: AppPage;
  agentReport: ProjectAgentReport | null;
  archiveDraft: ArchiveDraft | null;
  archiveIds: string[];
  isCreatingArchive: boolean;
  isLoadingUniverse: boolean;
  isRunningAgentReport: boolean;
  isRunningUniverseAgent: boolean;
  isRunningUniverseDiff: boolean;
  knowledgeUniverse: ProjectKnowledgeUniverse | null;
  locale: Locale;
  graphVisited: boolean;
  onCreateArchive: () => void;
  onGoPage: (page: AppPage) => void;
  onOpenUpload: () => void;
  onRunAgentReport: () => void;
  onRunFirstDiff: () => void;
  onRunUniverseAgent: () => void;
  selectedFileName: string;
  universeDiffReport: ProjectArchitectureDiffReport | null;
}) {
  const t = copy[locale];
  const hasArchive = Boolean(archiveDraft);
  const hasTwoArchives = archiveIds.length >= 2;
  const steps = [
    { id: "upload", label: t.demoStepUpload, complete: Boolean(selectedFileName || archiveDraft) },
    { id: "archive", label: t.demoStepArchive, complete: hasArchive },
    { id: "graph", label: t.demoStepGraph, complete: hasArchive && graphVisited },
    { id: "agent", label: t.demoStepAgent, complete: Boolean(agentReport) },
    { id: "universe", label: t.demoStepUniverse, complete: Boolean(knowledgeUniverse) },
    { id: "diff", label: t.demoStepDiff, complete: Boolean(universeDiffReport) },
  ];
  const completedCount = steps.filter((step) => step.complete).length;
  const progress = Math.round((completedCount / steps.length) * 100);
  let nextLabel = String(t.demoDone);
  let nextIcon: ReactNode = <ShieldCheck size={14} />;
  let nextAction: () => void = () => undefined;
  let disabled = false;

  if (!selectedFileName && !hasArchive) {
    nextLabel = String(t.demoActionSelectZip);
    nextIcon = <Upload size={14} />;
    nextAction = onOpenUpload;
  } else if (!hasArchive) {
    nextLabel = isCreatingArchive ? String(t.creatingArchive) : String(t.demoActionCreateArchive);
    nextIcon = <FolderInput size={14} />;
    nextAction = onCreateArchive;
    disabled = isCreatingArchive;
  } else if (activePage !== "graph") {
    nextLabel = String(t.demoActionOpenGraph);
    nextIcon = <Network size={14} />;
    nextAction = () => onGoPage("graph");
  } else if (!agentReport) {
    nextLabel = isRunningAgentReport ? String(t.agentReportRunning) : String(t.demoActionRunAgent);
    nextIcon = <Sparkles size={14} />;
    nextAction = () => {
      onGoPage("agents");
      onRunAgentReport();
    };
    disabled = isRunningAgentReport;
  } else if (!knowledgeUniverse) {
    nextLabel = isLoadingUniverse ? String(t.loadingUniverse) : String(t.demoActionOpenUniverse);
    nextIcon = <Boxes size={14} />;
    nextAction = () => onGoPage("universe");
    disabled = isLoadingUniverse;
  } else if (hasTwoArchives && !universeDiffReport) {
    nextLabel = isRunningUniverseDiff ? String(t.loadingUniverse) : String(t.demoActionRunDiff);
    nextIcon = <GitBranch size={14} />;
    nextAction = () => {
      onGoPage("universe");
      onRunFirstDiff();
    };
    disabled = isRunningUniverseDiff;
  } else if (!hasTwoArchives) {
    nextLabel = isRunningUniverseAgent ? String(t.loadingUniverse) : String(t.demoActionRunUniverseAgent);
    nextIcon = <Command size={14} />;
    nextAction = () => {
      onGoPage("universe");
      onRunUniverseAgent();
    };
    disabled = isRunningUniverseAgent;
  }

  return (
    <section className="demo-guide panel" aria-label={String(t.demoFlow)}>
      <div className="demo-guide-main">
        <div>
          <span className="eyebrow">{t.demoFlow}</span>
          <strong>{t.demoNext}</strong>
          <p>{t.demoFlowCopy}</p>
        </div>
        <button className="primary-button compact" disabled={disabled} onClick={nextAction} type="button">
          {nextIcon}
          {nextLabel}
        </button>
      </div>
      <div className="demo-guide-progress">
        <span>{t.demoProgress}: {progress}%</span>
        <progress max="100" value={progress} />
      </div>
      <div className="demo-guide-steps">
        {steps.map((step, index) => (
          <span className={step.complete ? "is-complete" : ""} key={step.id}>
            <CircleDot size={12} />
            {index + 1}. {String(step.label)}
          </span>
        ))}
      </div>
    </section>
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

function EmptyGeneratedArchiveState({
  archiveDraft,
  locale,
}: {
  archiveDraft: ArchiveDraft;
  locale: Locale;
}) {
  const t = copy[locale];
  return (
    <section className="empty-archive generated-archive-empty">
      <div className="empty-icon">
        <Archive size={24} />
      </div>
      <div>
        <span className="eyebrow">{archiveDraft.projectId}</span>
        <h2>{t.emptyGeneratedArchiveTitle}</h2>
        <p>{t.emptyGeneratedArchiveCopy}</p>
      </div>
      <div className="mission-task-metrics">
        <span>{(t.metrics as Record<string, string>).entities}: {formatNumber(archiveDraft.metrics.entities)}</span>
        <span>{(t.metrics as Record<string, string>).relations}: {formatNumber(archiveDraft.metrics.relations)}</span>
        <span>{(t.metrics as Record<string, string>).evidence}: {formatNumber(archiveDraft.metrics.evidence)}</span>
      </div>
    </section>
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
    visibleGraph.selectedRelation
      ? locale === "zh"
        ? `聚焦显示 ${formatNumber(visibleGraph.nodes.length)} 个节点 / ${formatNumber(visibleGraph.edges.length)} 条关系，当前匹配 ${formatNumber(visibleGraph.totalRelations)} 条`
        : `Focused sample: ${formatNumber(visibleGraph.nodes.length)} nodes / ${formatNumber(visibleGraph.edges.length)} relations from ${formatNumber(visibleGraph.totalRelations)} matches`
      : locale === "zh"
        ? `抽样显示 ${formatNumber(visibleGraph.nodes.length)} 个节点 / ${formatNumber(visibleGraph.edges.length)} 条关系，当前匹配 ${formatNumber(visibleGraph.totalRelations)} 条`
        : `Sampled ${formatNumber(visibleGraph.nodes.length)} nodes / ${formatNumber(visibleGraph.edges.length)} relations from ${formatNumber(visibleGraph.totalRelations)} matches`;
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
                <button className={`modality-${evidenceModality(card)}`} key={card.id} onClick={() => onEvidenceSelect(card)} type="button">
                  <span>{evidenceModalityLabel(evidenceModality(card), locale)}{evidenceIsHybrid(card) ? " · RAG" : ""}</span>
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
  const [selectedModality, setSelectedModality] = useState<EvidenceModality>("all");
  const modalityCounts = useMemo(() => evidenceModalityCounts(visibleCards), [visibleCards]);
  const imageCards = visibleCards.filter((card) => evidenceModality(card) === "image");
  const filteredCards = visibleCards
    .filter((card) => selectedModality === "all" || evidenceModality(card) === selectedModality)
    .sort((left, right) => {
      const leftImage = evidenceModality(left) === "image" ? 1 : 0;
      const rightImage = evidenceModality(right) === "image" ? 1 : 0;
      if (leftImage !== rightImage) return rightImage - leftImage;
      const leftHybrid = evidenceIsHybrid(left) ? 1 : 0;
      const rightHybrid = evidenceIsHybrid(right) ? 1 : 0;
      if (leftHybrid !== rightHybrid) return rightHybrid - leftHybrid;
      return right.confidence - left.confidence;
    });
  useEffect(() => {
    setSelectedModality("all");
  }, [hall.id]);
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
      {imageCards.length ? (
        <div className="image-evidence-strip" aria-label={locale === "zh" ? "图片证据" : "Image evidence"}>
          {imageCards.slice(0, 3).map((card) => (
            <button key={card.id} onClick={() => onEvidenceSelect(card)} type="button">
              {card.assetUrl ? <img src={card.assetUrl} alt={evidenceTitle(card, locale)} loading="lazy" /> : null}
              <span>{compactGraphLabel(evidenceTitle(card, locale), 42)}</span>
            </button>
          ))}
        </div>
      ) : null}
      <div className="evidence-modality-tabs" aria-label={locale === "zh" ? "证据类型" : "Evidence modality"}>
        {(["all", "image", "code", "config", "text"] as EvidenceModality[]).map((modality) => (
          <button
            className={selectedModality === modality ? "is-active" : ""}
            disabled={modalityCounts[modality] === 0}
            key={modality}
            onClick={() => setSelectedModality(modality)}
            type="button"
          >
            {evidenceModalityLabel(modality, locale)}
            <span>{formatNumber(modalityCounts[modality])}</span>
          </button>
        ))}
      </div>
      <div className="evidence-list">
        {filteredCards.length ? (
          filteredCards.slice(0, 8).map((card) => (
            <button
              className={`evidence-card ${card.id === selectedEvidenceId ? "is-active" : ""} modality-${evidenceModality(card)}`}
              key={card.id}
              onClick={() => onEvidenceSelect(card)}
              type="button"
            >
              <div className="evidence-meta">
                <span>{evidenceModalityLabel(evidenceModality(card), locale)} · {evidenceSourceType(card, locale)}</span>
                <span>{evidenceLineRange(card, locale)}</span>
              </div>
              <div className="evidence-badges">
                {evidenceIsHybrid(card) ? <span>Hybrid RAG</span> : null}
                {card.metadata?.vision_enabled ? <span>Vision</span> : null}
                {card.metadata?.vision_error ? <span>{locale === "zh" ? "视觉兜底" : "Vision fallback"}</span> : null}
              </div>
              <h3>{evidenceTitle(card, locale)}</h3>
              <code>{card.sourcePath}</code>
              {card.assetUrl ? (
                <img
                  className="evidence-image-preview"
                  src={card.assetUrl}
                  alt={evidenceTitle(card, locale)}
                  loading="lazy"
                />
              ) : null}
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
  const citedModalityCounts = evidenceModalityCounts(citedEvidence);
  const citedImageEvidence = citedEvidence.filter((card) => evidenceModality(card) === "image");
  const hybridRagMetadata = report?.metadata?.hybrid_rag;
  const reportModalityCounts = report?.metadata?.evidence_modalities ?? {};
  const hybridHitCount = hybridRagMetadata?.result_count ?? 0;

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
            <span>Hybrid RAG: {formatNumber(hybridHitCount)}</span>
            <span>{evidenceModalityLabel("image", locale)}: {formatNumber(report.metadata?.cited_image_evidence_count ?? citedModalityCounts.image)}</span>
          </div>
          <div className="agent-report-modality-row">
            {(["image", "code", "config", "text"] as const).map((modality) => (
              <span key={modality}>
                {evidenceModalityLabel(modality, locale)}: {formatNumber(Number(reportModalityCounts[modality] ?? citedModalityCounts[modality] ?? 0))}
              </span>
            ))}
            {hybridRagMetadata?.error ? <span>{locale === "zh" ? "RAG 错误" : "RAG error"}: {hybridRagMetadata.error}</span> : null}
          </div>
          {citedImageEvidence.length ? (
            <div className="agent-report-image-evidence">
              {citedImageEvidence.slice(0, 3).map((card) => (
                <article key={card.id}>
                  {card.assetUrl ? <img src={card.assetUrl} alt={evidenceTitle(card, locale)} loading="lazy" /> : null}
                  <div>
                    <span>{card.metadata?.vision_enabled ? "Vision" : locale === "zh" ? "图片兜底" : "Image fallback"}</span>
                    <strong>{evidenceTitle(card, locale)}</strong>
                    <code>{card.sourcePath}</code>
                  </div>
                </article>
              ))}
            </div>
          ) : null}
          {citedEvidence.length ? (
            <div className="agent-report-evidence">
              {citedEvidence.slice(0, 4).map((card) => (
                <article className={`modality-${evidenceModality(card)}`} key={card.id}>
                  <span>
                    {evidenceModalityLabel(evidenceModality(card), locale)} · {evidenceSourceType(card, locale)} · {evidenceLineRange(card, locale)}
                    {evidenceIsHybrid(card) ? " · Hybrid RAG" : ""}
                  </span>
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

const REACT_MISSION_POLL_DELAY_MS = 1000;
const REACT_MISSION_POLL_GRACE_ATTEMPTS = 8;

const reactMissionPollAttempts = (mission: AgentMission) => {
  const timeoutSeconds = Number(mission.budget.timeout_seconds);
  if (!Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0) return 90 + REACT_MISSION_POLL_GRACE_ATTEMPTS;
  return Math.ceil((timeoutSeconds * 1000) / REACT_MISSION_POLL_DELAY_MS) + REACT_MISSION_POLL_GRACE_ATTEMPTS;
};

const wait = (delayMs: number) => new Promise<void>((resolve) => window.setTimeout(resolve, delayMs));

const summarizeMissionItems = (items: Record<string, unknown>[], locale: Locale) => {
  if (!items.length) return locale === "zh" ? "无" : "None";
  return items
    .slice(0, 2)
    .map((item) => String(item.title ?? item.summary ?? item.detail ?? item.description ?? JSON.stringify(item)))
    .join(" · ");
};

const savedGraphRoutesKey = (projectId: string) => `twinmind:graph-routes:${projectId}`;

const loadSavedGraphRoutes = (projectId: string): SavedGraphRoute[] => {
  try {
    const raw = window.localStorage.getItem(savedGraphRoutesKey(projectId));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SavedGraphRoute[];
    return Array.isArray(parsed) ? parsed.slice(0, 12) : [];
  } catch {
    return [];
  }
};

const saveGraphRoutes = (projectId: string, routes: SavedGraphRoute[]) => {
  window.localStorage.setItem(savedGraphRoutesKey(projectId), JSON.stringify(routes.slice(0, 12)));
};

const graphWorkspaceStateKey = (projectId: string) => `twinmind:graph-workspace:${projectId}`;
const graphReviewResolvedKey = (projectId: string) => `twinmind:graph-review-resolved:${projectId}`;
const graphCurationStateKey = (projectId: string) => `twinmind:graph-curation:${projectId}`;

const emptyGraphCurationState = (): GraphCurationState => ({
  importantEntityIds: [],
  hiddenRelationIds: [],
  mergeCandidates: [],
});

const defaultGraphWorkspaceState = (archiveDraft: ArchiveDraft): GraphWorkspaceState => ({
  hallId: archiveDraft.halls[0]?.id ?? null,
  focusEntityId: null,
  depth: 1,
  viewMode: "cluster",
  panelMode: "balanced",
  searchQuery: "",
  nodeTypes: [],
  relationTypes: [],
  focusPreset: "all",
});

const normalizeGraphWorkspaceState = (
  archiveDraft: ArchiveDraft,
  state: Partial<GraphWorkspaceState> | null,
): GraphWorkspaceState => {
  const fallback = defaultGraphWorkspaceState(archiveDraft);
  const validHallIds = new Set(archiveDraft.halls.map((hall) => hall.id));
  const nextHallId =
    state?.hallId === null || (state?.hallId && validHallIds.has(state.hallId)) ? state.hallId : fallback.hallId;
  return {
    hallId: nextHallId ?? null,
    focusEntityId: typeof state?.focusEntityId === "string" ? state.focusEntityId : null,
    depth: state?.depth === 2 ? 2 : 1,
    viewMode: state?.viewMode === "hierarchy" ? "hierarchy" : "cluster",
    panelMode: state?.panelMode === "map" || state?.panelMode === "inspect" ? state.panelMode : "balanced",
    searchQuery: typeof state?.searchQuery === "string" ? state.searchQuery.slice(0, 160) : "",
    nodeTypes: Array.isArray(state?.nodeTypes)
      ? state.nodeTypes.filter((item) => typeof item === "string").slice(0, 12)
      : [],
    relationTypes: Array.isArray(state?.relationTypes)
      ? state.relationTypes.filter((item) => typeof item === "string").slice(0, 12)
      : [],
    focusPreset:
      state?.focusPreset === "entry" ||
      state?.focusPreset === "config" ||
      state?.focusPreset === "api" ||
      state?.focusPreset === "dependency"
        ? state.focusPreset
        : "all",
  };
};

const loadGraphWorkspaceState = (archiveDraft: ArchiveDraft): GraphWorkspaceState => {
  try {
    const raw = window.localStorage.getItem(graphWorkspaceStateKey(archiveDraft.projectId));
    if (!raw) return defaultGraphWorkspaceState(archiveDraft);
    return normalizeGraphWorkspaceState(archiveDraft, JSON.parse(raw) as Partial<GraphWorkspaceState>);
  } catch {
    return defaultGraphWorkspaceState(archiveDraft);
  }
};

const saveGraphWorkspaceState = (projectId: string, state: GraphWorkspaceState) => {
  window.localStorage.setItem(graphWorkspaceStateKey(projectId), JSON.stringify(state));
};

const loadGraphReviewResolvedIds = (projectId: string): string[] => {
  try {
    const raw = window.localStorage.getItem(graphReviewResolvedKey(projectId));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as string[];
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === "string").slice(0, 200) : [];
  } catch {
    return [];
  }
};

const saveGraphReviewResolvedIds = (projectId: string, ids: string[]) => {
  window.localStorage.setItem(graphReviewResolvedKey(projectId), JSON.stringify(ids.slice(0, 200)));
};

const loadGraphCurationState = (projectId: string): GraphCurationState => {
  try {
    const raw = window.localStorage.getItem(graphCurationStateKey(projectId));
    if (!raw) return emptyGraphCurationState();
    const parsed = JSON.parse(raw) as Partial<GraphCurationState>;
    return {
      importantEntityIds: Array.isArray(parsed.importantEntityIds)
        ? parsed.importantEntityIds.filter((id) => typeof id === "string").slice(0, 500)
        : [],
      hiddenRelationIds: Array.isArray(parsed.hiddenRelationIds)
        ? parsed.hiddenRelationIds.filter((id) => typeof id === "string").slice(0, 500)
        : [],
      mergeCandidates: Array.isArray(parsed.mergeCandidates)
        ? parsed.mergeCandidates
            .filter((candidate): candidate is GraphMergeCandidate =>
              Boolean(
                candidate &&
                  typeof candidate.id === "string" &&
                  typeof candidate.label === "string" &&
                  Array.isArray(candidate.entityIds) &&
                  typeof candidate.createdAt === "string",
              ),
            )
            .slice(0, 100)
        : [],
    };
  } catch {
    return emptyGraphCurationState();
  }
};

const saveGraphCurationState = (projectId: string, state: GraphCurationState) => {
  window.localStorage.setItem(
    graphCurationStateKey(projectId),
    JSON.stringify({
      importantEntityIds: [...new Set(state.importantEntityIds)].slice(0, 500),
      hiddenRelationIds: [...new Set(state.hiddenRelationIds)].slice(0, 500),
      mergeCandidates: state.mergeCandidates.slice(0, 100),
    }),
  );
};

const graphFocusPresetOptions = (locale: Locale) => [
  { id: "all" as GraphFocusPreset, label: String(copy[locale].graphPresetAll), icon: Network },
  { id: "entry" as GraphFocusPreset, label: String(copy[locale].graphPresetEntry), icon: CircleDot },
  { id: "config" as GraphFocusPreset, label: String(copy[locale].graphPresetConfig), icon: Braces },
  { id: "api" as GraphFocusPreset, label: String(copy[locale].graphPresetApi), icon: Command },
  { id: "dependency" as GraphFocusPreset, label: String(copy[locale].graphPresetDependency), icon: GitBranch },
];

const graphPresetNodeTypes = (
  preset: GraphFocusPreset,
  availableTypes: string[],
) => {
  const match = (...patterns: RegExp[]) =>
    availableTypes.filter((type) => patterns.some((pattern) => pattern.test(type.toLowerCase())));
  if (preset === "entry") return match(/file/, /function/, /class/, /module/);
  if (preset === "config") return match(/config/, /setting/, /env/, /yaml/, /toml/, /json/, /property/);
  if (preset === "api") return match(/function/, /class/, /interface/, /route/, /endpoint/, /controller/, /service/);
  if (preset === "dependency") return match(/file/, /module/, /package/, /dependency/, /import/);
  return [];
};

const graphPresetRelationTypes = (
  preset: GraphFocusPreset,
  availableTypes: string[],
) => {
  const match = (...patterns: RegExp[]) =>
    availableTypes.filter((type) => patterns.some((pattern) => pattern.test(type.toLowerCase())));
  if (preset === "entry") return match(/define/, /call/, /start/, /entry/, /contain/);
  if (preset === "config") return match(/config/, /read/, /use/, /depend/, /set/);
  if (preset === "api") return match(/call/, /route/, /expose/, /implement/, /define/, /use/);
  if (preset === "dependency") return match(/import/, /depend/, /use/, /call/, /require/);
  return [];
};

function GraphExplorerPage({
  archiveDraft,
  graphWorkspaceReport,
  locale,
  missionOverlay,
  onOpenMission,
}: {
  archiveDraft: ArchiveDraft;
  graphWorkspaceReport: GraphWorkspaceReport | null;
  locale: Locale;
  missionOverlay: MissionGraphOverlay | null;
  onOpenMission: () => void;
}) {
  const t = copy[locale];
  const initialWorkspaceState = loadGraphWorkspaceState(archiveDraft);
  const [summary, setSummary] = useState<GraphSummary | null>(null);
  const [neighborhood, setNeighborhood] = useState<GraphNeighborhood | null>(null);
  const [focusedEntityId, setFocusedEntityId] = useState<string | null>(initialWorkspaceState.focusEntityId);
  const [selectedRelationId, setSelectedRelationId] = useState<string | null>(null);
  const [selectedHallId, setSelectedHallId] = useState<string | null>(initialWorkspaceState.hallId);
  const [depth, setDepth] = useState(initialWorkspaceState.depth);
  const [graphViewMode, setGraphViewMode] = useState<GraphViewMode>(initialWorkspaceState.viewMode);
  const [graphPanelMode, setGraphPanelMode] = useState<GraphPanelMode>(initialWorkspaceState.panelMode);
  const [selectedNodeTypes, setSelectedNodeTypes] = useState<string[]>(initialWorkspaceState.nodeTypes);
  const [selectedRelationTypes, setSelectedRelationTypes] = useState<string[]>(initialWorkspaceState.relationTypes);
  const [graphFocusPreset, setGraphFocusPreset] = useState<GraphFocusPreset>(initialWorkspaceState.focusPreset);
  const [savedRoutes, setSavedRoutes] = useState<SavedGraphRoute[]>(() => loadSavedGraphRoutes(archiveDraft.projectId));
  const [resolvedReviewIds, setResolvedReviewIds] = useState<string[]>(() => loadGraphReviewResolvedIds(archiveDraft.projectId));
  const [curationState, setCurationState] = useState<GraphCurationState>(() => loadGraphCurationState(archiveDraft.projectId));
  const [isLeftOpen, setIsLeftOpen] = useState(true);
  const [isRightOpen, setIsRightOpen] = useState(true);
  const [isSummaryLoading, setIsSummaryLoading] = useState(false);
  const [isNeighborhoodLoading, setIsNeighborhoodLoading] = useState(false);
  const [graphSearchQuery, setGraphSearchQuery] = useState(initialWorkspaceState.searchQuery);
  const [graphSearchResults, setGraphSearchResults] = useState<GraphSearchResult[]>([]);
  const [isGraphSearchLoading, setIsGraphSearchLoading] = useState(false);
  const graphSearchAnchorRef = useRef<HTMLLabelElement | null>(null);
  const [graphSearchMenuStyle, setGraphSearchMenuStyle] = useState<CSSProperties | undefined>();
  const [graphSearchError, setGraphSearchError] = useState("");
  const [summaryError, setSummaryError] = useState("");
  const [neighborhoodError, setNeighborhoodError] = useState("");
  const graphProjectIdRef = useRef(archiveDraft.projectId);

  useEffect(() => {
    graphProjectIdRef.current = archiveDraft.projectId;
    const nextWorkspaceState = loadGraphWorkspaceState(archiveDraft);
    setSelectedHallId(nextWorkspaceState.hallId);
    setFocusedEntityId(nextWorkspaceState.focusEntityId);
    setSelectedRelationId(null);
    setDepth(nextWorkspaceState.depth);
    setGraphSearchQuery(nextWorkspaceState.searchQuery);
    setGraphSearchResults([]);
    setGraphSearchError("");
    setGraphViewMode(nextWorkspaceState.viewMode);
    setGraphPanelMode(nextWorkspaceState.panelMode);
    setSelectedNodeTypes(nextWorkspaceState.nodeTypes);
    setSelectedRelationTypes(nextWorkspaceState.relationTypes);
    setGraphFocusPreset(nextWorkspaceState.focusPreset);
    setSavedRoutes(loadSavedGraphRoutes(archiveDraft.projectId));
    setResolvedReviewIds(loadGraphReviewResolvedIds(archiveDraft.projectId));
    setCurationState(loadGraphCurationState(archiveDraft.projectId));
  }, [archiveDraft.projectId, archiveDraft.halls]);

  useEffect(() => {
    saveGraphWorkspaceState(archiveDraft.projectId, {
      hallId: selectedHallId,
      focusEntityId: focusedEntityId,
      depth,
      viewMode: graphViewMode,
      panelMode: graphPanelMode,
      searchQuery: graphSearchQuery,
      nodeTypes: selectedNodeTypes,
      relationTypes: selectedRelationTypes,
      focusPreset: graphFocusPreset,
    });
  }, [archiveDraft.projectId, depth, focusedEntityId, graphFocusPreset, graphPanelMode, graphSearchQuery, graphViewMode, selectedHallId, selectedNodeTypes, selectedRelationTypes]);

  useEffect(() => {
    let isMounted = true;
    fetchGraphCuration(archiveDraft.projectId)
      .then((serverState) => {
        if (!isMounted) return;
        const nextState = {
          importantEntityIds: serverState.importantEntityIds,
          hiddenRelationIds: serverState.hiddenRelationIds,
          mergeCandidates: serverState.mergeCandidates,
        };
        setCurationState(nextState);
        saveGraphCurationState(archiveDraft.projectId, nextState);
      })
      .catch(() => {
        // Keep the local curation layer usable when the API is offline or an old backend is running.
      });
    return () => {
      isMounted = false;
    };
  }, [archiveDraft.projectId]);

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
      relationTypes: selectedRelationTypes,
      nodeLimit: depth === 1 ? 120 : 160,
      relationLimit: depth === 1 ? 180 : 260,
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
  }, [archiveDraft.projectId, selectedHallId, focusedEntityId, depth, selectedRelationTypes]);

  const hiddenRelationIds = useMemo(() => new Set(curationState.hiddenRelationIds), [curationState.hiddenRelationIds]);
  const importantEntityIds = useMemo(() => new Set(curationState.importantEntityIds), [curationState.importantEntityIds]);
  const selectedNodeTypeSet = useMemo(() => new Set(selectedNodeTypes), [selectedNodeTypes]);
  const visibleNeighborhood = useMemo<GraphNeighborhood | null>(() => {
    if (!neighborhood) return null;
    const nodes = selectedNodeTypeSet.size
      ? neighborhood.nodes.filter((node) => selectedNodeTypeSet.has(node.type))
      : neighborhood.nodes;
    const visibleNodeIds = new Set(nodes.map((node) => node.id));
    return {
      ...neighborhood,
      nodes,
      relations: neighborhood.relations.filter(
        (relation) =>
          !hiddenRelationIds.has(relation.id) &&
          visibleNodeIds.has(relation.source_id) &&
          visibleNodeIds.has(relation.target_id),
      ),
      evidence_ids: neighborhood.evidence_ids,
    };
  }, [hiddenRelationIds, neighborhood, selectedNodeTypeSet]);
  const selectedRelation =
    visibleNeighborhood?.relations.find((relation) => relation.id === selectedRelationId) ?? null;
  const focusedNode =
    visibleNeighborhood?.nodes.find((node) => node.id === focusedEntityId) ?? null;
  const nodeById = useMemo(
    () => new Map(visibleNeighborhood?.nodes.map((node) => [node.id, node]) ?? []),
    [visibleNeighborhood],
  );
  const graphSearchMatchedEntityIds = useMemo(
    () => new Set(graphSearchResults.map((result) => result.entity_id)),
    [graphSearchResults],
  );
  const availableNodeTypes = useMemo(() => {
    const counts = new Map<string, number>();
    (neighborhood?.nodes ?? []).forEach((node) => {
      counts.set(node.type, (counts.get(node.type) ?? 0) + 1);
    });
    return [...counts.entries()]
      .map(([type, count]) => ({ type, count }))
      .sort((left, right) => right.count - left.count || left.type.localeCompare(right.type))
      .slice(0, 10);
  }, [neighborhood]);
  const archiveRelationTypes = useMemo(() => {
    const counts = new Map<string, number>();
    archiveDraft.relations
      .filter((relation) => !selectedHallId || relation.hallIds?.includes(selectedHallId) || relation.hall === selectedHallId)
      .forEach((relation) => {
        counts.set(relation.type, (counts.get(relation.type) ?? 0) + 1);
      });
    return [...counts.entries()]
      .map(([type, count]) => ({ type, count }))
      .sort((left, right) => right.count - left.count || left.type.localeCompare(right.type))
      .slice(0, 12);
  }, [archiveDraft.relations, selectedHallId]);
  const availableNodeTypeNames = useMemo(
    () => availableNodeTypes.map((item) => item.type),
    [availableNodeTypes],
  );
  const availableRelationTypeNames = useMemo(
    () => archiveRelationTypes.map((item) => item.type),
    [archiveRelationTypes],
  );
  const visibleNodeCount = visibleNeighborhood?.nodes.length ?? 0;
  const visibleRelationCount = visibleNeighborhood?.relations.length ?? 0;
  const nodeTypeClusters = useMemo(() => {
    const counts = new Map<string, number>();
    (visibleNeighborhood?.nodes ?? []).forEach((node) => {
      const label = typeLabel(node.type, locale);
      counts.set(label, (counts.get(label) ?? 0) + 1);
    });
    return [...counts.entries()]
      .map(([label, count]) => ({ label, count }))
      .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label))
      .slice(0, 8);
  }, [locale, visibleNeighborhood]);
  const relationTypeClusters = useMemo(() => {
    const counts = new Map<string, number>();
    (visibleNeighborhood?.relations ?? []).forEach((relation) => {
      counts.set(relation.type, (counts.get(relation.type) ?? 0) + 1);
    });
    return [...counts.entries()]
      .map(([label, count]) => ({ label, count }))
      .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label))
      .slice(0, 8);
  }, [visibleNeighborhood]);
  const reviewQueue = useMemo(() => {
    if (!visibleNeighborhood) return [];
    const resolvedIds = new Set(resolvedReviewIds);
    const mergeCandidateIds = new Set(curationState.mergeCandidates.flatMap((candidate) => candidate.entityIds));
    const items: GraphReviewItem[] = [];
    const nodesByLabel = new Map<string, GraphExplorerNode[]>();
    visibleNeighborhood.nodes.forEach((node) => {
      const labelKey = node.label.trim().toLowerCase();
      if (!labelKey) return;
      nodesByLabel.set(labelKey, [...(nodesByLabel.get(labelKey) ?? []), node]);
    });
    nodesByLabel.forEach((nodesWithLabel, labelKey) => {
      if (nodesWithLabel.length < 2) return;
      const firstNode = nodesWithLabel[0];
      items.push({
        id: `duplicate:${labelKey}`,
        kind: "duplicate",
        title: firstNode.label,
        reason:
          locale === "zh"
            ? `当前邻域里有 ${nodesWithLabel.length} 个同名实体，建议确认是否需要合并。`
            : `${nodesWithLabel.length} visible entities share this label. Confirm whether they should be merged.`,
        targetEntityId: firstNode.id,
        relationId: null,
        relatedEntityIds: nodesWithLabel.map((node) => node.id),
      });
    });
    visibleNeighborhood.relations
      .filter((relation) => relation.weight < 0.55 || relation.evidence_ids.length === 0)
      .sort((left, right) => left.weight - right.weight || left.evidence_ids.length - right.evidence_ids.length)
      .slice(0, 8)
      .forEach((relation) => {
        const source = nodeById.get(relation.source_id);
        const target = nodeById.get(relation.target_id);
        items.push({
          id: `relation:${relation.id}`,
          kind: "weak_relation",
          title: `${source?.label ?? relation.source_id} -> ${target?.label ?? relation.target_id}`,
          reason:
            relation.evidence_ids.length === 0
              ? locale === "zh"
                ? "这条关系没有直接证据引用。"
                : "This relation has no direct evidence references."
              : locale === "zh"
                ? `关系权重较低：${relation.weight}`
                : `Low relation weight: ${relation.weight}`,
          targetEntityId: relation.source_id,
          relationId: relation.id,
          relatedEntityIds: [relation.source_id, relation.target_id],
        });
      });
    visibleNeighborhood.nodes
      .filter((node) => !importantEntityIds.has(node.id))
      .filter((node) => node.evidence_ids.length === 0 || (node.importance < 0.18 && node.degree <= 1))
      .sort((left, right) => left.evidence_ids.length - right.evidence_ids.length || left.degree - right.degree)
      .slice(0, 8)
      .forEach((node) => {
        items.push({
          id: `node:${node.id}`,
          kind: "thin_evidence",
          title: node.label,
          reason:
            node.evidence_ids.length === 0
              ? locale === "zh"
                ? "这个实体没有直接证据卡。"
                : "This entity has no direct evidence card."
              : locale === "zh"
                ? "这个实体连接少且重要度较低。"
                : "This entity has low degree and low importance.",
          targetEntityId: node.id,
          relationId: null,
          relatedEntityIds: [node.id],
        });
      });
    return items
      .filter((item) => !resolvedIds.has(item.id))
      .filter((item) => !item.relatedEntityIds.some((entityId) => mergeCandidateIds.has(entityId)) || item.kind !== "duplicate")
      .slice(0, 12);
  }, [curationState.mergeCandidates, importantEntityIds, locale, nodeById, resolvedReviewIds, visibleNeighborhood]);
  const visibleError = neighborhoodError || summaryError;
  const statusText = visibleError
    ? visibleError
    : locale === "zh"
      ? `显示 ${formatNumber(visibleNodeCount)} 个节点 / ${formatNumber(visibleRelationCount)} 条关系`
      : `Showing ${formatNumber(visibleNodeCount)} nodes / ${formatNumber(visibleRelationCount)} relations`;
  const selectGraphSearchResult = (result: GraphSearchResult) => {
    const nextHallId = result.hall_ids.length ? result.hall_ids[0] : null;
    setSelectedHallId(nextHallId);
    setFocusedEntityId(result.entity_id);
    setSelectedRelationId(null);
    setDepth(2);
    setGraphPanelMode("map");
    setGraphFocusPreset("all");
    setSelectedNodeTypes([]);
    setSelectedRelationTypes([]);
    setGraphSearchQuery("");
    setGraphSearchResults([]);
    setGraphSearchError("");
    setIsRightOpen(true);
    setSavedRoutes((currentRoutes) => {
      const route: SavedGraphRoute = {
        id: `${Date.now()}-search-${result.entity_id}`,
        title: result.label,
        projectId: archiveDraft.projectId,
        hallId: nextHallId,
        focusEntityId: result.entity_id,
        depth: 2,
        viewMode: graphViewMode,
        panelMode: "map",
        nodeTypes: [],
        relationTypes: [],
        focusPreset: "all",
        source: "search",
        createdAt: new Date().toISOString(),
      };
      const nextRoutes = [
        route,
        ...currentRoutes.filter((item) => item.focusEntityId !== route.focusEntityId || item.hallId !== route.hallId),
      ].slice(0, 12);
      saveGraphRoutes(archiveDraft.projectId, nextRoutes);
      return nextRoutes;
    });
  };
  const restoreSavedRoute = (route: SavedGraphRoute) => {
    setSelectedHallId(route.hallId);
    setFocusedEntityId(route.focusEntityId);
    setSelectedRelationId(null);
    setDepth(route.depth);
    setGraphViewMode(route.viewMode);
    setGraphPanelMode(route.panelMode ?? "balanced");
    setSelectedNodeTypes(route.nodeTypes ?? []);
    setSelectedRelationTypes(route.relationTypes ?? []);
    setGraphFocusPreset(route.focusPreset ?? "all");
    setIsLeftOpen(true);
    setIsRightOpen(true);
  };
  const saveCurrentRoute = () => {
    const focusedLabel = focusedNode?.label ?? (locale === "zh" ? "全局邻域" : "Global neighborhood");
    const route: SavedGraphRoute = {
      id: `${Date.now()}-${focusedEntityId ?? "global"}`,
      title: focusedLabel,
      projectId: archiveDraft.projectId,
      hallId: selectedHallId,
      focusEntityId: focusedEntityId,
      depth,
      viewMode: graphViewMode,
      panelMode: graphPanelMode,
      nodeTypes: selectedNodeTypes,
      relationTypes: selectedRelationTypes,
      focusPreset: graphFocusPreset,
      source: "manual",
      createdAt: new Date().toISOString(),
    };
    const nextRoutes = [route, ...savedRoutes.filter((item) => item.focusEntityId !== route.focusEntityId || item.hallId !== route.hallId)].slice(0, 12);
    setSavedRoutes(nextRoutes);
    saveGraphRoutes(archiveDraft.projectId, nextRoutes);
  };
  const focusReviewItem = (item: GraphReviewItem) => {
    if (item.targetEntityId) setFocusedEntityId(item.targetEntityId);
    if (item.relationId) setSelectedRelationId(item.relationId);
    else setSelectedRelationId(null);
    setIsRightOpen(true);
  };
  const resolveReviewItem = (itemId: string) => {
    const nextResolvedIds = [itemId, ...resolvedReviewIds.filter((id) => id !== itemId)].slice(0, 200);
    setResolvedReviewIds(nextResolvedIds);
    saveGraphReviewResolvedIds(archiveDraft.projectId, nextResolvedIds);
  };
  const updateCurationState = (updater: (state: GraphCurationState) => GraphCurationState) => {
    const projectId = archiveDraft.projectId;
    setCurationState((currentState) => {
      const nextState = updater(currentState);
      saveGraphCurationState(projectId, nextState);
      saveGraphCuration(projectId, {
        projectId,
        importantEntityIds: nextState.importantEntityIds,
        hiddenRelationIds: nextState.hiddenRelationIds,
        mergeCandidates: nextState.mergeCandidates,
        updatedAt: "",
      })
        .then((serverState) => {
          if (graphProjectIdRef.current !== projectId) return;
          const normalizedState = {
            importantEntityIds: serverState.importantEntityIds,
            hiddenRelationIds: serverState.hiddenRelationIds,
            mergeCandidates: serverState.mergeCandidates,
          };
          setCurationState(normalizedState);
          saveGraphCurationState(projectId, normalizedState);
        })
        .catch(() => {
          // LocalStorage remains the offline fallback; the next successful save will resync.
        });
      return nextState;
    });
  };
  const markEntityImportant = (entityId: string | null) => {
    if (!entityId) return;
    updateCurationState((state) => ({
      ...state,
      importantEntityIds: [entityId, ...state.importantEntityIds.filter((id) => id !== entityId)].slice(0, 500),
    }));
  };
  const unmarkEntityImportant = (entityId: string) => {
    updateCurationState((state) => ({
      ...state,
      importantEntityIds: state.importantEntityIds.filter((id) => id !== entityId),
    }));
  };
  const hideRelation = (relationId: string | null) => {
    if (!relationId) return;
    updateCurationState((state) => ({
      ...state,
      hiddenRelationIds: [relationId, ...state.hiddenRelationIds.filter((id) => id !== relationId)].slice(0, 500),
    }));
    if (selectedRelationId === relationId) setSelectedRelationId(null);
  };
  const restoreRelation = (relationId: string) => {
    updateCurationState((state) => ({
      ...state,
      hiddenRelationIds: state.hiddenRelationIds.filter((id) => id !== relationId),
    }));
  };
  const recordMergeCandidate = (item: GraphReviewItem) => {
    if (!item.relatedEntityIds.length) return;
    const candidate: GraphMergeCandidate = {
      id: `merge:${item.relatedEntityIds.slice().sort().join("|")}`,
      label: item.title,
      entityIds: item.relatedEntityIds,
      createdAt: new Date().toISOString(),
    };
    updateCurationState((state) => ({
      ...state,
      mergeCandidates: [
        candidate,
        ...state.mergeCandidates.filter((current) => current.id !== candidate.id),
      ].slice(0, 100),
    }));
    resolveReviewItem(item.id);
  };
  const removeMergeCandidate = (candidateId: string) => {
    updateCurationState((state) => ({
      ...state,
      mergeCandidates: state.mergeCandidates.filter((candidate) => candidate.id !== candidateId),
    }));
  };
  const handleReviewPrimaryAction = (item: GraphReviewItem) => {
    if (item.kind === "duplicate") {
      recordMergeCandidate(item);
      return;
    }
    if (item.kind === "weak_relation") {
      hideRelation(item.relationId);
      resolveReviewItem(item.id);
      return;
    }
    markEntityImportant(item.targetEntityId);
    resolveReviewItem(item.id);
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
  const toggleNodeType = (nodeType: string) => {
    setSelectedNodeTypes((currentTypes) =>
      currentTypes.includes(nodeType)
        ? currentTypes.filter((item) => item !== nodeType)
        : [...currentTypes, nodeType].slice(0, 12),
    );
    setSelectedRelationId(null);
  };
  const toggleRelationType = (relationType: string) => {
    setSelectedRelationTypes((currentTypes) =>
      currentTypes.includes(relationType)
        ? currentTypes.filter((item) => item !== relationType)
        : [...currentTypes, relationType].slice(0, 12),
    );
    setSelectedRelationId(null);
  };
  const applyGraphFocusPreset = (preset: GraphFocusPreset) => {
    setGraphFocusPreset(preset);
    setSelectedNodeTypes(graphPresetNodeTypes(preset, availableNodeTypeNames));
    setSelectedRelationTypes(graphPresetRelationTypes(preset, availableRelationTypeNames));
    setSelectedRelationId(null);
    if (preset !== "all") {
      setGraphPanelMode((currentMode) => (currentMode === "balanced" ? "map" : currentMode));
    }
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
          <div className="graph-preset-filter" aria-label={String(t.graphFocusPreset)}>
            <span>{t.graphFocusPreset}</span>
            {graphFocusPresetOptions(locale).map((option) => {
              const Icon = option.icon;
              return (
                <button
                  className={graphFocusPreset === option.id ? "is-active" : ""}
                  key={option.id}
                  onClick={() => applyGraphFocusPreset(option.id)}
                  type="button"
                >
                  <Icon size={13} />
                  {option.label}
                </button>
              );
            })}
          </div>
          {availableNodeTypes.length ? (
            <div className="graph-type-filter" aria-label={String(t.entityTypeFilter)}>
              <span>{t.entityTypeFilter}</span>
              <button
                className={selectedNodeTypes.length === 0 ? "is-active" : ""}
                onClick={() => {
                  setSelectedNodeTypes([]);
                  setSelectedRelationId(null);
                }}
                type="button"
              >
                {t.allEntityTypes}
              </button>
              {availableNodeTypes.slice(0, 6).map((item) => (
                <button
                  className={selectedNodeTypes.includes(item.type) ? "is-active" : ""}
                  key={item.type}
                  onClick={() => toggleNodeType(item.type)}
                  type="button"
                  title={`${typeLabel(item.type, locale)}: ${item.count}`}
                >
                  {typeLabel(item.type, locale)}
                  <strong>{formatNumber(item.count)}</strong>
                </button>
              ))}
            </div>
          ) : null}
          {archiveRelationTypes.length ? (
            <div className="graph-relation-filter" aria-label={String(t.relationTypeFilter)}>
              <span>{t.relationTypeFilter}</span>
              <button
                className={selectedRelationTypes.length === 0 ? "is-active" : ""}
                onClick={() => {
                  setSelectedRelationTypes([]);
                  setSelectedRelationId(null);
                }}
                type="button"
              >
                {t.allRelationTypes}
              </button>
              {archiveRelationTypes.slice(0, 6).map((item) => (
                <button
                  className={selectedRelationTypes.includes(item.type) ? "is-active" : ""}
                  key={item.type}
                  onClick={() => toggleRelationType(item.type)}
                  type="button"
                  title={`${item.type}: ${item.count}`}
                >
                  {item.type}
                  <strong>{formatNumber(item.count)}</strong>
                </button>
              ))}
            </div>
          ) : null}
          <div className="graph-view-toggle" role="group" aria-label={locale === "zh" ? "图谱视图" : "Graph view"}>
            <button
              aria-pressed={graphViewMode === "cluster"}
              className={graphViewMode === "cluster" ? "is-active" : ""}
              onClick={() => setGraphViewMode("cluster")}
              type="button"
              title={locale === "zh" ? "聚类视图" : "Cluster view"}
            >
              <Network size={15} />
              {locale === "zh" ? "聚类" : "Cluster"}
            </button>
            <button
              aria-pressed={graphViewMode === "hierarchy"}
              className={graphViewMode === "hierarchy" ? "is-active" : ""}
              onClick={() => setGraphViewMode("hierarchy")}
              type="button"
              title={locale === "zh" ? "层级视图" : "Hierarchy view"}
            >
              <ListTree size={15} />
              {locale === "zh" ? "层级" : "Hierarchy"}
            </button>
          </div>
          <button className="secondary-action" onClick={saveCurrentRoute} type="button">
            <Save size={15} />
            {locale === "zh" ? "保存路径" : "Save route"}
          </button>
          <div className="graph-view-toggle graph-panel-toggle" role="group" aria-label={locale === "zh" ? "面板布局" : "Panel layout"}>
            <button
              aria-pressed={graphPanelMode === "balanced"}
              className={graphPanelMode === "balanced" ? "is-active" : ""}
              onClick={() => setGraphPanelMode("balanced")}
              type="button"
              title={locale === "zh" ? "平衡布局" : "Balanced layout"}
            >
              <PanelLeft size={15} />
              {locale === "zh" ? "平衡" : "Balanced"}
            </button>
            <button
              aria-pressed={graphPanelMode === "map"}
              className={graphPanelMode === "map" ? "is-active" : ""}
              onClick={() => setGraphPanelMode("map")}
              type="button"
              title={locale === "zh" ? "地图优先" : "Map first"}
            >
              <Network size={15} />
              {locale === "zh" ? "地图" : "Map"}
            </button>
            <button
              aria-pressed={graphPanelMode === "inspect"}
              className={graphPanelMode === "inspect" ? "is-active" : ""}
              onClick={() => setGraphPanelMode("inspect")}
              type="button"
              title={locale === "zh" ? "详情优先" : "Inspect first"}
            >
              <PanelRight size={15} />
              {locale === "zh" ? "详情" : "Inspect"}
            </button>
          </div>
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
      <GraphWorkspaceInsightPanel locale={locale} report={graphWorkspaceReport} />
      <div
        className={`graph-explorer-shell panel ${isLeftOpen ? "has-left" : "is-left-closed"} ${
          isRightOpen ? "has-right" : "is-right-closed"
        } is-panel-${graphPanelMode}`}
      >
        {isLeftOpen ? (
          <GraphStartsDrawer
            curationState={curationState}
            focusedEntityId={focusedEntityId}
            isLoading={isSummaryLoading}
            locale={locale}
            onClose={() => setIsLeftOpen(false)}
            onReviewFocus={focusReviewItem}
            onReviewPrimaryAction={handleReviewPrimaryAction}
            onReviewResolve={resolveReviewItem}
            onMergeCandidateRemove={removeMergeCandidate}
            onRelationRestore={restoreRelation}
            onImportantRemove={unmarkEntityImportant}
            onStartSelect={(entityId) => {
              setFocusedEntityId(entityId);
              setSelectedRelationId(null);
              setIsRightOpen(true);
            }}
            nodeTypeClusters={nodeTypeClusters}
            onRouteRestore={restoreSavedRoute}
            relationTypeClusters={relationTypeClusters}
            reviewQueue={reviewQueue}
            savedRoutes={savedRoutes}
            selectedHallId={selectedHallId}
            summary={summary}
          />
        ) : null}
        <GraphExplorerCanvas
          focusedEntityId={focusedEntityId}
          importantEntityIds={importantEntityIds}
          isLoading={isNeighborhoodLoading}
          locale={locale}
          missionOverlay={missionOverlay}
          neighborhood={visibleNeighborhood}
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
          viewMode={graphViewMode}
        />
        {isRightOpen ? (
          <GraphEntityDrawer
            evidenceCards={archiveDraft.evidenceCards}
            focusedNode={focusedNode}
            halls={archiveDraft.halls}
            importantEntityIds={importantEntityIds}
            locale={locale}
            nodeById={nodeById}
            onClose={() => setIsRightOpen(false)}
            onImportantToggle={(entityId) => {
              if (importantEntityIds.has(entityId)) unmarkEntityImportant(entityId);
              else markEntityImportant(entityId);
            }}
            onRelationHide={hideRelation}
            onNodeFocus={(entityId) => {
              setFocusedEntityId(entityId);
              setSelectedRelationId(null);
              setIsRightOpen(true);
            }}
            onRelationSelect={(relationId) => setSelectedRelationId(relationId)}
            relations={visibleNeighborhood?.relations ?? []}
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

function GraphWorkspaceInsightPanel({
  locale,
  report,
}: {
  locale: Locale;
  report: GraphWorkspaceReport | null;
}) {
  const labels = locale === "zh"
    ? {
        title: "图谱工作台洞察",
        subtitle: "模块聚类、边界、弱关系和快照变化来自后端真实图谱报告。",
        quality: "质量评分",
        clusters: "模块聚类",
        boundaries: "边界候选",
        weak: "弱关系",
        diff: "快照变化",
        advice: "建议",
        entryPoints: "推荐入口路径",
        entityQuality: "实体质量",
        languages: "语言结构",
        noise: "噪声",
        duplicates: "重复",
        empty: "打开或重新生成档案后会显示图谱工作台报告。",
      }
    : {
        title: "Graph workspace insights",
        subtitle: "Module clusters, boundaries, weak relations, and snapshot changes come from the backend graph report.",
        quality: "Quality score",
        clusters: "Module clusters",
        boundaries: "Boundary candidates",
        weak: "Weak relations",
        diff: "Snapshot diff",
        advice: "Advice",
        entryPoints: "Recommended entry paths",
        entityQuality: "Entity quality",
        languages: "Language structure",
        noise: "Noise",
        duplicates: "Duplicates",
        empty: "Open or regenerate an archive to show the graph workspace report.",
      };
  const snapshotDiff = report?.snapshot_diff ?? {};
  const changed = graphRecordNumber(snapshotDiff, "changed") + graphRecordNumber(snapshotDiff, "added") + graphRecordNumber(snapshotDiff, "removed");
  const quality = report?.quality;
  const entryPoints = report?.entry_points ?? [];
  const entityQuality = report?.entity_quality;
  const languageRows = Array.isArray(report?.language_structure?.languages)
    ? (report?.language_structure?.languages as Array<Record<string, unknown>>)
    : [];
  const languageNames = languageRows.slice(0, 4).map((row) => String(row.language ?? "")).filter(Boolean);
  return (
    <section className="graph-workspace-insights panel">
      <div>
        <span className="eyebrow">{labels.title}</span>
        <p>{report ? labels.subtitle : labels.empty}</p>
        {quality?.warnings.length ? (
          <div className="graph-quality-advice">
            <strong>{labels.advice}</strong>
            <span>{quality.recommendations[0] ?? quality.warnings[0]}</span>
          </div>
        ) : null}
        {entryPoints.length ? (
          <div className="graph-entry-points">
            <strong>{labels.entryPoints}</strong>
            <div>
              {entryPoints.slice(0, 3).map((entry) => {
                const entityIds = Array.isArray(entry.entity_ids) ? entry.entity_ids : [];
                return (
                  <span key={String(entry.id ?? entry.title)}>
                    {String(entry.title ?? entry.category ?? "")}
                    <small>{formatNumber(entityIds.length)}</small>
                  </span>
                );
              })}
            </div>
          </div>
        ) : null}
        {entityQuality ? (
          <div className="graph-entry-points">
            <strong>{labels.entityQuality}</strong>
            <div>
              <span>{labels.noise}<small>{formatNumber(entityQuality.metrics?.noisy_entities ?? 0)}</small></span>
              <span>{labels.duplicates}<small>{formatNumber(entityQuality.metrics?.duplicate_candidate_groups ?? 0)}</small></span>
              <span>{labels.languages}<small>{languageNames.join(", ") || "-"}</small></span>
            </div>
          </div>
        ) : null}
      </div>
      <div className="graph-workspace-metrics">
        <span className={`quality-grade is-${quality?.grade?.toLowerCase() ?? "empty"}`}>
          <strong>{quality ? `${Math.round(quality.score)} · ${quality.grade}` : "--"}</strong>
          {labels.quality}
        </span>
        <span><strong>{formatNumber(report?.module_clusters.length ?? 0)}</strong>{labels.clusters}</span>
        <span><strong>{formatNumber(report?.module_boundaries.length ?? 0)}</strong>{labels.boundaries}</span>
        <span><strong>{formatNumber(report?.weak_relations.length ?? 0)}</strong>{labels.weak}</span>
        <span><strong>{formatNumber(changed)}</strong>{labels.diff}</span>
      </div>
    </section>
  );
}

const graphRecordNumber = (record: Record<string, unknown>, key: string) => {
  const value = record[key];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
};

function GraphStartsDrawer({
  curationState,
  focusedEntityId,
  isLoading,
  locale,
  onClose,
  nodeTypeClusters,
  onImportantRemove,
  onMergeCandidateRemove,
  onReviewFocus,
  onReviewPrimaryAction,
  onReviewResolve,
  onRelationRestore,
  onRouteRestore,
  onStartSelect,
  relationTypeClusters,
  reviewQueue,
  savedRoutes,
  selectedHallId,
  summary,
}: {
  curationState: GraphCurationState;
  focusedEntityId: string | null;
  isLoading: boolean;
  locale: Locale;
  onClose: () => void;
  nodeTypeClusters: GraphClusterItem[];
  onImportantRemove: (entityId: string) => void;
  onMergeCandidateRemove: (candidateId: string) => void;
  onReviewFocus: (item: GraphReviewItem) => void;
  onReviewPrimaryAction: (item: GraphReviewItem) => void;
  onReviewResolve: (itemId: string) => void;
  onRelationRestore: (relationId: string) => void;
  onRouteRestore: (route: SavedGraphRoute) => void;
  onStartSelect: (entityId: string) => void;
  relationTypeClusters: GraphClusterItem[];
  reviewQueue: GraphReviewItem[];
  savedRoutes: SavedGraphRoute[];
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
      <div className="graph-drawer-scroll">
        <section className="graph-drawer-section">
          <div className="graph-section-title">
            <span>{t.recommendedStarts}</span>
            <small>{locale === "zh" ? "搜索前的入口" : "Entry points"}</small>
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
                  <div className="graph-start-explain">
                    <span>{t.whyRecommended}: {recommendedStartGroupLabel(start.group, locale)}</span>
                    <span>{locale === "zh" ? "展厅" : "Halls"}: {start.hall_ids.length || 1}</span>
                  </div>
                  <small>
                    {formatNumber(Math.round(start.score))} {String(t.graphStartScore)}
                  </small>
                </button>
              ))
            ) : (
              <p className="empty-note">{emptyText}</p>
            )}
          </div>
        </section>
        <section className="graph-drawer-section">
          <div className="graph-section-title">
            <span>{locale === "zh" ? "当前邻域聚类" : "Current clusters"}</span>
            <small>{locale === "zh" ? "只统计画布可见邻域" : "Visible neighborhood only"}</small>
          </div>
          <div className="graph-cluster-panel">
            <GraphClusterList
              emptyText={locale === "zh" ? "暂无节点聚类。" : "No node clusters."}
              items={nodeTypeClusters}
              locale={locale}
              title={locale === "zh" ? "实体类型" : "Entity types"}
            />
            <GraphClusterList
              emptyText={locale === "zh" ? "暂无关系聚类。" : "No relation clusters."}
              items={relationTypeClusters}
              locale={locale}
              title={locale === "zh" ? "关系类型" : "Relation types"}
            />
          </div>
        </section>
        <section className="graph-drawer-section">
          <div className="graph-section-title">
            <span>{locale === "zh" ? "已保存路径" : "Saved routes"}</span>
            <small>{locale === "zh" ? "恢复探索上下文" : "Restore context"}</small>
          </div>
          <div className="saved-route-list">
            {savedRoutes.length ? (
              savedRoutes.map((route) => (
                <button className="saved-route-item" key={route.id} onClick={() => onRouteRestore(route)} type="button">
                  <Route size={15} />
                  <span>
                    <strong>{route.title}</strong>
                    <small>
                      {savedRouteSourceLabel(route.source, locale)} · {graphFocusPresetLabel(route.focusPreset, locale)} ·{" "}
                      {route.viewMode === "hierarchy"
                        ? locale === "zh" ? "层级" : "Hierarchy"
                        : locale === "zh" ? "聚类" : "Cluster"}{" "}
                      · {locale === "zh" ? `深度 ${route.depth}` : `Depth ${route.depth}`}
                    </small>
                    <span className="saved-route-meta">
                      {route.hallId ? <em>{locale === "zh" ? "展厅" : "Hall"}: {compactGraphLabel(route.hallId, 18)}</em> : null}
                      {route.nodeTypes?.length ? <em>{locale === "zh" ? "实体" : "Entities"}: {route.nodeTypes.length}</em> : null}
                      {route.relationTypes?.length ? <em>{locale === "zh" ? "关系" : "Relations"}: {route.relationTypes.length}</em> : null}
                    </span>
                  </span>
                </button>
              ))
            ) : (
              <p className="empty-note">{locale === "zh" ? "还没有保存探索路径。" : "No saved routes yet."}</p>
            )}
          </div>
        </section>
        <section className="graph-drawer-section">
          <div className="graph-section-title">
            <span>{locale === "zh" ? "确认队列" : "Review queue"}</span>
            <small>{locale === "zh" ? "低置信与重复项" : "Low-confidence items"}</small>
          </div>
          <div className="graph-review-list">
            {reviewQueue.length ? (
              reviewQueue.map((item) => (
                <article className={`graph-review-item ${item.kind}`} key={item.id}>
                  <div>
                    <span>
                      <CircleDot size={13} />
                      {reviewKindLabel(item.kind, locale)}
                    </span>
                    <strong>{item.title}</strong>
                    <p>{item.reason}</p>
                  </div>
                  <div className="graph-review-actions">
                    <button onClick={() => onReviewFocus(item)} type="button">
                      {locale === "zh" ? "定位" : "Locate"}
                    </button>
                    <button onClick={() => onReviewPrimaryAction(item)} type="button">
                      {reviewPrimaryActionLabel(item.kind, locale)}
                    </button>
                    <button onClick={() => onReviewResolve(item.id)} type="button">
                      {locale === "zh" ? "忽略" : "Ignore"}
                    </button>
                  </div>
                </article>
              ))
            ) : (
              <p className="empty-note">{locale === "zh" ? "当前邻域没有待确认项。" : "No review items in this neighborhood."}</p>
            )}
          </div>
        </section>
        <section className="graph-drawer-section">
          <div className="graph-section-title">
            <span>{locale === "zh" ? "策展记录" : "Curation log"}</span>
            <small>{locale === "zh" ? "仅当前项目" : "This archive only"}</small>
          </div>
          <div className="graph-curation-log">
            <CurationLogGroup
              emptyText={locale === "zh" ? "暂无重要实体。" : "No important entities."}
              items={curationState.importantEntityIds}
              label={locale === "zh" ? "重要实体" : "Important entities"}
              onRemove={onImportantRemove}
              undoLabel={locale === "zh" ? "点击撤销" : "click to undo"}
            />
            <CurationLogGroup
              emptyText={locale === "zh" ? "暂无隐藏关系。" : "No hidden relations."}
              items={curationState.hiddenRelationIds}
              label={locale === "zh" ? "隐藏关系" : "Hidden relations"}
              onRemove={onRelationRestore}
              undoLabel={locale === "zh" ? "点击恢复" : "click to restore"}
            />
            <div className="curation-log-group">
              <strong>{locale === "zh" ? "合并候选" : "Merge candidates"}</strong>
              {curationState.mergeCandidates.length ? (
                curationState.mergeCandidates.slice(0, 6).map((candidate) => (
                  <button key={candidate.id} onClick={() => onMergeCandidateRemove(candidate.id)} type="button">
                    <span>{candidate.label}</span>
                    <small>{candidate.entityIds.length} ids · {locale === "zh" ? "点击移除" : "click to remove"}</small>
                  </button>
                ))
              ) : (
                <p className="empty-note">{locale === "zh" ? "暂无合并候选。" : "No merge candidates."}</p>
              )}
            </div>
          </div>
        </section>
      </div>
    </aside>
  );
}

function CurationLogGroup({
  emptyText,
  items,
  label,
  onRemove,
  undoLabel,
}: {
  emptyText: string;
  items: string[];
  label: string;
  onRemove: (id: string) => void;
  undoLabel: string;
}) {
  return (
    <div className="curation-log-group">
      <strong>{label}</strong>
      {items.length ? (
        items.slice(0, 6).map((id) => (
          <button key={id} onClick={() => onRemove(id)} type="button">
            <span>{compactGraphLabel(id, 30)}</span>
            <small>{undoLabel}</small>
          </button>
        ))
      ) : (
        <p className="empty-note">{emptyText}</p>
      )}
    </div>
  );
}

const reviewKindLabel = (kind: GraphReviewItem["kind"], locale: Locale) => {
  const labels = {
    zh: {
      duplicate: "疑似重复",
      weak_relation: "弱关系",
      thin_evidence: "证据薄弱",
    },
    en: {
      duplicate: "Possible duplicate",
      weak_relation: "Weak relation",
      thin_evidence: "Thin evidence",
    },
  };
  return labels[locale][kind];
};

const reviewPrimaryActionLabel = (kind: GraphReviewItem["kind"], locale: Locale) => {
  const labels = {
    zh: {
      duplicate: "记为合并",
      weak_relation: "隐藏关系",
      thin_evidence: "标重要",
    },
    en: {
      duplicate: "Track merge",
      weak_relation: "Hide relation",
      thin_evidence: "Mark important",
    },
  };
  return labels[locale][kind];
};

const recommendedStartGroupLabel = (group: string, locale: Locale) => {
  const labels: Record<Locale, Record<string, string>> = {
    zh: {
      entry_file: "疑似应用入口",
      high_degree: "高连接度核心节点",
      config_hotspot: "运行配置热点",
      document_center: "文档中心节点",
    },
    en: {
      entry_file: "Likely application entry",
      high_degree: "High-degree core node",
      config_hotspot: "Runtime configuration hotspot",
      document_center: "Documentation center",
    },
  };
  return labels[locale][group] ?? group;
};

const graphFocusPresetLabel = (preset: GraphFocusPreset | undefined, locale: Locale) => {
  const labels: Record<GraphFocusPreset, string> = {
    all: String(copy[locale].graphPresetAll),
    entry: String(copy[locale].graphPresetEntry),
    config: String(copy[locale].graphPresetConfig),
    api: String(copy[locale].graphPresetApi),
    dependency: String(copy[locale].graphPresetDependency),
  };
  return labels[preset ?? "all"];
};

const savedRouteSourceLabel = (source: SavedGraphRoute["source"], locale: Locale) => {
  if (source === "search") return locale === "zh" ? "搜索" : "Search";
  if (source === "recommendation") return locale === "zh" ? "推荐" : "Recommendation";
  return locale === "zh" ? "手动" : "Manual";
};

function GraphClusterList({
  emptyText,
  items,
  locale,
  title,
}: {
  emptyText: string;
  items: GraphClusterItem[];
  locale: Locale;
  title: string;
}) {
  const t = copy[locale];
  const [isExpanded, setIsExpanded] = useState(false);
  const maxCount = Math.max(...items.map((item) => item.count), 1);
  const visibleItems = isExpanded ? items : items.slice(0, 4);
  return (
    <div className="graph-cluster-list">
      <div className="graph-cluster-list-head">
        <strong>{title}</strong>
        {items.length > 4 ? (
          <button onClick={() => setIsExpanded((current) => !current)} type="button">
            {isExpanded ? t.collapseCluster : t.expandCluster}
          </button>
        ) : null}
      </div>
      {items.length ? (
        <div className="graph-cluster-grid">
          {visibleItems.map((item) => (
            <div className="graph-cluster-item" key={item.label}>
              <span>{item.label}</span>
              <div aria-hidden="true">
                <i style={{ width: `${Math.max(12, (item.count / maxCount) * 100)}%` }} />
              </div>
              <b>{formatNumber(item.count)}</b>
            </div>
          ))}
        </div>
      ) : (
        <p className="empty-note">{emptyText}</p>
      )}
    </div>
  );
}

function GraphEntityDrawer({
  evidenceCards,
  focusedNode,
  halls,
  importantEntityIds,
  locale,
  nodeById,
  onClose,
  onImportantToggle,
  onNodeFocus,
  onRelationHide,
  onRelationSelect,
  relations,
  selectedRelation,
}: {
  evidenceCards: EvidenceCard[];
  focusedNode: GraphExplorerNode | null;
  halls: ArchiveHall[];
  importantEntityIds: Set<string>;
  locale: Locale;
  nodeById: Map<string, GraphExplorerNode>;
  onClose: () => void;
  onImportantToggle: (entityId: string) => void;
  onNodeFocus: (entityId: string) => void;
  onRelationHide: (relationId: string | null) => void;
  onRelationSelect: (relationId: string) => void;
  relations: GraphExplorerRelation[];
  selectedRelation: GraphExplorerRelation | null;
}) {
  const t = copy[locale];
  const sourceNode = selectedRelation ? nodeById.get(selectedRelation.source_id) : null;
  const targetNode = selectedRelation ? nodeById.get(selectedRelation.target_id) : null;
  const emptyText =
    locale === "zh" ? "选择一个节点或关系查看详情。" : "Select a node or relation to inspect details.";
  const sourcePathFallback = locale === "zh" ? "未提供来源路径" : "No source path provided";
  const evidenceById = useMemo(() => new Map(evidenceCards.map((card) => [card.id, card])), [evidenceCards]);
  const focusedEvidenceIds = focusedNode?.evidence_ids ?? [];
  const relationEvidenceIds = selectedRelation?.evidence_ids ?? [];
  const hallById = useMemo(() => new Map(halls.map((hall) => [hall.id, hallTitle(hall, locale)])), [halls, locale]);
  const focusedRelations = useMemo(() => {
    if (!focusedNode) return [];
    return relations
      .filter((relation) => relation.source_id === focusedNode.id || relation.target_id === focusedNode.id)
      .sort((left, right) => right.weight - left.weight || right.evidence_ids.length - left.evidence_ids.length)
      .slice(0, 14);
  }, [focusedNode, relations]);
  const incomingCount = focusedNode
    ? relations.filter((relation) => relation.target_id === focusedNode.id).length
    : 0;
  const outgoingCount = focusedNode
    ? relations.filter((relation) => relation.source_id === focusedNode.id).length
    : 0;
  const focusedHallLabel = focusedNode?.hall_ids.map((hallId) => hallById.get(hallId) ?? hallId).join(" · ") || sourcePathFallback;
  const isFocusedImportant = Boolean(focusedNode && importantEntityIds.has(focusedNode.id));

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
              <span>{locale === "zh" ? "入 / 出" : "In / Out"}</span>
              <strong>{incomingCount} / {outgoingCount}</strong>
              <span>{locale === "zh" ? "展厅" : "Halls"}</span>
              <strong>{focusedHallLabel}</strong>
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
            <div className="entity-action-row">
              <button onClick={() => onImportantToggle(focusedNode.id)} type="button">
                {isFocusedImportant
                  ? locale === "zh" ? "取消重要" : "Unmark important"
                  : locale === "zh" ? "标记重要" : "Mark important"}
              </button>
            </div>
          </section>
        ) : (
          <p className="empty-note">{emptyText}</p>
        )}
        {focusedNode ? (
          <section className="entity-detail-card relation-neighborhood">
            <span className="entity-label">{locale === "zh" ? "关联实体" : "Related entities"}</span>
            <div className="entity-relation-list">
              {focusedRelations.length ? (
                focusedRelations.map((relation) => {
                  const isOutgoing = relation.source_id === focusedNode.id;
                  const relatedNode = nodeById.get(isOutgoing ? relation.target_id : relation.source_id);
                  return (
                    <article className="entity-relation-item" key={relation.id}>
                      <button onClick={() => onRelationSelect(relation.id)} type="button">
                        <span>{isOutgoing ? locale === "zh" ? "出边" : "Out" : locale === "zh" ? "入边" : "In"}</span>
                        <strong>{relatedNode?.label ?? (isOutgoing ? relation.target_id : relation.source_id)}</strong>
                        <small>
                          {relation.type} · {locale === "zh" ? "权重" : "Weight"} {relation.weight} · {relation.evidence_ids.length} {t.evidenceUsed}
                        </small>
                      </button>
                      {relatedNode ? (
                        <button className="entity-focus-button" onClick={() => onNodeFocus(relatedNode.id)} type="button">
                          {locale === "zh" ? "聚焦" : "Focus"}
                        </button>
                      ) : null}
                    </article>
                  );
                })
              ) : (
                <p className="empty-note">{locale === "zh" ? "当前邻域没有关联关系。" : "No related relations in the current neighborhood."}</p>
              )}
            </div>
          </section>
        ) : null}
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
              <strong>
                {selectedRelation.hall_ids.map((hallId) => hallById.get(hallId) ?? hallId).join(" · ") ||
                  selectedRelation.hall_ids.length}
              </strong>
            </div>
            <div className="entity-action-row">
              <button onClick={() => onRelationHide(selectedRelation.id)} type="button">
                {locale === "zh" ? "隐藏这条关系" : "Hide this relation"}
              </button>
            </div>
          </section>
        ) : null}
        <EvidenceChain
          evidenceById={evidenceById}
          evidenceIds={[...focusedEvidenceIds, ...relationEvidenceIds]}
          locale={locale}
          title={locale === "zh" ? "证据链" : "Evidence chain"}
        />
      </div>
    </aside>
  );
}

function EvidenceChain({
  evidenceById,
  evidenceIds,
  locale,
  title,
}: {
  evidenceById: Map<string, EvidenceCard>;
  evidenceIds: string[];
  locale: Locale;
  title: string;
}) {
  const uniqueEvidenceIds = [...new Set(evidenceIds)].slice(0, 8);
  return (
    <section className="entity-detail-card evidence-chain">
      <span className="entity-label">{title}</span>
      {uniqueEvidenceIds.length ? (
        <div className="evidence-chain-list">
          {uniqueEvidenceIds.map((evidenceId) => {
            const card = evidenceById.get(evidenceId);
            return (
              <article className="evidence-chain-item" key={evidenceId}>
                <strong>{card ? evidenceTitle(card, locale) : evidenceId}</strong>
                <code>{card?.sourcePath ?? evidenceId}</code>
                {card ? <p>{locale === "zh" ? card.snippetZh || card.snippet : card.snippet}</p> : null}
              </article>
            );
          })}
        </div>
      ) : (
        <p className="empty-note">{locale === "zh" ? "当前选择没有直接证据引用。" : "No direct evidence for the current selection."}</p>
      )}
    </section>
  );
}

const metadataObject = (source: unknown, key: string): Record<string, unknown> => {
  if (!source || typeof source !== "object") return {};
  const value = (source as Record<string, unknown>)[key];
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
};

const missionMetadataObject = (mission: AgentMission | null, key: string): Record<string, unknown> =>
  metadataObject(mission?.metadata, key);

const metadataNumber = (source: Record<string, unknown>, key: string): number => {
  const value = source[key];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
};

function GraphExplorerCanvas({
  focusedEntityId,
  importantEntityIds,
  isLoading,
  locale,
  missionOverlay,
  neighborhood,
  onNodeFocus,
  onRelationSelect,
  searchMatchedEntityIds,
  selectedRelationId,
  viewMode,
}: {
  focusedEntityId: string | null;
  importantEntityIds: Set<string>;
  isLoading: boolean;
  locale: Locale;
  missionOverlay: MissionGraphOverlay | null;
  neighborhood: GraphNeighborhood | null;
  onNodeFocus: (entityId: string) => void;
  onRelationSelect: (relationId: string) => void;
  searchMatchedEntityIds: Set<string>;
  selectedRelationId: string | null;
  viewMode: GraphViewMode;
}) {
  const layout = useMemo(
    () => (neighborhood ? layoutGraph(neighborhood, focusedEntityId, viewMode) : { nodes: [], relations: [] }),
    [focusedEntityId, neighborhood, viewMode],
  );
  const selectedConnectedNodeIds = useMemo(() => {
    if (!selectedRelationId || !neighborhood) return new Set<string>();
    const selected = neighborhood.relations.find((relation) => relation.id === selectedRelationId);
    return new Set(selected ? [selected.source_id, selected.target_id] : []);
  }, [neighborhood, selectedRelationId]);
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
          const isSelectedRelationEnd = selectedConnectedNodeIds.has(node.id);
          const isCuratedImportant = importantEntityIds.has(node.id);
          return (
            <g
              aria-label={node.label}
              className={`explorer-node ${node.tone} ${node.isFocused ? "is-focused" : ""} ${
                node.isDimmed ? "is-dimmed" : ""
              } ${isSearchMatch ? "is-search-match" : ""} ${isSelectedRelationEnd ? "is-selected-relation-end" : ""} ${
                isCuratedImportant ? "is-curated-important" : ""
              } ${isExplored ? "is-agent-explored" : ""
              } ${isRisk ? "is-agent-risk" : ""}`}
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
  viewMode: GraphViewMode,
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
  const incomingFocusIds = new Set<string>();
  const outgoingFocusIds = new Set<string>();
  visibleRelations.forEach((relation) => {
    if (!requestedFocus) return;
    if (relation.target_id === centerNodeId) incomingFocusIds.add(relation.source_id);
    if (relation.source_id === centerNodeId) outgoingFocusIds.add(relation.target_id);
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
  const placeY = (index: number, count: number) => {
    if (count <= 1) return centerY;
    const top = 80;
    const bottom = 455;
    return top + (index / Math.max(1, count - 1)) * (bottom - top);
  };
  const typeColumns = [...new Set(orderedNodes.map((node) => typeLabel(node.type, "en")))].slice(0, 5);
  const nodesByType = new Map<string, GraphExplorerNode[]>();
  orderedNodes.forEach((node) => {
    const key = typeColumns.includes(typeLabel(node.type, "en")) ? typeLabel(node.type, "en") : "Other";
    nodesByType.set(key, [...(nodesByType.get(key) ?? []), node]);
  });
  const hierarchyColumns = requestedFocus
    ? [
        { ids: [...incomingFocusIds], x: 160 },
        { ids: [centerNodeId], x: centerX },
        { ids: [...outgoingFocusIds], x: 680 },
        {
          ids: outerNodes
            .map((node) => node.id)
            .filter((id) => !incomingFocusIds.has(id) && !outgoingFocusIds.has(id)),
          x: 420,
        },
      ]
    : [...nodesByType.entries()].map(([type, nodesOfType], index, columns) => ({
        ids: nodesOfType.map((node) => node.id),
        x: 120 + (index / Math.max(1, columns.length - 1)) * 600,
        type,
      }));

  orderedNodes.forEach((node, index) => {
    const isCenter = node.id === centerNodeId;
    const connected = focusConnectedIds.has(node.id);
    let x = centerX;
    let y = centerY;
    if (viewMode === "hierarchy") {
      const column = hierarchyColumns.find((candidate) => candidate.ids.includes(node.id));
      const columnIds = column?.ids ?? [node.id];
      const columnIndex = columnIds.indexOf(node.id);
      x = column?.x ?? centerX;
      y = placeY(Math.max(0, columnIndex), Math.max(columnIds.length, 1));
      if (requestedFocus && !connected && !isCenter) {
        x = 420 + ((index % 2 === 0 ? -1 : 1) * 78);
        y = 88 + (index % 7) * 54;
      }
    } else {
      const outerIndex = Math.max(0, index - 1);
      const outerCount = Math.max(outerNodes.length, 1);
      const angle = -Math.PI / 2 + (outerIndex / outerCount) * Math.PI * 2 + (outerCount > 14 ? (outerIndex % 2) * 0.1 : 0);
      const radiusX = connected || !requestedFocus ? 255 : 315;
      const radiusY = connected || !requestedFocus ? 155 : 205;
      x = isCenter ? centerX : centerX + Math.cos(angle) * radiusX;
      y = isCenter ? centerY : centerY + Math.sin(angle) * radiusY;
    }
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

function KnowledgeUniversePage({
  archiveIds,
  diffReport,
  error,
  isRunningDiff,
  isRunningUniverseAgent,
  isLoading,
  locale,
  onOpenProject,
  onRefresh,
  onRunDiff,
  onRunUniverseAgent,
  onSavePath,
  onToggleProject,
  paths,
  selectedProjectIds,
  tasks,
  universe,
}: {
  archiveIds: string[];
  diffReport: ProjectArchitectureDiffReport | null;
  error: string;
  isRunningDiff: boolean;
  isRunningUniverseAgent: boolean;
  isLoading: boolean;
  locale: Locale;
  onOpenProject: (projectId: string) => void;
  onRefresh: () => void;
  onRunDiff: (leftProjectId: string, rightProjectId: string) => void;
  onRunUniverseAgent: () => void;
  onSavePath: (focus: MetaverseFocus | null) => void;
  onToggleProject: (projectId: string) => void;
  paths: UniverseExplorationPath[];
  selectedProjectIds: string[];
  tasks: UniverseAgentTask[];
  universe: ProjectKnowledgeUniverse | null;
}) {
  const t = copy[locale];
  const selectedSet = new Set(selectedProjectIds);
  const metrics = universe?.metrics ?? {};
  const links = universe?.links ?? [];
  const clusters = universe?.clusters ?? [];
  const metricLabels = copy[locale].metrics as Record<string, string>;
  const [metaverseFocus, setMetaverseFocus] = useState<MetaverseFocus | null>(null);
  const [leftProjectId, setLeftProjectId] = useState(selectedProjectIds[0] ?? archiveIds[0] ?? "");
  const [rightProjectId, setRightProjectId] = useState(selectedProjectIds[1] ?? archiveIds[1] ?? "");

  useEffect(() => {
    setLeftProjectId((current) => current || selectedProjectIds[0] || archiveIds[0] || "");
    setRightProjectId((current) => {
      if (current && current !== leftProjectId) return current;
      return selectedProjectIds.find((projectId) => projectId !== leftProjectId) ?? archiveIds.find((projectId) => projectId !== leftProjectId) ?? "";
    });
  }, [archiveIds, leftProjectId, selectedProjectIds]);

  return (
    <section className="universe-page">
      <div className="universe-hero panel">
        <div>
          <span className="eyebrow">{t.universePage}</span>
          <h1>{t.crossProjectLinks}</h1>
          <p>{t.universeSummary}</p>
        </div>
        <button className="primary-button compact" disabled={isLoading} onClick={onRefresh} type="button">
          <Sparkles size={14} />
          {isLoading ? t.loadingUniverse : t.refreshUniverse}
        </button>
      </div>
      <div className="universe-selector panel">
        <div className="panel-title">
          <Boxes size={16} />
          {t.selectedProjects}
        </div>
        <div className="universe-project-chips">
          {archiveIds.length ? (
            archiveIds.map((projectId) => (
              <button
                className={selectedSet.has(projectId) ? "is-selected" : ""}
                key={projectId}
                onClick={() => onToggleProject(projectId)}
                type="button"
              >
                {projectId}
              </button>
            ))
          ) : (
            <span>{t.universeEmpty}</span>
          )}
        </div>
      </div>
      {error ? (
        <div className="mission-error" role="alert">
          <strong>{t.universeLoadFailed}</strong>
          <span>{error}</span>
        </div>
      ) : null}
      {universe ? (
        <>
          <KnowledgeMetaverseViewport locale={locale} onFocusChange={setMetaverseFocus} universe={universe} />
          <div className="universe-metrics">
            <Metric label={metricLabels.entities} value={metrics.entities ?? 0} icon={<Boxes size={18} />} />
            <Metric label={metricLabels.relations} value={metrics.relations ?? 0} icon={<GitBranch size={18} />} />
            <Metric label={String(t.sharedClusters)} value={metrics.clusters ?? 0} icon={<Network size={18} />} />
            <Metric label={String(t.crossProjectLinks)} value={metrics.links ?? 0} icon={<Route size={18} />} />
          </div>
          <section className="universe-operations panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">{t.metaverseFocus}</span>
                <h2>{t.universeAgentTasks}</h2>
              </div>
              <Command size={18} />
            </div>
            <div className="universe-action-row">
              <button className="secondary-button compact" onClick={() => onSavePath(metaverseFocus)} type="button">
                <Save size={14} />
                {t.saveUniversePath}
              </button>
              <button className="primary-button compact" disabled={isRunningUniverseAgent} onClick={onRunUniverseAgent} type="button">
                <Sparkles size={14} />
                {isRunningUniverseAgent ? t.loadingUniverse : t.runUniverseAgent}
              </button>
            </div>
            <div className="universe-compare-row">
              <label>
                <span>A</span>
                <select value={leftProjectId} onChange={(event) => setLeftProjectId(event.target.value)}>
                  {archiveIds.map((projectId) => <option key={projectId} value={projectId}>{projectId}</option>)}
                </select>
              </label>
              <label>
                <span>B</span>
                <select value={rightProjectId} onChange={(event) => setRightProjectId(event.target.value)}>
                  {archiveIds.map((projectId) => <option key={projectId} value={projectId}>{projectId}</option>)}
                </select>
              </label>
              <button
                className="secondary-button compact"
                disabled={isRunningDiff || archiveIds.length < 2}
                onClick={() => onRunDiff(leftProjectId, rightProjectId)}
                type="button"
              >
                <GitBranch size={14} />
                {isRunningDiff ? t.loadingUniverse : t.runCompare}
              </button>
            </div>
          </section>
          <div className="universe-grid">
            <section className="universe-panel panel">
              <div className="panel-title">
                <Archive size={16} />
                {t.universeProjects}
              </div>
              <div className="universe-project-list">
                {universe.projects.map((project) => (
                  <button
                    className="universe-project-card"
                    key={project.project_id}
                    onClick={() => onOpenProject(project.project_id)}
                    type="button"
                  >
                    <strong>{project.project_id}</strong>
                    <div>
                      <span>{typeLabel("File", locale)}: {formatNumber(project.metrics.entities ?? 0)}</span>
                      <span>{t.evidenceUsed}: {formatNumber(project.metrics.evidence ?? 0)}</span>
                    </div>
                    <p>
                      {project.top_entity_types.slice(0, 3).map((item) => `${typeLabel(item.type, locale)} ${item.count}`).join(" · ") ||
                        String(t.pending)}
                    </p>
                  </button>
                ))}
              </div>
            </section>
            <section className="universe-panel panel">
              <div className="panel-title">
                <ListTree size={16} />
                {t.sharedClusters}
              </div>
              <div className="universe-cluster-list">
                {clusters.length ? (
                  clusters.map((cluster) => (
                    <article className="universe-cluster" key={cluster.id}>
                      <div>
                        <strong>{cluster.label}</strong>
                        <span>{formatPercent(cluster.score)}</span>
                      </div>
                      <p>{cluster.project_ids.join(" / ")}</p>
                      <div className="mission-task-metrics">
                        <span>{cluster.type}</span>
                        <span>{t.entitiesUsed}: {cluster.entity_refs.length}</span>
                      </div>
                    </article>
                  ))
                ) : (
                  <p className="empty-note">{t.noCrossProjectLinks}</p>
                )}
              </div>
            </section>
          </div>
          <div className="universe-grid">
            <UniversePathsPanel locale={locale} paths={paths} />
            <UniverseAgentTasksPanel locale={locale} tasks={tasks} />
          </div>
          {diffReport ? <UniverseDiffPanel locale={locale} report={diffReport} /> : null}
          <section className="universe-links panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">{t.allProjects}</span>
                <h2>{t.crossProjectLinks}</h2>
              </div>
              <Route size={18} />
            </div>
            {links.length ? (
              <div className="universe-link-list">
                {links.map((link) => (
                  <article className="universe-link" key={link.id}>
                    <div className="universe-link-main">
                      <div>
                        <span>{link.source.project_id}</span>
                        <strong>{link.source.label}</strong>
                        <code>{link.source.source_path ?? link.source.type}</code>
                      </div>
                      <Route size={16} />
                      <div>
                        <span>{link.target.project_id}</span>
                        <strong>{link.target.label}</strong>
                        <code>{link.target.source_path ?? link.target.type}</code>
                      </div>
                    </div>
                    <div className="universe-link-meta">
                      <span>{t.linkScore}: {formatPercent(link.score)}</span>
                      <span>{link.type}</span>
                      <span>{t.linkReason}: {link.reason}</span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p className="empty-note">{t.noCrossProjectLinks}</p>
            )}
          </section>
        </>
      ) : (
        <EmptyArchiveState archiveCount={archiveIds.length} locale={locale} />
      )}
    </section>
  );
}

function UniversePathsPanel({ locale, paths }: { locale: Locale; paths: UniverseExplorationPath[] }) {
  const t = copy[locale];
  return (
    <section className="universe-panel panel">
      <div className="panel-title">
        <Route size={16} />
        {t.savedPaths}
      </div>
      <div className="universe-mini-list">
        {paths.length ? (
          paths.slice(0, 8).map((path) => (
            <article className="universe-mini-card" key={path.id}>
              <strong>{path.name}</strong>
              <p>{path.project_ids.join(" / ")}</p>
              <div className="mission-task-metrics">
                <span>{t.sharedClusters}: {path.cluster_ids.length}</span>
                <span>{t.crossProjectLinks}: {path.link_ids.length}</span>
              </div>
            </article>
          ))
        ) : (
          <p className="empty-note">{t.noSavedPaths}</p>
        )}
      </div>
    </section>
  );
}

function UniverseAgentTasksPanel({ locale, tasks }: { locale: Locale; tasks: UniverseAgentTask[] }) {
  const t = copy[locale];
  return (
    <section className="universe-panel panel">
      <div className="panel-title">
        <Command size={16} />
        {t.universeAgentTasks}
      </div>
      <div className="universe-mini-list">
        {tasks.length ? (
          tasks.slice(0, 8).map((task) => (
            <article className="universe-mini-card" key={task.id}>
              <div className="universe-mini-head">
                <strong>{task.objective}</strong>
                <span>{missionStatusLabel(task.status, locale)}</span>
              </div>
              <p>{task.project_ids.join(" / ")}</p>
              <div className="mission-task-metrics">
                <span>{t.findings}: {task.findings.length}</span>
                <span>{t.evidenceUsed}: {task.evidence.length}</span>
              </div>
            </article>
          ))
        ) : (
          <p className="empty-note">{t.noUniverseTasks}</p>
        )}
      </div>
    </section>
  );
}

const diffValueText = (value: unknown, fallback = "") => {
  if (typeof value === "string") return value;
  if (typeof value === "number" && Number.isFinite(value)) return formatNumber(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  return fallback;
};

const diffStringList = (value: unknown) =>
  Array.isArray(value)
    ? value
        .map((item) => diffValueText(item))
        .filter((item) => item.length > 0)
    : [];

const diffNumberValue = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value) ? value : 0;

function UniverseDiffPanel({ locale, report }: { locale: Locale; report: ProjectArchitectureDiffReport }) {
  const t = copy[locale];
  const labels = locale === "zh"
    ? {
        sections: "正式章节",
        componentDelta: "组件差异",
        riskPoints: "风险点",
        migrationNotes: "迁移/复用建议",
        evidenceChain: "证据链",
        left: "A",
        right: "B",
        delta: "差值",
        severity: "等级",
      }
    : {
        sections: "Formal sections",
        componentDelta: "Component delta",
        riskPoints: "Risk points",
        migrationNotes: "Migration / reuse notes",
        evidenceChain: "Evidence chain",
        left: "A",
        right: "B",
        delta: "Delta",
        severity: "Severity",
      };
  const componentLeft = metadataObject(report.component_delta, "left");
  const componentRight = metadataObject(report.component_delta, "right");
  const componentDelta = metadataObject(report.component_delta, "delta");
  const componentCategories = Array.from(
    new Set([...Object.keys(componentLeft), ...Object.keys(componentRight), ...Object.keys(componentDelta)]),
  ).sort();

  return (
    <section className="universe-diff panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{report.left_project_id} / {report.right_project_id}</span>
          <h2>{t.diffReport}</h2>
        </div>
        <GitBranch size={18} />
      </div>
      <p>{report.summary}</p>
      <div className="universe-diff-grid">
        <div>
          <strong>{t.sharedClusters}</strong>
          <span>{report.shared_clusters.slice(0, 6).map((cluster) => cluster.label).join(" · ") || t.pending}</span>
        </div>
        <div>
          <strong>{t.uniqueLeft}</strong>
          <span>{report.only_left.slice(0, 6).map((ref) => ref.label).join(" · ") || t.pending}</span>
        </div>
        <div>
          <strong>{t.uniqueRight}</strong>
          <span>{report.only_right.slice(0, 6).map((ref) => ref.label).join(" · ") || t.pending}</span>
        </div>
      </div>
      <div className="mission-task-metrics">
        {Object.entries(report.metric_delta).map(([key, value]) => (
          <span key={key}>{key}: {formatNumber(value)}</span>
        ))}
      </div>
      <div className="universe-diff-section-list" aria-label={labels.sections}>
        {report.sections.slice(0, 6).map((section, index) => {
          const title = diffValueText(section.title, `${labels.sections} ${index + 1}`);
          const summary = diffValueText(section.summary);
          const bullets = diffStringList(section.bullets);
          return (
            <article className="universe-diff-section" key={diffValueText(section.id, title)}>
              <strong>{title}</strong>
              {summary ? <p>{summary}</p> : null}
              {bullets.length ? (
                <ul>
                  {bullets.slice(0, 5).map((bullet) => (
                    <li key={bullet}>{bullet}</li>
                  ))}
                </ul>
              ) : null}
            </article>
          );
        })}
      </div>
      <div className="universe-diff-split">
        <section className="universe-diff-block" aria-label={labels.componentDelta}>
          <strong>{labels.componentDelta}</strong>
          <div className="component-delta-table">
            <span>Component</span>
            <span>{labels.left}</span>
            <span>{labels.right}</span>
            <span>{labels.delta}</span>
            {componentCategories.slice(0, 10).map((category) => (
              <Fragment key={category}>
                <b>{category}</b>
                <span>{formatNumber(diffNumberValue(componentLeft[category]))}</span>
                <span>{formatNumber(diffNumberValue(componentRight[category]))}</span>
                <span className={diffNumberValue(componentDelta[category]) === 0 ? "" : "accent"}>
                  {diffNumberValue(componentDelta[category]) > 0 ? "+" : ""}
                  {formatNumber(diffNumberValue(componentDelta[category]))}
                </span>
              </Fragment>
            ))}
          </div>
        </section>
        <section className="universe-diff-block" aria-label={labels.riskPoints}>
          <strong>{labels.riskPoints}</strong>
          {report.risk_points.length ? report.risk_points.slice(0, 5).map((risk, index) => (
            <article className="risk-point" key={`${diffValueText(risk.title, "risk")}-${index}`}>
              <span>{labels.severity}: {diffValueText(risk.severity, "review")}</span>
              <b>{diffValueText(risk.title, "Risk")}</b>
              <p>{diffValueText(risk.summary)}</p>
            </article>
          )) : <p className="empty-note">{t.pending}</p>}
        </section>
      </div>
      <div className="universe-diff-split">
        <section className="universe-diff-block" aria-label={labels.migrationNotes}>
          <strong>{labels.migrationNotes}</strong>
          {report.migration_notes.length ? (
            <ul className="compact-list">
              {report.migration_notes.slice(0, 6).map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          ) : <p className="empty-note">{t.pending}</p>}
        </section>
        <section className="universe-diff-block" aria-label={labels.evidenceChain}>
          <strong>{labels.evidenceChain}</strong>
          <div className="universe-evidence-chain">
            {report.evidence_chain.slice(0, 6).map((item, index) => (
              <article key={`${diffValueText(item.evidence_id, "evidence")}-${index}`}>
                <span>{diffValueText(item.project_id)} · {diffValueText(item.entity_label)}</span>
                <b>{diffValueText(item.title, diffValueText(item.evidence_id, "Evidence"))}</b>
                <code>{diffValueText(item.source_path, diffValueText(item.source_type))}</code>
                <p>{diffValueText(item.snippet)}</p>
              </article>
            ))}
            {!report.evidence_chain.length ? <p className="empty-note">{t.pending}</p> : null}
          </div>
        </section>
      </div>
    </section>
  );
}

type MetaverseFocus = {
  id: string;
  rawId: string;
  kind: "project" | "cluster";
  label: string;
  detail: string;
};

function KnowledgeMetaverseViewport({
  locale,
  onFocusChange,
  universe,
}: {
  locale: Locale;
  onFocusChange: (focus: MetaverseFocus | null) => void;
  universe: ProjectKnowledgeUniverse;
}) {
  const t = copy[locale];
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [focus, setFocus] = useState<MetaverseFocus | null>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x061018);
    scene.fog = new THREE.Fog(0x061018, 12, 28);

    const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 100);
    camera.position.set(0, 5.5, 13);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: false,
      preserveDrawingBuffer: true,
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    mount.appendChild(renderer.domElement);

    const root = new THREE.Group();
    scene.add(root);

    const ambient = new THREE.AmbientLight(0x8fb8ff, 0.8);
    scene.add(ambient);
    const keyLight = new THREE.PointLight(0x35d0ba, 2.2, 40);
    keyLight.position.set(4, 7, 5);
    scene.add(keyLight);
    const rimLight = new THREE.PointLight(0xf3b65f, 1.4, 32);
    rimLight.position.set(-6, -2, 6);
    scene.add(rimLight);

    const projectPositions = new Map<string, THREE.Vector3>();
    const selectable: THREE.Mesh[] = [];
    const projectGeometry = new THREE.SphereGeometry(0.24, 32, 18);
    const clusterGeometry = new THREE.IcosahedronGeometry(0.18, 1);
    const projectMaterials = [
      new THREE.MeshStandardMaterial({ color: 0x35d0ba, emissive: 0x0b5e56, roughness: 0.42, metalness: 0.2 }),
      new THREE.MeshStandardMaterial({ color: 0x6aa8ff, emissive: 0x183a73, roughness: 0.38, metalness: 0.18 }),
      new THREE.MeshStandardMaterial({ color: 0xf3b65f, emissive: 0x6a3b10, roughness: 0.46, metalness: 0.16 }),
      new THREE.MeshStandardMaterial({ color: 0xb894ff, emissive: 0x3d2473, roughness: 0.42, metalness: 0.18 }),
    ];
    const clusterMaterial = new THREE.MeshStandardMaterial({
      color: 0xeef6ff,
      emissive: 0x335577,
      roughness: 0.32,
      metalness: 0.08,
    });
    const projectCount = Math.max(universe.projects.length, 1);
    universe.projects.forEach((project, index) => {
      const angle = (index / projectCount) * Math.PI * 2;
      const radius = 4.9 + (index % 3) * 0.25;
      const position = new THREE.Vector3(
        Math.cos(angle) * radius,
        Math.sin(index * 1.7) * 0.6,
        Math.sin(angle) * radius,
      );
      projectPositions.set(project.project_id, position);
      const mesh = new THREE.Mesh(projectGeometry, projectMaterials[index % projectMaterials.length]);
      mesh.position.copy(position);
      mesh.userData = {
        id: `project:${project.project_id}`,
        rawId: project.project_id,
        kind: "project",
        label: project.project_id,
        detail: `${formatNumber(project.metrics.entities ?? 0)} ${t.entitiesUsed} · ${formatNumber(project.metrics.evidence ?? 0)} ${t.evidenceUsed}`,
      } satisfies MetaverseFocus;
      root.add(mesh);
      selectable.push(mesh);
    });

    const clusterPositions = new Map<string, THREE.Vector3>();
    const clusterCount = Math.max(universe.clusters.length, 1);
    universe.clusters.slice(0, 40).forEach((cluster, index) => {
      const angle = (index / clusterCount) * Math.PI * 2 + Math.PI / 7;
      const radius = 1.65 + (index % 4) * 0.22;
      const position = new THREE.Vector3(
        Math.cos(angle) * radius,
        Math.sin(index * 1.2) * 1.1,
        Math.sin(angle) * radius,
      );
      clusterPositions.set(cluster.id, position);
      const mesh = new THREE.Mesh(clusterGeometry, clusterMaterial.clone());
      mesh.scale.setScalar(0.85 + Math.min(0.7, cluster.entity_refs.length * 0.08));
      mesh.position.copy(position);
      mesh.userData = {
        id: `cluster:${cluster.id}`,
        rawId: cluster.id,
        kind: "cluster",
        label: cluster.label,
        detail: `${cluster.project_ids.length} ${t.universeProjects} · ${formatPercent(cluster.score)}`,
      } satisfies MetaverseFocus;
      root.add(mesh);
      selectable.push(mesh);
    });

    const lineMaterial = new THREE.LineBasicMaterial({
      color: 0x6aa8ff,
      transparent: true,
      opacity: 0.42,
    });
    const clusterByProject = new Map<string, THREE.Vector3[]>();
    universe.clusters.slice(0, 40).forEach((cluster) => {
      const clusterPosition = clusterPositions.get(cluster.id);
      if (!clusterPosition) return;
      cluster.project_ids.forEach((projectId) => {
        const current = clusterByProject.get(projectId) ?? [];
        current.push(clusterPosition);
        clusterByProject.set(projectId, current);
      });
    });
    clusterByProject.forEach((positions, projectId) => {
      const projectPosition = projectPositions.get(projectId);
      if (!projectPosition) return;
      positions.slice(0, 10).forEach((clusterPosition) => {
        const geometry = new THREE.BufferGeometry().setFromPoints([
          projectPosition,
          new THREE.Vector3(
            (projectPosition.x + clusterPosition.x) / 2,
            1.2,
            (projectPosition.z + clusterPosition.z) / 2,
          ),
          clusterPosition,
        ]);
        root.add(new THREE.Line(geometry, lineMaterial));
      });
    });

    const starGeometry = new THREE.BufferGeometry();
    const starPositions: number[] = [];
    for (let index = 0; index < 420; index += 1) {
      const radius = 9 + Math.random() * 10;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      starPositions.push(
        radius * Math.sin(phi) * Math.cos(theta),
        radius * Math.cos(phi),
        radius * Math.sin(phi) * Math.sin(theta),
      );
    }
    starGeometry.setAttribute("position", new THREE.Float32BufferAttribute(starPositions, 3));
    const stars = new THREE.Points(
      starGeometry,
      new THREE.PointsMaterial({ color: 0x9fb7d8, size: 0.025, transparent: true, opacity: 0.65 }),
    );
    scene.add(stars);

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2(2, 2);
    let hovered: THREE.Mesh | null = null;
    let targetRotationY = 0;
    let targetRotationX = 0;
    let targetDistance = 13;
    let isDragging = false;
    let lastPointerX = 0;
    let lastPointerY = 0;
    let frameId = 0;

    const resize = () => {
      const width = Math.max(320, mount.clientWidth);
      const height = Math.max(360, mount.clientHeight);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    };

    const updatePointer = (event: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      if (isDragging) {
        targetRotationY += (event.clientX - lastPointerX) * 0.006;
        targetRotationX += (event.clientY - lastPointerY) * 0.004;
        targetRotationX = Math.max(-0.55, Math.min(0.55, targetRotationX));
      }
      lastPointerX = event.clientX;
      lastPointerY = event.clientY;
    };

    const handlePointerDown = (event: PointerEvent) => {
      isDragging = true;
      lastPointerX = event.clientX;
      lastPointerY = event.clientY;
      renderer.domElement.setPointerCapture(event.pointerId);
    };

    const handlePointerUp = (event: PointerEvent) => {
      isDragging = false;
      if (renderer.domElement.hasPointerCapture(event.pointerId)) {
        renderer.domElement.releasePointerCapture(event.pointerId);
      }
    };

    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();
      targetDistance = Math.max(6.8, Math.min(18, targetDistance + event.deltaY * 0.006));
    };

    const handleClick = () => {
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(selectable, false)[0]?.object as THREE.Mesh | undefined;
      if (hit?.userData) {
        const nextFocus = hit.userData as MetaverseFocus;
        setFocus(nextFocus);
        onFocusChange(nextFocus);
      }
    };

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(mount);
    renderer.domElement.addEventListener("pointerdown", handlePointerDown);
    renderer.domElement.addEventListener("pointermove", updatePointer);
    renderer.domElement.addEventListener("pointerup", handlePointerUp);
    renderer.domElement.addEventListener("pointerleave", handlePointerUp);
    renderer.domElement.addEventListener("wheel", handleWheel, { passive: false });
    renderer.domElement.addEventListener("click", handleClick);
    resize();

    const animate = () => {
      frameId = window.requestAnimationFrame(animate);
      camera.position.z += (targetDistance - camera.position.z) * 0.08;
      camera.lookAt(0, 0, 0);
      root.rotation.y += (targetRotationY + performance.now() * 0.00007 - root.rotation.y) * 0.018;
      root.rotation.x += (targetRotationX - root.rotation.x) * 0.025;
      stars.rotation.y += 0.0005;

      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(selectable, false)[0]?.object as THREE.Mesh | undefined;
      if (hovered && hovered !== hit) hovered.scale.setScalar(1);
      hovered = hit ?? null;
      if (hovered) hovered.scale.setScalar(1.28);

      renderer.render(scene, camera);
    };
    animate();

    return () => {
      window.cancelAnimationFrame(frameId);
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener("pointerdown", handlePointerDown);
      renderer.domElement.removeEventListener("pointermove", updatePointer);
      renderer.domElement.removeEventListener("pointerup", handlePointerUp);
      renderer.domElement.removeEventListener("pointerleave", handlePointerUp);
      renderer.domElement.removeEventListener("wheel", handleWheel);
      renderer.domElement.removeEventListener("click", handleClick);
      mount.removeChild(renderer.domElement);
      projectGeometry.dispose();
      clusterGeometry.dispose();
      starGeometry.dispose();
      lineMaterial.dispose();
      projectMaterials.forEach((material) => material.dispose());
      clusterMaterial.dispose();
      renderer.dispose();
    };
  }, [locale, onFocusChange, t.entitiesUsed, t.evidenceUsed, t.universeProjects, universe]);

  const fallbackFocus =
    focus ??
    (universe.projects[0]
      ? {
          id: `project:${universe.projects[0].project_id}`,
          rawId: universe.projects[0].project_id,
          kind: "project" as const,
          label: universe.projects[0].project_id,
          detail: `${formatNumber(universe.projects[0].metrics.entities ?? 0)} ${t.entitiesUsed}`,
        }
      : null);

  return (
    <section className="metaverse-stage" aria-label={String(t.metaverseLayer)}>
      <div className="metaverse-canvas" ref={mountRef} />
      <div className="metaverse-overlay">
        <div>
          <span className="eyebrow">{t.metaverseLayer}</span>
          <h2>{t.universePage}</h2>
          <p>{t.metaverseHint}</p>
        </div>
        <div className="metaverse-focus">
          <span>{t.metaverseFocus}</span>
          <strong>{fallbackFocus?.label ?? t.pending}</strong>
          <p>{fallbackFocus?.detail ?? t.universeEmpty}</p>
        </div>
      </div>
    </section>
  );
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

function agentProofPhases(report: ProjectAgentReport | null, locale: Locale) {
  const t = copy[locale];
  const results = report ? agentRoleOrder.map((role) => report.agents[role]).filter(Boolean) : [];
  const workLogCount = results.reduce(
    (count, result) => count + (result.metadata?.agent_sdk?.work_log?.length ?? 0),
    0,
  );
  const toolCount = new Set(
    results.flatMap((result) => result.metadata?.agent_sdk?.tools ?? []),
  ).size;
  const evidenceCount = new Set(results.flatMap((result) => result.evidence_card_ids)).size;
  const entityCount = new Set(results.flatMap((result) => result.entity_ids)).size;
  const validationCount = results.filter((result) => result.metadata?.agent_sdk?.validation?.status).length;
  const curator = report?.agents.curator;

  return [
    {
      label: String(t.proofPhasePlan),
      value: report ? `${results.length}/5` : "0/5",
      detail: locale === "zh" ? "角色计划" : "roles planned",
      complete: Boolean(report),
    },
    {
      label: String(t.proofPhaseAction),
      value: String(workLogCount || toolCount),
      detail: locale === "zh" ? `${toolCount} 个工具信号` : `${toolCount} tool signals`,
      complete: workLogCount > 0 || toolCount > 0,
    },
    {
      label: String(t.proofPhaseObservation),
      value: String(evidenceCount),
      detail: locale === "zh" ? `${entityCount} 个实体` : `${entityCount} entities`,
      complete: evidenceCount > 0 || entityCount > 0,
    },
    {
      label: String(t.proofPhaseVerify),
      value: String(validationCount),
      detail: locale === "zh" ? "验证状态" : "validation states",
      complete: validationCount > 0,
    },
    {
      label: String(t.proofPhaseFinal),
      value: curator ? `${Math.round(curator.confidence * 100)}%` : "0%",
      detail: locale === "zh" ? "策展置信度" : "curator confidence",
      complete: Boolean(curator?.summary),
    },
  ];
}

function agentProofTimeline(report: ProjectAgentReport | null, locale: Locale): AgentProofTimelineEvent[] {
  if (!report) return [];
  return agentRoleOrder.flatMap((role) => {
    const result = report.agents[role];
    if (!result) return [];
    const sdk = result.metadata?.agent_sdk;
    const validationStatus = sdk?.validation?.status ?? "pending";
    const validationNotes = sdk?.validation?.notes ?? [];
    const missingOutputs = sdk?.validation?.missing_outputs ?? [];
    const isAccepted = validationStatus === "accepted";
    const status: AgentProofTimelineEvent["status"] =
      result.status === "complete" && isAccepted ? "supported" : "review";
    const roleLabel = agentRoleLabels[locale][role] ?? role;
    const workLogDetail = sdk?.work_log?.map((item) => item.detail || item.step).filter(Boolean).join(" ");
    const handoffCount = Object.keys(sdk?.handoffs ?? {}).length;
    const inputCounts = sdk?.input_counts ?? {};
    const expectedOutputs = sdk?.expected_outputs ?? [];
    const tools = sdk?.tools ?? [];

    return [
      {
        id: `${role}:plan`,
        phase: "plan",
        role,
        title: `${roleLabel} · ${String(copy[locale].proofPhasePlan)}`,
        detail:
          sdk?.mission ||
          (locale === "zh" ? "加载角色目标和依赖。" : "Loaded role objective and dependencies."),
        status: sdk ? "supported" : "pending",
        evidenceCount: 0,
        entityCount: Number(inputCounts.entities ?? 0),
        relationCount: Number(inputCounts.relations ?? 0),
        tools: [],
      },
      {
        id: `${role}:action`,
        phase: "action",
        role,
        title: `${roleLabel} · ${String(copy[locale].proofPhaseAction)}`,
        detail:
          tools.length
            ? `${locale === "zh" ? "执行工具" : "Executed tools"}: ${tools.join(", ")}`
            : (locale === "zh" ? "没有记录工具调用。" : "No tool call record."),
        status: tools.length ? "supported" : "review",
        evidenceCount: 0,
        entityCount: 0,
        relationCount: 0,
        tools,
      },
      {
        id: `${role}:observation`,
        phase: "observation",
        role,
        title: `${roleLabel} · ${String(copy[locale].proofPhaseObservation)}`,
        detail:
          workLogDetail ||
          result.summary ||
          (locale === "zh" ? "没有观察记录。" : "No observation record."),
        status: result.summary ? "supported" : "review",
        evidenceCount: result.evidence_card_ids.length,
        entityCount: result.entity_ids.length,
        relationCount: result.relation_ids.length,
        tools: [],
      },
      {
        id: `${role}:verify`,
        phase: "verify",
        role,
        title: `${roleLabel} · ${String(copy[locale].proofPhaseVerify)}`,
        detail:
          [
            `${locale === "zh" ? "验证状态" : "Validation"}: ${validationStatus}`,
            validationNotes.length ? validationNotes.join("; ") : "",
            missingOutputs.length ? `${locale === "zh" ? "缺少输出" : "Missing outputs"}: ${missingOutputs.join(", ")}` : "",
          ].filter(Boolean).join(" · ") ||
          (locale === "zh" ? "没有验证记录。" : "No validation record."),
        status,
        evidenceCount: result.evidence_card_ids.length,
        entityCount: result.entity_ids.length,
        relationCount: result.relation_ids.length,
        tools: sdk?.validation ? ["output_validator"] : [],
      },
      {
        id: `${role}:final`,
        phase: "final",
        role,
        title: `${roleLabel} · ${String(copy[locale].proofPhaseFinal)}`,
        detail:
          `${result.summary} ${
            handoffCount
              ? locale === "zh"
                ? `接收 ${handoffCount} 个上游 handoff。`
                : `Received ${handoffCount} upstream handoff(s).`
              : ""
          }`.trim(),
        status,
        evidenceCount: result.evidence_card_ids.length,
        entityCount: result.entity_ids.length,
        relationCount: result.relation_ids.length,
        tools: expectedOutputs,
      },
    ];
  });
}

function ModelStatusPanel({
  agentStatus,
  graphStoreStatus,
  hybridRagStatus,
  isRebuildingHybridRag,
  locale,
  onRebuildHybridRag,
  report,
}: {
  agentStatus: AgentStatus | null;
  graphStoreStatus: GraphStoreStatus | null;
  hybridRagStatus: HybridRagStatus | null;
  isRebuildingHybridRag: boolean;
  locale: Locale;
  onRebuildHybridRag: () => void;
  report: ProjectAgentReport | null;
}) {
  const t = copy[locale];
  const coverageLabel = hybridRagStatus?.coverage_percent !== undefined
    ? `${formatPercent(Number(hybridRagStatus.coverage_ratio ?? 0))}`
    : "";
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
        <span>{t.graphStore}</span>
        <strong>
          {graphStoreStatus
            ? `${graphStoreStatus.provider} · ${
                graphStoreStatus.mode === "production"
                  ? t.productionGraph
                  : graphStoreStatus.mode
              }`
            : t.pending}
        </strong>
        <span>{t.scope}</span>
        <strong>{report?.scan_profile ?? "architecture"}</strong>
        <span>{t.hybridRag}</span>
        <strong>
          {hybridRagStatus
            ? `${formatNumber(hybridRagStatus.indexed_chunks)} / ${formatNumber(hybridRagStatus.candidate_chunks ?? 0)} · ${coverageLabel}`
            : t.pending}
        </strong>
        {hybridRagStatus?.stale || hybridRagStatus?.health === "warning" ? (
          <>
            <span>{locale === "zh" ? "RAG 状态" : "RAG status"}</span>
            <strong>{hybridRagStatus.health_warnings?.[0] ?? (locale === "zh" ? "需要重建" : "Needs rebuild")}</strong>
          </>
        ) : null}
        <span>{t.multimodal}</span>
        <strong>
          {hybridRagStatus
            ? `${formatNumber(hybridRagStatus.image_chunks)} image chunks · ${
                hybridRagStatus.vision_enabled ? hybridRagStatus.vision_provider : t.fallback
              }`
            : t.pending}
        </strong>
      </div>
      <button
        className="ghost-button compact"
        disabled={isRebuildingHybridRag}
        onClick={onRebuildHybridRag}
        type="button"
      >
        <Sparkles size={14} />
        {isRebuildingHybridRag
          ? locale === "zh" ? "重建中" : "Rebuilding"
          : locale === "zh" ? "重建 RAG 索引" : "Rebuild RAG index"}
      </button>
    </section>
  );
}

const systemStatusLabel = (status: string, locale: Locale) => {
  const labels: Record<Locale, Record<string, string>> = {
    zh: {
      working: "工作中",
      warning: "需检查",
      disabled: "未启用",
      partial: "部分可用",
      error: "错误",
    },
    en: {
      working: "Working",
      warning: "Review",
      disabled: "Disabled",
      partial: "Partial",
      error: "Error",
    },
  };
  return labels[locale][status] ?? status;
};

const systemDetailText = (value: unknown, locale: Locale) => {
  if (typeof value === "boolean") return value ? (locale === "zh" ? "是" : "Yes") : (locale === "zh" ? "否" : "No");
  if (typeof value === "number") return formatNumber(value);
  if (typeof value === "string") {
    if (!value || value === "none") return locale === "zh" ? "无" : "-";
    return value;
  }
  if (value === null || value === undefined) return "-";
  return JSON.stringify(value);
};

const systemDetailLabel = (key: string, locale: Locale) => {
  if (locale === "en") return key;
  const labels: Record<string, string> = {
    api_key_present: "API Key 存在",
    api_key_required: "需要 API Key",
    base_url_present: "Base URL 存在",
    endpoint_reachable: "端点可访问",
    model_available: "模型已安装",
    configured_dimensions: "配置维度",
    latest_dense_provider: "最近向量提供方",
    latest_dense_dimension: "最近向量维度",
    latest_vision_provider: "最近视觉提供方",
    latest_archive_used_vision: "最近档案使用视觉",
    latest_image_chunks: "最近图片块",
    max_image_size: "最大图片尺寸",
    mode: "模式",
    database: "数据库",
    uri_present: "URI 存在",
    project_isolation: "项目隔离",
    persist_directory: "持久化目录",
    latest_collection: "最近集合",
    latest_indexed_chunks: "最近索引块",
    latest_bm25_collection: "最近 BM25 集合",
    latest_text_chunks: "最近文本块",
    dense_top_k: "Dense Top-K",
    sparse_top_k: "BM25 Top-K",
    fusion_top_k: "融合 Top-K",
    rrf_k: "RRF K",
    llm_enabled: "LLM 已启用",
    used: "已使用",
    provider: "提供方",
    model: "模型",
    fallback: "降级",
    dimension: "维度",
    fallback_reasons: "降级原因",
    collection: "集合",
    indexed_chunks: "索引块",
    chroma_ready: "Chroma 就绪",
    bm25_ready: "BM25 就绪",
    rrf_ready: "RRF 就绪",
    text_chunks: "文本块",
    image_chunks: "图片块",
    enabled: "已启用",
  };
  return labels[key] ?? key;
};

const systemWarningText = (warning: unknown, locale: Locale) => {
  const text = String(warning);
  if (locale === "en") return text;
  if (text === "Vision LLM is disabled in settings.") return "Vision LLM 在配置中未启用。";
  if (text === "Vision is enabled, but no usable credential or local endpoint was detected.") {
    return "Vision 已启用，但没有检测到可用凭证或本地端点。";
  }
  if (text.startsWith("Ollama vision endpoint is not reachable:")) {
    return `Ollama Vision 端点不可访问：${text.split(": ").slice(1).join(": ")}`;
  }
  if (text.startsWith("Configured Ollama vision model is not installed:")) {
    return `配置的 Ollama Vision 模型还没有安装：${text.split(": ").slice(1).join(": ")}`;
  }
  if (text === "Latest archive has image chunks but did not successfully use vision; image evidence may be metadata fallback only.") {
    return "最近档案包含图片块，但没有成功使用视觉模型；图片证据可能只是元数据兜底。";
  }
  if (text === "No archive with image/vision status has been generated yet.") {
    return "还没有生成带图片/视觉状态的档案。";
  }
  if (text === "Latest archive has no image chunks, so vision has not been exercised by archive ingestion yet.") {
    return "最近档案没有图片块，所以摄取流程还没有实际验证 Vision。";
  }
  if (text === "Latest Hybrid RAG index used local_hash fallback embeddings.") {
    return "最近 Hybrid RAG 索引用了 local_hash 兜底向量。";
  }
  if (text === "No Hybrid RAG index status exists yet; upload or regenerate an archive to verify embeddings.") {
    return "还没有 Hybrid RAG 索引状态；上传或重新生成档案后才能验证 Embedding。";
  }
  if (text === "No archive has built a vector index yet.") {
    return "还没有档案构建过向量索引。";
  }
  if (text === "No Hybrid RAG index status exists yet.") {
    return "还没有 Hybrid RAG 索引状态。";
  }
  if (text === "Latest Hybrid RAG status did not include a BM25 collection.") {
    return "最近 Hybrid RAG 状态里没有 BM25 集合。";
  }
  if (text === "Agent runtime is available, but currently using deterministic rules instead of LLM enhancement.") {
    return "Agent 运行时可用，但当前使用规则兜底而不是 LLM 增强。";
  }
  return text;
};

function SystemConfigPage({
  check,
  error,
  harnessSummary,
  isLoading,
  locale,
  onRefresh,
}: {
  check: SystemConfigCheck | null;
  error: string;
  harnessSummary: HarnessRunSummary | null;
  isLoading: boolean;
  locale: Locale;
  onRefresh: () => void;
}) {
  const labels = locale === "zh"
    ? {
        title: "系统配置检查",
        subtitle: "检查 DeepSeek / Ollama / Embedding / Vision / Neo4j / Chroma / BM25 / RRF / Agent 是否配置并工作。",
        refresh: "刷新检查",
        loading: "正在检查系统配置",
        empty: "还没有配置检查结果。",
        provider: "提供方",
        model: "模型",
        configured: "已配置",
        working: "可工作",
        details: "细节",
        harness: "Harness 运行证据",
        warnings: "提醒",
        lastSuccess: "最近成功",
      }
    : {
        title: "System Configuration Check",
        subtitle: "Check whether DeepSeek, Ollama, embeddings, vision, Neo4j, Chroma, BM25, RRF, and Agent runtime are configured and working.",
        refresh: "Refresh check",
        loading: "Checking system configuration",
        empty: "No system check result yet.",
        provider: "Provider",
        model: "Model",
        configured: "Configured",
        working: "Working",
        details: "Details",
        harness: "Harness run evidence",
        warnings: "Warnings",
        lastSuccess: "Last success",
      };
  return (
    <main className="system-config-page">
      <section className="system-config-hero panel">
        <div>
          <span className="eyebrow">{systemStatusLabel(check?.status ?? "partial", locale)}</span>
          <h2>{labels.title}</h2>
          <p>{check?.summary ?? labels.subtitle}</p>
        </div>
        <button className="primary-button compact" disabled={isLoading} onClick={onRefresh} type="button">
          <ShieldCheck size={15} />
          {isLoading ? labels.loading : labels.refresh}
        </button>
      </section>
      {error ? (
        <div className="mission-error" role="alert">
          <strong>{locale === "zh" ? "配置检查失败" : "Config check failed"}</strong>
          <span>{error}</span>
        </div>
      ) : null}
      {check?.metadata?.runtime_evidence ? (
        <RuntimeEvidencePanel evidence={check.metadata.runtime_evidence as Record<string, unknown>} locale={locale} />
      ) : null}
      {harnessSummary ? (
        <section className="runtime-evidence-panel panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">{labels.harness}</span>
              <h2>{statusLabel(harnessSummary.status, locale)}</h2>
            </div>
            <Route size={18} />
          </div>
          <p>{harnessSummary.next_best_action}</p>
          <div className="runtime-evidence-grid">
            <article>
              <strong>{locale === "zh" ? "最近运行" : "Last run"}</strong>
              <span>{String(harnessSummary.last_run.run_id ?? "-")}</span>
              <span>{String(harnessSummary.last_run.kind ?? harnessSummary.phase)}</span>
            </article>
            <article>
              <strong>{locale === "zh" ? "事件" : "Events"}</strong>
              <span>{locale === "zh" ? "最新序列" : "Latest sequence"}: {formatNumber(harnessSummary.latest_sequence)}</span>
              <span>{locale === "zh" ? "产物" : "Artifacts"}: {formatNumber(harnessSummary.artifacts.length)}</span>
            </article>
            <article>
              <strong>{locale === "zh" ? "恢复建议" : "Resume guidance"}</strong>
              <span>{harnessSummary.resume_available ? harnessSummary.resume_action : "-"}</span>
              <span>{harnessSummary.errors[0] ?? harnessSummary.warnings[0] ?? "-"}</span>
            </article>
          </div>
        </section>
      ) : null}
      {check ? (
        <section className="system-config-grid">
          {check.components.map((component) => (
            <article className={`system-config-card ${component.status}`} key={component.id}>
              <div className="system-config-card-head">
                <div>
                  <span className="eyebrow">{component.id}</span>
                  <h3>{component.label}</h3>
                </div>
                <span className={`system-config-status ${component.status}`}>{systemStatusLabel(component.status, locale)}</span>
              </div>
              <div className="system-config-meta">
                <span>{labels.provider}</span>
                <strong>{component.provider}</strong>
                <span>{labels.model}</span>
                <strong>{component.model ?? "-"}</strong>
                <span>{labels.configured}</span>
                <strong>{systemDetailText(component.configured, locale)}</strong>
                <span>{labels.working}</span>
                <strong>{systemDetailText(component.working, locale)}</strong>
              </div>
              <div className="system-config-details">
                <strong>{labels.details}</strong>
                {Object.entries(component.details).slice(0, 9).map(([key, value]) => (
                  <span key={key}>{systemDetailLabel(key, locale)}: {systemDetailText(value, locale)}</span>
                ))}
                {component.last_success ? (
                  <span>{labels.lastSuccess}: {systemDetailText(component.last_success.project_id, locale)}</span>
                ) : null}
              </div>
              {component.warnings.length ? (
                <div className="system-config-warnings">
                  <strong>{labels.warnings}</strong>
                  {component.warnings.map((warning) => (
                    <span key={warning}>{systemWarningText(warning, locale)}</span>
                  ))}
                </div>
              ) : null}
            </article>
          ))}
        </section>
      ) : (
        <section className="empty-archive panel">
          <div className="empty-archive-icon" aria-hidden="true">
            <ShieldCheck size={22} />
          </div>
          <div>
            <h2>{labels.empty}</h2>
            <p>{labels.subtitle}</p>
          </div>
        </section>
      )}
    </main>
  );
}

function RuntimeEvidencePanel({
  evidence,
  locale,
}: {
  evidence: Record<string, unknown>;
  locale: Locale;
}) {
  const labels = locale === "zh"
    ? {
        title: "运行时证据",
        subtitle: "本次系统检查看到的模型、检索器、图谱存储、视觉能力和 fallback。",
      }
    : {
        title: "Runtime evidence",
        subtitle: "Models, retrievers, graph store, vision path, and fallback state observed by this check.",
      };
  const entries = Object.entries(evidence).filter(([key]) => key !== "fallbacks");
  const fallbacks = Array.isArray(evidence.fallbacks) ? evidence.fallbacks : [];
  return (
    <section className="runtime-evidence-panel panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{labels.title}</span>
          <h2>{labels.title}</h2>
        </div>
        <ShieldCheck size={18} />
      </div>
      <p>{labels.subtitle}</p>
      <div className="runtime-evidence-grid">
        {entries.map(([key, value]) => {
          const record = typeof value === "object" && value !== null ? value as Record<string, unknown> : {};
          return (
            <article key={key}>
              <strong>{key}</strong>
              {Object.entries(record).slice(0, 4).map(([itemKey, itemValue]) => (
                <span key={itemKey}>{systemDetailLabel(itemKey, locale)}: {systemDetailText(itemValue, locale)}</span>
              ))}
            </article>
          );
        })}
      </div>
      {fallbacks.length ? (
        <div className="system-config-warnings">
          <strong>{locale === "zh" ? "Fallback / 警告" : "Fallbacks / warnings"}</strong>
          {fallbacks.slice(0, 6).map((warning) => <span key={String(warning)}>{systemWarningText(warning, locale)}</span>)}
        </div>
      ) : null}
    </section>
  );
}

function EvaluationBenchmarkPanel({
  history,
  isRunning,
  locale,
  onRun,
  report,
}: {
  history: EvaluationHistory | null;
  isRunning: boolean;
  locale: Locale;
  onRun: () => void;
  report: ArchiveEvaluationReport | null;
}) {
  const t = copy[locale];
  const metrics = report?.aggregate_metrics ?? {};
  const cases = report?.case_results ?? [];
  return (
    <section className="agent-side-panel evaluation-panel">
      <div className="panel-title">
        <ShieldCheck size={16} />
        {t.evaluationBenchmark}
      </div>
      <div className="evaluation-actions">
        <span>
          {report
            ? `${t.goldenQuestions}: ${report.golden_question_count}`
            : t.pending}
          {history?.metrics?.runs ? ` · ${locale === "zh" ? "历史" : "History"} ${formatNumber(history.metrics.runs)}` : ""}
        </span>
        <button className="ghost-button compact" disabled={isRunning} onClick={onRun} type="button">
          <Sparkles size={14} />
          {isRunning ? t.evaluationRunning : t.runEvaluation}
        </button>
      </div>
      {report ? (
        <>
          <div className="evaluation-metrics">
            <div>
              <span>{t.caseScore}</span>
              <strong>{formatPercent(metrics.case_score)}</strong>
            </div>
            <div>
              <span>{t.entityHitRate}</span>
              <strong>{formatPercent(metrics.entity_hit_rate)}</strong>
            </div>
            <div>
              <span>{t.relationHitRate}</span>
              <strong>{formatPercent(metrics.relation_hit_rate)}</strong>
            </div>
            <div>
              <span>{t.evidenceCoverage}</span>
              <strong>{formatPercent(metrics.evidence_coverage)}</strong>
            </div>
          </div>
          <div className="evaluation-case-list">
            {cases.slice(0, 5).map((item) => (
              <article className="evaluation-case" key={item.question_id}>
                <div>
                  <span className="eyebrow">{item.category}</span>
                  <strong>{formatPercent(item.metrics.case_score)}</strong>
                </div>
                <p>{item.question}</p>
                <div className="mission-task-metrics">
                  <span>{t.entitiesUsed}: {item.matched_entity_ids.length}</span>
                  <span>{t.relationsUsed}: {item.matched_relation_ids.length}</span>
                  <span>{t.evidenceUsed}: {item.matched_evidence_ids.length}</span>
                </div>
              </article>
            ))}
          </div>
        </>
      ) : (
        <p className="empty-note">{t.noEvaluationReport}</p>
      )}
    </section>
  );
}

function AgentEvalHarnessPanel({
  artifacts,
  error,
  harnessCommands,
  harnessSummary,
  harnessTimeline,
  harnessToolResult,
  isRunningHarnessTool,
  isRunning,
  locale,
  onCleanupDryRun,
  onDryRunLiveCommand,
  onExport,
  onRun,
  report,
}: {
  artifacts: HarnessArtifactManifest | null;
  error: string;
  harnessCommands: HarnessCommand[];
  harnessSummary: HarnessRunSummary | null;
  harnessTimeline: HarnessTimeline | null;
  harnessToolResult: HarnessCommandDryRun | Record<string, unknown> | null;
  isRunningHarnessTool: boolean;
  isRunning: boolean;
  locale: Locale;
  onCleanupDryRun: () => void;
  onDryRunLiveCommand: () => void;
  onExport: () => void;
  onRun: () => void;
  report: AgentEvalReport | null;
}) {
  const labels = locale === "zh"
    ? {
        title: "AgentEval Harness",
        subtitle: "把 Agent 输出、Golden Questions、Hybrid RAG、证据支撑和回归检查放在同一个质量闸门里。",
        run: "运行 AgentEval",
        running: "评测中",
        empty: "还没有 AgentEval 报告。运行后会生成质量门、回归结果和项目记忆。",
        gates: "质量门",
        regression: "质量回归",
        recommendations: "建议",
        score: "总评分",
        duration: "耗时",
        indexed: "RAG 索引",
        unsupported: "未支撑声明",
        harness: "运行证据",
        sequence: "事件序列",
        artifacts: "产物",
        next: "下一步",
        liveDryRun: "Live dry-run",
        export: "导出",
        cleanup: "清理预检",
        commands: "命令",
        timeline: "Timeline",
        lastTool: "最近工具",
      }
    : {
        title: "AgentEval Harness",
        subtitle: "Unifies Agent output, golden questions, Hybrid RAG, evidence support, and regression checks.",
        run: "Run AgentEval",
        running: "Evaluating",
        empty: "No AgentEval report yet. Run it to create gates, regression checks, and project memory.",
        gates: "Quality gates",
        regression: "Regression",
        recommendations: "Recommendations",
        score: "Score",
        duration: "Duration",
        indexed: "RAG index",
        unsupported: "Unsupported claims",
        harness: "Run evidence",
        sequence: "Event sequence",
        artifacts: "Artifacts",
        next: "Next",
        liveDryRun: "Live dry-run",
        export: "Export",
        cleanup: "Cleanup check",
        commands: "Commands",
        timeline: "Timeline",
        lastTool: "Last tool",
      };
  const metrics = report?.metrics ?? {};
  const score = Number(metrics.evaluation_score ?? 0);
  const indexed = Number(metrics.rag_indexed_chunks ?? 0);
  const candidate = Number(metrics.rag_candidate_chunks ?? 0);
  const unsupported = Number(metrics.trust_unsupported_claims ?? 0);
  const latestHarnessEvent = harnessTimeline?.timeline.length
    ? harnessTimeline.timeline[harnessTimeline.timeline.length - 1]?.type
    : "-";
  return (
    <section className="agent-eval-panel panel">
      <div className="agent-eval-head">
        <div>
          <span className="eyebrow">{labels.title}</span>
          <h2>{report ? statusLabel(report.status, locale) : labels.title}</h2>
          <p>{labels.subtitle}</p>
        </div>
        <button className="primary-button compact" disabled={isRunning} onClick={onRun} type="button">
          <ShieldCheck size={14} />
          {isRunning ? labels.running : labels.run}
        </button>
      </div>
      {error ? (
        <div className="mission-error" role="alert">
          <strong>{locale === "zh" ? "AgentEval 失败" : "AgentEval failed"}</strong>
          <span>{error}</span>
        </div>
      ) : null}
      {harnessSummary ? (
        <>
          <div className="agent-eval-harness-summary">
            <span>
              <strong>{statusLabel(harnessSummary.status, locale)}</strong>
              {labels.harness}
            </span>
            <span>
              <strong>{formatNumber(harnessSummary.latest_sequence)}</strong>
              {labels.sequence}
            </span>
            <span>
              <strong>{formatNumber(artifacts?.artifacts.length ?? harnessSummary.artifacts.length)}</strong>
              {labels.artifacts}
            </span>
            <span className="agent-eval-harness-next">
              <strong>{labels.next}</strong>
              {harnessSummary.next_best_action}
            </span>
          </div>
          <div className="harness-tool-row">
            <button className="secondary-action compact" disabled={isRunningHarnessTool} onClick={onDryRunLiveCommand} type="button">
              <Command size={14} />
              {labels.liveDryRun}
            </button>
            <button className="secondary-action compact" disabled={isRunningHarnessTool} onClick={onExport} type="button">
              <FileArchive size={14} />
              {labels.export}
            </button>
            <button className="secondary-action compact" disabled={isRunningHarnessTool} onClick={onCleanupDryRun} type="button">
              <ShieldCheck size={14} />
              {labels.cleanup}
            </button>
          </div>
          <div className="harness-tool-status">
            <span><strong>{formatNumber(harnessCommands.length)}</strong>{labels.commands}</span>
            <span><strong>{formatNumber(harnessTimeline?.timeline.length ?? 0)}</strong>{labels.timeline}</span>
            <span><strong>{String(latestHarnessEvent ?? "-")}</strong>{locale === "zh" ? "最新事件" : "Latest event"}</span>
          </div>
          {harnessToolResult ? (
            <pre className="harness-tool-preview" aria-label={labels.lastTool}>
              {JSON.stringify(harnessToolResult, null, 2).slice(0, 900)}
            </pre>
          ) : null}
        </>
      ) : null}
      {report ? (
        <>
          <div className="agent-eval-metrics">
            <span><strong>{formatPercent(score)}</strong>{labels.score}</span>
            <span><strong>{report.duration_seconds.toFixed(1)}s</strong>{labels.duration}</span>
            <span><strong>{formatNumber(indexed)} / {formatNumber(candidate)}</strong>{labels.indexed}</span>
            <span><strong>{formatNumber(unsupported)}</strong>{labels.unsupported}</span>
          </div>
          <div className="agent-eval-grid">
            <article>
              <div className="panel-title">
                <ShieldCheck size={15} />
                {labels.gates}
              </div>
              <div className="agent-eval-gates">
                {report.quality_gates.map((gate) => (
                  <div className={`agent-eval-gate is-${gate.status}`} key={gate.id}>
                    <div>
                      <strong>{gate.label}</strong>
                      <span>{gate.summary}</span>
                    </div>
                    <em>{formatPercent(gate.score)}</em>
                  </div>
                ))}
              </div>
            </article>
            <article>
              <div className="panel-title">
                <Route size={15} />
                {labels.regression}: {statusLabel(report.regression.status, locale)}
              </div>
              <p className="empty-note">{report.regression.summary}</p>
              <div className="agent-eval-checks">
                {report.regression.checks.slice(0, 5).map((check, index) => (
                  <span key={`${String(check.metric)}-${index}`}>
                    <strong>{String(check.metric ?? "metric")}</strong>
                    {String(check.status ?? "pass")} · {String(check.delta ?? "0")}
                  </span>
                ))}
                {!report.regression.checks.length ? (
                  <span><strong>{report.regression.status}</strong>{report.regression.summary}</span>
                ) : null}
              </div>
              <div className="agent-eval-recommendations">
                <strong>{labels.recommendations}</strong>
                {report.recommendations.slice(0, 5).map((item) => <span key={item}>{item}</span>)}
              </div>
            </article>
          </div>
        </>
      ) : (
        <p className="empty-note">{labels.empty}</p>
      )}
    </section>
  );
}

function AgentMemoryPanel({
  locale,
  memory,
}: {
  locale: Locale;
  memory: AgentMemory | null;
}) {
  const labels = locale === "zh"
    ? {
        title: "项目记忆",
        empty: "运行 AgentEval 或 ReAct 任务后，这里会记录项目事实、风险和 Harness 历史。",
        facts: "事实",
        risks: "风险",
        runs: "运行",
        entities: "实体",
        evidence: "证据",
        relations: "关系",
        recommendations: "建议",
      }
    : {
        title: "Project memory",
        empty: "Run AgentEval or ReAct missions to persist facts, risks, and Harness history here.",
        facts: "Facts",
        risks: "Risks",
        runs: "Runs",
        entities: "Entities",
        evidence: "Evidence",
        relations: "Relations",
        recommendations: "Recommendations",
      };
  return (
    <section className="agent-side-panel agent-memory-panel">
      <div className="panel-title">
        <Save size={16} />
        {labels.title}
      </div>
      {memory ? (
        <>
          <div className="trust-metrics">
            <span><strong>{formatNumber(memory.facts.length)}</strong>{labels.facts}</span>
            <span><strong>{formatNumber(memory.risks.length)}</strong>{labels.risks}</span>
            <span><strong>{formatNumber(memory.harness_runs.length)}</strong>{labels.runs}</span>
            <span><strong>{formatNumber(memory.entities.length)}</strong>{labels.entities}</span>
          </div>
          <div className="agent-memory-counts">
            <span>{labels.evidence}: {formatNumber(memory.evidence.length)}</span>
            <span>{labels.relations}: {formatNumber(memory.relations.length)}</span>
            {memory.updated_at ? <span>{memory.updated_at.slice(0, 19).replace("T", " ")}</span> : null}
          </div>
          <div className="agent-memory-list">
            {memory.facts.slice(0, 3).map((item, index) => (
              <article key={`fact-${index}`}>
                <strong>{labels.facts}</strong>
                <p>{item.text ?? item.title}</p>
              </article>
            ))}
            {memory.risks.slice(0, 3).map((item, index) => (
              <article className="is-risk" key={`risk-${index}`}>
                <strong>{item.severity ?? labels.risks}</strong>
                <p>{item.title ?? item.text}</p>
              </article>
            ))}
          </div>
          {memory.recommendations.length ? (
            <div className="agent-eval-recommendations">
              <strong>{labels.recommendations}</strong>
              {memory.recommendations.slice(0, 4).map((item) => <span key={item}>{item}</span>)}
            </div>
          ) : null}
        </>
      ) : (
        <p className="empty-note">{labels.empty}</p>
      )}
    </section>
  );
}

function AgentTrustPanel({
  locale,
  report,
}: {
  locale: Locale;
  report: AgentTrustReport | null;
}) {
  const labels = locale === "zh"
    ? {
        title: "Agent 信任检查",
        empty: "运行 Agent 分析后会显示结论、证据支撑和低置信警告。",
        supported: "有证据",
        partial: "部分支撑",
        unsupported: "未支撑",
        low: "低置信",
        warnings: "警告",
      }
    : {
        title: "Agent trust check",
        empty: "Run Agent analysis to see claims, evidence support, and low-confidence warnings.",
        supported: "Supported",
        partial: "Partial",
        unsupported: "Unsupported",
        low: "Low confidence",
        warnings: "Warnings",
      };
  const metrics = report?.metrics ?? {};
  return (
    <section className="agent-side-panel trust-panel">
      <div className="panel-title">
        <ShieldCheck size={16} />
        {labels.title}
      </div>
      {report ? (
        <>
          <div className="trust-metrics">
            <span><strong>{formatNumber(metrics.supported_claims ?? 0)}</strong>{labels.supported}</span>
            <span><strong>{formatNumber(metrics.partial_claims ?? 0)}</strong>{labels.partial}</span>
            <span><strong>{formatNumber(metrics.unsupported_claims ?? 0)}</strong>{labels.unsupported}</span>
            <span><strong>{formatNumber(metrics.low_confidence_claims ?? 0)}</strong>{labels.low}</span>
          </div>
          {report.warnings.length ? (
            <div className="trust-warning-list">
              <strong>{labels.warnings}</strong>
              {report.warnings.slice(0, 4).map((warning) => <span key={warning}>{warning}</span>)}
            </div>
          ) : null}
        </>
      ) : (
        <p className="empty-note">{labels.empty}</p>
      )}
    </section>
  );
}

function MultimodalInsightsPanel({
  insights,
  locale,
}: {
  insights: MultimodalInsights | null;
  locale: Locale;
}) {
  const labels = locale === "zh"
    ? {
        title: "多模态证据",
        empty: "当前档案还没有图片理解报告。重新生成包含图片的项目后会显示。",
        images: "图片",
        vision: "Vision",
        ocr: "OCR",
        quality: "质量",
        candidates: "图谱候选",
        aligned: "实体对齐",
        support: "支撑状态",
        methods: "理解方法",
      }
    : {
        title: "Multimodal evidence",
        empty: "No image understanding report exists yet. Regenerate an archive with images to show it.",
        images: "Images",
        vision: "Vision",
        ocr: "OCR",
        quality: "Quality",
        candidates: "Graph candidates",
        aligned: "Entity alignment",
        support: "Support status",
        methods: "Understanding methods",
      };
  const contributions = insights?.graph_contributions ?? {};
  const entityCandidates = Array.isArray(contributions.candidate_entities) ? contributions.candidate_entities.length : 0;
  const relationCandidates = Array.isArray(contributions.candidate_relations) ? contributions.candidate_relations.length : 0;
  const alignmentCount = insights?.entity_alignment?.alignment_count ?? 0;
  const alignedImageCount = insights?.entity_alignment?.aligned_image_count ?? 0;
  const supportStatus = String(insights?.evidence_support?.support_status ?? "none");
  const methods = Object.entries(insights?.method_counts ?? {}).slice(0, 3);
  return (
    <section className="agent-side-panel multimodal-panel">
      <div className="panel-title">
        <Boxes size={16} />
        {labels.title}
      </div>
      {insights ? (
        <>
          <div className="trust-metrics">
            <span><strong>{formatNumber(insights.image_count)}</strong>{labels.images}</span>
            <span><strong>{formatNumber(insights.vision_supported)}</strong>{labels.vision}</span>
            <span><strong>{formatNumber(insights.ocr_supported)}</strong>{labels.ocr}</span>
            <span><strong>{formatPercent(insights.average_quality)}</strong>{labels.quality}</span>
          </div>
          <p className="empty-note">
            {labels.candidates}: {formatNumber(entityCandidates)} / {formatNumber(relationCandidates)}
          </p>
          <div className="multimodal-alignment">
            <span><strong>{formatNumber(alignmentCount)}</strong>{labels.aligned} · {formatNumber(alignedImageCount)} {labels.images}</span>
            <span><strong>{supportStatus}</strong>{labels.support}</span>
            {methods.length ? (
              <span>
                <strong>{labels.methods}</strong>
                {methods.map(([method, count]) => `${method}: ${count}`).join(" · ")}
              </span>
            ) : null}
          </div>
        </>
      ) : (
        <p className="empty-note">{labels.empty}</p>
      )}
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
  const phases = agentProofPhases(report, locale);
  const timeline = agentProofTimeline(report, locale);
  return (
    <section className="agent-proof panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{t.agentProof}</span>
          <h2>{t.agentPage}</h2>
        </div>
        <Sparkles size={18} />
      </div>
      <div className="agent-proof-phases">
        {phases.map((phase) => (
          <div className={phase.complete ? "is-complete" : ""} key={phase.label}>
            <span>{phase.label}</span>
            <strong>{phase.value}</strong>
            <small>{phase.detail}</small>
          </div>
        ))}
      </div>
      <div className="agent-proof-timeline">
        <div className="agent-proof-timeline-head">
          <strong>{t.proofTimeline}</strong>
          <span>{timeline.length} events</span>
        </div>
        {timeline.length ? (
          <div className="agent-proof-events">
            {timeline.map((event) => (
              <article className={`agent-proof-event is-${event.status}`} key={event.id}>
                <div>
                  <span>{event.phase}</span>
                  <strong>{event.title}</strong>
                </div>
                <p>{event.detail}</p>
                <div className="mission-task-metrics">
                  <span>{event.status === "supported" ? t.proofSupported : t.proofUncertain}</span>
                  <span>{t.evidenceUsed}: {event.evidenceCount}</span>
                  <span>{t.entitiesUsed}: {event.entityCount}</span>
                  <span>{t.relationsUsed}: {event.relationCount}</span>
                  {event.tools.length ? <span>{t.toolsUsed}: {event.tools.slice(0, 3).join(", ")}</span> : null}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="empty-note">{t.proofTimelineEmpty}</p>
        )}
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

function ProjectIntelligenceReportPanel({
  error,
  isGenerating,
  locale,
  onDownloadMarkdown,
  onDownloadPdf,
  onGenerate,
  report,
}: {
  error: string;
  isGenerating: boolean;
  locale: Locale;
  onDownloadMarkdown: () => void;
  onDownloadPdf: () => void;
  onGenerate: () => void;
  report: ProjectIntelligenceReport | null;
}) {
  const labels = locale === "zh"
    ? {
        title: "正式项目智能报告",
        subtitle: "汇总图谱质量、Agent 结论、评测、多模态、Hybrid RAG 和证据链。",
        generate: "生成正式报告",
        generating: "生成中",
        download: "下载 Markdown",
        downloadPdf: "下载 PDF",
        empty: "还没有正式报告。运行后会生成 JSON 和 Markdown 两份报告。",
        quality: "图谱质量",
        evaluation: "评测分",
        risks: "风险",
        evidence: "证据链",
        next: "下一步",
        rag: "Hybrid RAG",
        multimodal: "多模态",
      }
    : {
        title: "Project intelligence report",
        subtitle: "Combines graph quality, Agent output, evaluation, multimodal evidence, Hybrid RAG, and evidence chains.",
        generate: "Generate formal report",
        generating: "Generating",
        download: "Download Markdown",
        downloadPdf: "Download PDF",
        empty: "No formal report yet. Generate one to persist JSON and Markdown reports.",
        quality: "Graph quality",
        evaluation: "Evaluation",
        risks: "Risks",
        evidence: "Evidence chain",
        next: "Next actions",
        rag: "Hybrid RAG",
        multimodal: "Multimodal",
      };
  const coverage = report?.coverage ?? {};
  const rag = report?.rag_citations ?? {};
  const multimodal = report?.multimodal_evidence ?? {};
  const qualityScore = Number(coverage.quality_score ?? 0);
  const evaluationScore = Number(coverage.evaluation_score ?? 0);
  return (
    <section className="project-report-panel panel">
      <div className="project-report-head">
        <div>
          <span className="eyebrow">{labels.title}</span>
          <h2>{report ? report.project_id : labels.title}</h2>
          <p>{report?.summary ?? labels.subtitle}</p>
        </div>
        <div className="project-report-actions">
          <button className="primary-button compact" disabled={isGenerating} onClick={onGenerate} type="button">
            <FileArchive size={14} />
            {isGenerating ? labels.generating : labels.generate}
          </button>
          <button className="secondary-action compact" disabled={!report} onClick={onDownloadMarkdown} type="button">
            <Save size={14} />
            {labels.download}
          </button>
          <button className="secondary-action compact" disabled={!report} onClick={onDownloadPdf} type="button">
            <FileArchive size={14} />
            {labels.downloadPdf}
          </button>
        </div>
      </div>
      {error ? (
        <div className="mission-error" role="alert">
          <strong>{locale === "zh" ? "报告生成失败" : "Report failed"}</strong>
          <span>{error}</span>
        </div>
      ) : null}
      {report ? (
        <>
          <div className="project-report-metrics">
            <span><strong>{Math.round(qualityScore)} · {String(coverage.quality_grade ?? "E")}</strong>{labels.quality}</span>
            <span><strong>{formatPercent(evaluationScore)}</strong>{labels.evaluation}</span>
            <span><strong>{formatNumber(report.risks.length)}</strong>{labels.risks}</span>
            <span><strong>{formatNumber(report.evidence_chain.length)}</strong>{labels.evidence}</span>
            <span><strong>{formatNumber(Number(rag.indexed_chunks ?? 0))}</strong>{labels.rag}</span>
            <span><strong>{formatNumber(Number(multimodal.image_count ?? 0))}</strong>{labels.multimodal}</span>
          </div>
          <div className="project-report-grid">
            <article>
              <strong>{labels.next}</strong>
              {report.next_actions.slice(0, 4).map((action) => (
                <span key={action}>{action}</span>
              ))}
            </article>
            <article>
              <strong>{labels.risks}</strong>
              {report.risks.slice(0, 4).map((risk, index) => (
                <span key={`${String(risk.title ?? "risk")}-${index}`}>
                  [{String(risk.severity ?? "review")}] {String(risk.title ?? risk.detail ?? "")}
                </span>
              ))}
            </article>
            <article>
              <strong>{labels.evidence}</strong>
              {report.evidence_chain.slice(0, 4).map((item, index) => (
                <span key={`${String(item.claim ?? "claim")}-${index}`}>
                  {String(item.status ?? "unknown")} · {String(item.claim ?? "")}
                </span>
              ))}
            </article>
          </div>
        </>
      ) : (
        <p className="empty-note">{labels.empty}</p>
      )}
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

function TaskCenterPage({
  currentProjectId,
  error,
  isLoading,
  isRunningStressTest,
  jobs,
  locale,
  onCancel,
  onRefresh,
  onRunStressTest,
  stressTestError,
  stressTestReport,
}: {
  currentProjectId: string;
  error: string;
  isLoading: boolean;
  isRunningStressTest: boolean;
  jobs: ArchiveJob[];
  locale: Locale;
  onCancel: (jobId: string) => void;
  onRefresh: () => void;
  onRunStressTest: () => void;
  stressTestError: string;
  stressTestReport: StressTestReport | null;
}) {
  const labels = locale === "zh"
    ? {
        title: "任务中心",
        subtitle: "查看上传、生成档案、Agent 分析等后台任务的状态、进度和失败原因。",
        refresh: "刷新",
        loading: "加载中",
        cancel: "取消",
        current: "当前项目",
        all: "全部任务",
        running: "运行中",
        complete: "已完成",
        failed: "失败",
        cancelled: "已取消",
        empty: "还没有后台任务。上传 ZIP 或运行 Agent 分析后会出现在这里。",
        steps: "阶段记录",
        stressTitle: "档案压力测试",
        stressRun: "运行压力测试",
        stressRunning: "测试中",
        blocking: "阻塞失败",
        languageCoverage: "语言覆盖",
      }
    : {
        title: "Task center",
        subtitle: "Track upload, archive generation, Agent analysis, progress, and failure reasons.",
        refresh: "Refresh",
        loading: "Loading",
        cancel: "Cancel",
        current: "Current project",
        all: "All tasks",
        running: "Running",
        complete: "Complete",
        failed: "Failed",
        cancelled: "Cancelled",
        empty: "No background tasks yet. Upload a ZIP or run Agent analysis to see tasks here.",
        steps: "Stage history",
        stressTitle: "Archive stress test",
        stressRun: "Run stress test",
        stressRunning: "Testing",
        blocking: "Blocking failures",
        languageCoverage: "Language coverage",
      };
  const runningCount = jobs.filter((job) => ["queued", "running"].includes(job.status)).length;
  const completeCount = jobs.filter((job) => job.status === "complete").length;
  const failedCount = jobs.filter((job) => job.status === "failed").length;
  const cancelledCount = jobs.filter((job) => job.status === "cancelled").length;
  const currentProjectJobs = currentProjectId ? jobs.filter((job) => job.project_id === currentProjectId) : [];
  return (
    <section className="task-center-page">
      <div className="task-center-hero panel">
        <div>
          <span className="eyebrow">{labels.title}</span>
          <h2>{labels.all}</h2>
          <p>{labels.subtitle}</p>
        </div>
        <button className="primary-button compact" disabled={isLoading} onClick={onRefresh} type="button">
          <Command size={14} />
          {isLoading ? labels.loading : labels.refresh}
        </button>
      </div>
      <StressTestPanel
        error={stressTestError}
        isRunning={isRunningStressTest}
        labels={labels}
        locale={locale}
        onRun={onRunStressTest}
        report={stressTestReport}
      />
      {error ? (
        <div className="mission-error" role="alert">
          <strong>{locale === "zh" ? "任务加载失败" : "Task load failed"}</strong>
          <span>{error}</span>
        </div>
      ) : null}
      <div className="task-center-metrics">
        <Metric label={labels.running} value={runningCount} icon={<Sparkles size={18} />} />
        <Metric label={labels.complete} value={completeCount} icon={<ShieldCheck size={18} />} />
        <Metric label={labels.failed} value={failedCount} icon={<X size={18} />} />
        <Metric label={labels.cancelled} value={cancelledCount} icon={<Command size={18} />} />
      </div>
      {currentProjectJobs.length ? (
        <section className="task-center-section panel">
          <div className="panel-title">
            <Archive size={16} />
            {labels.current}: {currentProjectId}
          </div>
          <TaskCenterList jobs={currentProjectJobs} labels={labels} locale={locale} onCancel={onCancel} />
        </section>
      ) : null}
      <section className="task-center-section panel">
        <div className="panel-title">
          <ListTree size={16} />
          {labels.all}
        </div>
        {jobs.length ? (
          <TaskCenterList jobs={jobs} labels={labels} locale={locale} onCancel={onCancel} />
        ) : (
          <p className="empty-note">{labels.empty}</p>
        )}
      </section>
    </section>
  );
}

function StressTestPanel({
  error,
  isRunning,
  labels,
  locale,
  onRun,
  report,
}: {
  error: string;
  isRunning: boolean;
  labels: Record<string, string>;
  locale: Locale;
  onRun: () => void;
  report: StressTestReport | null;
}) {
  const summary = report?.summary ?? {};
  const topProjects = report?.projects.slice(0, 5) ?? [];
  const blockingFailures = report?.blocking_failures ?? [];
  const languageCoverage = report?.language_coverage ?? {};
  return (
    <section className="task-center-section stress-test-panel panel">
      <div className="stress-test-head">
        <div>
          <span className="eyebrow">{labels.stressTitle}</span>
          <h3>{locale === "zh" ? "大项目可用性巡检" : "Large-project readiness check"}</h3>
          <p>
            {locale === "zh"
              ? "批量检查档案质量、评测状态、Hybrid RAG、多模态和关键风险。"
              : "Checks archive quality, evaluation, Hybrid RAG, multimodal readiness, and key risks."}
          </p>
        </div>
        <button className="primary-button compact" disabled={isRunning} onClick={onRun} type="button">
          <ShieldCheck size={14} />
          {isRunning ? labels.stressRunning : labels.stressRun}
        </button>
      </div>
      {error ? (
        <div className="mission-error" role="alert">
          <strong>{locale === "zh" ? "压力测试失败" : "Stress test failed"}</strong>
          <span>{error}</span>
        </div>
      ) : null}
      {report ? (
        <>
          <div className="stress-test-metrics">
            <span><strong>{formatNumber(summary.project_count ?? 0)}</strong>{locale === "zh" ? "项目" : "Projects"}</span>
            <span><strong>{formatNumber(summary.pass_count ?? 0)}</strong>{locale === "zh" ? "通过" : "Pass"}</span>
            <span><strong>{formatNumber(summary.warn_count ?? 0)}</strong>{locale === "zh" ? "预警" : "Warn"}</span>
            <span><strong>{formatNumber(summary.fail_count ?? 0)}</strong>{locale === "zh" ? "失败" : "Fail"}</span>
            <span><strong>{Math.round(Number(summary.average_quality_score ?? 0))}</strong>{locale === "zh" ? "平均质量" : "Avg quality"}</span>
            <span><strong>{formatNumber(summary.hybrid_rag_ready_count ?? 0)}</strong>Hybrid RAG</span>
            <span><strong>{formatNumber(blockingFailures.length)}</strong>{labels.blocking}</span>
            <span><strong>{formatNumber(Number(languageCoverage.language_count ?? 0))}</strong>{labels.languageCoverage}</span>
          </div>
          {report.recommendations.length ? (
            <div className="stress-test-recommendations">
              {report.recommendations.slice(0, 3).map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
          ) : null}
          {topProjects.length ? (
            <div className="stress-project-list">
              {topProjects.map((project) => (
                <article className={`stress-project is-${project.status}`} key={project.project_id}>
                  <strong>{project.project_id}</strong>
                  <span className={`pipeline-status ${project.status}`}>{project.status}</span>
                  <small>
                    {locale === "zh" ? "质量" : "Quality"} {Math.round(project.quality_score)} · {project.quality_grade}
                  </small>
                  <small>
                    {locale === "zh" ? "实体/关系" : "Entities/Relations"} {formatNumber(project.metrics.entities ?? 0)} / {formatNumber(project.metrics.relations ?? 0)}
                  </small>
                </article>
              ))}
            </div>
          ) : null}
        </>
      ) : (
        <p className="empty-note">
          {locale === "zh"
            ? "还没有压力测试报告。运行一次后会在这里看到档案库健康度。"
            : "No stress test report yet. Run one to see archive health."}
        </p>
      )}
    </section>
  );
}

function TaskCenterList({
  jobs,
  labels,
  locale,
  onCancel,
}: {
  jobs: ArchiveJob[];
  labels: Record<string, string>;
  locale: Locale;
  onCancel: (jobId: string) => void;
}) {
  return (
    <div className="task-center-list">
      {jobs.slice(0, 60).map((job) => {
        const canCancel = ["queued", "running"].includes(job.status);
        return (
          <article className={`task-center-card is-${job.status}`} key={job.id}>
            <div className="task-center-card-head">
              <div>
                <span className="eyebrow">{job.kind}</span>
                <strong>{job.project_id ?? (locale === "zh" ? "未绑定项目" : "No project")}</strong>
                <small>{job.id}</small>
              </div>
              <span className={`pipeline-status ${job.status}`}>{taskStatusLabel(job.status, locale)}</span>
            </div>
            <div className="task-center-progress">
              <span>{formatNumber(job.progress)}%</span>
              <progress max={100} value={job.progress} />
            </div>
            <p>{job.message}</p>
            {job.error ? <code>{job.error}</code> : null}
            <div className="task-center-meta">
              <span>{formatTaskTime(job.updated_at ?? job.created_at)}</span>
              <span>{job.cancel_requested ? (locale === "zh" ? "已请求取消" : "Cancel requested") : labels.steps}: {job.steps.length}</span>
            </div>
            {job.steps.length ? (
              <details className="task-center-steps">
                <summary>{labels.steps}</summary>
                {job.steps.slice(-8).map((step, index) => (
                  <span key={`${job.id}-step-${index}`}>
                    {formatNumber(step.progress)}% · {step.message}
                  </span>
                ))}
              </details>
            ) : null}
            {canCancel ? (
              <button className="secondary-action compact danger" onClick={() => onCancel(job.id)} type="button">
                <X size={14} />
                {labels.cancel}
              </button>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}

const taskStatusLabel = (status: ArchiveJob["status"], locale: Locale) => {
  const labels = {
    zh: {
      queued: "排队中",
      running: "运行中",
      complete: "已完成",
      failed: "失败",
      cancelled: "已取消",
    },
    en: {
      queued: "Queued",
      running: "Running",
      complete: "Complete",
      failed: "Failed",
      cancelled: "Cancelled",
    },
  };
  return labels[locale][status] ?? status;
};

const formatTaskTime = (value: string | undefined) => {
  if (!value) return "";
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) return value;
  return new Date(timestamp).toLocaleString();
};

function ReactAgentMissionPanel({
  error,
  isStarting,
  locale,
  mission,
  onAction,
  onStart,
  trace,
  visualization,
}: {
  error: string;
  isStarting: boolean;
  locale: Locale;
  mission: AgentMission | null;
  onAction: (action: "pause" | "resume" | "stop") => void;
  onStart: () => void;
  trace: AgentTraceEvent[];
  visualization: AgentMissionVisualization | null;
}) {
  const t = copy[locale];
  const completedCount = mission?.tasks.filter((task) => ["completed", "complete"].includes(task.status)).length ?? 0;
  const terminal = isMissionTerminal(mission);
  const canStart = !isStarting && (!mission || terminal);
  const canStop = Boolean(mission && !terminal && !isStarting);
  const statusText = mission
    ? missionStatusLabel(mission.status, locale)
    : locale === "zh"
      ? "未启动"
      : "Not started";
  const errorLabel = mission && !terminal
    ? locale === "zh"
      ? "状态提示"
      : "Status note"
    : t.missionError;
  const traceEvents = trace.length ? trace : mission?.trace_events ?? [];
  const verifierStatus = mission?.verifier_result?.status
    ? missionStatusLabel(mission.verifier_result.status, locale)
    : locale === "zh"
      ? "未校验"
      : "Not verified";
  const budgetUsage = missionMetadataObject(mission, "budget_usage");
  const agentMemory = missionMetadataObject(mission, "agent_memory");
  const memoryCounts = metadataObject(agentMemory, "counts");
  const criticReviews = Array.isArray(mission?.metadata?.critic_reviews)
    ? (mission.metadata.critic_reviews as Array<Record<string, unknown>>)
    : [];
  const retryCount = criticReviews.filter((review) => Boolean(review.retry_performed)).length;
  const taskQueue = Array.isArray(mission?.metadata?.task_queue)
    ? (mission.metadata.task_queue as Array<Record<string, unknown>>)
    : [];
  const visualAudit = visualization?.audit ?? {};
  const visualPhases = visualization?.loop_phases ?? [];

  return (
    <section className="react-agent-panel panel" aria-label={locale === "zh" ? "ReAct Agent 任务" : "ReAct Agent mission"}>
      <div className="mission-control-head">
        <div>
          <span className="eyebrow">{locale === "zh" ? "Graph-grounded ReAct" : "Graph-grounded ReAct"}</span>
          <h2>{locale === "zh" ? "Agent 任务追踪" : "Agent mission trace"}</h2>
        </div>
        <div className="mission-actions">
          <span className={`pipeline-status ${mission?.status ?? "pending"}`}>{statusText}</span>
          <button className="primary-button compact" disabled={!canStart} onClick={onStart} type="button">
            <Sparkles size={14} />
            {isStarting ? t.missionStarting : locale === "zh" ? "启动 ReAct 任务" : "Start ReAct mission"}
          </button>
          <button className="secondary-action compact danger" disabled={!canStop} onClick={() => onAction("stop")} type="button">
            <X size={14} />
            {t.stopMission}
          </button>
        </div>
      </div>
      {error ? (
        <div className="mission-error" role="alert">
          <strong>{errorLabel}</strong>
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
          <div className="agent-loop-grid">
            <div>
              <span>{locale === "zh" ? "预算使用" : "Budget usage"}</span>
              <strong>
                {metadataNumber(budgetUsage, "tool_calls_used")} / {mission.budget.max_tool_calls}
              </strong>
              <small>{metadataNumber(budgetUsage, "trace_events")} {locale === "zh" ? "条 trace" : "trace events"}</small>
            </div>
            <div>
              <span>{locale === "zh" ? "Agent 记忆" : "Agent memory"}</span>
              <strong>
                {metadataNumber(memoryCounts, "entities")} / {metadataNumber(memoryCounts, "evidence")} / {metadataNumber(memoryCounts, "relations")}
              </strong>
              <small>{locale === "zh" ? "实体 / 证据 / 关系" : "entities / evidence / relations"}</small>
            </div>
            <div>
              <span>{locale === "zh" ? "Critic / Retry" : "Critic / Retry"}</span>
              <strong>{criticReviews.length} / {retryCount}</strong>
              <small>{locale === "zh" ? "校验 / 重试" : "reviews / retries"}</small>
            </div>
            <div>
              <span>{locale === "zh" ? "任务队列" : "Task queue"}</span>
              <strong>{taskQueue.length || mission.tasks.length}</strong>
              <small>{locale === "zh" ? "Planner 输出" : "Planner output"}</small>
            </div>
          </div>
          {visualization ? (
            <div className="react-visual-summary">
              <div className="react-visual-head">
                <strong>{locale === "zh" ? "ReAct 可视化审计" : "ReAct visual audit"}</strong>
                <span>
                  {formatNumber(Number(visualAudit.trace_events ?? traceEvents.length))} {locale === "zh" ? "事件" : "events"} · {formatNumber(Number(visualAudit.tool_calls ?? 0))} tools
                </span>
              </div>
              <div className="react-phase-grid">
                {visualPhases.map((phase) => (
                  <article key={String(phase.phase)}>
                    <strong>{String(phase.phase)}</strong>
                    <span>{formatNumber(Number(phase.event_count ?? 0))} {locale === "zh" ? "事件" : "events"}</span>
                    <small>{String(phase.summary ?? "")}</small>
                  </article>
                ))}
              </div>
              {visualization.warnings.length ? (
                <div className="react-visual-warnings">
                  {visualization.warnings.slice(0, 4).map((warning) => (
                    <span key={warning}>{warning}</span>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
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
                    {metadataObject(task.metadata, "critic").status ? (
                      <p>
                        <strong>Critic</strong>{" "}
                        {String(metadataObject(task.metadata, "critic").status)}
                        {metadataObject(task.metadata, "critic").retry_performed
                          ? locale === "zh" ? " · 已重试" : " · retried"
                          : ""}
                      </p>
                    ) : null}
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
                    {event.metadata?.selection ? <span>{locale === "zh" ? "选择" : "Selection"}: {String(event.metadata.selection)}</span> : null}
                    {event.metadata?.retry_reason ? <span>Retry: {String(event.metadata.retry_reason)}</span> : null}
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

function AgentTaskPlanPanel({
  locale,
  plan,
}: {
  locale: Locale;
  plan: AgentTaskPlan | null;
}) {
  const labels = locale === "zh"
    ? {
        title: "Agent 任务计划",
        empty: "选择或生成项目档案后会显示项目级任务计划。",
        priority: "优先级",
        tools: "工具",
        entities: "实体",
      }
    : {
        title: "Agent task plan",
        empty: "Select or generate an archive to show the project-level task plan.",
        priority: "Priority",
        tools: "Tools",
        entities: "Entities",
      };
  const tasks = plan?.tasks ?? [];
  return (
    <section className="agent-task-plan panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{labels.title}</span>
          <h2>{plan ? plan.project_id : labels.title}</h2>
        </div>
        <Command size={18} />
      </div>
      <p>{plan?.summary ?? labels.empty}</p>
      {tasks.length ? (
        <div className="agent-task-plan-list">
          {tasks.slice(0, 6).map((task) => {
            const tools = Array.isArray(task.recommended_tools) ? task.recommended_tools : [];
            const entityIds = Array.isArray(task.input_entity_ids) ? task.input_entity_ids : [];
            return (
              <article key={String(task.id ?? task.task_type)}>
                <div>
                  <strong>{String(task.title ?? task.task_type ?? "")}</strong>
                  <span>{String(task.reason ?? "")}</span>
                </div>
                <small>{labels.priority}: {String(task.priority ?? "-")}</small>
                <small>{labels.tools}: {tools.length}</small>
                <small>{labels.entities}: {entityIds.length}</small>
              </article>
            );
          })}
        </div>
      ) : null}
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
  const [graphStoreStatus, setGraphStoreStatus] = useState<GraphStoreStatus | null>(null);
  const [archiveDraft, setArchiveDraft] = useState<ArchiveDraft | null>(null);
  const [agentReport, setAgentReport] = useState<ProjectAgentReport | null>(null);
  const [intelligenceReport, setIntelligenceReport] = useState<ProjectIntelligenceReport | null>(null);
  const [isGeneratingIntelligenceReport, setIsGeneratingIntelligenceReport] = useState(false);
  const [intelligenceReportError, setIntelligenceReportError] = useState("");
  const [agentTrustReport, setAgentTrustReport] = useState<AgentTrustReport | null>(null);
  const [agentEvalReport, setAgentEvalReport] = useState<AgentEvalReport | null>(null);
  const [harnessSummary, setHarnessSummary] = useState<HarnessRunSummary | null>(null);
  const [harnessCommands, setHarnessCommands] = useState<HarnessCommand[]>([]);
  const [harnessTimeline, setHarnessTimeline] = useState<HarnessTimeline | null>(null);
  const [harnessArtifacts, setHarnessArtifacts] = useState<HarnessArtifactManifest | null>(null);
  const [harnessToolResult, setHarnessToolResult] = useState<HarnessCommandDryRun | Record<string, unknown> | null>(null);
  const [isRunningHarnessTool, setIsRunningHarnessTool] = useState(false);
  const [agentMemory, setAgentMemory] = useState<AgentMemory | null>(null);
  const [isRunningAgentEval, setIsRunningAgentEval] = useState(false);
  const [agentEvalError, setAgentEvalError] = useState("");
  const [evaluationReport, setEvaluationReport] = useState<ArchiveEvaluationReport | null>(null);
  const [evaluationHistory, setEvaluationHistory] = useState<EvaluationHistory | null>(null);
  const [graphWorkspaceReport, setGraphWorkspaceReport] = useState<GraphWorkspaceReport | null>(null);
  const [hybridRagStatus, setHybridRagStatus] = useState<HybridRagStatus | null>(null);
  const [isRebuildingHybridRag, setIsRebuildingHybridRag] = useState(false);
  const [ingestionDiagnostics, setIngestionDiagnostics] = useState<IngestionDiagnostics | null>(null);
  const [multimodalInsights, setMultimodalInsights] = useState<MultimodalInsights | null>(null);
  const [systemConfigCheck, setSystemConfigCheck] = useState<SystemConfigCheck | null>(null);
  const [systemConfigError, setSystemConfigError] = useState("");
  const [isLoadingSystemConfig, setIsLoadingSystemConfig] = useState(false);
  const [mission, setMission] = useState<AutonomousMission | null>(null);
  const [reactMission, setReactMission] = useState<AgentMission | null>(null);
  const [agentTaskPlan, setAgentTaskPlan] = useState<AgentTaskPlan | null>(null);
  const [knowledgeUniverse, setKnowledgeUniverse] = useState<ProjectKnowledgeUniverse | null>(null);
  const [universePaths, setUniversePaths] = useState<UniverseExplorationPath[]>([]);
  const [universeAgentTasks, setUniverseAgentTasks] = useState<UniverseAgentTask[]>([]);
  const [universeDiffReport, setUniverseDiffReport] = useState<ProjectArchitectureDiffReport | null>(null);
  const [taskCenterJobs, setTaskCenterJobs] = useState<ArchiveJob[]>([]);
  const [taskCenterError, setTaskCenterError] = useState("");
  const [isLoadingTaskCenter, setIsLoadingTaskCenter] = useState(false);
  const [stressTestReport, setStressTestReport] = useState<StressTestReport | null>(null);
  const [stressTestError, setStressTestError] = useState("");
  const [isRunningStressTest, setIsRunningStressTest] = useState(false);
  const [reactTrace, setReactTrace] = useState<AgentTraceEvent[]>([]);
  const [reactVisualization, setReactVisualization] = useState<AgentMissionVisualization | null>(null);
  const [reactMissionError, setReactMissionError] = useState("");
  const [universeError, setUniverseError] = useState("");
  const [isStartingReactMission, setIsStartingReactMission] = useState(false);
  const [isLoadingUniverse, setIsLoadingUniverse] = useState(false);
  const [isRunningUniverseAgent, setIsRunningUniverseAgent] = useState(false);
  const [isRunningUniverseDiff, setIsRunningUniverseDiff] = useState(false);
  const [missionOverlay, setMissionOverlay] = useState<MissionGraphOverlay | null>(null);
  const [missionError, setMissionError] = useState("");
  const [missionAction, setMissionAction] = useState<MissionAction>(null);
  const [archiveIds, setArchiveIds] = useState<string[]>([]);
  const [selectedUniverseProjectIds, setSelectedUniverseProjectIds] = useState<string[]>([]);
  const [isFallbackArchive, setIsFallbackArchive] = useState(false);
  const [isLoadingArchive, setIsLoadingArchive] = useState(true);
  const [isSwitchingArchive, setIsSwitchingArchive] = useState(false);
  const [selectedHallId, setSelectedHallId] = useState("");
  const [selectedArchiveId, setSelectedArchiveId] = useState("");
  const [locale, setLocale] = useState<Locale>("zh");
  const [activePage, setActivePage] = useState<AppPage>("overview");
  const [demoVisitedPages, setDemoVisitedPages] = useState<AppPage[]>(["overview"]);
  const [queryMode] = useState<ScopeMode>("architecture_tour");
  const [scanProfile, setScanProfile] = useState<ScanProfile>("architecture");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedFileName, setSelectedFileName] = useState("");
  const [isCreatingArchive, setIsCreatingArchive] = useState(false);
  const [isRunningAgentReport, setIsRunningAgentReport] = useState(false);
  const [isRunningEvaluation, setIsRunningEvaluation] = useState(false);
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
  const archiveRequestTokenRef = useRef(0);
  const reactMissionRequestTokenRef = useRef(0);
  const universeRequestTokenRef = useRef(0);
  const reactMissionRef = useRef<AgentMission | null>(null);

  const updateReactMissionState = (nextMission: AgentMission | null) => {
    reactMissionRef.current = nextMission;
    setReactMission(nextMission);
  };

  const resetHarnessState = () => {
    setAgentEvalReport(null);
    setHarnessSummary(null);
    setHarnessTimeline(null);
    setHarnessArtifacts(null);
    setHarnessToolResult(null);
  };

  const loadSystemConfigCheck = async () => {
    setIsLoadingSystemConfig(true);
    setSystemConfigError("");
    try {
      const nextCheck = await fetchSystemConfigCheck();
      setSystemConfigCheck(nextCheck);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setSystemConfigError(message);
    } finally {
      setIsLoadingSystemConfig(false);
    }
  };

  const loadTaskCenterJobs = async (projectId?: string) => {
    setIsLoadingTaskCenter(true);
    setTaskCenterError("");
    try {
      const jobs = await listArchiveJobs(projectId);
      setTaskCenterJobs(jobs);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setTaskCenterError(message);
    } finally {
      setIsLoadingTaskCenter(false);
    }
  };

  const loadStressTestReport = async () => {
    setStressTestError("");
    try {
      const report = await fetchStressTestReport();
      setStressTestReport(report);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setStressTestError(message);
    }
  };

  useEffect(() => {
    activeProjectIdRef.current = archiveDraft?.projectId ?? "";
  }, [archiveDraft?.projectId]);

  useEffect(() => {
    activeMissionIdRef.current = mission?.id ?? null;
  }, [mission?.id]);

  useEffect(() => {
    setDemoVisitedPages((pages) => (pages.includes(activePage) ? pages : [...pages, activePage]));
  }, [activePage]);

  useEffect(() => {
    if (activePage !== "tasks") return;
    void loadTaskCenterJobs();
    void loadStressTestReport();
  }, [activePage]);

  useEffect(() => {
    let isMounted = true;
    const token = archiveRequestTokenRef.current;

    fetchArchiveDraft().then(({ archiveIds: nextArchiveIds }) => {
      if (!isMounted || token !== archiveRequestTokenRef.current) return;
      setArchiveIds(nextArchiveIds);
      setSelectedUniverseProjectIds(nextArchiveIds);
      setArchiveDraft(null);
      setSelectedArchiveId("");
      setSelectedHallId("");
      setIsFallbackArchive(false);
      setIsLoadingArchive(false);
      setAgentReport(null);
      setIntelligenceReport(null);
      setIntelligenceReportError("");
      setAgentTrustReport(null);
      resetHarnessState();
      setAgentMemory(null);
      setAgentEvalError("");
      setEvaluationReport(null);
      setEvaluationHistory(null);
      setGraphWorkspaceReport(null);
      setHybridRagStatus(null);
      setIngestionDiagnostics(null);
      setMultimodalInsights(null);
      setAgentTaskPlan(null);
      reactMissionRequestTokenRef.current += 1;
      updateReactMissionState(null);
      setReactTrace([]);
      setReactVisualization(null);
      setReactMissionError("");
      setIsStartingReactMission(false);
      setIsRunningEvaluation(false);
    });

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    setSelectedUniverseProjectIds((currentIds) => {
      const retained = currentIds.filter((projectId) => archiveIds.includes(projectId));
      if (retained.length) return retained;
      return archiveIds;
    });
  }, [archiveIds]);

  useEffect(() => {
    let isMounted = true;

    Promise.allSettled([fetchAgentStatus(), fetchGraphStoreStatus(), fetchSystemConfigCheck()])
      .then(([agentResult, graphResult, systemResult]) => {
        if (!isMounted) return;
        if (agentResult.status === "fulfilled") {
          setAgentStatus(agentResult.value);
        } else {
          setAgentStatus({
            llm_enabled: false,
            provider: "rules",
            mode: "deterministic",
            model: null,
          });
        }
        if (graphResult.status === "fulfilled") {
          setGraphStoreStatus(graphResult.value);
        } else {
          setGraphStoreStatus({
            provider: "sqlite",
            mode: "local",
            database: null,
            uri: null,
            project_isolation: true,
          });
        }
        if (systemResult.status === "fulfilled") {
          setSystemConfigCheck(systemResult.value);
          setSystemConfigError("");
        } else {
          setSystemConfigError(systemResult.reason instanceof Error ? systemResult.reason.message : String(systemResult.reason));
        }
      })
      .catch(() => undefined);

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

  const resetArchiveView = (
    draft: ArchiveDraft,
    report: ProjectAgentReport | null = null,
    archiveToken = archiveRequestTokenRef.current,
  ) => {
    if (archiveToken !== archiveRequestTokenRef.current) return false;
    activeProjectIdRef.current = draft.projectId;
    activeMissionIdRef.current = null;
    missionActionTokenRef.current += 1;
    missionActionRef.current = null;
    reactMissionRequestTokenRef.current += 1;
    setArchiveDraft(draft);
    setAgentReport(report);
    setIntelligenceReport(null);
    setIntelligenceReportError("");
    setAgentTrustReport(null);
    resetHarnessState();
    setAgentMemory(null);
    setAgentEvalError("");
    setEvaluationReport(null);
    setEvaluationHistory(null);
    setGraphWorkspaceReport(null);
    setHybridRagStatus(null);
    setIngestionDiagnostics(null);
    setMultimodalInsights(null);
    setAgentTaskPlan(null);
    fetchGraphWorkspaceReport(draft.projectId)
      .then((report) => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setGraphWorkspaceReport(report);
        }
      })
      .catch(() => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setGraphWorkspaceReport(null);
        }
      });
    fetchAgentTrustReport(draft.projectId)
      .then((report) => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setAgentTrustReport(report);
        }
      })
      .catch(() => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setAgentTrustReport(null);
        }
      });
    fetchAgentEvalReport(draft.projectId)
      .then((report) => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setAgentEvalReport(report);
          setAgentEvalError("");
        }
      })
      .catch(() => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setAgentEvalReport(null);
        }
      });
    fetchHarnessRunSummary(draft.projectId)
      .then((summary) => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setHarnessSummary(summary);
        }
      })
      .catch(() => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setHarnessSummary(null);
        }
      });
    fetchHarnessTimeline(draft.projectId)
      .then((timeline) => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setHarnessTimeline(timeline);
        }
      })
      .catch(() => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setHarnessTimeline(null);
        }
      });
    fetchHarnessArtifactManifest(draft.projectId)
      .then((manifest) => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setHarnessArtifacts(manifest);
        }
      })
      .catch(() => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setHarnessArtifacts(null);
        }
      });
    fetchHarnessCommands()
      .then((commands) => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setHarnessCommands(commands);
        }
      })
      .catch(() => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setHarnessCommands([]);
        }
      });
    fetchAgentMemory(draft.projectId)
      .then((memory) => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setAgentMemory(memory);
        }
      })
      .catch(() => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setAgentMemory(null);
        }
      });
    fetchProjectIntelligenceReport(draft.projectId)
      .then((report) => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setIntelligenceReport(report);
        }
      })
      .catch(() => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setIntelligenceReport(null);
        }
      });
    fetchAgentTaskPlan(draft.projectId)
      .then((plan) => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setAgentTaskPlan(plan);
        }
      })
      .catch(() => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setAgentTaskPlan(null);
        }
      });
    fetchArchiveEvaluation(draft.projectId)
      .then((evaluation) => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setEvaluationReport(evaluation);
        }
      })
      .catch(() => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setEvaluationReport(null);
        }
      });
    fetchEvaluationHistory(draft.projectId)
      .then((history) => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setEvaluationHistory(history);
        }
      })
      .catch(() => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setEvaluationHistory(null);
        }
      });
    fetchHybridRagStatus(draft.projectId)
      .then((status) => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setHybridRagStatus(status);
        }
      })
      .catch(() => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setHybridRagStatus(null);
        }
      });
    fetchMultimodalInsights(draft.projectId)
      .then((insights) => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setMultimodalInsights(insights);
        }
      })
      .catch(() => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setMultimodalInsights(null);
        }
      });
    fetchIngestionDiagnostics(draft.projectId)
      .then((diagnostics) => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setIngestionDiagnostics(diagnostics);
        }
      })
      .catch(() => {
        if (archiveToken === archiveRequestTokenRef.current && activeProjectIdRef.current === draft.projectId) {
          setIngestionDiagnostics(null);
        }
      });
    setMission(null);
    updateReactMissionState(null);
    setReactTrace([]);
    setReactVisualization(null);
    setReactMissionError("");
    setIsStartingReactMission(false);
    setIsRunningEvaluation(false);
    setMissionOverlay(null);
    setMissionError("");
    setMissionAction(null);
    setSelectedArchiveId(draft.projectId);
    setSelectedHallId(loadGraphWorkspaceState(draft).hallId ?? draft.halls[0]?.id ?? "");
    setSelectedRelationId("");
    setSelectedEvidenceId("");
    setSearchQuery("");
    return true;
  };

  const handleArchiveChange = async (projectId: string) => {
    if (!projectId) {
      resetArchiveSelection();
      return;
    }
    if (projectId === archiveDraft?.projectId) return;
    const token = archiveRequestTokenRef.current + 1;
    archiveRequestTokenRef.current = token;
    setIsSwitchingArchive(true);
    try {
      const draft = await fetchProjectArchive(projectId);
      if (token !== archiveRequestTokenRef.current) return;
      const report = await fetchProjectAgentReport(projectId).catch(() => null);
      if (token !== archiveRequestTokenRef.current) return;
      if (!resetArchiveView(draft, report, token)) return;
      setIsFallbackArchive(false);
      notify(`${copy[locale].archiveSwitched}: ${draft.projectId}`);
    } catch (error) {
      if (token !== archiveRequestTokenRef.current) return;
      const message = error instanceof Error ? error.message : String(copy[locale].archiveSwitchFailed);
      notify(`${copy[locale].archiveSwitchFailed}: ${message}`);
    } finally {
      if (token === archiveRequestTokenRef.current) setIsSwitchingArchive(false);
    }
  };

  const resetArchiveSelection = () => {
    archiveRequestTokenRef.current += 1;
    activeProjectIdRef.current = "";
    activeMissionIdRef.current = null;
    missionActionTokenRef.current += 1;
    missionActionRef.current = null;
    reactMissionRequestTokenRef.current += 1;
    setArchiveDraft(null);
    setAgentReport(null);
    setIntelligenceReport(null);
    setIntelligenceReportError("");
    setAgentTrustReport(null);
    resetHarnessState();
    setAgentMemory(null);
    setAgentEvalError("");
    setEvaluationReport(null);
    setEvaluationHistory(null);
    setGraphWorkspaceReport(null);
    setHybridRagStatus(null);
    setIngestionDiagnostics(null);
    setMultimodalInsights(null);
    setAgentTaskPlan(null);
    setMission(null);
    updateReactMissionState(null);
    setReactTrace([]);
    setReactVisualization(null);
    setReactMissionError("");
    setIsStartingReactMission(false);
    setIsRunningEvaluation(false);
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
    setIsSwitchingArchive(false);
  };

  const handleCreateArchive = async () => {
    document.getElementById("project-intake")?.scrollIntoView({ behavior: "smooth", block: "center" });
    if (!selectedFile) {
      notify(String(copy[locale].createNeedsZip));
      return;
    }

    const token = archiveRequestTokenRef.current + 1;
    archiveRequestTokenRef.current = token;
    setIsCreatingArchive(true);
    setUploadProgress(2);
    setUploadProgressMessage(String(copy[locale].createPending));
    notify(String(copy[locale].createPending));
    let archiveWasCreated = false;
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
      if (!resetArchiveView(draft, null, token)) return;
      setArchiveIds((currentIds) =>
        currentIds.includes(draft.projectId) ? currentIds : [...currentIds, draft.projectId].sort(),
      );
      setSelectedUniverseProjectIds((currentIds) =>
        currentIds.includes(draft.projectId) ? currentIds : [...currentIds, draft.projectId].sort(),
      );
      setIsFallbackArchive(false);
      setSelectedFile(null);
      setSelectedFileName("");
      archiveWasCreated = true;
      notify(`${copy[locale].archiveCreated}: ${draft.projectId}`);
    } catch (error) {
      if (token !== archiveRequestTokenRef.current) return;
      const message = error instanceof Error ? error.message : String(copy[locale].uploadFailed);
      setUploadProgress((progress) => (progress > 0 ? progress : 100));
      setUploadProgressMessage(`${message}. ${copy[locale].retryUpload}`);
      notify(`${copy[locale].uploadFailed}: ${message}`);
    } finally {
      setIsCreatingArchive(false);
      if (archiveWasCreated) {
        window.setTimeout(() => {
          setUploadProgress(0);
          setUploadProgressMessage("");
        }, 1200);
      }
    }
  };

  const handleSearchGraph = () => {
    if (!archiveDraft) {
      setActivePage("overview");
      notify(String(copy[locale].noArchiveSelected));
      return;
    }
    setActivePage("graph");
    window.setTimeout(() => {
      document.querySelector<HTMLInputElement>(".graph-toolbar-search input")?.focus();
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
      setIntelligenceReport(null);
      setIntelligenceReportError("");
      const trust = await fetchAgentTrustReport(projectId).catch(() => null);
      if (activeProjectIdRef.current === projectId) setAgentTrustReport(trust);
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

  const handleGenerateIntelligenceReport = async () => {
    if (!archiveDraft) {
      notify(String(copy[locale].noArchiveSelected));
      return;
    }
    const projectId = archiveDraft.projectId;
    setIsGeneratingIntelligenceReport(true);
    setIntelligenceReportError("");
    notify(locale === "zh" ? "正在生成正式项目报告" : "Generating project intelligence report");
    try {
      const report = await runProjectIntelligenceReport(projectId);
      if (activeProjectIdRef.current !== projectId) return;
      setIntelligenceReport(report);
      notify(locale === "zh" ? "正式项目报告已生成" : "Project intelligence report generated");
    } catch (error) {
      if (activeProjectIdRef.current !== projectId) return;
      const message = error instanceof Error ? error.message : String(error);
      setIntelligenceReportError(message);
      notify(`${locale === "zh" ? "正式项目报告失败" : "Project report failed"}: ${message}`);
    } finally {
      if (activeProjectIdRef.current === projectId) setIsGeneratingIntelligenceReport(false);
    }
  };

  const handleDownloadIntelligenceMarkdown = async () => {
    if (!archiveDraft) {
      notify(String(copy[locale].noArchiveSelected));
      return;
    }
    try {
      const markdown = await downloadProjectIntelligenceMarkdown(archiveDraft.projectId);
      const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${archiveDraft.projectId}-intelligence-report.md`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      notify(locale === "zh" ? "Markdown 报告已下载" : "Markdown report downloaded");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setIntelligenceReportError(message);
      notify(`${locale === "zh" ? "下载失败" : "Download failed"}: ${message}`);
    }
  };

  const handleDownloadIntelligencePdf = async () => {
    if (!archiveDraft) {
      notify(String(copy[locale].noArchiveSelected));
      return;
    }
    try {
      const blob = await downloadProjectIntelligencePdf(archiveDraft.projectId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${archiveDraft.projectId}-intelligence-report.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      notify(locale === "zh" ? "PDF 报告已下载" : "PDF report downloaded");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setIntelligenceReportError(message);
      notify(`${locale === "zh" ? "PDF 下载失败" : "PDF download failed"}: ${message}`);
    }
  };

  const handleRunEvaluation = async () => {
    if (!archiveDraft) {
      notify(String(copy[locale].noArchiveSelected));
      return;
    }
    const projectId = archiveDraft.projectId;
    setIsRunningEvaluation(true);
    notify(String(copy[locale].evaluationRunning));
    try {
      const report = await runArchiveEvaluation(projectId);
      if (activeProjectIdRef.current !== projectId) return;
      setEvaluationReport(report);
      fetchEvaluationHistory(projectId)
        .then((history) => {
          if (activeProjectIdRef.current === projectId) setEvaluationHistory(history);
        })
        .catch(() => undefined);
      recordJobProgress(
        String(copy[locale].evaluationBenchmark),
        100,
        String(copy[locale].evaluationReady),
        projectId,
      );
      notify(String(copy[locale].evaluationReady));
    } catch (error) {
      if (activeProjectIdRef.current !== projectId) return;
      const message = error instanceof Error ? error.message : String(error);
      notify(`${copy[locale].evaluationFailed}: ${message}`);
    } finally {
      if (activeProjectIdRef.current === projectId) setIsRunningEvaluation(false);
    }
  };

  const handleRunAgentEval = async () => {
    if (!archiveDraft) {
      notify(String(copy[locale].noArchiveSelected));
      return;
    }
    const projectId = archiveDraft.projectId;
    setIsRunningAgentEval(true);
    setAgentEvalError("");
    notify(locale === "zh" ? "正在运行 AgentEval Harness" : "Running AgentEval harness");
    try {
      const report = await runAgentEvalHarness(projectId, {
        run_evaluation: true,
        evaluation_limit: 6,
        run_agent_report: false,
        agent_llm_mode: "fast",
      });
      if (activeProjectIdRef.current !== projectId) return;
      setAgentEvalReport(report);
      const [memory, evaluation, trust, summary, timeline, artifacts] = await Promise.all([
        fetchAgentMemory(projectId).catch(() => null),
        fetchArchiveEvaluation(projectId).catch(() => null),
        fetchAgentTrustReport(projectId).catch(() => null),
        fetchHarnessRunSummary(projectId).catch(() => null),
        fetchHarnessTimeline(projectId).catch(() => null),
        fetchHarnessArtifactManifest(projectId).catch(() => null),
      ]);
      if (activeProjectIdRef.current !== projectId) return;
      setAgentMemory(memory);
      setEvaluationReport(evaluation);
      setAgentTrustReport(trust);
      setHarnessSummary(summary);
      setHarnessTimeline(timeline);
      setHarnessArtifacts(artifacts);
      fetchEvaluationHistory(projectId)
        .then((history) => {
          if (activeProjectIdRef.current === projectId) setEvaluationHistory(history);
        })
        .catch(() => undefined);
      recordJobProgress(
        locale === "zh" ? "AgentEval Harness" : "AgentEval harness",
        100,
        locale === "zh" ? `质量状态：${report.status}` : `Quality status: ${report.status}`,
        projectId,
      );
      notify(locale === "zh" ? "AgentEval 已完成" : "AgentEval complete");
    } catch (error) {
      if (activeProjectIdRef.current !== projectId) return;
      const message = error instanceof Error ? error.message : String(error);
      setAgentEvalError(message);
      notify(`${locale === "zh" ? "AgentEval 失败" : "AgentEval failed"}: ${message}`);
    } finally {
      if (activeProjectIdRef.current === projectId) setIsRunningAgentEval(false);
    }
  };

  const handleHarnessCommandDryRun = async () => {
    if (!archiveDraft) {
      notify(String(copy[locale].noArchiveSelected));
      return;
    }
    const command = harnessCommands.find((item) => item.id === "agent-eval-live");
    setIsRunningHarnessTool(true);
    setAgentEvalError("");
    try {
      const plan = await dryRunHarnessCommand("agent-eval-live", {
        project_id: archiveDraft.projectId,
        provider: agentStatus?.provider ?? "configured",
        model: agentStatus?.model ?? null,
        llm_enabled: agentStatus?.llm_enabled ?? false,
      });
      if (activeProjectIdRef.current !== archiveDraft.projectId) return;
      setHarnessToolResult({
        ...plan,
        command_title: command?.title ?? "AgentEval Live Provider",
      });
      notify(locale === "zh" ? "已生成 Harness dry-run 计划" : "Harness dry-run plan generated");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setAgentEvalError(message);
      notify(`${locale === "zh" ? "Harness dry-run 失败" : "Harness dry-run failed"}: ${message}`);
    } finally {
      setIsRunningHarnessTool(false);
    }
  };

  const handleHarnessExport = async () => {
    if (!archiveDraft) {
      notify(String(copy[locale].noArchiveSelected));
      return;
    }
    setIsRunningHarnessTool(true);
    setAgentEvalError("");
    try {
      const exported = await fetchHarnessExport(archiveDraft.projectId);
      if (activeProjectIdRef.current !== archiveDraft.projectId) return;
      setHarnessToolResult({
        kind: "harness_export",
        metrics: exported?.metrics ?? {},
        schema_version: exported?.schema_version,
      });
      notify(locale === "zh" ? "Harness export 已生成预览" : "Harness export preview generated");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setAgentEvalError(message);
      notify(`${locale === "zh" ? "Harness export 失败" : "Harness export failed"}: ${message}`);
    } finally {
      setIsRunningHarnessTool(false);
    }
  };

  const handleHarnessArtifactCleanupDryRun = async () => {
    if (!archiveDraft) {
      notify(String(copy[locale].noArchiveSelected));
      return;
    }
    setIsRunningHarnessTool(true);
    setAgentEvalError("");
    try {
      const cleanup = await dryRunHarnessArtifactCleanup(archiveDraft.projectId);
      const manifest = await fetchHarnessArtifactManifest(archiveDraft.projectId).catch(() => null);
      if (activeProjectIdRef.current !== archiveDraft.projectId) return;
      setHarnessArtifacts(manifest);
      setHarnessToolResult({
        kind: "artifact_cleanup_dry_run",
        dry_run: cleanup?.dry_run,
        candidates: cleanup?.candidates?.length ?? 0,
        metrics: cleanup?.metrics ?? {},
      });
      notify(locale === "zh" ? "已完成 artifact cleanup dry-run" : "Artifact cleanup dry-run complete");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setAgentEvalError(message);
      notify(`${locale === "zh" ? "Artifact dry-run 失败" : "Artifact dry-run failed"}: ${message}`);
    } finally {
      setIsRunningHarnessTool(false);
    }
  };

  const handleRebuildHybridRag = async () => {
    if (!archiveDraft) {
      notify(String(copy[locale].noArchiveSelected));
      return;
    }
    const projectId = archiveDraft.projectId;
    setIsRebuildingHybridRag(true);
    notify(locale === "zh" ? "正在重建 Hybrid RAG 索引" : "Rebuilding Hybrid RAG index");
    try {
      const status = await rebuildHybridRagIndexJob(
        projectId,
        (progress, message, jobProjectId) => {
          recordJobProgress(
            locale === "zh" ? "重建 RAG 索引" : "Rebuild RAG index",
            progress,
            message,
            jobProjectId ?? projectId,
          );
        },
      );
      if (activeProjectIdRef.current !== projectId) return;
      setHybridRagStatus(status);
      notify(locale === "zh" ? "Hybrid RAG 索引已重建" : "Hybrid RAG index rebuilt");
    } catch (error) {
      if (activeProjectIdRef.current !== projectId) return;
      const message = error instanceof Error ? error.message : String(error);
      notify(`${locale === "zh" ? "RAG 索引重建失败" : "RAG rebuild failed"}: ${message}`);
    } finally {
      if (activeProjectIdRef.current === projectId) setIsRebuildingHybridRag(false);
    }
  };

  const handleCancelTaskCenterJob = async (jobId: string) => {
    try {
      await cancelArchiveJob(jobId);
      await loadTaskCenterJobs();
      notify(locale === "zh" ? "任务已请求取消" : "Cancellation requested");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      notify(`${locale === "zh" ? "取消失败" : "Cancel failed"}: ${message}`);
    }
  };

  const handleRunStressTest = async () => {
    if (!archiveIds.length) {
      notify(locale === "zh" ? "还没有可测试的项目档案" : "No archives are available to test");
      return;
    }
    setIsRunningStressTest(true);
    setStressTestError("");
    notify(locale === "zh" ? "正在运行档案压力测试" : "Running archive stress test");
    try {
      const report = await runStressTest(archiveIds);
      setStressTestReport(report);
      notify(locale === "zh" ? "压力测试报告已生成" : "Stress test report generated");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setStressTestError(message);
      notify(`${locale === "zh" ? "压力测试失败" : "Stress test failed"}: ${message}`);
    } finally {
      setIsRunningStressTest(false);
    }
  };

  const loadKnowledgeUniverse = async (projectIds = selectedUniverseProjectIds) => {
    const token = universeRequestTokenRef.current + 1;
    universeRequestTokenRef.current = token;
    setIsLoadingUniverse(true);
    setUniverseError("");
    const validProjectIds = projectIds.filter((projectId) => archiveIds.includes(projectId));
    try {
      const [universe, paths, tasks] = await Promise.all([
        fetchKnowledgeUniverse(validProjectIds.length ? validProjectIds : archiveIds),
        fetchUniversePaths(),
        fetchUniverseAgentTasks(),
      ]);
      if (universeRequestTokenRef.current !== token) return;
      setKnowledgeUniverse(universe);
      setUniversePaths(paths);
      setUniverseAgentTasks(tasks);
    } catch (error) {
      if (universeRequestTokenRef.current !== token) return;
      setKnowledgeUniverse(null);
      setUniverseError(error instanceof Error ? error.message : String(error));
    } finally {
      if (universeRequestTokenRef.current === token) setIsLoadingUniverse(false);
    }
  };

  const handleToggleUniverseProject = (projectId: string) => {
    setSelectedUniverseProjectIds((currentIds) => {
      const baseIds = currentIds.length ? currentIds : archiveIds;
      const nextIds = baseIds.includes(projectId)
        ? baseIds.filter((item) => item !== projectId)
        : [...baseIds, projectId].sort();
      return nextIds.length ? nextIds : [projectId];
    });
  };

  const handleSaveUniversePath = async (focus: MetaverseFocus | null) => {
    const projectIds = selectedUniverseProjectIds.length ? selectedUniverseProjectIds : archiveIds;
    if (!projectIds.length) {
      notify(String(copy[locale].noArchiveSelected));
      return;
    }
    try {
      const saved = await saveUniversePath({
        name: focus?.label ? `${focus.kind}: ${focus.label}` : String(copy[locale].metaverseFocus),
        project_ids: projectIds,
        cluster_ids: focus?.kind === "cluster" ? [focus.rawId] : [],
        link_ids: knowledgeUniverse?.links.slice(0, 8).map((link) => link.id) ?? [],
        notes: focus?.detail ?? "",
      });
      setUniversePaths((paths) => [saved, ...paths.filter((path) => path.id !== saved.id)].slice(0, 100));
      notify(String(copy[locale].saveUniversePath));
    } catch (error) {
      notify(error instanceof Error ? error.message : String(error));
    }
  };

  const handleRunUniverseAgent = async () => {
    const projectIds = selectedUniverseProjectIds.length ? selectedUniverseProjectIds : archiveIds;
    if (!projectIds.length) {
      notify(String(copy[locale].noArchiveSelected));
      return;
    }
    setIsRunningUniverseAgent(true);
    try {
      const tasks = await runUniverseAgentTasks({ project_ids: projectIds, max_tasks: 6 });
      setUniverseAgentTasks(tasks);
      notify(
        locale === "zh"
          ? `已生成 ${tasks.length} 个跨项目探索任务`
          : `Generated ${tasks.length} cross-project exploration tasks`,
      );
    } catch (error) {
      notify(error instanceof Error ? error.message : String(error));
    } finally {
      setIsRunningUniverseAgent(false);
    }
  };

  const handleRunUniverseDiff = async (leftProjectId: string, rightProjectId: string) => {
    if (!leftProjectId || !rightProjectId || leftProjectId === rightProjectId) {
      notify(String(copy[locale].chooseSecondProject));
      return;
    }
    setIsRunningUniverseDiff(true);
    try {
      const report = await compareUniverseProjects(leftProjectId, rightProjectId);
      setUniverseDiffReport(report);
      notify(String(copy[locale].diffReport));
    } catch (error) {
      notify(error instanceof Error ? error.message : String(error));
    } finally {
      setIsRunningUniverseDiff(false);
    }
  };

  useEffect(() => {
    if (activePage !== "universe") return;
    if (!archiveIds.length) {
      setKnowledgeUniverse(null);
      setUniverseError("");
      return;
    }
    void loadKnowledgeUniverse(selectedUniverseProjectIds.length ? selectedUniverseProjectIds : archiveIds);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activePage, archiveIds.join("|"), selectedUniverseProjectIds.join("|")]);

  const handleStartReactMission = async () => {
    if (!archiveDraft || isStartingReactMission) return;
    const projectId = archiveDraft.projectId;
    const currentVisibleMission =
      reactMissionRef.current?.project_id === projectId ? reactMissionRef.current : null;
    if (currentVisibleMission && !isMissionTerminal(currentVisibleMission)) return;
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
      updateReactMissionState(nextMission);
      setReactTrace(nextMission.trace_events);
      fetchAgentMissionVisualization(nextMission.id)
        .then((visualization) => {
          if (isCurrentReactRequest()) setReactVisualization(visualization);
        })
        .catch(() => {
          if (isCurrentReactRequest()) setReactVisualization(null);
        });
      setIsStartingReactMission(false);

      let latestMission = nextMission;
      const pollAttempts = reactMissionPollAttempts(nextMission);
      for (let attempt = 0; attempt < pollAttempts; attempt += 1) {
        if (attempt > 0) await wait(REACT_MISSION_POLL_DELAY_MS);
        if (!isCurrentReactRequest()) return;
        const [polledMission, latestTrace, visualization] = await Promise.all([
          fetchAgentMission(nextMission.id),
          fetchAgentMissionTrace(nextMission.id),
          fetchAgentMissionVisualization(nextMission.id).catch(() => null),
        ]);
        if (!isCurrentReactRequest()) return;
        latestMission = polledMission;
        const currentMission = reactMissionRef.current;
        if (
          currentMission?.id === polledMission.id &&
          isMissionTerminal(currentMission) &&
          !isMissionTerminal(polledMission)
        ) {
          return;
        }
        updateReactMissionState(polledMission);
        setReactTrace(latestTrace);
        setReactVisualization(visualization);
        setReactMissionError("");
        if (isMissionTerminal(polledMission)) break;
      }

      if (!isCurrentReactRequest()) return;
      if (isMissionTerminal(latestMission)) {
        notify(locale === "zh" ? "ReAct Agent 任务已完成" : "ReAct Agent mission complete");
      } else {
        setReactMissionError(
          locale === "zh"
            ? "任务仍在运行；稍后刷新或停止。"
            : "Mission is still running; refresh or stop later.",
        );
      }
    } catch (error) {
      if (!isCurrentReactRequest()) return;
      const message = error instanceof Error ? error.message : String(error);
      setReactMissionError(message);
    } finally {
      if (isCurrentReactRequest()) setIsStartingReactMission(false);
    }
  };

  const handleReactMissionAction = async (action: "pause" | "resume" | "stop") => {
    if (!reactMission) return;
    const projectId = reactMission.project_id;
    const missionId = reactMission.id;
    setReactMissionError("");
    if (action === "stop") {
      reactMissionRequestTokenRef.current += 1;
    }
    try {
      const updated = await updateAgentMissionStatus(missionId, action);
      if (activeProjectIdRef.current !== projectId || reactMissionRef.current?.id !== missionId) return;
      updateReactMissionState(updated);
      setReactTrace(updated.trace_events);
      const visualization = await fetchAgentMissionVisualization(missionId).catch(() => null);
      if (activeProjectIdRef.current === projectId && reactMissionRef.current?.id === missionId) {
        setReactVisualization(visualization);
      }
    } catch (error) {
      if (activeProjectIdRef.current !== projectId || reactMissionRef.current?.id !== missionId) return;
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
        isLoading={isLoadingArchive}
        isSwitchingArchive={isSwitchingArchive}
        locale={locale}
        onArchiveChange={handleArchiveChange}
        onLocaleChange={setLocale}
        onSearchGraph={handleSearchGraph}
        selectedArchiveId={selectedArchiveId}
      />
      {notice ? <div className="notice-bar" role="status">{notice}</div> : null}
      <PageTabs activePage={activePage} locale={locale} onPageChange={setActivePage} />
      <DemoGuidePanel
        activePage={activePage}
        agentReport={agentReport}
        archiveDraft={archiveDraft}
        archiveIds={archiveIds}
        graphVisited={demoVisitedPages.includes("graph")}
        isCreatingArchive={isCreatingArchive}
        isLoadingUniverse={isLoadingUniverse}
        isRunningAgentReport={isRunningAgentReport}
        isRunningUniverseAgent={isRunningUniverseAgent}
        isRunningUniverseDiff={isRunningUniverseDiff}
        knowledgeUniverse={knowledgeUniverse}
        locale={locale}
        onCreateArchive={handleCreateArchive}
        onGoPage={setActivePage}
        onOpenUpload={() => {
          setActivePage("overview");
          window.setTimeout(() => {
            document.getElementById("project-intake")?.scrollIntoView({ behavior: "smooth", block: "center" });
          }, 0);
        }}
        onRunAgentReport={handleRunAgentReport}
        onRunFirstDiff={() => {
          const projectIds = selectedUniverseProjectIds.length ? selectedUniverseProjectIds : archiveIds;
          const [leftProjectId, rightProjectId] = projectIds;
          if (leftProjectId && rightProjectId) void handleRunUniverseDiff(leftProjectId, rightProjectId);
        }}
        onRunUniverseAgent={handleRunUniverseAgent}
        selectedFileName={selectedFileName}
        universeDiffReport={universeDiffReport}
      />
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
          {archiveDraft ? (
            <>
              <ProjectPassport
                archiveDraft={archiveDraft}
                isFallback={isFallbackArchive}
                locale={locale}
              />
              <IngestionDiagnosticsPanel
                diagnostics={
                  ingestionDiagnostics?.project_id === archiveDraft.projectId
                    ? ingestionDiagnostics
                    : null
                }
                locale={locale}
              />
              {selectedHall ? (
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
              ) : (
                <EmptyGeneratedArchiveState archiveDraft={archiveDraft} locale={locale} />
              )}
            </>
          ) : (
            <EmptyArchiveState archiveCount={archiveIds.length} locale={locale} />
          )}
        </>
      ) : activePage === "system" ? (
        <SystemConfigPage
          check={systemConfigCheck}
          error={systemConfigError}
          harnessSummary={
            harnessSummary?.project_id === (archiveDraft?.projectId ?? selectedArchiveId)
              ? harnessSummary
              : null
          }
          isLoading={isLoadingSystemConfig}
          locale={locale}
          onRefresh={loadSystemConfigCheck}
        />
      ) : activePage === "tasks" ? (
        <TaskCenterPage
          currentProjectId={archiveDraft?.projectId ?? selectedArchiveId}
          error={taskCenterError}
          isLoading={isLoadingTaskCenter}
          isRunningStressTest={isRunningStressTest}
          jobs={taskCenterJobs}
          locale={locale}
          onCancel={handleCancelTaskCenterJob}
          onRefresh={() => void loadTaskCenterJobs()}
          onRunStressTest={handleRunStressTest}
          stressTestError={stressTestError}
          stressTestReport={stressTestReport}
        />
      ) : activePage === "graph" && archiveDraft ? (
        <GraphExplorerPage
          archiveDraft={archiveDraft}
          graphWorkspaceReport={graphWorkspaceReport?.project_id === archiveDraft.projectId ? graphWorkspaceReport : null}
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
      ) : activePage === "universe" ? (
        <KnowledgeUniversePage
          archiveIds={archiveIds}
          diffReport={universeDiffReport}
          error={universeError}
          isRunningDiff={isRunningUniverseDiff}
          isRunningUniverseAgent={isRunningUniverseAgent}
          isLoading={isLoadingUniverse}
          locale={locale}
          onOpenProject={(projectId) => {
            void handleArchiveChange(projectId);
            setActivePage("overview");
          }}
          onRefresh={() => {
            void loadKnowledgeUniverse(selectedUniverseProjectIds.length ? selectedUniverseProjectIds : archiveIds);
          }}
          onToggleProject={handleToggleUniverseProject}
          onRunDiff={handleRunUniverseDiff}
          onRunUniverseAgent={handleRunUniverseAgent}
          onSavePath={handleSaveUniversePath}
          paths={universePaths}
          selectedProjectIds={selectedUniverseProjectIds.length ? selectedUniverseProjectIds : archiveIds}
          tasks={universeAgentTasks}
          universe={knowledgeUniverse}
        />
      ) : archiveDraft && selectedHall ? (
        <div className="agent-analysis-page">
          <div className="agent-analysis-main">
            <AgentTaskPlanPanel
              locale={locale}
              plan={
                agentTaskPlan?.project_id === archiveDraft.projectId
                  ? agentTaskPlan
                  : null
              }
            />
            <AgentEvalHarnessPanel
              artifacts={
                harnessArtifacts?.project_id === archiveDraft.projectId
                  ? harnessArtifacts
                  : null
              }
              error={agentEvalError}
              harnessCommands={harnessCommands}
              harnessSummary={
                harnessSummary?.project_id === archiveDraft.projectId
                  ? harnessSummary
                  : null
              }
              harnessTimeline={
                harnessTimeline?.project_id === archiveDraft.projectId
                  ? harnessTimeline
                  : null
              }
              harnessToolResult={harnessToolResult}
              isRunningHarnessTool={isRunningHarnessTool}
              isRunning={isRunningAgentEval}
              locale={locale}
              onCleanupDryRun={handleHarnessArtifactCleanupDryRun}
              onDryRunLiveCommand={handleHarnessCommandDryRun}
              onExport={handleHarnessExport}
              onRun={handleRunAgentEval}
              report={
                agentEvalReport?.project_id === archiveDraft.projectId
                  ? agentEvalReport
                  : null
              }
            />
            <ReactAgentMissionPanel
              error={reactMissionError}
              isStarting={isStartingReactMission}
              locale={locale}
              mission={reactMission?.project_id === archiveDraft.projectId ? reactMission : null}
              onAction={handleReactMissionAction}
              onStart={handleStartReactMission}
              trace={reactMission?.project_id === archiveDraft.projectId ? reactTrace : []}
              visualization={
                reactVisualization?.project_id === archiveDraft.projectId
                  ? reactVisualization
                  : null
              }
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
            <ProjectIntelligenceReportPanel
              error={intelligenceReportError}
              isGenerating={isGeneratingIntelligenceReport}
              locale={locale}
              onDownloadMarkdown={handleDownloadIntelligenceMarkdown}
              onDownloadPdf={handleDownloadIntelligencePdf}
              onGenerate={handleGenerateIntelligenceReport}
              report={
                intelligenceReport?.project_id === archiveDraft.projectId
                  ? intelligenceReport
                  : null
              }
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
              graphStoreStatus={graphStoreStatus}
              hybridRagStatus={hybridRagStatus}
              isRebuildingHybridRag={isRebuildingHybridRag}
              locale={locale}
              onRebuildHybridRag={handleRebuildHybridRag}
              report={agentReport}
            />
            <AgentMemoryPanel
              locale={locale}
              memory={
                agentMemory?.project_id === archiveDraft.projectId
                  ? agentMemory
                  : null
              }
            />
            <AgentTrustPanel
              locale={locale}
              report={
                agentTrustReport?.project_id === archiveDraft.projectId
                  ? agentTrustReport
                  : null
              }
            />
            <MultimodalInsightsPanel
              insights={
                multimodalInsights?.project_id === archiveDraft.projectId
                  ? multimodalInsights
                  : null
              }
              locale={locale}
            />
            <EvaluationBenchmarkPanel
              history={
                evaluationHistory?.project_id === archiveDraft.projectId
                  ? evaluationHistory
                  : null
              }
              isRunning={isRunningEvaluation}
              locale={locale}
              onRun={handleRunEvaluation}
              report={
                evaluationReport?.project_id === archiveDraft.projectId
                  ? evaluationReport
                  : null
              }
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
