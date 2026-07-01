# TwinMind Archive 快速开始

TwinMind Archive 是基于 `MODULAR-RAG-MCP-SERVER` 扩展出来的项目知识数字孪生工作台。它把一个代码项目摄取为“档案馆”：扫描代码、文档和配置，抽取实体、关系和证据卡，再用 Agent 查询模式进行架构导览、影响分析、风险审计和证据问答。

## 1. 启动 Dashboard

推荐入口是根目录的一键 Python 启动器：

```bash
python3 /Users/kitten/MultimodalRAG/start_twinmind_archive.py
```

打开：

```text
http://127.0.0.1:5174
```

它会同时启动：

- FastAPI 后端：`http://127.0.0.1:8010`
- React 前端：`http://127.0.0.1:5174`

如果页面无法访问，先运行：

```bash
python3 /Users/kitten/MultimodalRAG/start_twinmind_archive.py health
```

前端右上角可以切换 `中文 / EN`。切换后，主要页面、导航、按钮和状态说明会跟着改变。

## 2. 摄取示例项目

进入 React 前端后，默认会看到一个干净的空状态。你需要先上传 ZIP 生成档案，或从右上角 `项目档案` 下拉框选择已有档案。

如果只是想用内置夹具快速验证后端，可以直接运行单元测试或回归脚本。示例项目路径：

```text
tests/fixtures/project_archive_sample
```

更接近真实使用的测试方式是跑 GitHub ZIP 回归：

```bash
cd "/Users/kitten/MultimodalRAG/TwinMind Archive"
.venv/bin/python scripts/run_github_zip_regression.py --limit 3 --skip-existing
```

报告会写到 `output/github_zip_regression_report.md`。

## 3. 摄取你自己的项目

在 `档案总览` 页面，优先使用上传入口：

- 上传项目 `.zip` 压缩包，最稳定，适合完整项目和大型项目
- TwinMind 会自动忽略 `.git`、`.venv`、`node_modules`、`data`、缓存和构建产物等重目录
- `摄取范围` 默认选择 `架构优先`，适合快速理解源码、配置、入口文件和模块协作
- `项目 ID` 不需要手动填写，系统会自动根据 ZIP 名称生成

然后点击 `生成档案`。生成过程中进度条会显示当前阶段；完成后才会切换到新档案。

摄取范围可以按目的切换：

- `架构优先`：默认，跳过 `tests`、`.claude`、`.github` 等噪声目录，优先看 `src`、`config`、README、入口文件和普通 docs
- `完整审计`：包含所有支持文件，适合全面审查
- `文档优先`：聚焦 README、DEV_SPEC 和 docs
- `测试质量分析`：聚焦 tests 和源码

不建议在浏览器里直接上传大型项目文件夹。浏览器会先枚举并传输每一个文件，如果项目里包含虚拟环境、依赖目录、数据库或缓存，可能出现几千到几万个文件，页面会变慢甚至无响应。大型项目请先压缩成 ZIP 再上传。

生成的数据默认保存在：

```text
data/project_archive/<project-id>/
```

其中包括：

- `draft_archive.json`：档案草稿、实体、关系、证据卡
- `graph.sqlite`：默认 SQLite 图存储
- `graph.kuzu`：使用 Kuzu provider 时生成

上传的项目源码会临时保存到：

```text
data/project_uploads/<project-id>/source/
```

## 4. 当前 MVP 能力

- React 工作台：档案总览、图谱探索、Agent 分析、知识宇宙、任务中心、系统配置
- 多语言基础：中文 / English
- 项目扫描：Python、Markdown、JSON、YAML、TOML、通用文本
- Tree-sitter 结构抽取：Java、C++、TypeScript/JavaScript、Go、Rust
- 项目知识图谱草稿：实体、关系、证据卡、档案展厅
- 大项目图谱工作台：搜索驱动、邻域展开、聚类/层级视图、实体详情、证据链、路径保存
- Hybrid RAG：Chroma + BM25 + RRF，检索结果会进入 Agent 证据上下文
- 多模态：项目图片会生成图片证据卡，并可通过 Ollama vision 接口增强说明
- Agent 查询模式：架构导览、影响分析、风险审计、证据问答、ReAct 任务轨迹
- DeepSeek Agent 增强：在 `config/settings.yaml` 配置 DeepSeek 后，规则 Agent 会自动升级为 DeepSeek 增强报告；未配置或调用失败时回退到规则 Agent
- 项目智能报告：Markdown/PDF 导出
- Evaluation and Benchmarking：黄金问题、命中率、证据覆盖、压力测试
- MCP 工具：`ingest_project_archive`、`query_project_twin`
- 图存储：SQLite 默认，Kuzu / Neo4j 可选

### DeepSeek Agent 配置

配置文件位置：

```text
config/settings.yaml
```

将 `llm` 段改成或确认如下：

```yaml
llm:
  provider: "deepseek"
  model: "deepseek-v4-flash"
  base_url: "https://api.deepseek.com"
  api_key: "你的 DeepSeek API Key"
  temperature: 0.2
  max_tokens: 1200
```

也可以用环境变量临时覆盖配置文件中的 key 或模型：

```bash
export DEEPSEEK_API_KEY="你的 DeepSeek API Key"
export TWINMIND_DEEPSEEK_MODEL="deepseek-v4-flash"
export TWINMIND_DEEPSEEK_TEMPERATURE="0.2"
export TWINMIND_DEEPSEEK_MAX_TOKENS="1200"
```

如果希望临时禁用模型增强：

```bash
export TWINMIND_AGENT_LLM_ENABLED="false"
```

然后重启 FastAPI 后端。前端右上角 `Agent` 状态会显示当前模型；如果模型增强生效，会显示 `deepseek · <model>`；否则显示 `规则 Agent`。

## 6. Ollama Vision / Embedding 配置

本项目可以使用 Ollama 本地模型做图片理解和 embedding。常见搭配：

- 图片理解：`llava` 或 `llama3.2-vision`
- Embedding：`nomic-embed-text`

先确认 Ollama 已启动并拉取模型：

```bash
ollama pull nomic-embed-text
ollama pull llava
```

然后检查 `config/settings.yaml` 中的 `embedding` 和 `vision_llm` 配置。前端 `系统配置` 页面会显示 embedding、vision、Hybrid RAG、Agent、图存储等组件是否可用。

## 7. 回归测试和质量判断

当你上传某些大项目后，如果发现只有一个展厅有内容，或者图谱很稀疏，优先不要凭感觉判断。运行：

```bash
cd "/Users/kitten/MultimodalRAG/TwinMind Archive"
.venv/bin/python scripts/run_github_zip_regression.py --limit 3 --skip-existing
```

重点看报告里的：

- `Sparse Halls`：是否有空展厅或弱展厅
- `Hybrid Chunks`：Hybrid RAG 是否真的建索引
- `Images / Vision`：是否有图片，图片理解是否运行
- `Quality / Health`：图谱质量和摄取健康度
- `Recommendations`：下一步该调扫描、结构抽取、关系规则还是模型配置

四条收口优化记录在：

```text
docs/twinmind_archive_finalization_plan.md
```
