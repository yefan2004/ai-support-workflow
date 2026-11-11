# AI 客服邮件分流与人工审核（Demo）

> ## ⚠️ 演示项目声明
>
> **本项目仅用于学习与技术演示，不可直接用于生产环境。**
>
> - 不包含真实 AI 模型调用（仅使用离线、确定性的 Mock Provider）
> - 不接入真实邮箱（Gmail / Outlook）与 Slack
> - 不包含任何真实密钥，所有默认账号口令仅用于本地演示
> - 未实现鉴权、审计、限流、数据加密与合规能力
> - 当前已实现邮件任务登记、数据库去重、分流/审核字段与状态定义、风险规则与 Mock AI 分类、process/GET/review API；其余流程尚未实现

基于 **FastAPI + PostgreSQL + n8n** 的 AI 辅助客服邮件分流与人工审核流程骨架。业务流程参考 `架构图/` 下的四张流程图：

1. 邮件接入与去重（已实现登记与去重，未接入真实邮箱）
2. 规则检查与 Mock AI 分流（已实现规则、Mock 与 process API；未接入真实 AI）
3. 人工审核与回复发送（已实现 review API；未实现发送）
4. 异常处理与人工提醒（未实现）

## 当前阶段范围

### 阶段 1（已完成）：项目骨架

- [x] 目录结构、FastAPI 应用入口、`GET /health`
- [x] PostgreSQL 的 Docker Compose 配置、`.env.example`、`.gitignore`
- [x] 基础 README、pytest 基础测试、GitHub Actions CI

### 阶段 2（已完成）：邮件任务登记与数据库去重

- [x] SQLAlchemy 2.0 ORM 模型 `email_tasks`
- [x] Alembic 迁移（含可回滚的 downgrade）
- [x] `mailbox_id + message_id` 数据库唯一约束
- [x] `POST /api/v1/emails`：首次创建（201，`status=received`），重复提交返回已有任务（200，`duplicate=true`）
- [x] 必填字段校验（缺失/空白返回 422）
- [x] 并发唯一约束冲突处理（回滚后复用已提交记录）
- [x] PostgreSQL 集成测试（含真实 8 线程并发）
- [x] CI 增加 PostgreSQL 服务与迁移步骤

### 阶段 3（已完成）：数据库字段 + 状态定义 + 迁移验证

- [x] `email_tasks` 新增 12 个字段（分流结果、人工审核、异常信息）
- [x] `requires_human` 在 ORM 与数据库层默认 `true`，历史记录升级后自动回填
- [x] 新迁移 `0002_add_triage_review_fields`（可 upgrade / downgrade，不删除重建表）
- [x] 7 个状态与允许的状态转换集中在 `app/core/email_status.py`
- [x] 状态合法/非法转换测试
- [x] schema 测试（新字段、默认值、唯一约束）
- [x] 仅在独立测试库 `ai_support_test` 完成迁移与测试验证

### 阶段 4（已完成）：风险规则服务 + Mock AI Provider

- [x] `app/services/rules.py`：纯规则判断，不访问数据库、不修改状态、不调用 AI
- [x] 规则结果使用 `requires_immediate_handoff`；未命中时 `risk_level` / `suggested_category` 为 `None`
- [x] 共享类型 `app/core/triage_types.py`（类别与风险等级），规则与 Provider 共用
- [x] `AIProvider` 抽象接口 + Pydantic `ClassificationResult` schema
- [x] `MockAIProvider`：离线、确定性、关键词分类，`requires_human=true`，不生成不实草稿
- [x] 57 个新增单元测试（不依赖数据库）
- [x] 全量测试 130 passed

**当前阶段明确不包含**：process API、review API、真实 AI、n8n 工作流、邮件发送、Slack、真实通知、鉴权。

### 阶段 5（本阶段已完成）：process / GET / review API

- [x] `POST /api/v1/emails/{id}/process`：原子认领、规则检查、Mock AI 分流、状态落库
- [x] `GET /api/v1/emails/{id}`：任务完整详情
- [x] `POST /api/v1/emails/{id}/review`：approve / reject / takeover，approve 要求非空草稿
- [x] 无草稿的普通分类结果直接 `human_takeover`，不进入 `awaiting_review`
- [x] 重复 process 约定：`awaiting_review` 返回已有结果，其他不允许状态返回 409
- [x] Provider 预期错误/非法输出 → `failed` + 502；未预期编程错误 → 500
- [x] 数据库异常回滚并返回 503，明确“任务状态可能不确定”
- [x] 42 个新增 API/并发测试（真实 PostgreSQL）；全量 172 passed

