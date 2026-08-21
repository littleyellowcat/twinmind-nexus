# TwinMind Nexus opencode Harness Engineering Design

## 目标

本设计把 opencode 中值得借鉴的 harness 工程能力转译到 TwinMind Nexus。目标不是把 TwinMind 改成通用 Coding Agent，而是强化它作为项目知识数字孪生、GraphRAG、Agent 分析平台的可靠性、可审计性、运行治理、产物管理和开发者体验。

## 边界

TwinMind 应继续以项目摄取、知识图谱、证据卡、Hybrid RAG、Agent 分析、AgentEval 和报告导出为核心。opencode 的 Bash、文件编辑、patch、TUI、桌面端、多插件市场能力不直接照搬。

本次借鉴的主线是 harness 工程：

- durable run evidence：每次摄取、AgentEval、Agent mission、报告生成、RAG 重建都留下可排序事件。
- permission/governance：把操作映射成业务风险，而不是只看工具名。
- bounded output：长报告、模型原始输出、trace 和评测详情保留全文落盘，只把预览放入 API/上下文。
- run status/resume metadata：运行状态、失败原因、下一步动作可查询。
- agent capability matrix：角色、任务、工具、风险等级结构化。
- provider/runtime policy：模型调用、外部 API、付费操作、生产操作有显式策略。
- regression gates：质量门禁能解释为何 pass/warn/fail。
- observability contract：前端、API、测试都消费同一套事件和产物元数据。

## opencode 可借鉴点

### 1. 权限评估模型

opencode 使用 `action + resource + ruleset -> allow / ask / deny` 的思路。TwinMind 应转译为：

| Operation | 默认效果 | 说明 |
|---|---:|---|
| `read_only` | allow | 读 archive、读报告、读状态 |
| `local_artifact_write` | allow | 写本地报告、事件、memory、artifact |
| `live_model_call` | ask | DeepSeek/OpenAI/Ollama 等真实模型调用 |
| `external_api_call` | ask | 下载 GitHub ZIP、访问外部服务 |
| `paid_operation` | ask | 付费生图、付费 LLM、大批量任务 |
| `production_operation` | deny | 删除、发布、部署、清空状态 |

第一阶段不做交互式审批 UI，而是把治理结果写入报告和事件，让 API 能说明“这个操作为何允许、为何需要人工确认、为何禁止”。

### 2. Durable Event Stream

opencode 将 session、permission、tool、message 等变化做成事件。TwinMind 需要项目级、运行级事件：

- `run.started`
- `run.stage.started`
- `run.stage.completed`
- `run.stage.failed`
- `run.completed`
- `run.failed`
- `governance.evaluated`
- `artifact.persisted`
- `agent.capability.selected`

事件必须有：

- `id`
- `project_id`
- `run_id`
- `type`
- `sequence`
- `created_at`
- `data`

这让系统可以回答：这次运行从哪里开始，执行了什么，哪些工具/模型参与，哪些产物生成，失败在哪里，下一步应该做什么。

### 3. Bounded Output Store

opencode 的 tool output store 会限制 lines/bytes，全文写入受管理目录，API 只返回预览。TwinMind 应统一管理：

- AgentEval report
- Agent report
- mission trace
- DeepSeek raw response
- intelligence report
- stress test report
- long retrieval result

产物记录应包含：

- `artifact_id`
- `kind`
- `path`
- `sha256`
- `bytes`
- `preview`
- `truncated`
- `omitted_bytes`
- `created_at`

这样可以避免把超长 JSON、Markdown、trace 全塞进模型上下文或前端首屏，同时保持可审计。

### 4. Agent Capability Matrix

opencode 的 agent schema 有 mode、tools、permission。TwinMind 应把五类 Agent 和 mission task 的职责边界结构化：

| Role | 允许工具 | 禁止行为 |
|---|---|---|
| Archivist | list halls, get evidence, inspect entity | 不能做最终风险裁决 |
| Cartographer | graph summary, graph neighborhood, graph search | 不能生成无证据架构结论 |
| Detective | hybrid search, inspect entity, graph neighborhood | 不能跳过证据直接总结 |
| Skeptic | get evidence, graph search, trust check | 不能修改 archive |
| Curator | read prior role results, compose report | 不能引入未引用事实 |

矩阵应暴露 API，供前端、测试、文档和 Agent runtime 使用。

### 5. Run Status 和 Resume Metadata

TwinMind 已有 job、mission、AgentEval、version history，但还缺统一 run-level 摘要。需要形成统一状态合同：

- `status`: queued/running/complete/warn/failed/cancelled
- `phase`
- `last_event_sequence`
- `artifacts`
- `warnings`
- `errors`
- `resume_available`
- `resume_action`
- `next_best_action`

第一阶段先生成只读 summary，不承诺真正断点续跑。

### 6. Provider 和外部服务策略

TwinMind 应将 DeepSeek、OpenAI、Ollama、Chroma、Neo4j、Kuzu、GitHub ZIP 回归等运行依赖纳入 policy：

- credential presence 不泄露 secret。
- external reachability 失败要变成结构化 warning。
- live model call 默认标记为 governance `ask`。
- fast/rules fallback 必须保留证据。
- 真实外部调用不得在测试中成为默认路径。

