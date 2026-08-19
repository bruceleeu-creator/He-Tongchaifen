# AGENTS.md — 项目拆分监督应用（AI 协作护栏）

> 本文件是 AI 协作护栏，非说明书。面向产品的使用与部署说明见 `README.md`；Git 推送拉取见 `GIT_推送拉取指南.md`。
> 本文件已合并原 `docs/README.md`（后端文档）、`CO_项目拆分工作台复制到其他电脑使用手册_20260714.md` 等文档内容。
> 最后更新：2026-08-19（第五轮，文档规整）

## 项目定位

年度财税顾问合同任务拆分监督应用。以合同原文理解为核心：深度读取合同 → 识别摘要 → 动态追问 → 二次拆分 → 报告校验 → 交付成果 → 导出。

## 运行模式

- **rule（默认）**：规则解析，无需 API Key，用正则/关键词从合同提取真实字段
- **llm_enhanced**：规则优先 + LLM 增强（配置 API Key 后自动切换）
- **mock**：仅演示，不用于真实合同

禁止在真实合同模式下使用 Mock 样例数据（"客户A农业公司"等）。

## 启动方式

```bash
# 方式一：一键启动（自动建 venv、装依赖）
chmod +x start.sh && ./start.sh

# 方式二：手动启动
# 后端
cd api && source venv/bin/activate && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# 前端（默认端口 3131，由 vite.config.ts 固定，/api 代理到 8000）
cd app && npm run dev
```

- 前端：http://127.0.0.1:3131（默认；如以 `--port 5173` 启动也可，CORS 已放行 5173/5174）
- 后端：http://127.0.0.1:8000
- API 文档：http://127.0.0.1:8000/docs（ReDoc：/redoc）
- 健康检查：http://127.0.0.1:8000/health（返回 mode, llm_available, llm_model）

## 核心约束（11 条）

1. 真实合同上传时不初始化 Mock 数据（`upload.py` 已修改）
2. 合同签署日期为空时不得虚构日期
3. 只上传合同时不得引用不存在的服务计划
4. 任务依据必须标注合同条款来源
5. 报告导出前必须通过 9 项校验规则（`validators.py`）
6. 前端不写死模型，通过侧边栏 AI 配置面板动态切换 DeepSeek/通义千问/OpenAI（`.ai_config.json` 持久化，无需重启）
7. AI 调用失败时自动回退到规则解析，保证流程不中断
8. 全流程自动化中 `_update_step` 写入步骤状态后，禁止用过期的本地 `state` 变量覆盖保存
9. `_infer_file_type` 当用户显式选择 contract 或 plan 时，尊重用户选择，不强制修正类型，仅返回警告
10. 管线步骤1找不到合同文件时，需检查是否只有 plan 文件并给出明确提示
11. 前端"AI 全流程分析"按钮在未上传合同文件时应直接拦截，不发后端请求

## 技术栈

- 后端：FastAPI + python-docx + httpx（LLM 调用）+ uvicorn，数据存储为纯 JSON 文件（无数据库）
- 前端：React 18 + Ant Design 5 + Vite + Zustand + TypeScript + axios（baseURL `/api`，走 vite proxy）
- LLM：OpenAI-compatible 接口（DeepSeek 默认 / 通义千问 / OpenAI 可切换）
- 主题：顾问账簿（Advisor's Ledger）— 深墨蓝 #1B2332 / 羊皮纸 #F6F3EC / 古金 #B8954A
- 字体：Noto Serif SC（标题）/ Noto Sans SC（正文）/ JetBrains Mono（数据）

## 完整文件清单

### 后端（api/）