**当前阶段明确不包含**：真实 AI、Gmail/Slack/n8n、邮件发送、真实通知、鉴权、自动重试、processing 超时回收。

## 技术栈

| 组件 | 用途 | 当前状态 |
| --- | --- | --- |
| Python 3.10+ / FastAPI | HTTP API | 已启用（健康检查 + 登记 + process/GET/review） |
| PostgreSQL 16 | 业务数据存储 | 已接入（`email_tasks` 表） |
| SQLAlchemy 2.0 + Alembic | ORM 与数据库迁移 | 已启用 |
| psycopg 3 | PostgreSQL 驱动 | 已启用 |
| 规则 + Mock AI | 风险规则与离线分类 | 已启用（仅 Mock，无真实 AI） |
| pytest / httpx | 自动化测试 | 172 个测试 |
| n8n | 邮件接入与流程编排 | Docker Compose 已配置，工作流待实现 |

## 目录结构

```text
ai-support-workflow/
├── app/
│   ├── main.py                     # FastAPI 应用入口
│   ├── config.py                   # pydantic-settings 配置（DATABASE_URL）
│   ├── api/
│   │   ├── deps.py                 # get_ai_provider 依赖
│   │   └── routes/
│   │       ├── health.py           # GET /health
│   │       └── emails.py           # 登记 / GET / process / review
│   ├── core/
│   │   ├── email_status.py         # 任务状态与转换校验
│   │   └── triage_types.py         # 分类/风险共享类型
│   ├── db/
│   │   ├── base.py                 # SQLAlchemy DeclarativeBase
│   │   ├── models.py               # email_tasks 模型（含分流/审核字段）
│   │   └── session.py              # 引擎、Session、get_db 依赖
│   ├── providers/
│   │   └── ai/
│   │       ├── base.py             # AIProvider 接口与 ClassificationResult
│   │       └── mock_provider.py    # 离线确定性 Mock Provider
│   ├── schemas/emails.py           # 请求/响应 Pydantic 模型
│   └── services/
│       ├── db_utils.py             # 服务层数据库辅助
│       ├── email_tasks.py          # 登记与数据库去重服务
│       ├── errors.py               # 领域异常
│       ├── review.py               # 人工审核状态更新
│       ├── rules.py                # 高风险规则服务（纯函数）
│       └── triage.py               # process 编排
├── alembic/
│   ├── env.py                      # 从 DATABASE_URL 读取连接
│   └── versions/
│       ├── 0001_create_email_tasks.py
│       └── 0002_add_triage_review_fields.py
├── tests/
│   ├── api_helpers.py              # API 测试辅助
│   ├── conftest.py                 # PostgreSQL fixture + 库名保护 + Provider 覆盖
│   ├── db_safety.py                # 测试库名安全校验
│   ├── fakes.py                    # 测试用 Provider 假实现
│   ├── test_db_safety.py
│   ├── test_email_schema.py        # 字段/默认值/唯一约束测试
│   ├── test_email_status.py        # 状态转换测试
│   ├── test_emails.py              # 邮件登记/去重测试
│   ├── test_get_email_api.py       # GET 详情测试
│   ├── test_health.py
│   ├── test_mock_ai_provider.py    # Mock Provider/schema/异常测试
│   ├── test_process_api.py         # process 正常/规则分支
│   ├── test_process_concurrency.py # 重复/并发/事务边界
│   ├── test_process_errors.py      # Provider 错误/终态冲突
│   ├── test_review_api.py          # review 防御性测试
│   ├── test_review_concurrency.py  # 并发审核
│   └── test_rules.py               # 规则服务测试
├── n8n/                            # 后续：n8n 工作流 JSON 占位
├── 架构图/                          # 业务流程图（01-04，未改动）
├── .github/workflows/ci.yml        # CI（含 PostgreSQL 测试库）
├── alembic.ini
├── docker-compose.yml              # PostgreSQL + n8n（本地演示）
├── requirements.txt
├── pyproject.toml
├── .env.example
└── README.md
```

