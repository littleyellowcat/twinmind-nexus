# TwinMind Nexus opencode Gap Optimization Design

## 目的

本文把上一轮对比中提出的 10 个优化方向补充成可执行规格。它不是要把 TwinMind Nexus 变成通用 Coding Agent，而是继续借鉴 opencode 的工程化长处，强化 TwinMind 作为项目知识数字孪生、GraphRAG、Agent 分析和证据工作台的可靠性、可复现性、治理能力和开发体验。

## 参考来源

- opencode Agents 文档：Agent 可配置 description、mode、tools、permission，并区分 primary/subagent。
- opencode Permissions 文档：权限模型围绕 tool/action/resource 做 allow/ask/deny 决策，支持更细粒度规则。
- opencode Tools 文档：工具执行需要有清晰边界、输入输出约束和权限参与。
- opencode Commands 文档：通过项目内命令文件定义可复用工作流。
- opencode Rules 文档：通过项目规则文件给 Agent 提供稳定工程约定。
- opencode GitHub 文档：通过 GitHub runner 在 issue/PR 中触发 Agent 工作流。
- opencode Changelog：持续强化 session chronology、JSON export、message ordering、tool output truncation、share/export 等调试和审计能力。

## 当前已落地能力

上一阶段已经补齐：

- `harness_events.jsonl` 项目级事件流。
- `HarnessArtifactStore` 长产物全文落盘、API 返回 preview/hash/bytes。
- `HarnessGovernanceDecision` 和 allow/ask/deny 基础策略。
- `harness_capability_matrix()` 角色能力矩阵。
- `harness_run_summary()` 最近运行状态、失败原因、下一步动作。
- `POST /api/harness/policy-check` dry-run 策略检查。
- `GET /api/agent-missions/{mission_id}/trace-artifact` trace artifact 化。
- `scripts/harness_doctor.py` 和 `scripts/harness_events.py`。
- AgentEval/System 前端展示 harness summary。
- GitHub ZIP regression 行级 harness 摘要。

## 总体实施路径

推荐路径：先补可复现性和规则治理，再补 timeline/export，最后做外部 runner。

### 方案 A：P0 先行

先做测试环境、细粒度 policy、AGENTS/llms 规则。优点是能立刻提高后续开发可信度；缺点是用户可见功能较少。

### 方案 B：可视化优先

先做 timeline/export 和前端页面。优点是演示效果强；缺点是如果测试环境和规则层不稳，后续容易返工。

### 方案 C：自动化优先

先做 commands、GitHub runner、regression workflow。优点是很像 opencode 的工程体验；缺点是外部服务、权限和失败恢复风险更高。

推荐选择方案 A，然后滚动进入 B。TwinMind 当前最需要的是“可靠地验证和解释自己”，不是更早接入更多外部动作。

## 优先级总览

| 编号 | 优化项 | 优先级 | 主要收益 | 风险 |
|---:|---|---:|---|---|
| 1 | 测试/环境可复现性 | P0 | 让 API、前端、harness 验证稳定可跑 | 依赖安装需要用户确认 |
| 2 | 细粒度 permission policy | P0 | 让治理从 action 级提升到 role/tool/resource 级 | 规则复杂度上升 |
| 3 | 项目级 AGENTS.md / llms.txt | P0 | 固化项目规则，提升 Agent 与人类协作一致性 | 规则过期需检测 |
| 4 | Session timeline / JSON export | P1 | 完整审计、分享、复盘 | 导出包可能泄露路径 |
| 5 | 自定义 commands / 运维快捷动作 | P1 | 把常用安全工作流模板化 | 不能变成任意 shell |
| 6 | Agent profile 配置化 | P1 | 角色能力可演化、可测试、可展示 | 配置和代码需保持一致 |
| 7 | Ingestion/query trace 接入 harness | P1 | 全链路统一事件视图 | 事件噪声和体积增长 |
| 8 | Artifact retention / cleanup policy | P1 | 控制磁盘、发现孤儿产物 | 误删风险 |
| 9 | Provider resilience | P1 | 外部模型/服务失败可解释、可恢复 | 需要避免真实调用进入测试 |
| 10 | GitHub report-only runner | P2 | PR/issue 中自动生成证据报告 | CI 权限和隐私边界 |