| 文件 | 职责 |
|------|------|
| `config.py` | 配置管理，`llm_available` 动态读取环境变量 + `.ai_config.json`；含 18 字段选项/映射常量 |
| `main.py` | FastAPI 入口，注册所有路由，CORS 配置（5173/5174） |
| `requirements.txt` | 依赖清单（fastapi, uvicorn, python-docx, httpx, python-multipart, pydantic, python-dotenv） |
| `services/contract_parser.py` | 合同规则解析器（正则提取核心字段） |
| `services/validators.py` | 报告校验服务（9 条校验规则） |
| `services/llm_client.py` | LLM 客户端（httpx 真实调用，从 `ai_config_store` 动态读取参数） |
| `services/ai_config_store.py` | AI 配置动态存储（JSON 持久化，运行时切换服务商） |
| `services/docx_parser.py` | Word 文档解析（python-docx） |
| `services/csv_export.py` | CSV 导出（18 字段） |
| `services/deliverable_writer.py` | 交付成果文档生成（文件写出、打包） |
| `services/json_store.py` | JSON 文件存储（运行实例数据读写） |
| `services/ai_services/base.py` | 三层模式基类（mock/rule/llm，`llm_available`/`rule_mode` 为动态属性） |
| `services/ai_services/contract_recognition.py` | 合同识别 AI 服务 |
| `services/ai_services/plan_recognition.py` | 计划识别 AI 服务 |
| `services/ai_services/cross_validation.py` | 交叉核验 AI 服务 |
| `services/ai_services/clarification_form.py` | 动态追问 AI 服务 |
| `services/ai_services/task_split.py` | 任务拆分 AI 服务 |
| `services/ai_services/granularity_check.py` | 颗粒度检查 AI 服务 |
| `services/ai_services/pending_list.py` | 待确认清单 AI 服务 |
| `services/ai_services/risk_warning.py` | 风险提示 AI 服务 |
| `services/ai_services/deliverable_design.py` | 交付成果设计 AI 服务 |
| `services/mock_data/` | Mock 模式预设 JSON（task_list/contract_result/plan_result 等） |
| `routers/upload.py` | 上传路由（`_infer_file_type` 尊重用户显式选择，返回 warning） |
| `routers/recognition.py` | 合同识别路由 |
| `routers/clarification.py` | 动态追问路由 |
| `routers/task.py` | 任务 CRUD、颗粒度检查路由 |
| `routers/review.py` | 任务复核路由 |
| `routers/version.py` | 版本管理路由 |
| `routers/export.py` | 导出路由（CSV + Markdown + 完整数据包） |
| `routers/ai_config.py` | AI 配置 API：获取/更新配置、测试连接、预设列表 |
| `routers/pipeline.py` | 全流程自动化：9步编排、进度追踪、暂停/恢复/跳过/重试 |
| `routers/deliverable.py` | 交付成果路由：设计、按任务/整单生成、下载、打包下载、模板管理 |
| `prompts/*.txt` | 8 个提示词模板（contract_recognition / plan_recognition / cross_validation / clarification_form / task_split / granularity_check / pending_list / risk_warning） |
| `models/` | Pydantic 模型（recognition, clarification, task, version） |

### 前端（app/src/）

