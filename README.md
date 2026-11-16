# AI 邮件分流与人工审核系统

> 真实 IMAP 邮件进入 n8n 后，由 FastAPI 完成登记、去重、风险规则检查、AI 辅助分流和人工审核状态管理。
>
> **项目定位**：可演示的 Portfolio Demo。AI 分类默认使用离线 Mock Provider，不会自动调用外部 API；可选择启用的 DeepSeek Provider 已接入，并完成有限次合成数据真实端到端联调。已提供最小同源审核页 `/ui` 和 Streamlit 待审核收件箱 `frontend_app.py`；Streamlit 支持 English / 中文界面切换、待审核列表、详情查看、可编辑草稿和 approve / reject / takeover。它仍不是完整生产级前端，也尚未实现任务分页和生产级鉴权，不宣称生产级稳定性。

`FastAPI` · `PostgreSQL` · `SQLAlchemy` · `Alembic` · `n8n` · `Mock AI` · `DeepSeek（可选）`

> **文档口径**：本文区分已确认事实、当前未实现功能和后续规划。事实部分来自项目阶段报告及用户提供的真实联调记录。DeepSeek Provider 已使用真实 DeepSeek 完成有限次合成数据联调（普通咨询、英文报价咨询），验证了 `received` → `awaiting_review`；未进行更大样本、压力或生产环境验证，本文不宣称生产级稳定性或生产级多语言质量。

## 项目价值

- 自动接收并登记邮件，减少人工搬运邮件信息。
- 以 `mailbox_id + message_id` 去重，避免同一来源邮件重复创建任务。
- 高风险内容优先转人工，避免自动生成不当回复。
- 普通内容在生成有效草稿后进入待审核状态，人工确认后才进入下一阶段。
- 用明确的任务状态为后续审核、发送和可靠性处理提供基础。

当前系统不包含自动发送、生产级鉴权或完整商业产品能力。

## 当前架构

```mermaid
flowchart TD
    A["真实 163 测试邮箱<br/>（合成邮件）"] --> B["n8n Schedule Trigger"]
    B --> C["IMAP 节点"]
    C --> D["Code 节点<br/>清洗与字段映射"]
    D --> E["FastAPI<br/>邮件登记"]
    E --> F{"Switch 状态路由<br/>duplicate / status"}
    F -->|"received"| G["Process 任务"]
    F -->|"已有任务 / 其他状态"| H["GET 任务详情"]
    G --> I{"风险规则"}
    I -->|"命中"| J["human_takeover"]
    I -->|"未命中"| K["AI Provider 分类<br/>默认 Mock，可选 DeepSeek"]
    K --> L{"结果与草稿"}
    L -->|"普通且草稿有效"| M["awaiting_review"]
    L -->|"高风险 / 无有效草稿"| J
    E --- P[("PostgreSQL<br/>任务状态与去重约束")]
    G --- P
    H --- P
```

当前真实链路的节点顺序：

```text
真实 163 测试邮箱
  → n8n Schedule Trigger
  → IMAP 节点
  → Code 节点（清洗与字段映射）
  → FastAPI POST /api/v1/emails
  → Switch 状态路由（duplicate / status）
  → Process 任务或 GET 已有任务详情
  → awaiting_review / human_takeover
```

- n8n 负责定时触发、IMAP 读取和流程编排。
- FastAPI 负责邮件登记、去重、风险规则、状态机与数据库写入。
- PostgreSQL 负责任务状态持久化和 `mailbox_id + message_id` 唯一约束。
- AI Provider 默认使用离线 Mock，不访问网络；显式配置后可切换到 DeepSeek，邮件内容会发送给第三方模型。
- 上述真实链路是 n8n UI 中实际配置的工作流，不是仓库内早期测试 Webhook JSON。

### 技术栈现状

| 组件 | 作用 | 当前状态 |
| --- | --- | --- |
| FastAPI | HTTP API 与业务流程入口 | 已实现 |
| PostgreSQL | 任务状态与去重约束 | 已接入 |
| SQLAlchemy 2.x + Alembic | ORM 与数据库迁移 | 已实现 |
| n8n | 定时触发、IMAP 读取、流程编排 | 已接入真实 163 测试邮箱 |
| Mock AI Provider | 离线、确定性的分类与草稿 | 默认 Provider；离线回归 |
| DeepSeek Chat Completions | 可选在线分类与草稿 | 已接入，默认不启用；已完成有限次合成数据真实联调 |
| 同源 HTML 审核页 | 单任务人工审核 | 已实现最小版本（`/ui`） |
| Streamlit 待审核收件箱 | 双语列表、详情、草稿编辑与审核 | 已实现（`frontend_app.py`；English / 中文切换、基础视觉优化；需安装 streamlit） |