---

## 1. 测试/环境可复现性

### 当前缺口

当前 checkout 中：

- 系统 `python3` 是 3.9，项目代码用到 `datetime.UTC`、`tomllib` 等 3.10+ 能力。
- `/Users/kitten/.local/bin/python3.12` 可做 `py_compile`，但没有 pytest/project deps。
- API pytest 收集被 `jieba` 缺失阻塞。
- 前端 `npm run build` 被 `node_modules`/`tsc` 缺失阻塞。

### opencode 借鉴点

opencode 强调可重复运行的命令、非交互流程、runner 和 session 输出可追踪。TwinMind 需要把“怎么验证”变成一等公民。

### 目标状态

任何开发者拿到仓库后，可以通过少量命令得到清晰结果：

- harness 单元测试可跑。
- API 单元测试可跑。
- 前端 build 可跑。
- 环境缺口能被 doctor 明确指出。
- 不需要猜哪个 Python、哪个 node、哪些依赖。

### 建议实现

新增：

- `Makefile`
  - `make doctor`
  - `make test-harness`
  - `make test-api`
  - `make py-compile`
  - `make frontend-build`
  - `make verify`
- `scripts/dev_env_doctor.py`
  - 检查 Python 版本、pytest、jieba、tomllib、FastAPI、node、npm、frontend/node_modules、tsc。
  - 输出 JSON 和人类可读两种格式。
  - 不自动安装依赖。
- `docs/twinmind_dev_environment.md`
  - 明确推荐 Python 版本。
  - 明确依赖安装命令。
  - 明确哪些测试需要外部服务，哪些不需要。
- `pyproject.toml` 可选补充 test extras，例如：
  - `project.optional-dependencies.test`
  - `project.optional-dependencies.frontend` 不适合放 Python，可只在 docs 说明。

### 验收标准

- `make doctor` 在缺依赖时退出 0，但 status 为 `warn`，列出缺失项。
- `make test-harness` 只跑不依赖外部服务的 harness tests。
- `make py-compile` 使用 3.10+ Python，输出清晰。
- `make verify` 不会静默跳过失败项；阻塞项必须被报告。
- 文档说明不要求付费 API key。

### 风险边界

- 不在脚本中自动安装依赖。
- 不把真实 DeepSeek/OpenAI/Ollama 调用作为默认测试路径。

---

## 2. 细粒度 Permission Policy

### 当前缺口

当前治理只有 operation action 层级：

- `read_only`
- `local_artifact_write`
- `live_model_call`
- `external_api_call`
- `paid_operation`
- `production_operation`

它还不能表达：

- 哪个 role 允许调用哪个 tool。
- 哪个 resource pattern 需要 ask。
- 哪类路径/目录不可读取。
- 是否允许某个 mission 临时提升权限。
- 连续失败或循环调用是否要拦截。

### opencode 借鉴点

opencode 将 Agent mode、tools、permission、tool/resource 规则放在配置和运行时决策中。TwinMind 应转译为业务语义，而不是照搬 shell/file-write 权限。

### 目标状态

权限决策从 `action + resource` 扩展为：

```text
subject(role/mission) + action + tool + resource + context -> allow/ask/deny
```

### 建议实现

新增：

- `src/project_archive/harness_policy.py`
  - `HarnessPolicyRule`
  - `HarnessPolicyContext`
  - `evaluate_policy(context)`
  - 支持 priority、role、tool、action、resource_pattern、effect、reason。
- `config/harness_policy.yaml`
  - 默认规则仍然内置，配置文件只覆盖/扩展。
  - 支持 glob-like resource pattern。
- API：
  - `GET /api/harness/policy`
  - `POST /api/harness/policy-check`
  - `GET /api/archives/{project_id}/harness/policy-events`