### 7. 测试和回归

借鉴 opencode 的测试风格，TwinMind 应补齐：

- 事件序列和过滤测试。
- bounded artifact 的 byte/preview/hash 测试。
- governance allow/ask/deny 测试。
- capability matrix 不含 shell/file-write 这类 coding-agent 工具的测试。
- AgentEval 运行后能查询 harness events/artifacts 的 API 测试。
- 失败情况下也写 run.failed 事件的测试。

## TwinMind 现状判断

已具备的基础：

- `src/project_archive/service.py` 已有 archive ingestion、Agent report、AgentEval、version history、stress test、memory、mission trace。
- `src/project_archive/api.py` 已有 jobs、cancel、agent mission trace、AgentEval、agent memory、intelligence report 等 API。
- `src/project_archive/agent_tools.py` 已有 allowlist 和 bounded tool limits。
- `src/project_archive/types.py` 已有 AgentMission、AgentTraceEvent、ProjectAgentReport 等结构。
- `tests/unit/test_project_archive_api.py` 已覆盖 AgentEval、memory、stress、system config、versions。
- `tests/unit/test_project_archive_agent_tools.py` 已覆盖 tool allowlist、limit cap、输入校验。

主要缺口：

- version history 是业务事件，不是统一 durable run event stream。
- AgentEval artifacts 只是路径字符串，缺少 sha256、preview、truncation 元数据。
- tool allowlist 存在，但缺少 opencode 风格的 action/resource/ruleset 解释。
- Agent role 权限存在于代码和 prompt 语义中，缺少可测试的 capability matrix。
- job 状态和 mission 状态分散，没有统一 harness summary。
- 外部服务/模型调用风险没有统一 governance 记录。
- 没有统一 API 暴露 harness events/capabilities/artifacts。

## 分阶段实施

### Phase 1：Harness 底座

目标：不依赖真实 DeepSeek、不改前端主流程，先补平台证据层。

交付：

- `src/project_archive/harness_events.py`
- `src/project_archive/harness_artifacts.py`
- `src/project_archive/harness_governance.py`
- AgentEval 写 `run.started`、`artifact.persisted`、`run.completed` 或 `run.failed`。
- API 暴露 `/api/harness/capabilities`、`/api/archives/{project_id}/harness/events`。
- AgentEval report 的 artifacts 增加 bounded artifact metadata。
- 聚焦单元测试通过。

### Phase 2：Run Summary 和 Resume Guidance

目标：统一 job、mission、AgentEval、version history 的状态视图。

交付：

- `GET /api/archives/{project_id}/harness/summary`
- summary 包含 last run、last failure、artifacts、warnings、next action。
- mission stop/fail/cancel 事件统一写入 harness event stream。
- 前端 Agent/System 页面展示 run summary。

### Phase 3：Provider Policy 和 Cost Guard

目标：真实模型、外部 API、付费操作统一治理。

交付：

- service 层所有 live model call 走 governance evaluation。
- AgentEval/Agent report metadata 标记 governance result。
- API 支持 dry-run policy check。
- 测试覆盖 DeepSeek 不可达、Ollama 不可达、缺少 key、fast fallback。

### Phase 4：Tool Settlement 和 Trace Artifact 化

目标：mission trace、tool payload、retrieval payload 都有可控预览和完整落盘。

交付：

- AgentToolResult 增加 artifact refs。
- oversize payload 自动进入 artifact store。
- `/api/agent-missions/{id}/trace` 返回 bounded preview。
- 完整 trace 可通过 artifact path/report endpoint 查看。

### Phase 5：Developer Experience

目标：像 opencode 一样，让开发者能快速排查运行问题。

交付：

- `scripts/harness_doctor.py`
- `scripts/harness_events.py`
- README/quickstart 增加 harness debugging。
- GitHub ZIP regression 报告附带 event/artifact summary。

## 不应照搬的内容

- Bash/file edit/patch permission。
- Coding-agent session prompt 和 plan/build mode。
- TUI/desktop runtime。
- 通用插件市场。
- 自动提交、自动部署、自动删除产物。

这些能力会拉偏 TwinMind 的产品定位，也会显著提高安全风险。

## 第一阶段验收标准

- AgentEval 运行后能在项目目录下看到 `harness_events.jsonl`。
- 事件 sequence 单调递增，且包含 run start、artifact persisted、run complete。
- AgentEval report 的 `artifacts` 中有至少一个包含 sha256/bytes/preview/truncated 的 harness artifact。
- API 可查询 project harness events。
- API 可查询 capability matrix。
- governance 测试证明 read-only/local write allow，live model/external/paid ask，production deny。
- capability matrix 中不包含 shell、bash、file_write、patch 等 coding-agent 工具。
- 聚焦测试通过。

## 成功标准

完成后，TwinMind 不只是“能生成报告”，而是能回答：

- 本次运行做了什么？
- 哪些阶段成功或失败？
- 哪些产物生成了，完整内容在哪里，hash 是什么？
- 哪些操作需要人工确认或被禁止？
- 哪个 Agent 有权使用哪些工具？
- 如果失败，下一步最合理动作是什么？

这就是 opencode 值得借鉴的 harness 工程精神在 TwinMind 场景下的转译。