## 核心流程

### 邮件登记

`POST /api/v1/emails` 接收 `mailbox_id`、`message_id`、`subject`、`body` 四个字段。其中 `mailbox_id` 与 `message_id` 必填，`subject`、`body` 可缺省为空字符串。首次登记创建任务，状态为 `received`；该接口不会调用 AI，也不会发送邮件。

### 去重

`mailbox_id + message_id` 在数据库层有唯一约束。重复登记返回已有任务和 `duplicate=true`，不会新增记录；并发插入由数据库唯一约束兜底，冲突时回滚并复用已提交记录。

### Process 与状态流转

`POST /api/v1/emails/{task_id}/process` 只处理 `received` 状态的任务：先原子认领为 `processing`，再执行风险规则；规则未命中时才调用配置的 AI Provider，最后把结果写回数据库。

- 风险规则命中：直接进入 `human_takeover`，不调用 AI Provider。
- 普通分类且存在非空草稿：进入 `awaiting_review`。
- 高风险分类或没有可审核草稿：进入 `human_takeover`。
- Provider 调用或输出校验失败：任务标记为 `failed`。
- 对 `awaiting_review` 的重复 process 返回已有结果（200）；`processing` 或终态返回 409。

### 已有任务与重复邮件

工作流根据登记响应中的 `duplicate` 和 `status` 路由。已有任务通过 `GET /api/v1/emails/{task_id}` 查询详情，不重复创建任务，也不重复执行 process。真实联调中，历史邮件走的就是该分支。

### 风险规则

规则服务基于主题和正文中的关键词判断，优先级为：法律/投诉/赔偿 > 退款/拒付 > 订单修改 > 付款/账户权限修改。正文为空或仅空白也会直接要求人工处理。

规则命中即进入 `human_takeover`，不调用 AI Provider。规则未命中不代表邮件安全，生成的草稿仍然必须人工审核。精确关键词规则可能漏判同义词、拼写错误或其他语言，也可能误判。

### 人工审核

`POST /api/v1/emails/{task_id}/review` 支持 `approve`、`reject`、`takeover` 三种动作，只接受 `awaiting_review` 状态的任务。

- `approve` 要求草稿存在且去除空白后非空。
- `reject` 和 `takeover` 允许处理异常记录。
- `reviewed_by` 是客户端自报的演示值，不代表真实身份。
- 已提供同源最小页面 `GET /ui`，以及 Streamlit 待审核收件箱 `frontend_app.py`：收件箱通过 `GET /api/v1/emails` 获取待审核列表，点击选择后加载详情并审核；界面支持 English / 中文切换和基础视觉优化。
- Streamlit 右侧草稿使用可编辑文本区域；审核请求可携带编辑后的 `draft_body`，随 approve / reject / takeover 保存。未携带时保持原草稿。

### 状态语义

```text
received → processing → awaiting_review → approved / rejected / human_takeover
                     ↘ human_takeover / failed
```

终态为 `approved`、`rejected`、`human_takeover`、`failed`。

**`approved` 仅表示人工审核通过，不表示邮件已发送。** 系统当前没有 `sent` / `sending` 状态，也没有真实发送能力。

## 真实 IMAP 接入

当前使用专用 163 测试邮箱和合成邮件进行演示，不接入真实客户邮箱。

- 工作流在 n8n UI 中配置，由 Schedule Trigger 定时触发读取。
- 读取节点是 n8n 社区 IMAP 节点，不是原先的测试 Webhook。
- IMAP 节点读取邮件后，由 Code 节点清洗并映射为 FastAPI 需要的四个字段：`mailbox_id`、`message_id`、`subject`、`body`。
- 历史邮件在登记时返回 `duplicate=true`，工作流进入已有任务查询分支，不重复处理。
- 联调中 163 邮箱曾返回 `SELECT Unsafe Login`。最终通过兼容的 IMAP 节点与配置完成了真实邮件拉取；这是客户端兼容性处理，不是对网易安全机制的绕过，本文不推测其底层实现细节。
- IMAP 授权码不保存在仓库、README 或工作流 JSON 中；请只在实际 n8n 实例的安全凭据配置中使用，不要写入文档或提交历史。
- 仓库中的 `n8n/workflows/06_test_webhook_triage.json` 是早期测试 Webhook 草稿，不是当前真实 IMAP 工作流。当前真实工作流在 n8n UI 中配置，仓库未包含经过验证的 IMAP 工作流导出文件。