| 文件 | 职责 |
|------|------|
| `main.tsx` | 应用入口，引入主题 |
| `App.tsx` | 路由配置（6 页） |
| `theme.ts` | 顾问账簿主题配置 |
| `index.css` | 全局样式（CSS 变量 + 侧边栏 AI 功能区） |
| `components/Layout/MainLayout.tsx` | 主布局，集成 AI 配置和全流程分析入口 |
| `components/AISettingsPanel/AISettingsPanel.tsx` | AI 配置侧边栏（预设切换、API Key、连接测试） |
| `components/PipelineProgress/PipelineProgress.tsx` | 全流程进度面板（9步进度、暂停/恢复/跳过/重试） |
| `components/StepNav/StepNav.tsx` | 步骤导航 |
| `components/ModeIndicator/index.tsx` | 模式指示器 |
| `components/FileUpload/FileUploadCard.tsx` | 文件上传卡片 |
| `components/EditableTable/TaskEditableTable.tsx` | 可编辑任务表格 |
| `components/EditableTable/AddTaskModal.tsx` | 添加任务弹窗 |
| `components/EditableTable/TaskDetailDrawer.tsx` | 任务详情抽屉 |
| `components/Deliverables/DeliverablePanel.tsx` | AI 交付成果面板（嵌于任务复核页） |
| `pages/Upload/index.tsx` | 上传页（含 AI 全流程分析按钮、合同检查拦截、类型警告） |
| `pages/Recognition/index.tsx` | 合同识别摘要页 |
| `pages/Clarification/index.tsx` | 动态追问页 |
| `pages/TaskReview/index.tsx` | 任务复核页（任务主表 + 交付成果面板） |
| `pages/VersionHistory/index.tsx` | 版本记录页 |
| `pages/Export/index.tsx` | 导出报告页 |
| `services/api.ts` | axios 实例（baseURL `/api`，由 vite proxy 转发到 8000） |
| `services/*.ts` | 各域 API（upload/recognition/clarification/task/review/version/export/aiConfig/pipeline/deliverable） |
| `stores/projectStore.ts` | 项目状态（Zustand + localStorage，key: psw-project） |
| `stores/stepStore.ts` | 步骤状态 |
| `stores/taskStore.ts` | 任务状态 |
| `types/` | TypeScript 类型定义（含 deliverable.ts） |
| `utils/constants.ts` | 常量（18 字段定义、6 步导航、菜单） |
| `utils/csv.ts` | CSV 工具 |
| `utils/markdown.ts` | Markdown 工具 |
| `utils/messageBridge.tsx` | 消息桥接 |

### 数据与配置（项目根目录）

| 路径 | 说明 |
|------|------|
| `runs/` | 运行数据（按 run_id 分目录，gitignore） |
| `uploads/` | 上传的原始文件（gitignore） |
| `exports/` | 导出文件（gitignore） |
| `parsed/` | 解析缓存（gitignore） |
| `.env` / `.env.example` | 环境变量（RUN_MODE、PARSER_MODE、LLM_*、APP_*） |
| `.ai_config.json` / `.ai_config.example.json` | 本机 AI 配置（gitignore，绝不提交） |
| `start.sh` | 一键启动脚本 |

## API 端点参考

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查（返回 mode, llm_available, llm_model） |
| POST | `/api/upload/docx` | 上传 Word 文档 |
| POST | `/api/recognition/{run_id}` | 合同识别 |
| POST | `/api/clarification/{run_id}` | 生成追问 |
| POST | `/api/clarification/{run_id}/submit` | 提交追问回答 |
| POST | `/api/task/{run_id}/split` | 二次任务拆分 |
| GET | `/api/task/{run_id}` | 获取任务列表 |
| PUT | `/api/task/{run_id}/{task_id}` | 更新任务 |
| POST | `/api/review/{run_id}/validate` | 报告校验 |
| POST | `/api/version/{run_id}/save` | 保存版本 |
| GET | `/api/version/{run_id}` | 版本列表 |
| GET | `/api/export/{run_id}/csv` | 导出 CSV |
| GET | `/api/export/{run_id}/markdown` | 导出 Markdown |
| GET | `/api/export/{run_id}/full` | 完整导出 |
| GET | `/api/ai-config` | 获取 AI 配置 |
| POST | `/api/ai-config/update` | 更新 AI 配置 |
| POST | `/api/ai-config/test` | 测试 LLM 连接 |
| GET | `/api/ai-config/presets` | 预设服务商列表 |
| POST | `/api/pipeline/{run_id}/run` | 启动全流程 |
| GET | `/api/pipeline/{run_id}/status` | 管线状态 |
| POST | `/api/pipeline/{run_id}/pause` | 暂停 |
| POST | `/api/pipeline/{run_id}/resume` | 恢复 |
| POST | `/api/pipeline/{run_id}/skip/{step_key}` | 跳过步骤 |
| POST | `/api/pipeline/{run_id}/retry/{step_key}` | 重试步骤 |
| POST | `/api/pipeline/{run_id}/reset` | 重置管线 |
| GET | `/api/pipeline/steps` | 步骤定义 |
| POST | `/api/deliverables/{run_id}/generate` | 整单生成交付成果 |
| POST | `/api/deliverables/{run_id}/tasks/{task_id}/generate` | 按任务生成交付成果 |
| GET | `/api/deliverables/{run_id}` | 获取交付成果清单 |
| PATCH | `/api/deliverables/{run_id}/artifacts/{artifact_id}` | 更新交付成果条目 |
| GET | `/api/deliverables/{run_id}/download/{artifact_id}` | 下载单个交付成果 |
| GET | `/api/deliverables/{run_id}/download-all` | 打包下载全部交付成果 |
| POST | `/api/deliverables/{run_id}/artifacts/{artifact_id}/save-template` | 保存为模板 |

