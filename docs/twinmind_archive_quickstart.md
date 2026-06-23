# TwinMind Archive 快速开始

TwinMind Archive 是基于 `MODULAR-RAG-MCP-SERVER` 扩展出来的项目知识数字孪生工作台。它把一个代码项目摄取为“档案馆”：扫描代码、文档和配置，抽取实体、关系和证据卡，再用 Agent 查询模式进行架构导览、影响分析、风险审计和证据问答。

## 1. 启动 Dashboard

```bash
cd "/Users/kitten/MultimodalRAG/TwinMind Archive"
source .venv/bin/activate
streamlit run src/observability/dashboard/app.py
```

打开：

```text
http://127.0.0.1:8501
```

左侧可以切换 `中文 / English`。切换后，导航和主要页面会跟着改变。

## 2. 摄取示例项目

进入左侧 `TwinMind 档案馆` 页面。

在 `示例项目摄取流程` 中：

1. 点击 `使用示例项目`
2. 点击 `构建档案`
3. 在 `项目档案` 下拉框选择生成的 `sample-project`
4. 尝试 `架构导览`、`风险审计`、`证据问答`

示例项目路径：

```text
tests/fixtures/project_archive_sample
```

## 3. 摄取你自己的项目

在 `TwinMind 档案馆` 页面填写：

- `项目路径`：你的本地项目目录，例如 `/Users/kitten/YourProject`
- `项目 ID`：一个稳定名称，例如 `my-service`

然后点击 `构建档案`。

生成的数据默认保存在：

```text
data/project_archive/<project-id>/
```

其中包括：

- `draft_archive.json`：档案草稿、实体、关系、证据卡
- `graph.sqlite`：默认 SQLite 图存储
- `graph.kuzu`：使用 Kuzu provider 时生成

## 4. 当前 MVP 能力

- 多语言 Dashboard 基础：中文 / English
- 项目扫描：Python、Markdown、JSON、YAML、TOML、通用文本
- 项目知识图谱草稿：实体、关系、证据卡、档案展厅
- Agent 查询模式：架构导览、影响分析、风险审计、证据问答
- MCP 工具：`ingest_project_archive`、`query_project_twin`
- 图存储：SQLite 默认，Kuzu 可选

## 5. 下一步建议

建议按这个顺序继续增强：

1. 补齐全页面 i18n，包括追踪页和评估页
2. 把项目摄取结果接入 Hybrid Search，实现向量 + BM25 + 图谱多跳融合
3. 增强 Java / C++ / TypeScript 等语言适配器
4. 加入可视化星图关系图
5. 升级为更强的多 Agent 自主分析流程