## 本地运行

### 1. 启动 PostgreSQL（本阶段接口依赖数据库）

```bash
cp .env.example .env          # 可选，默认值即为本地演示配置
docker compose up -d db       # 仅启动数据库；如需 n8n 可执行 docker compose up -d
```

- PostgreSQL：`localhost:5432`（用户/密码/库名默认均为演示值，见 `.env.example`）
- n8n（可选）：http://localhost:5678 （本地演示未开启登录鉴权）

> 生产环境必须启用 n8n 鉴权、修改数据库口令，并限制端口暴露范围。

### 2. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> 本机若缺少 `python3-venv`，请先安装 `python3-venv`，或使用其他隔离环境工具（如 uv）。
> 应用与 Alembic 均从 `DATABASE_URL` 读取连接；未设置时使用 `app/config.py` 中的本地演示默认值。

### 3. 开发库迁移（运行 API 前）

```bash
alembic upgrade head
```

> 本阶段验证**未**对开发库 `ai_support` 执行 `0002`；若要在本机运行 API 并写入新任务，请自行确认后执行上述迁移。

### 4. 创建并迁移独立测试库

```bash
docker compose exec -T db psql -U demo -d postgres \
  -c 'CREATE DATABASE ai_support_test OWNER demo;'

DATABASE_URL=postgresql+psycopg://demo:demo@localhost:5432/ai_support_test \
  alembic upgrade head
```

> 若 `ai_support_test` 已存在，请先确认其数据用途，不要擅自删除重建。
> 测试清理 fixture 只允许操作 `ai_support_test`，其他库名会立即终止测试，避免误清空开发数据。

### 5. 启动 API

```bash
uvicorn app.main:app --reload
```

- 健康检查：`GET http://127.0.0.1:8000/health`
- 接口文档：http://127.0.0.1:8000/docs

### 6. 登记邮件任务（示例）

```bash
# 首次提交：201，status=received，duplicate=false
curl -i -X POST http://127.0.0.1:8000/api/v1/emails \
  -H 'Content-Type: application/json' \
  -d '{"mailbox_id":"support@example.com","message_id":"<demo-001@example.com>","subject":"无法登录","body":"请协助处理"}'

# 相同 mailbox_id + message_id 再次提交：200，返回已有任务，duplicate=true
curl -i -X POST http://127.0.0.1:8000/api/v1/emails \
  -H 'Content-Type: application/json' \
  -d '{"mailbox_id":"support@example.com","message_id":"<demo-001@example.com>","subject":"无法登录","body":"请协助处理"}'
```

必填字段：`mailbox_id`、`message_id`（非空白）；`subject`、`body` 可省略，默认为空字符串。

### 7. 处理与审核（示例）

```bash
# 处理任务：规则未命中时调用 Mock Provider
curl -i -X POST http://127.0.0.1:8000/api/v1/emails/1/process

# 查询任务详情
curl http://127.0.0.1:8000/api/v1/emails/1

# 人工审核（仅 awaiting_review 且草稿非空时 approve 成功）
curl -i -X POST http://127.0.0.1:8000/api/v1/emails/1/review \
  -H 'Content-Type: application/json' \
  -d '{"action":"approve","reviewed_by":"agent@example.com","review_comment":"同意"}'
```

约定：

- 规则要求立即转人工时直接 `human_takeover`，不调用 Mock；
- Provider 返回 high / refund_request / complaint，或普通结果没有非空草稿时，均转 `human_takeover`；
- 普通结果且有非空草稿才进入 `awaiting_review`；
- 重复 process：`awaiting_review` 返回已有结果（200），`processing` / 终态返回 409；
- `approve` 无草稿返回 409；`reject` / `takeover` 对异常无草稿记录仍允许；
- 所有草稿必须人工审核，系统不发送邮件。

### 8. 运行测试

```bash
DATABASE_URL=postgresql+psycopg://demo:demo@localhost:5432/ai_support_test \
TEST_DATABASE_URL=postgresql+psycopg://demo:demo@localhost:5432/ai_support_test \
env -u PYTHONPATH .venv/bin/python -m pytest -v
```

测试要求：