- 事件：
  - `governance.policy.loaded`
  - `governance.evaluated`
  - `governance.denied`

### 默认规则建议

| Role | Tool | Action | Effect |
|---|---|---|---:|
| archivist | list_halls/get_evidence/inspect_entity | read_only | allow |
| cartographer | graph_summary/graph_neighborhood/graph_search | read_only | allow |
| detective | hybrid_search/inspect_entity/graph_neighborhood | read_only | allow |
| skeptic | get_evidence/graph_search/trust_check | read_only | allow |
| curator | compose_report/read_prior_results | local_artifact_write | allow |
| any | live model provider | live_model_call | ask |
| any | GitHub/network fetch | external_api_call | ask |
| any | delete/clear/deploy/push | production_operation | deny |
| any | shell/bash/apply_patch/file_write | coding_agent_tool | deny |

### 验收标准

- 单元测试覆盖 role/tool/action/resource 四维组合。
- 默认禁止 shell/bash/apply_patch/file_write/git_push/deploy。
- policy-check 响应不泄露 API key。
- Agent mission 中每次 tool selection 都可关联 policy decision。
- denied 决策写 harness event。

### 风险边界

- 不增加任意命令执行能力。
- 不让前端直接编辑生产 policy，除非未来加入明确审批。

---

## 3. 项目级 AGENTS.md / llms.txt

### 当前缺口

TwinMind 仓库没有项目级 `AGENTS.md` 或 `llms.txt`。现有规则散落在 README、DEV_SPEC、docs、prompt 和代码中，Agent 难以稳定识别“本项目的工程契约”。

### opencode 借鉴点

opencode 的 Rules 能把项目规则加载给 Agent。TwinMind 可以把规则文件作为 archive 的高权重证据，同时用于本地开发协作。

### 目标状态

仓库根目录提供：

- `AGENTS.md`：给 coding/analysis agents 的工程规则。
- `llms.txt`：给外部 LLM/RAG 的项目导航、重要入口和禁止事项。
- `docs/twinmind_engineering_contract.md`：更长的工程契约说明。

摄取项目时：

- 自动识别这些文件。
- 提升为高权重 evidence cards。
- 在 Agent report 中把它们作为规则来源。

### 建议实现

新增：

- `AGENTS.md`
  - 项目定位。
  - 测试命令。
  - 禁止自动安装依赖、push、删除资产。
  - harness debugging 命令。
  - 真实 provider 调用必须走 policy。
- `llms.txt`
  - `README.md`
  - `src/project_archive/service.py`
  - `src/project_archive/api.py`
  - `src/project_archive/harness_*.py`
  - `frontend/src/App.tsx`
  - `docs/superpowers/specs/...`
- Scanner 增强：
  - `_is_project_rule_file(path)`
  - metadata `rule_file: true`
  - evidence confidence 提升。
- Agent prompt/metadata：
  - `rule_sources`
  - `engineering_contract_version`

### 验收标准

- 根目录存在 `AGENTS.md` 和 `llms.txt`。
- 上传/扫描包含这些文件的项目时，evidence cards 标记 `rule_file: true`。
- AgentEval 报告 metadata 中出现 `rule_sources`。
- 文档不包含 secrets 或机器私有绝对路径。

### 风险边界

- 规则文件是指导，不是自动执行许可。
- 规则冲突时以用户显式指令和仓库内最新 AGENTS.md 为准。

---

## 4. Session Timeline / JSON Export

### 当前缺口

已有 project events 和 summary，但还没有完整 session/timeline 导出：

- 不能一键导出某个项目的全部 harness 证据。
- 前端没有按时间线查看 run/stage/tool/artifact。
- 事件、version history、agent_eval、mission trace、artifacts manifest 仍分散。

### opencode 借鉴点

opencode 持续强化 session chronology、JSON export、message ordering、share/export。TwinMind 可以做项目级证据导出，而不是聊天 session 导出。

### 目标状态

新增项目证据包：