本次联调中，n8n 曾成功读取 7 封测试邮件，其中包括历史邮件和新邮件。这些结果说明当前真实邮箱到 FastAPI 的演示链路已经跑通，但不代表压力测试、长期稳定性或生产可靠性。本文不固定该社区节点的包名、版本或底层库实现，具体以当前 n8n 实例为准。

## API 摘要

| 方法与路径 | 用途 | 关键行为 |
| --- | --- | --- |
| `GET /api/v1/emails` | 任务列表 | 返回 id、状态、摘要、风险等级，按更新时间倒序；前端过滤 `awaiting_review` |
| `POST /api/v1/emails` | 登记邮件 | 首次创建返回 `201`，状态 `received`；重复登记返回 `200`、`duplicate=true` 和已有任务 |
| `GET /api/v1/emails/{task_id}` | 查询任务详情 | 只读，返回正文、分类、风险、草稿和审核字段；任务不存在返回 `404` |
| `POST /api/v1/emails/{task_id}/process` | 执行规则与 AI Provider 分流 | 仅处理 `received`；结果为 `awaiting_review` 或 `human_takeover`；Provider 失败标记 `failed` |
| `POST /api/v1/emails/{task_id}/review` | 人工审核 | 支持 `approve` / `reject` / `takeover`；仅接受 `awaiting_review`；`approve` 要求非空草稿；可选 `draft_body` 保存编辑后的草稿 |

补充说明：

- `process` 对 `processing` 或终态任务返回 409；Provider 失败返回 502 且任务为 `failed`；数据库异常返回 503，任务状态可能不确定。
- `review` 在 `approve` 没有可用草稿时返回 409。
- 所有接口当前都没有生产级鉴权。

重要状态：

| 状态 | 含义 |
| --- | --- |
| `received` | 已登记，等待处理 |
| `processing` | 正在处理 |
| `awaiting_review` | 已生成可审核草稿，等待人工审核 |
| `approved` | 审核通过；不代表已发送 |
| `rejected` | 审核拒绝 |
| `human_takeover` | 需要人工接管 |
| `failed` | 处理失败 |

当前已有最小任务列表接口 `GET /api/v1/emails` 和 Streamlit 收件箱 `frontend_app.py`；尚无发件人字段、分页和完整前端。

`GET /health` 只返回进程状态，不检查数据库连通性。FastAPI 启动后可通过 `/docs` 查看 OpenAPI 文档。

## 验证结果

| 场景 | 观察结果 |
| --- | --- |
| 普通新邮件 | 进入 Process 分支，最终为 `awaiting_review` |
| 退款新邮件 | 命中退款规则，进入 `human_takeover`，不调用 AI Provider |
| 历史/重复邮件 | 登记返回 `duplicate=true`，进入已有任务查询分支 |
| 真实邮箱读取 | n8n 成功读取 7 封测试邮件，包含历史邮件和新邮件 |

### DeepSeek 能力验证

已完成有限次合成数据的真实 DeepSeek 端到端联调，验证结果如下：

- DeepSeek Provider 已接入，可通过配置启用。
- 普通咨询任务可从 `received` 进入 `awaiting_review`。
- 能生成并持久化 `category`、`risk_level`、`summary`、`risk_reason` 和 `draft_body`。
- 已使用一条英文合成报价询价验证真实 DeepSeek：`summary`、`risk_reason` 和 `draft_body` 均为英文，任务进入 `awaiting_review`。
- 报价咨询示例中，草稿直接回应报价诉求，并要求客户补充产品版本、采购数量、使用规模和部署方式；未给出具体价格、库存、折扣、交付时间或已安排人员。
- `requires_human` 由应用强制为 `true`，所有结果仍需人工审核。
- `approved` 仅表示人工审核通过，不代表邮件已发送。

> 英文报价验证仅来自有限次合成数据，不代表生产级多语言质量或稳定性。