注：上传/识别/任务/复核/版本等模块在路由内部另有细分子端点（如 `/api/upload/create-run`、`/api/tasks/{run_id}/{task_id}` 删除与 PATCH 复核、`/api/versions/{run_id}/{version_id}/rollback` 回退等），以 `/docs` Swagger 为准。

## 9 步全流程管线

| 步骤 | key | 名称 | 输入 | 输出 |
|------|-----|------|------|------|
| 1 | contract_recognition | 合同识别 | contract_parsed.json | contract_result.json |
| 2 | plan_recognition | 计划识别 | plan_parsed.json | plan_result.json |
| 3 | cross_check | 交叉核验 | contract + plan | cross_check_result.json |
| 4 | clarification | 动态追问 | contract_result | clarification_form.json |
| 5 | task_split | 任务拆分 | contract + answers | task_list.json |
| 6 | granularity_check | 颗粒度检查 | task_list | granularity_result.json |
| 7 | pending_list | 待确认清单 | task_list | pending_list.json |
| 8 | risk_warning | 风险提示 | task_list | risk_list.json |
| 9 | validation | 报告校验 | 全部数据 | validation_result.json |

前端页面导航为 6 步：资料上传 → 识别结果 → 澄清追问 → 任务复核（含交付成果面板）→ 版本记录 → 导出。

## 数据存储结构

所有数据按 `runs/{run_id}/` 目录组织（纯 JSON 文件，无数据库）：

```text
runs/run_20260711_120000_abc12345/
  meta.json                  # 运行实例元数据
  uploads/                   # 上传的原始文件
  contract_parsed.json       # 合同解析结果
  plan_parsed.json           # 计划解析结果
  contract_result.json       # 合同识别结果
  plan_result.json           # 计划识别结果
  cross_check_result.json    # 交叉核验结果
  task_list.json             # 任务主表
  clarification_form.json    # 澄清表单
  granularity_result.json    # 颗粒度检查结果
  pending_list.json          # 待确认清单
  risk_list.json             # 风险提示清单
  versions.json              # 版本历史
```

## 18 字段标准（任务主表）

| # | 字段 | 英文 key | 必填 | # | 字段 | 英文 key | 必填 |
|---|------|----------|------|---|------|----------|------|
| 1 | 客户名称 | customer_name | 是 | 10 | 客户需提供的资料或配合事项 | client_requirements | 否 |
| 2 | 项目名称 | project_name | 是 | 11 | 当前状态 | current_status | 是 |
| 3 | 任务名称 | task_name | 是 | 12 | 延期责任归属 | delay_responsibility | 是 |
| 4 | 服务模块 | service_module | 是 | 13 | 节点目标/达到效果 | milestone_goal | 否 |
| 5 | 任务类型 | task_type | 是 | 14 | 下一步动作及承诺完成时间 | next_action | 是 |
| 6 | 计划开始时间 | plan_start_date | 否 | 15 | 交付成果或完成凭证 | deliverables | 否 |
| 7 | 计划完成时间 | plan_end_date | 否 | 16 | AI定制交付成果说明 | ai_deliverable_desc | 否 |
| 8 | 我方负责人 | our_owner | 是 | 17 | AI提取依据 | ai_extraction_basis | 是 |
| 9 | 客户责任人 | client_contact | 否 | 18 | 人工复核状态 | review_status | 是 |

## LLM 配置（凭据安全红线）