```text
harness_export_<project_id>_<timestamp>.json
```

包含：

- `project_id`
- `created_at`
- `summary`
- `events`
- `runs`
- `artifacts_manifest`
- `version_history`
- `agent_eval_report`
- `agent_memory`
- `mission_summaries`
- `trace_artifacts`
- `redactions`

### 建议实现

新增：

- `src/project_archive/harness_export.py`
  - `build_harness_timeline(project_id)`
  - `build_harness_export(project_id, redact_paths=True)`
  - `write_harness_export(project_id)`
- API：
  - `GET /api/archives/{project_id}/harness/timeline`
  - `GET /api/archives/{project_id}/harness/export`
- Frontend：
  - Agent/System 页面中增加 timeline 折叠面板。
  - export 下载按钮。
- Script：
  - `scripts/harness_export.py --project-id ...`

### Redaction 规则

- 默认不导出 full artifact content，只导出 manifest 和 preview。
- 绝对路径可保留 basename/project-relative path。
- secrets pattern 统一扫描并标注 redacted。

### 验收标准

- export JSON 可被 `json.loads` 读取。
- timeline 按 `created_at + sequence` 稳定排序。
- artifact manifest 中有 sha256/bytes/truncated。
- 默认 export 不包含 API key、环境变量 secret、用户 home 绝对路径。

### 风险边界

- 分享/导出必须默认脱敏。
- 完整 artifact content 需要显式参数，例如 `include_artifact_content=false` 默认。

---

## 5. 自定义 Commands / 运维快捷动作

### 当前缺口

TwinMind 有脚本和 API，但没有统一的“安全命令目录”。开发者要记住很多命令和 endpoint。

### opencode 借鉴点

opencode 支持项目命令文件，用自然语言触发标准工作流。TwinMind 可以借鉴“命令注册表”，但命令只能映射到已知 service/API/script，不允许任意 shell。

### 目标状态

项目内定义命令：

```text
.twinmind/commands/doctor.md
.twinmind/commands/agent-eval.md
.twinmind/commands/export-harness.md
.twinmind/commands/rebuild-rag.md
.twinmind/commands/regression.md
```

每个命令声明：

- `id`
- `description`
- `arguments`
- `allowed_actions`
- `policy_action`
- `implementation`
- `outputs`

### 建议实现

新增：

- `src/project_archive/harness_commands.py`
  - `HarnessCommand`
  - `list_harness_commands()`
  - `run_harness_command(id, args, dry_run=True)`
- API：
  - `GET /api/harness/commands`
  - `POST /api/harness/commands/{command_id}/dry-run`
  - `POST /api/harness/commands/{command_id}/run`
- Script：
  - `scripts/harness_command.py doctor --project-id sample`

### 默认命令

| Command | 行为 | Policy |
|---|---|---:|
| `doctor` | 读取环境和项目 harness 状态 | allow |
| `events` | 列出 harness events | allow |
| `agent-eval` | 运行 deterministic AgentEval | allow |
| `agent-eval-live` | 运行 live model agent report + eval | ask |
| `export-harness` | 导出脱敏证据包 | allow |
| `rebuild-rag` | 重建本地 Hybrid RAG | allow |
| `github-regression` | 读取本地 zip fixtures 跑 regression | allow/ask，取决于是否下载 |

### 验收标准

- commands list 不包含 shell/raw command。
- dry-run 会返回 policy decision 和预计产物。
- ask/deny 命令默认不执行。
- 每次 run 写 `command.started/completed/failed` event。

### 风险边界

- 禁止命令执行任意 shell 字符串。
- 只允许调用白名单 Python 函数。

---

## 6. Agent Profile 配置化

### 当前缺口

角色矩阵当前在 `harness_governance.py` 里硬编码。Agent prompt、工具、职责、证据要求分散在代码中。

### opencode 借鉴点

opencode agent 可以配置 description、mode、tools、permission。TwinMind 应把 archive roles 配置化，但保留业务语义。

### 目标状态

新增：