当前仍没有真实邮件发送；已有最小任务列表接口、`/ui` 单页和 Streamlit 收件箱 `frontend_app.py`。生产级鉴权、自动重试和 `processing` 超时回收仍未实现。以上结果来自有限次合成数据联调，不宣称生产级稳定性。

> **说明**：上述 IMAP 与 DeepSeek 结果均为有限次合成数据联调演示，不等同于压力测试或生产稳定性证明。

### 隔离测试记录

在独立 PostgreSQL 容器、`AI_PROVIDER=mock` 和仅供本次测试使用的 internal Docker 网络中运行完整 pytest：

- **257 passed**
- **1 warning**（Starlette/httpx 弃用提示）
- **0 failed**
- **0 skipped**

测试使用临时测试副本和独立 `ai_support_test` 数据库，未使用现有 `ai_support`、现有 `ai_support_test` 或 Docker Demo 的 `ai_support_demo`。测试容器没有挂载宿主机 `.env`，没有传入 DeepSeek Key；公网访问被 internal 网络阻断。本轮没有真实调用 DeepSeek、n8n、邮箱，也没有执行浏览器审核提交。

这组结果只证明本次隔离测试运行通过，不代表生产稳定性、跨机器冷启动、多副本迁移或完整浏览器 E2E 证明。此前有限次真实 DeepSeek/IMAP 联调事实仍保留，不被本次结果替代。

## 当前状态

已完成：

- [x] FastAPI + PostgreSQL 后端
- [x] 邮件登记与 `mailbox_id + message_id` 去重
- [x] 风险规则
- [x] Mock AI 分类与草稿
- [x] DeepSeek Provider 接入
- [x] 使用真实 DeepSeek 完成有限次合成数据端到端联调（普通咨询、报价咨询）
- [x] AI Provider 配置选择（默认 Mock，可选 DeepSeek）
- [x] process API 与任务详情查询
- [x] 最小同源人工审核页面（`/ui`）
- [x] Streamlit 待审核收件箱（`frontend_app.py`）
- [x] Streamlit English / 中文界面切换、待审核列表、详情查看和草稿编辑
- [x] Streamlit 基础视觉优化（浅灰背景、卡片列表、审核按钮配色）
- [x] 人工审核状态机（approve / reject / takeover）
- [x] n8n 真实 163 IMAP 接入
- [x] 真实邮箱到 FastAPI 的分流联调（7 封测试邮件演示）
- [x] Alembic 迁移，以及阶段报告记录的 PostgreSQL 并发相关测试
- [x] 隔离 Docker 本地可复现 Demo（PostgreSQL + FastAPI + Streamlit，默认 Mock，已本地验证）
- [x] 隔离完整 pytest（独立 PostgreSQL + Mock Provider + internal 网络；257 passed, 1 warning, 0 failed, 0 skipped）

关键实现位于 `app/api/routes/emails.py`、`app/services/triage.py`、`app/services/rules.py`、`app/services/review.py`、`app/providers/ai/mock_provider.py`、`app/providers/ai/deepseek_provider.py` 和 `app/config.py`。

## 后续规划

以下为后续规划；V2 已接入 DeepSeek 并完成有限次合成数据真实联调，仍需更大样本验证；V3 已有最小版本但需继续增强，V4 尚未实现。

### V2：真实 AI Provider（DeepSeek 已接入，已完成有限次受控联调）

- 已实现 DeepSeek Provider、配置选择、超时/错误映射和 JSON 输出校验。
- 保留 Mock Provider 作为默认 Provider 和离线回归基线。
- 已完成：使用受控测试 Key 完成有限次合成数据真实联调（普通咨询、报价咨询），验证了 `received` → `awaiting_review` 和关键字段生成。
- 仍需：扩大样本，系统评估输出质量、延迟、成本和错误表现；不宣称生产级稳定性。
- 不把真实 API Key 写入仓库。

### V3：审核前端增强

- 在现有 `/ui` 和 `frontend_app.py` 基础上继续完善。
- 增加分页、状态/风险/关键词筛选。
- 增加发件人字段和更完整的详情交互。
- 增加审核人鉴权、审核历史记录和更完整的审核工作流。
- 现有 `GET /api/v1/emails` 列表接口和审核时草稿保存字段已经实现，不再列为待补齐项。

### V4：发送与可靠性

- 实现人工批准后的发送。
- 定义发送状态和幂等边界。
- 增加 Error Trigger。
- 实现受控重试和告警。
- 不把 `approved` 直接描述为 `sent`。