- 测试库需已执行 `alembic upgrade head`；
- 数据库不可用时，数据库相关用例会被跳过（不会伪装成通过）；数据库可用但未迁移时，测试会失败并提示先执行迁移；
- `db_engine` 建连后立即检查 `current_database()`，`clean_db` 在 TRUNCATE 前再次检查；不是 `ai_support_test` 就立即终止；
- 本机 ROS 的 `PYTHONPATH` 可能干扰 pytest 插件加载，因此示例使用 `env -u PYTHONPATH`。

### 本地验证结果（2026-11-11，阶段 3）

- 环境：Python 3.10.12、FastAPI 0.162.4、SQLAlchemy 2.0.57、Alembic 1.20.1、psycopg 3.3.8、PostgreSQL 16（Docker）
- 仅在 `ai_support_test` 上执行迁移演练：
  - `alembic upgrade 0001_create_email_tasks` → 插入模拟历史记录（id=1）
  - `alembic upgrade head` → 历史记录保留，`requires_human=true`，其余新字段为 NULL，唯一约束保留
  - `alembic downgrade 0001_create_email_tasks` → 历史记录保留，新字段移除，唯一约束保留
  - 再次 `alembic upgrade head` → 成功
  - `alembic check` → `No new upgrade operations detected`
- `pytest -v`（测试库为 `ai_support_test`）：**73 passed, 1 warning**（多次运行 1.22–1.30s）
- `ai_support` 未被修改：迁移版本与行数在验证前后均为 `0001_create_email_tasks` / 1 行，非敏感摘要一致
- 说明：GitHub Actions 未在本地实际触发；未进行多实例部署与压力测试

### 本地验证结果（2026-11-11，阶段 4）

- 新增单元测试：`pytest tests/test_rules.py tests/test_mock_ai_provider.py -v` → **57 passed**（0.06s）
- 将 `DATABASE_URL` / `TEST_DATABASE_URL` 指向不可达地址后重跑新增测试 → **57 passed**（证明不依赖数据库）
- 全量测试（测试库 `ai_support_test`）→ **130 passed, 1 warning**（1.19s）
- `ai_support` 未被修改：迁移版本 `0001_create_email_tasks`、1 行数据、非敏感摘要与验证前一致
- GitHub Actions 未实际触发；本阶段未接入真实 AI

### 本地验证结果（2026-11-11，阶段 5）

- 新增 API/并发测试：**42 passed, 1 warning**（真实 PostgreSQL，约 2.6s）
- 全量测试：**172 passed, 1 warning**（3.28s）
- 并发/事务验证：
  - 两个 process 请求：第二个在第一个处于 `processing` 时返回 409，Provider 只调用 1 次
  - 两个并发 review 请求：结果 `[200, 409]`，只有一个审核动作落库
  - 最终条件更新未命中：返回 409，不报告成功
  - 认领/最终提交数据库异常：返回 503，明确“任务状态可能不确定”，未断言状态未改变
- `ai_support` 未被修改：迁移版本 `0001_create_email_tasks`、1 行数据、非敏感摘要与验证前一致
- GitHub Actions 未实际触发；未接入真实 AI；未验证真实网络中断后的最终提交状态

## 配置说明

配置通过环境变量或 `.env` 读取（见 `app/config.py` 与 `.env.example`），默认值全部为本地演示配置：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_NAME` | `AI Support Workflow` | 应用名称 |
| `APP_ENV` | `local` | 运行环境标识 |
| `APP_VERSION` | `0.1.0` | 版本号 |
| `DATABASE_URL` | `postgresql+psycopg://demo:demo@localhost:5432/ai_support` | SQLAlchemy 连接串（psycopg 3 驱动） |
| `TEST_DATABASE_URL` | 未设置时复用 `DATABASE_URL`；`.env.example` 推荐指向 `ai_support_test` | 测试专用连接串（清理保护要求库名为 `ai_support_test`） |

`.env` 已被 `.gitignore` 忽略，请勿提交真实密钥。

## CI

`.github/workflows/ci.yml` 在 push 到 `main` 及 Pull Request 时，在 Python 3.10 / 3.11 / 3.12 上：

1. 启动 PostgreSQL 16 服务，数据库名为 `ai_support_test`；
2. 安装 `requirements.txt` 依赖；
3. 执行 `alembic upgrade head`；
4. 运行 `pytest -v`（含数据库集成测试）。

> 以上为 CI 配置说明；本次本地开发未实际触发 GitHub Actions 运行。