```text
config/agent_profiles.yaml
```

结构：

```yaml
roles:
  archivist:
    purpose: Select and organize project evidence.
    allowed_tools: [list_halls, get_evidence, inspect_entity]
    disallowed_actions: [final_risk_verdict, archive_mutation]
    evidence_requirements:
      min_evidence_cards: 1
      citation_required: true
    policy_overrides: []
```

### 建议实现

新增：

- `src/project_archive/agent_profiles.py`
  - `load_agent_profiles()`
  - `validate_agent_profiles()`
  - `profiles_to_capability_matrix()`
- `harness_capability_matrix()` 从 profile loader 读取。
- Agent mission planner 根据 profile 限制 allowed tools。
- API：
  - `GET /api/harness/agent-profiles`

### 验收标准

- 配置缺字段时报可读错误。
- 配置里的 forbidden coding tools 会被拒绝加载。
- capability endpoint 和 mission planner 使用同一 profile 来源。
- 测试覆盖 profile 加载、非法工具拒绝、默认 fallback。

### 风险边界

- 配置化不代表用户可在前端任意增加工具。
- profile 文件只允许引用已注册工具。

---

## 7. Ingestion/Query Trace 接入 Harness

### 当前缺口

项目原始 DEV_SPEC 中已有 ingestion/query trace 思路，当前 archive harness events 主要覆盖 AgentEval 和 Agent mission。摄取、查询、RAG 重建、报告生成还没有统一事件流。

### opencode 借鉴点

opencode 将 session、tool、permission、message 等运行变化统一成可排序记录。TwinMind 应把 archive ingestion/query/report 都转成 harness events。

### 目标状态

新增事件：

- `ingestion.started`
- `ingestion.stage.completed`
- `ingestion.failed`
- `query.started`
- `query.retrieval.completed`
- `query.completed`
- `query.failed`
- `rag.rebuild.started`
- `rag.rebuild.completed`
- `report.generated`

### 建议实现

接入点：

- `ProjectArchiveService.ingest_project()`
- `ProjectArchiveService.query_project()`
- `ProjectArchiveService.rebuild_hybrid_rag_index()`
- `ProjectArchiveService.generate_project_intelligence_report()`
- `ProjectHybridRAGIndex.search/build/rebuild_from_draft()` 返回阶段 metadata。

新增：

- `HarnessRunContext`
  - `run_id`
  - `project_id`
  - `kind`
  - `append_stage()`
  - `complete()`
  - `fail()`

### 验收标准

- 上传项目后 harness summary 能显示 ingestion run。
- 查询项目后能看到 query run 和 retrieval metrics。
- RAG 重建成功/失败都有事件。
- 超长 retrieval payload 进入 artifact store。
- 事件数量可控，不记录每个 chunk 的细节。

### 风险边界

- 默认只记录阶段聚合，不记录大块源码全文。
- 不让 query events 泄露用户敏感问题，必要时提供 redaction。

---

## 8. Artifact Retention / Cleanup Policy

### 当前缺口

Artifact 现在会保存全文，但没有：

- retention days。
- 每项目最大 bytes。
- orphan artifact 检测。
- artifact manifest。
- 清理 dry-run。

### opencode 借鉴点

opencode 对 tool output truncation 和 session cleanup 持续优化。TwinMind 的 artifact store 需要生命周期管理。

### 目标状态

每个项目有：

```text
harness_artifacts/manifest.json
```

包含：

- artifact_id
- kind
- run_id
- path
- sha256
- bytes
- created_at
- referenced_by_event_id
- retention_policy

### 建议实现

新增：

- `src/project_archive/harness_artifact_retention.py`
  - `build_artifact_manifest(project_id)`
  - `validate_artifacts(project_id)`
  - `cleanup_artifacts(project_id, dry_run=True)`
- API：
  - `GET /api/archives/{project_id}/harness/artifacts`
  - `POST /api/archives/{project_id}/harness/artifacts/cleanup-dry-run`
  - cleanup real run 需要 ask，不默认开放。