## 当前限制

- 默认 AI Provider 仍为 Mock；DeepSeek Provider 已接入但默认不启用；已完成有限次合成数据真实联调，样本不足以证明稳定性。
- 启用 DeepSeek 时，邮件主题和正文会发送给第三方模型；只应使用合成或脱敏测试数据。
- DeepSeek 仅在有限次合成数据联调中观察了输出质量；延迟、成本和更大样本的稳定性尚未系统验证。
- 已有最小 `/ui` 和 Streamlit 双语收件箱（列表、详情、草稿编辑、基础视觉优化）；尚未实现分页、完整前端和草稿历史记录。
- 尚未实现真实邮件发送。
- 当前不连接 Slack。
- 无生产级鉴权。
- 无自动重试。
- `processing` 超时回收尚未实现。
- 不承诺 exactly-once。
- 风险规则基于关键词，可能误判或漏判。
- 已有最小任务列表 API 和审核时草稿修改保存字段；尚无发件人字段、分页和历史记录。
- 真实邮箱验证使用专用测试邮箱和合成邮件，结果不等于生产稳定性证明。

## 安全说明

- 不要提交 IMAP 授权码、DeepSeek API Key 或 `.env`。
- 真实邮箱只使用专用测试账号，不要接入真实客户邮箱做公开演示。
- 邮件正文和 AI 草稿属于敏感数据；当前 `GET` 详情会返回正文和草稿，且没有生产级鉴权。
- 启用 DeepSeek 时，邮件主题、正文和生成请求会发送给第三方模型；仅使用合成或脱敏测试数据，不要发送真实客户隐私。
- 当前 API 与 `/ui`、`frontend_app.py` 均无生产级鉴权；前端仍为最小实现。
- 本项目当前定位为可演示的 Portfolio Demo，不应直接用于生产环境。

## 运行与配置

当前仓库包含 FastAPI 应用、Alembic 迁移、PostgreSQL + n8n 的现有 Docker Compose 配置，以及 n8n 早期测试工作流草稿。真实 n8n 链路仍依赖 n8n UI 中的 IMAP 凭据和 FastAPI 访问地址配置；本阶段只验证了隔离 Docker Demo（见文末 English Quick Start），没有重新验证真实 IMAP 或完整生产启动流程。

| 配置项 | 作用 | 当前说明 |
| --- | --- | --- |
| `DATABASE_URL` | FastAPI 与 Alembic 的 PostgreSQL 连接 | 使用 psycopg 3 DSN；`.env.example` 只包含本地演示默认值 |
| n8n IMAP 凭据 | 读取 163 测试邮箱 | 在 n8n 实例的凭据配置中设置，不进入仓库 |
| n8n 中的 FastAPI Base URL | 让 n8n 调用登记、process 和 GET 接口 | 应配置在 n8n 工作流或环境变量中，不要从 Webhook 输入接收 |
| `AI_PROVIDER` | 选择 AI Provider | 默认 `mock`（离线）；可选 `deepseek` |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | 仅 `AI_PROVIDER=deepseek` 时需要；只从环境或本地私密配置读取，不进入仓库 |
| `DEEPSEEK_BASE_URL` | DeepSeek API Base URL | 默认 `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | DeepSeek 模型名 | 默认 `deepseek-flash`，可按官方文档覆盖 |
| `DEEPSEEK_TIMEOUT_SECONDS` | 请求超时（秒） | 默认 `30`；必须是正数，上限 120 |

默认 `AI_PROVIDER=mock`，安装项目不会自动调用外部 API。显式启用 `deepseek` 并提供 Key 后，邮件主题和正文会发送给第三方模型；仍需人工审核。DeepSeek Provider 已完成有限次合成数据真实联调，但默认仍不启用；本次联调不代表生产级稳定性。

其他说明：

- Python 要求为 3.10 及以上；PostgreSQL 使用 Docker Compose 中的 16 版本。
- `docker-compose.yml` 仍只包含 PostgreSQL 与 n8n；新增的 `docker-compose.demo.yml` 提供已本地验证的隔离 Demo（PostgreSQL + FastAPI + Streamlit，默认 Mock），但它不是生产部署。原有 FastAPI 与 `frontend_app.py` 单独运行方式仍可使用。
- n8n 版本未在仓库中固定，具体节点行为以当前 n8n 实例为准。
- `.env` 已被 `.gitignore` 忽略；不要提交任何真实凭据。
- `get_ai_provider()` 根据 `AI_PROVIDER` 选择 Provider；默认 Mock，只有显式配置 DeepSeek 并设置 Key 才会发起外部请求。
- Streamlit 待审核收件箱需先安装 `streamlit`，运行 `API_BASE_URL=http://127.0.0.1:<FastAPI端口> streamlit run frontend_app.py`；代码默认连接本地 `http://127.0.0.1:8014`。
- 后续扩大真实 DeepSeek 联调前仍需确认 Key、Base URL、模型名、网络访问和费用边界；不要使用真实客户数据。
- FastAPI 的 `/health` 仅用于确认进程可访问，不验证数据库；接口文档可在 `/docs` 查看。