## 状态定义与转换（阶段 3）

已定义（`app/core/email_status.py`）：

```text
received → processing
processing → awaiting_review | human_takeover | failed
awaiting_review → approved | rejected | human_takeover

终态（本阶段无出边）：approved / rejected / human_takeover / failed
```

- 同状态转换视为非法；process 对 `awaiting_review` 的重复请求直接返回已有结果，不通过状态自转实现幂等，也不代表端到端 exactly-once。
- 未定义 `sent` / `sending`，未实现发送功能。
- 状态仅在 Python 层校验，直接写库可绕过（见已知限制）。

## process / review API 行为（阶段 5）

### process

- 认领使用 `UPDATE ... WHERE status='received' RETURNING`；提交认领后才调用规则/Mock，不在 Provider 调用期间持有行锁。
- 规则要求立即转人工：`human_takeover`，不调用 Mock。
- 规则未命中时调用 Mock：
  - high / refund_request / complaint → `human_takeover`，强制 `draft_body=NULL`；
  - 普通类别 + 非空草稿 → `awaiting_review`，`requires_human=true`；
  - 普通类别 + 无/空白草稿 → `human_takeover`，`risk_reason` 说明原因。
- Provider 预期异常或输出校验失败 → `failed` + 502；未预期编程错误 → 500，不伪装成 Provider 故障。
- 最终写回使用 `WHERE id=:id AND status='processing'`；未命中返回 409，不报告成功。
- 重复 process：`received` 尝试认领；`processing` 409；`awaiting_review` 200 + 已有结果（不调用 Provider、不覆盖字段）；其余终态 409；不存在 404。

### review

- 请求体：`action`（approve / reject / takeover）、`reviewed_by`（非空白）、`review_comment`（可选）。
- `review_action` 保存动作值（approve / reject / takeover），`status` 保存对应状态（approved / rejected / human_takeover）。
- `reviewed_by` 是客户端自报的演示值，不代表真实身份。
- 使用 `UPDATE ... WHERE status='awaiting_review'`；approve 还要求 `draft_body` 去除空白后非空。
- approve 无草稿 → 409，不更新状态；reject / takeover 对异常无草稿记录仍允许。
- 两个并发 review 只有一个成功，另一个 409。
- 审核通过不代表已发送邮件；系统未实现发送。

### API 返回码摘要

| 接口 | 200 | 404 | 409 | 422 | 502 | 503 |
| --- | --- | --- | --- | --- | --- | --- |
| `POST .../process` | 处理完成（awaiting_review / human_takeover） | 任务不存在 | processing / 终态 / 结果写回冲突 | — | Provider 失败或输出无效（任务 failed） | 数据库异常，状态可能不确定 |
| `GET .../{id}` | 详情 | 不存在 | — | — | — | 数据库异常 |
| `POST .../review` | 审核完成 | 不存在 | 非 awaiting_review / approve 无草稿 / 并发失败 | 请求字段无效 | — | 数据库异常 |

未预期内部错误统一返回 500。

## 风险规则与 Mock AI（阶段 4）

### 规则服务（`app/services/rules.py`）

纯函数 `evaluate_rules(subject, body)`：不访问数据库、不修改任务状态、不调用 AI、不产生自动发送指令。

返回字段：`matched`、`risk_level`（未命中为 `None`）、`risk_reason`、`suggested_category`（未命中为 `None`）、`requires_immediate_handoff`、`matched_keywords`。

| 规则 | 风险等级 | 建议类别 | 立即转人工 |
| --- | --- | --- | --- |
| 法律/投诉/赔偿关键词 | high | complaint | 是 |
| 退款/拒付关键词 | high | refund_request | 是 |
| 修改订单 | medium | order_inquiry | 是 |
| 修改付款/账户权限 | medium | other | 是 |
| 正文为空/仅空白 | medium | other | 是 |
| 未命中 | None（未判断） | None | 否 |

- 优先级：法律/投诉/赔偿 > 退款/拒付 > 订单修改 > 付款/账户权限修改。
- 未命中规则不代表邮件安全，后续草稿仍必须人工审核。
- 空正文规则直接要求人工处理，process API 不会调用 Mock。

### Mock AI Provider（`app/providers/ai/mock_provider.py`）