- Script：
  - `scripts/harness_artifacts.py --project-id sample --validate`

### 默认策略

- 保留最近 50 个 run 的 artifact。
- 单项目默认上限 256MB。
- 任何未被 manifest 或 event 引用的文件标为 orphan。
- cleanup 默认 dry-run。

### 验收标准

- manifest 可重建且稳定。
- orphan 文件会被 doctor 报告。
- cleanup dry-run 不删除文件，只列出 candidate。
- 真实 cleanup 需要显式确认和 governance ask。

### 风险边界

- 不自动删除用户资产。
- 不清理 `draft_archive.json`、graph store、agent memory。

---

## 9. Provider Resilience

### 当前缺口

已有 dry-run policy check，但真实 provider 调用链路还不完全统一：

- DeepSeek/OpenAI/Ollama 调用前不一定都写 governance event。
- provider 失败不一定有结构化 artifact。
- fallback 原因分散。
- 测试环境不能稳定模拟 provider。

### opencode 借鉴点

opencode 对 provider、model、tool execution、permission 都有明确 runtime contract。TwinMind 应让 provider failure 成为可诊断事件，而不是散落字符串。

### 目标状态

统一 provider contract：

```text
provider.policy.evaluated
provider.call.started
provider.call.completed
provider.call.failed
provider.fallback.used
```

### 建议实现

新增：

- `src/project_archive/provider_runtime.py`
  - `ProviderCallContext`
  - `provider_call_guard()`
  - `sanitize_provider_error()`
- 修改：
  - `create_archive_llm_enhancer_from_config()`
  - `run_agent_report()`
  - `query_project()`
  - vision/image caption path
  - evaluation/rerank provider path
- 增加 fake provider：
  - `FakeLLMProvider`
  - `FailingLLMProvider`
  - `SlowLLMProvider`

### 错误分类

| Category | 示例 | 处理 |
|---|---|---|
| `missing_credentials` | API key 未配置 | fallback + warning |
| `network_unreachable` | Ollama/remote URL 不可达 | fallback + event |
| `provider_timeout` | 请求超时 | retry bounded + artifact |
| `rate_limited` | 429 | ask/warn |
| `provider_error` | 5xx/invalid response | artifact + fallback |

### 验收标准

- live model call 前写 governance event。
- provider 失败不泄露 secret。
- deterministic fallback 有 event 和 summary warning。
- 单元测试使用 fake provider，不访问真实网络。

### 风险边界

- 不在测试中默认调用真实外部模型。
- 不把 provider retry 做成无限重试。

---

## 10. GitHub Report-only Runner

### 当前缺口

TwinMind 有 GitHub ZIP regression 脚本，但没有 GitHub issue/PR runner。不能像 opencode 那样在 GitHub 上触发分析工作流。

### opencode 借鉴点

opencode 支持 GitHub runner，由 issue/PR 评论触发 Agent。TwinMind 应做 report-only runner：只生成报告，不修改代码、不提交、不部署。

### 目标状态

GitHub Actions workflow：

```text
.github/workflows/twinmind-report.yml
```

触发方式：

- issue_comment 包含 `/twinmind analyze`
- pull_request 手动 workflow_dispatch

输出：

- architecture summary
- risk/evidence report
- harness export artifact
- PR comment summary

### 建议实现

新增：

- `scripts/github_report_runner.py`
  - clone/checkout 已由 GitHub Actions 负责。
  - 调用 ProjectArchiveService 摄取当前工作区。
  - 运行 deterministic AgentEval。
  - 导出 harness evidence package。
  - 写 markdown summary。
- `.github/workflows/twinmind-report.yml`
  - permissions 最小化：contents read, pull-requests write, issues write。
  - 不配置 secrets 时只运行 deterministic 模式。
- `docs/twinmind_github_runner.md`

### 安全边界

- 不运行 shell 分析插件。
- 不 push commit。
- 不 apply patch。
- 不使用 paid/live provider，除非 workflow 明确配置并通过 policy ask/allow。
- forks PR 默认只做只读 deterministic analysis。