## Docker Demo Quick Start (English)

This repository includes an isolated local Docker demo for the email triage workflow. It runs PostgreSQL, FastAPI, and Streamlit in a dedicated Compose project named `ai-support-demo`. It is a local Portfolio Demo, not a production deployment.

### What it is

- PostgreSQL 16, FastAPI, and Streamlit;
- default `AI_PROVIDER=mock`, with no external AI calls;
- synthetic emails only;
- no real IMAP import, no DeepSeek key, no n8n, and no email sending;
- no production authentication;
- `approved` only means human approval; it does not mean an email has been sent;
- `/health` checks the API process only, not database readiness;
- dependency versions are not locked, so build results may change over time;
- the API runs `alembic upgrade head` on startup as a single-instance demo simplification.

### Files

- `docker-compose.demo.yml`
- `Dockerfile.api`
- `Dockerfile.ui`
- `.dockerignore`

### Build and start

The demo database and volume are isolated from `ai-support-workflow` and from the existing n8n services.

```bash
# Build images. The optional PIP_INDEX_URL is useful when the default PyPI
# index is slow or unreachable; omit it if your network can reach PyPI.
docker compose -p ai-support-demo -f docker-compose.demo.yml build \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# Start the demo. The database is not published to the host.
docker compose -p ai-support-demo -f docker-compose.demo.yml up -d --no-build

# Check container health.
docker compose -p ai-support-demo -f docker-compose.demo.yml ps
```

If Docker Hub cannot provide `python:3.12-slim`, pull the same `3.12-slim` image from a reachable registry, tag it as `python:3.12-slim`, and rebuild. The first build also needs access to a Python package index.

### Access

- API: http://127.0.0.1:8020
- API docs: http://127.0.0.1:8020/docs
- API health: http://127.0.0.1:8020/health
- Streamlit: http://127.0.0.1:8503
- PostgreSQL: internal only (`demo-db:5432`), no host port

### Create a synthetic task

```bash
CREATE_RESPONSE=$(curl -sS -X POST http://127.0.0.1:8020/api/v1/emails \
  -H 'Content-Type: application/json' \
  -d '{"mailbox_id":"demo@example.com","message_id":"<quickstart-001@example.com>","subject":"Product feature question","body":"This is a synthetic demo message. What features are available?"}')

TASK_ID=$(printf '%s' "$CREATE_RESPONSE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "task_id=$TASK_ID"

curl -sS -X POST "http://127.0.0.1:8020/api/v1/emails/$TASK_ID/process"
```

The process request should return `status: "awaiting_review"` for this synthetic question. Open the Streamlit page and select the task in **Pending Review**. The verification flow does not submit a review action, send email, import real IMAP mail, or call DeepSeek/n8n.

### Stop

```bash
docker compose -p ai-support-demo -f docker-compose.demo.yml down
```

This keeps the demo volume (`ai-support-demo_demo_pgdata`). Do not use `down -v` unless you explicitly want to delete the demo database. Do not run this command against the existing `ai-support-workflow` project.

### Troubleshooting

- If `8020` or `8503` is already in use, change the host side of the port mapping in `docker-compose.demo.yml`; do not stop the existing service.
- If the API container exits, inspect `docker compose -p ai-support-demo -f docker-compose.demo.yml logs demo-api`; migration failures stop the API by design.
- If Streamlit cannot load tasks, verify `API_BASE_URL=http://demo-api:8000` and that `demo-api` is healthy.
- The demo explicitly uses `AI_PROVIDER=mock`; it does not read the host `.env` and does not receive `DEEPSEEK_API_KEY`.