- 完全离线：不访问网络、不读取 API Key、不访问数据库、不发送邮件。
- 确定性关键词分类，优先级：投诉/法律 > 退款/拒付 > 订单/物流 > 产品/功能 > 其他。
- `requires_human` 始终为 `true`。
- `product_question`、`order_inquiry` 可生成通用草稿；`refund_request`、`complaint`、`other` 不生成草稿。
- 草稿不包含订单号、发货、付款、退款、账户状态等事实；所有草稿仍需人工审核。
- `ClassificationResult` 使用 Pydantic 校验：非法 category/risk_level、缺少字段、额外字段都会被拒绝。
- 测试中通过 fake provider 注入异常、超时和可重试异常，未引入网络调用。

### 已知局限（规则/Mock）

- 精确关键词规则可能漏判（同义词、拼写错误、其他语言）或误判。
- 例如 `illegal` 不会匹配 `legal`，但这**不代表**邮件安全。
- Prompt 注入相关测试只验证 Mock 的行为，不能证明真实 LLM 已被防护。
- 本阶段没有真实 AI、邮件发送或通知；规则与 Mock 已接入 process API，但没有真实模型调用。

## 后续待实现模块

已完成：

- 邮件任务登记与数据库去重（`email_tasks`、`POST /api/v1/emails`）
- 分流/审核字段与状态定义（字段、状态与校验）
- 风险规则服务与 Mock AI Provider（离线）
- process 编排与 `POST /api/v1/emails/{id}/process`
- `GET /api/v1/emails/{id}`
- review API（approve / reject / takeover）

待实现：

1. **异常处理与提醒**（图 4）：安全重试、超时提醒、人工通知（模拟）
2. **发送功能**：发送前检查与结果记录（模拟）；届时再定义 `sent` / `sending` 等状态
3. **n8n 工作流**：`n8n/` 下工作流 JSON 导出与导入说明
4. **可观测性与就绪探针**：`/ready`、结构化日志、请求 ID、统一异常处理
5. **数据层扩展**：tickets、review_records、send_records、error_logs 等表与迁移
6. **安全加固**：鉴权、审计日志、限流、敏感数据脱敏
7. **真实 AI 接入（未来）**：需单独评估提示注入防护、密钥管理、审计与数据合规，不在当前演示范围
8. **processing 超时回收、重试与幂等键（未来）**：当前未实现

## 已知限制与风险（演示阶段）

- API 无鉴权、无速率限制，仅适合本地演示
- `subject` / `body` 允许为空字符串；未限制请求体大小与正文长度
- 状态校验仅在 Python 层完成，数据库未设置 CHECK/ENUM；直接 SQL 写库可以绕过状态转换校验
- 测试清理 fixture 固定只允许数据库名 `ai_support_test`；其他名称（包括开发库）会被拒绝并终止测试
- 本阶段未对 `ai_support` 执行 `0002` 迁移，开发库仍停留在 `0001`（迁移验证仅在测试库完成）
- 并发验证为单进程多线程 + 单 PostgreSQL 实例，未做多实例部署与压力测试
- 未实现 `/ready`、结构化日志、监控与告警
- CI 配置未在 GitHub 上实际运行验证
- 规则/Mock 使用精确关键词，可能漏判（同义词、拼写错误、其他语言）或误判
- 例如 `illegal` 不匹配 `legal`，但这不代表邮件安全
- Prompt 注入相关测试只验证 Mock 行为，不能证明真实 LLM 已被防护
- 规则与 Mock 已接入 process API；未接入真实 AI；Mock 的 `requires_human` 始终为 `true`，草稿必须人工审核
- 未接入真实 AI、网络、邮箱、Slack 或通知；Mock 测试不等同于真实 DeepSeek 等 API 验证
- 进程在 `processing` 中途退出（被杀、断电等）会留下无自动恢复的 `processing` 任务，需要人工或未来 reaper；本阶段未实现超时回收
- 数据库提交确认阶段中断时，任务状态可能未知；接口只返回 503 并提示重新查询，不断言状态未改变
- 未实现端到端 exactly-once；重复 process 的 200/409 只是本接口约定
- 无邮件发送能力，`approved` / `rejected` 不代表已发送或已退款
- `GET` 返回邮件正文/草稿，且无鉴权，存在隐私风险（仅演示）