### 验收标准

- workflow_dispatch 能生成 artifact。
- PR comment 只包含 summary 和 artifact 链接。
- 没有 secrets 时仍能跑 deterministic archive。
- runner 输出 harness events/export。
- 单元测试覆盖 report markdown 生成。

---

## 跨项数据模型建议

### HarnessPolicyContext

```python
{
  "project_id": "sample",
  "run_id": "agent-eval:...",
  "subject": {"kind": "agent_role", "id": "detective"},
  "action": "read_only",
  "tool": "hybrid_search",
  "resource": "archive:sample",
  "mode": "deterministic",
  "metadata": {}
}
```

### HarnessTimelineItem

```python
{
  "id": "timeline:...",
  "project_id": "sample",
  "run_id": "agent-eval:...",
  "sequence": 12,
  "created_at": "...",
  "category": "run|stage|tool|policy|artifact|provider",
  "status": "complete|warn|failed|running",
  "title": "AgentEval completed",
  "summary": "...",
  "artifact_ids": []
}
```

### HarnessArtifactManifest

```python
{
  "project_id": "sample",
  "generated_at": "...",
  "artifacts": [
    {
      "artifact_id": "artifact_...",
      "kind": "agent_eval_report",
      "run_id": "agent-eval:...",
      "sha256": "...",
      "bytes": 1234,
      "path": "harness_artifacts/...",
      "referenced": true
    }
  ]
}
```

## 推荐实施计划

### Sprint 1：验证环境和规则

交付：

- `Makefile`
- `scripts/dev_env_doctor.py`
- `AGENTS.md`
- `llms.txt`
- scanner rule-file evidence 标记
- API/frontend build 阻塞文档化

验收：

- `make doctor` 可运行。
- `make test-harness` 可运行。
- rule files 能被 archive 识别。

### Sprint 2：Policy v2 和 Agent profiles

交付：

- `harness_policy.py`
- `config/harness_policy.yaml`
- `agent_profiles.py`
- `config/agent_profiles.yaml`
- capability endpoint 改为读取 profile。

验收：

- role/tool/resource policy 单元测试。
- forbidden coding tools 配置拒绝。

### Sprint 3：Timeline/export 和 trace 统一

交付：

- `harness_export.py`
- timeline/export API
- ingestion/query/rag/report events
- 前端 timeline 面板

验收：

- 项目可导出脱敏 JSON。
- 上传、查询、RAG 重建都有 harness events。

### Sprint 4：Artifact retention 和 provider resilience

交付：

- artifact manifest。
- cleanup dry-run。
- provider call guard。
- fake/failing provider tests。

验收：

- doctor 能报告 orphan artifacts。
- provider failure 变成结构化 event/warning。

### Sprint 5：GitHub report-only runner

交付：

- `scripts/github_report_runner.py`
- GitHub Actions workflow。
- Markdown report/comment generator。

验收：

- workflow_dispatch 生成 deterministic report artifact。
- 无 patch、无 push、无部署动作。

## 明确不做

- 不引入 Bash/file edit/apply_patch 工具给 TwinMind Agent。
- 不把 TwinMind 变成 coding agent。
- 不默认调用付费模型或外部网络。
- 不自动清理用户资产。
- 不在没有用户确认时安装依赖。

## 最终成功标准

完成这 10 项后，TwinMind Nexus 应能够回答：

- 当前环境为什么能跑或不能跑？
- 哪条项目规则影响了 Agent 行为？
- 某个 role 为什么能或不能调用某个 tool？
- 某次运行完整 timeline 是什么？
- 哪些 artifact 生成了、是否被引用、是否可安全清理？
- provider 失败时是否用了 fallback，失败证据在哪里？
- 能否在 GitHub PR 中生成只读证据报告，而不修改代码？

这才是 opencode 的工程化精神在 TwinMind 场景里的完整转译：不是更强的执行权限，而是更强的边界、证据、复现和恢复能力。
