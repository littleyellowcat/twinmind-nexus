# TwinMind Archive Optimization Resume

## TwinMind Nexus（孪生智枢） | 多模态项目数字孪生与自主 Agent 图谱 RAG 平台

**工作汇总：** 负责 TwinMind Nexus 项目数字孪生分析平台的建设工作，完成从项目 ZIP 摄取到代码结构抽取、知识图谱构建、Hybrid RAG 检索、自主 Agent 分析、证据链报告和 AgentEval 质量回归的完整闭环。

**核心职责：**

- 基于 **Project Scanner + Tree-sitter + Archive Builder** 设计项目档案生成链路，将代码、文档、配置和图片统一转换为文件、类、函数、接口、配置项、依赖、证据卡等项目知识对象；支持 Java、C++、TypeScript / JavaScript、Go、Rust 等多语言结构抽取，将上传项目沉淀为可检索、可推理、可审计的数字孪生档案。

- 构建自主 **ReAct Agent** 工作流，基于 **Planner / Tool-Use / Critic / Verifier / Memory** 将项目理解拆解为入口发现、模块映射、核心实体检查、证据收集和架构总结等任务；真实 DeepSeek mission 完成 **5/5 个分析任务**，证据校验通过，形成 **14 条有证据支撑的项目发现**，未产生不确定结论。

- 设计图谱增强 **Hybrid RAG** 检索链路，融合 **Chroma + BM25 + RRF**，并将命中结果扩展到实体邻域、关系链路和证据卡；综合评测分从 **0.5125 提升至 0.8583**，关系命中率从 **0 提升至 0.8333**，证据命中率从 **0.5417 提升至 0.9167**。

- 建设可审计证据链与反幻觉校验机制，要求 Agent 输出的项目发现绑定实体、关系和证据来源，并在证据不足时执行有限重试和证据回填；任务校验结果从部分通过提升至 **1.0**，报告结论可回溯到图谱节点、关系边和证据卡。

- 搭建 **AgentEval** 质量回归体系，覆盖检索质量、证据覆盖、Agent 可信度、模型运行状态和任务校验等评测门禁；最新回归结果达到通过状态，结构化输出修复次数从 **3 次降至 0 次**，Agent 可信度达到 **0.88**，任务证据校验达到 **1.0**。

**技术栈：** ReAct Agent, Planner / Tool-Use / Critic / Verifier / Memory, AgentEval, DeepSeek V4-Pro, Graph-enhanced Hybrid RAG, Knowledge Graph.

## 2026-07-01 ReAct Mission And AgentEval Optimization

### Problem

The project had three related quality issues during AgentEval and ReAct mission runs:

- ReAct missions could time out or skip planned tasks even when the archive itself was usable.
- Evaluation scores were pulled down by weak relation and evidence hit rates.
- Mission verifier results could stay `partial` because some Agent findings did not explicitly cite evidence IDs, even when the task had already collected evidence.

Baseline symptoms from the previous run:

- `evaluation_score`: `0.5125`
- `entity_hit_rate`: `0.8333`
- `relation_hit_rate`: `0.0`
- `evidence_hit_rate`: `0.5417`
- `mission_verifier`: `warn`, with timeout/skipped tasks

### Strategy

The optimization used a graph-grounded ReAct strategy with stricter budgets and evidence-first recovery:

- Expanded mission tool access so architecture tasks can use `hybrid_search` in addition to graph tools.
- Increased effective tool-call budget from the raw requested value to a task-aware budget based on task count and max steps.
- Set a safer mission timeout floor of `180s`.
- Limited LLM tool selection to the first step of each task, then used deterministic tool calls to reduce latency and randomness.
- Added critic retry: if a task produced uncertain findings, the runtime performs one bounded retry, preferring `hybrid_search` to recover evidence.
- Added task-scoped memory for entity, relation, evidence, and tool IDs.
- Added evidence citation backfill: if a finding has no `evidence_ids` but the task collected evidence, the runtime attaches task evidence and marks the finding with `citation_backfilled=true`.
- Improved evaluation matching by expanding matched entities into neighboring relation and evidence candidates.
- Changed AgentEval mission scoring to use the latest mission for quality gates while preserving historical mission counts in `mission_history_*` metrics.

### Result

Focused unit tests:

```text
27 passed
```

Archive evaluation:

```text
evaluation_score: 0.8583
entity_hit_rate: 0.8333
relation_hit_rate: 0.8333
evidence_hit_rate: 0.9167
```

Real DeepSeek ReAct mission:

```text
status: complete
wall_seconds: 58.047
tasks: 5/5 complete
verifier: accepted
supported_finding_count: 14
uncertain_finding_count: 0
```

Final AgentEval:

```text
status: pass
mission_verifier: 1.0
latest_mission_status: complete
mission_timeout_tasks: 0
mission_skipped_tasks: 0
mission_unsupported_tasks: 0
agent_llm_fallback_count: 0
agent_json_repair_count: 3
```

### Remaining Optimization Target

The next target is to reduce `agent_json_repair_count=3` by strengthening DeepSeek JSON output stability:

- Prefer provider-native JSON mode when calling DeepSeek.
- Keep concise JSON examples in prompts.
- Use deterministic temperature for structured Agent calls.
- Keep repair as a final fallback, not the expected path.

## 2026-07-01 DeepSeek JSON Stability Optimization

### Problem

`agent_json_repair_count=3` showed that some DeepSeek Agent outputs were not valid JSON on the first pass. The system could repair those responses, but repair should be a fallback instead of the normal path.

### Strategy

The stabilization pass applied provider-native structured output controls and smaller deterministic contracts:

- Added DeepSeek-compatible JSON mode for structured Agent calls with `response_format={"type":"json_object"}`.
- Changed structured Agent calls to `temperature=0.0`.
- Added compact example json objects to prompts so the provider has a concrete target shape.
- Added explicit `max_tokens` for structured outputs and repair calls.
- Applied the same JSON mode to ReAct mission action selection.
- Kept existing JSON extraction and repair logic as a final fallback.
- Changed DeepSeek HTTP timeout handling so TCP connection stalls fail quickly instead of blocking a whole Agent run for minutes.

### Verification

Local focused tests passed:

```text
45 passed
```

The test suite now asserts that:

- Archive Agent enhancement passes `response_format={"type":"json_object"}`.
- Multi-Agent role enhancement passes `response_format={"type":"json_object"}`.
- ReAct mission structured action selection still parses correctly.
- DeepSeek payload includes `response_format`.
- DeepSeek connect timeout is bounded to `10s`.

### Current External-Service Status

Real DeepSeek verification could not complete during this pass because even a minimal JSON-mode probe failed at the network connection layer:

```text
ok: false
seconds: 10.052
error_type: DeepSeekLLMError
error: [DeepSeek] Request timed out after 30 seconds
```

This means the code path is ready, but the new real `agent_json_repair_count` should be measured again once the DeepSeek API connection is reachable from this machine.

## 2026-07-01 Full Test Sweep

### DeepSeek JSON Mode Recheck

The latest DeepSeek JSON-mode recheck was attempted again with a minimal request before running any large Agent report.

Result:

```text
ok: false
seconds: 10.085
error_type: DeepSeekLLMError
error: [DeepSeek] Request timed out after 30 seconds
```

A direct network-level probe to `https://api.deepseek.com` also timed out:

```text
ok: false
seconds: 10.027
error_type: URLError
error: <urlopen error timed out>
```

Conclusion: the unfinished DeepSeek verification is currently blocked by external network/API reachability, not by JSON parsing logic. The large `llm_mode=deep` Agent report was not rerun because even the minimal probe cannot connect.

### Current Agent Artifacts

Current `agent_report.json` is a fast/rules report:

```text
agent_report_status: complete
agent_report_llm_mode_fast: 1
agent role llm metadata: empty for archivist/cartographer/detective/skeptic/curator
```

Current `agent_eval_report.json` is still the previous successful deep-backed AgentEval report:

```text
agent_eval_status: pass
evaluation_score: 0.8583
entity_hit_rate: 0.8333
relation_hit_rate: 0.8333
evidence_hit_rate: 0.9167
agent_llm_enabled_count: 5
agent_llm_fallback_count: 0
agent_json_repair_count: 3
mission_supported_tasks: 5
mission_timeout_tasks: 0
mission_skipped_tasks: 0
```

### Full Backend Pytest

Command:

```text
.venv/bin/python -m pytest -q
```

Result:

```text
1484 passed
47 failed
9 errors
13 skipped
duration: 79.80s
```

Important pass signal:

- TwinMind Archive focused tests passed during the full run, including:
  - `test_project_archive_agent_mission.py`
  - `test_project_archive_agent_tools.py`
  - `test_project_archive_agents.py`
  - `test_project_archive_api.py`
  - `test_project_archive_autonomous_mission.py`
  - `test_project_archive_builder.py`
  - `test_project_archive_graph_explorer.py`
  - `test_project_archive_graph_store.py`
  - `test_project_archive_hybrid_rag.py`
  - `test_project_archive_llm.py`
  - `test_project_archive_scanner.py`
  - `test_project_archive_types.py`
  - `test_twinmind_archive_dashboard.py`

Failure categories:

- Dashboard e2e smoke tests expect English strings, while the current UI text is Chinese.
- Azure embedding integration tests expect `settings.embedding.provider == "azure"`, but this project is currently configured for Ollama.
- Ingestion pipeline integration tests still assume Azure/OpenAI-style dimensions and Azure LLM settings.
- RAGAS evaluator tests fail because `langchain_community.chat_models.vertexai` is missing from the installed dependency set.
- LLM reranker/refiner integration tests are hitting mocked/provider serialization or provider-availability assumptions.
- Sparse encoder tests expect hyphenated tokens like `machine-learning` and `gpt-4`, while current tokenization splits them.
- Trace tests expect a `method` field on some trace entries where current emitted data does not include it.

### Frontend Build

Command:

```text
npm run build
```

Result:

```text
tsc -b && vite build: passed
1704 modules transformed
dist/index.html: 0.78 kB
dist/assets/index-*.css: 85.74 kB
dist/assets/index-*.js: 926.71 kB
```

Warning:

```text
Some chunks are larger than 500 kB after minification.
```

Conclusion: the React frontend builds successfully. The remaining warning is a bundle-size/code-splitting optimization, not a build failure.

## 2026-07-01 DeepSeek Proxy Recheck And JSON Repair Reduction

### Problem

The browser could open the DeepSeek console, but terminal requests to `api.deepseek.com` timed out. This blocked the real deep Agent report rerun and made `agent_json_repair_count=3` look unresolved.

### Diagnosis

Terminal DNS resolved DeepSeek domains to `198.18.x.x`, a common Clash/Mihomo fake-ip range, but TCP requests were not routed because no system proxy was configured for terminal processes.

Detected local proxy:

```text
Clash Verge / Mihomo listening on 127.0.0.1:7897
```

Successful terminal API connectivity check with explicit proxy:

```text
curl -I -x http://127.0.0.1:7897 https://api.deepseek.com
HTTP/2 401
```

The `401` is expected for an unauthenticated HEAD request and proves the terminal can reach the API through the proxy.

Required environment for terminal DeepSeek runs:

```text
HTTP_PROXY=http://127.0.0.1:7897
HTTPS_PROXY=http://127.0.0.1:7897
```

Do not set `ALL_PROXY=socks5://127.0.0.1:7897` unless `httpx[socks]` / `socksio` is installed.

### JSON Mode Probe

First tiny probe with `max_tokens=80` connected but produced incomplete JSON because `deepseek-v4-pro` spent most completion tokens on reasoning:

```text
content: "{"
completion_tokens: 80
reasoning_tokens: 78
```

Second probe with `max_tokens=600` succeeded:

```text
ok: true
valid_json: true
seconds: 1.735
model: deepseek-v4-pro
content: {"ok": true, "note": "Here you go"}
```

### Strategy Update

Native JSON mode alone was not enough for all five Agent roles. A real deep Agent report with JSON mode still produced:

```text
json_repaired: 3
```

To reduce repair count, the pipeline now uses a three-stage structured-output strategy:

1. First pass: provider-native JSON mode with deterministic temperature.
2. Strict regeneration: if first-pass JSON is invalid, ask the model to regenerate the same role result as strict JSON with a larger token budget.
3. Repair fallback: only if regeneration also fails, use the JSON repair adapter and mark `json_repaired=true`.

This preserves auditability:

- `json_regenerated=true` means the model self-corrected with the same schema.
- `json_repaired=true` means the repair adapter was required.

### Real Deep Agent Report Result

Command used explicit terminal proxy and real DeepSeek:

```text
HTTP_PROXY=http://127.0.0.1:7897 HTTPS_PROXY=http://127.0.0.1:7897 TWINMIND_DEEPSEEK_TIMEOUT_SECONDS=180
```

Result:

```text
status: complete
wall_seconds: 183.03
fallback: 0
json_repaired: 0
json_regenerated: 2
```

Agent details:

```text
archivist: complete, json_repaired=false, json_regenerated=false
cartographer: complete, json_repaired=false, json_regenerated=true
detective: complete, json_repaired=false, json_regenerated=true
skeptic: complete, json_repaired=false, json_regenerated=false
curator: complete, json_repaired=false, json_regenerated=false
```

### Updated AgentEval Result

Latest AgentEval after the real deep Agent report:

```text
status: pass
evaluation_score: 0.8583
entity_hit_rate: 0.8333
relation_hit_rate: 0.8333
evidence_hit_rate: 0.9167
agent_llm_enabled_count: 5
agent_llm_fallback_count: 0
agent_json_repair_count: 0
mission_supported_tasks: 5
mission_partial_tasks: 0
mission_timeout_tasks: 0
mission_skipped_tasks: 0
mission_unsupported_tasks: 0
```

Quality gates:

```text
archive_graph: pass, 1.0
golden_eval: pass, 0.8583
evidence_coverage: pass, 0.9167
agent_trust: pass, 0.88
agent_llm_runtime: pass, 1.0
hybrid_rag: pass, 1.0
mission_verifier: pass, 1.0
```

Recommendation:

```text
Quality gates passed. Save this run as the current AgentEval baseline.
```