- 配置来源：后端 `.ai_config.json`（gitignore）或 `.env` 的 `LLM_*` 环境变量，两者均含真实 API Key 明文
- **红线：AI/Agent 禁止读取、展示、复制、echo/cat 输出或以任何方式外发上述两个文件的内容**；需要检查配置状态时只允许调用脱敏接口（`GET /api/ai-config`，Key 仅返回前 4 位 + 后 4 位）或前端"测试连接"
- API Key 只能由用户本人通过前端侧边栏 AI 配置面板填写；禁止把真实 Key 写入代码、文档、对话、日志或任何对外渠道；Agent 不得代填、代粘贴真实 Key
- 预设：DeepSeek（默认）/ 通义千问 / OpenAI
- DeepSeek 端点：`https://api.deepseek.com/v1`，模型 `deepseek-chat`
- 通义千问端点：`https://dashscope.aliyuncs.com/compatible-mode/v1`，模型 `qwen-plus`
- OpenAI 端点：`https://api.openai.com/v1`，模型 `gpt-4o`
- API Key 脱敏返回（显示前 4 位 + 后 4 位）
- 配置持久化由后端代码完成（面板 → `.ai_config.json`，无需重启）；Agent 不得手工编辑该文件

## 整改历史（5 轮）

### 第一轮：基础整改（2026-07-12 上午）

- 后端修改 16 个文件：6 个 AI 服务重写 + 4 个路由更新 + 2 个新增服务 + 配置更新
- 前端修改 13 个功能文件 + 8 个视觉文件（主题重构为顾问账簿）
- 修复：Mock 样例污染、费用识别错误、虚构日期、合同依据缺失、执行条款遗漏
- 验证：华圣合同规则模式，36 个任务，9 项校验全部通过

### 第二轮：AI 接口集成（2026-07-12 下午）

- 新增 8 个文件：`ai_config_store.py`、`routers/ai_config.py`、`routers/pipeline.py`、`aiConfig.ts`、`pipeline.ts`、`AISettingsPanel.tsx`、`PipelineProgress.tsx`
- 修复管线状态覆盖 bug：`_update_step` 原子写入后，`_update_pipeline_meta` 仅更新流程级元数据

### 第三轮：DeepSeek LLM 验收（2026-07-12 傍晚）

- 运行实例 run_20260712184150_45102f41：8 步 LLM 增强 100% 成功，1 步跳过，总耗时 75 秒，9 项校验全部通过
- 修复 5 个代码问题：httpx 顶层导入、`llm_available`/`rule_mode` 改动态属性、`Settings.llm_available` 读取 `.ai_config.json`、回退后 mode 标签修正为 `rule`、venv 安装 httpx 0.28.1

### 第四轮：上传解析修复（2026-07-12 晚间）

- 问题：用户上传"年度业财一体化服务计划"选择类型 contract，被 `_infer_file_type()` 强制修正为 plan，导致管线步骤1找不到合同文件
- 修复 3 个文件：`upload.py`（返回 `(file_type, warning)` 尊重用户选择）、`pipeline.py`（只有 plan 时明确提示）、`Upload/index.tsx`（`hasContract` 拦截 + 类型警告）
- 验证：实例 run_20260712185433_fa13f17b 全流程通过

### 第五轮：交付成果模块 + 文档规整（2026-07-14 ~ 2026-08-19）

- 新增交付成果能力：`routers/deliverable.py`、`services/deliverable_writer.py`、`services/ai_services/deliverable_design.py`、前端 `DeliverablePanel.tsx` 与 `services/deliverable.ts`
- 文档规整：仅保留 `AGENTS.md`（AI 协作护栏）+ `README.md`（产品说明）+ `GIT_推送拉取指南.md`（仓库同步），其余文档内容已合并
- 代码仓库迁移至 GitHub：`https://github.com/bruceleeu-creator/He-Tongchaifen.git`

## 关键运行实例

| 运行实例 | 模式 | 任务数 | 校验 | 说明 |
|----------|------|--------|------|------|
| run_20260712175514_39fe7dc5 | rule | 36 | 9/9 通过 | 华圣合同规则模式验收 |
| run_20260712184150_45102f41 | llm_enhanced | 34 | 9/9 通过 | 华圣合同 LLM 增强 100% 成功 |
| run_20260712185433_fa13f17b | llm_enhanced | - | 通过 | 上传修复后验证实例 |
| run_20260712184718_50138d19 | - | - | - | 只有 plan 文件的失败案例（已修复） |

## 9 项报告校验规则

1. 客户名称一致性（合同 vs 任务）
2. 项目名称一致性（合同 vs 任务）
3. 合同金额识别（不为空、不为"未明确"）
4. 日期来源合规（不虚构日期）
5. 任务依据来自合同条款
6. Mock 数据检查（无"客户A农业公司"等样例）
7. 核心模块覆盖（商业模式、股权架构、资产重塑、人效提升、业财合规）
8. 执行条款任务化（验收、响应、季度报告、现场服务）
9. 运行模式标识（真实解析模式 / Mock 演示模式）

## 华圣合同验收基准

- 甲方：昆明华圣科技有限公司；乙方：昆明天靖税务师事务所有限公司
- 项目名称：顶层架构设计与业财陪跑服务
- 服务费用：240000.00 元（含税）；首期款 140000.00 元 / 尾期款 100000.00 元
- 服务期限：自合同生效之日起十二个月；驻场：每季度至少现场服务五个工作日；响应时效：四十八小时内

## 关键设计决策

1. API Key 存储在后端 `.ai_config.json`（非前端 localStorage），兼顾安全与便利
2. 全流程步骤状态用 `_update_step` 原子写入，`_update_pipeline_meta` 仅更新流程级元数据，避免覆盖
3. 动态追问步骤自动提交空回答让流程继续，用户可后续补充
4. `AIServiceBase` 的 `llm_available` 和 `rule_mode` 必须为动态属性，禁止在构造函数中赋值静态快照
5. `Settings.llm_available` 必须同时检查环境变量和 `.ai_config.json`
6. `llm_client.py` 中 `import httpx` 必须在模块顶层，禁止在函数内部导入
7. LLM 失败回退规则解析时，返回的 `mode` 必须为 `rule`，不得标记为 `llm_enhanced`
8. `_infer_file_type` 用户显式选择时尊重用户选择，不强制修正，仅返回 warning
9. 数据全部走 JSON 文件存储（`json_store.py`），不引入数据库；运行数据与代码分离，便于 gitignore 与迁移

## 教训记录

- `runs/`、`uploads/`、`exports/`、`parsed/` 可能包含客户合同、计划书与运行结果（.gitignore 已排除）：**AI/Agent 禁止读取其内容、禁止打包压缩、禁止推送到任何远程仓库**；如确需迁移，由用户本人确认并手工操作
- `.ai_config.json` 与 `.env` 含真实 API Key（.gitignore 已排除）：**禁止读取、展示或提交**；执行任何 `git add` / `git push` 前必须先 `git status` 确认未包含这两个文件，对外发送类操作须逐次征得用户确认
- `--reload` 模式下修改代码后需确认是否真正重载，必要时手动重启
- Python3 系统环境可能与 venv 冲突（PYTHONHOME），运行 Python 时需 `source venv/bin/activate` 或如 `start.sh` 用 `env -u PYTHONHOME -u PYTHONPATH`
- TRAE 内置浏览器中文件上传控件偶发不稳定，需要继续优化兼容性
- 风险文案中"四十八小时内内"存在重复字，需要修正文案拼接
- 使用 koa-connect 包装 Express 中间件会导致 ctx.state 数据丢失（本项目不涉及，但记录）

## 飞书知识库同步（历史产出归档）

- 飞书 Space ID：7658639936228166868；TRAE 产出库 node_token：F1Mbw0UhTi8alikUoNRcRMnvnMb；产出索引 node_token：VUS8wRMQtip1xQkj4AAc9HANnBc
- 历史产出文档（TR_最终使用说明 / TR_前端端到端验收记录 / TR_华圣合同最终验收报告 / TR_DeepSeek_LLM 验收报告等）原存于旧工作区，本仓库不再保留副本，现行说明以 `README.md` 为准
