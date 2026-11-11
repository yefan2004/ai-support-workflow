# AI 客服邮件分流与人工审核（Demo）

> ## ⚠️ 演示项目声明
>
> **本项目仅用于学习与技术演示，不可直接用于生产环境。**
>
> - 不包含真实 AI 模型调用（AI 分流为后续阶段，且仅做模拟）
> - 不接入真实邮箱（Gmail / Outlook）与 Slack
> - 不包含任何真实密钥，所有默认账号口令仅用于本地演示
> - 未实现鉴权、审计、限流、数据加密与合规能力
> - 当前仅实现邮件任务登记、数据库去重、分流/审核字段与状态定义，其余流程尚未实现

基于 **FastAPI + PostgreSQL + n8n** 的 AI 辅助客服邮件分流与人工审核流程骨架。业务流程参考 `架构图/` 下的四张流程图：

1. 邮件接入与去重（已实现登记与去重，未接入真实邮箱）
2. 规则检查与 AI 分流（仅预留字段与状态，未实现服务）
3. 人工审核与回复发送（仅预留字段与状态，未实现 API 与发送）
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

### 阶段 3（本阶段已完成）：数据库字段 + 状态定义 + 迁移验证

- [x] `email_tasks` 新增 12 个字段（分流结果、人工审核、异常信息）
- [x] `requires_human` 在 ORM 与数据库层默认 `true`，历史记录升级后自动回填
- [x] 新迁移 `0002_add_triage_review_fields`（可 upgrade / downgrade，不删除重建表）
- [x] 7 个状态与允许的状态转换集中在 `app/core/email_status.py`
- [x] 状态合法/非法转换测试
- [x] schema 测试（新字段、默认值、唯一约束）
- [x] 仅在独立测试库 `ai_support_test` 完成迁移与测试验证

**本阶段明确不包含**：规则服务、Mock AI、process/review API、真实 AI、n8n 工作流、邮件发送、Slack、鉴权。

## 技术栈

| 组件 | 用途 | 当前状态 |
| --- | --- | --- |
| Python 3.10+ / FastAPI | HTTP API | 已启用（健康检查 + 邮件登记） |
| PostgreSQL 16 | 业务数据存储 | 已接入（`email_tasks` 表） |
| SQLAlchemy 2.0 + Alembic | ORM 与数据库迁移 | 已启用 |
| psycopg 3 | PostgreSQL 驱动 | 已启用 |
| pytest / httpx | 自动化测试 | 73 个测试 |
| n8n | 邮件接入与流程编排 | Docker Compose 已配置，工作流待实现 |

## 目录结构

```text
ai-support-workflow/
├── app/
│   ├── main.py                     # FastAPI 应用入口
│   ├── config.py                   # pydantic-settings 配置（DATABASE_URL）
│   ├── api/routes/
│   │   ├── health.py               # GET /health
│   │   └── emails.py               # POST /api/v1/emails
│   ├── core/
│   │   └── email_status.py         # 状态枚举与转换校验
│   ├── db/
│   │   ├── base.py                 # SQLAlchemy DeclarativeBase
│   │   ├── models.py               # email_tasks 模型（含分流/审核字段）
│   │   └── session.py              # 引擎、Session、get_db 依赖
│   ├── schemas/emails.py           # 请求/响应 Pydantic 模型
│   └── services/email_tasks.py     # 登记与数据库去重服务
├── alembic/
│   ├── env.py                      # 从 DATABASE_URL 读取连接
│   └── versions/
│       ├── 0001_create_email_tasks.py
│       └── 0002_add_triage_review_fields.py
├── tests/
│   ├── conftest.py                 # PostgreSQL 测试 fixture（含清理保护）
│   ├── db_safety.py                # 测试库名安全校验
│   ├── test_db_safety.py
│   ├── test_email_schema.py        # 字段/默认值/唯一约束测试
│   ├── test_email_status.py        # 状态转换测试
│   ├── test_emails.py              # 邮件登记/去重测试
│   └── test_health.py
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

### 7. 运行测试

```bash
TEST_DATABASE_URL=postgresql+psycopg://demo:demo@localhost:5432/ai_support_test \
env -u PYTHONPATH .venv/bin/python -m pytest -v
```

测试要求：

- 测试库需已执行 `alembic upgrade head`；
- 数据库不可用时，数据库相关用例会被跳过（不会伪装成通过）；数据库可用但未迁移时，测试会失败并提示先执行迁移；
- `clean_db` fixture 在 TRUNCATE 前执行 `SELECT current_database()`，只有 `ai_support_test` 才允许清理，否则立即终止；
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

- 同状态转换视为非法；重复 API 请求应直接返回已有结果实现幂等，不依赖状态自转。
- 本阶段未定义 `sent` / `sending`，也未实现发送功能。
- 状态仅在 Python 层校验，直接写库可绕过（见已知限制）。

## 后续待实现模块

已完成：

- 邮件任务登记与数据库去重（`email_tasks`、`POST /api/v1/emails`）
- 分流/审核字段与状态定义（本阶段仅字段、状态与校验，无业务服务）

待实现：

1. **规则检查服务**（图 2）：高风险规则（退款、投诉、隐私等）
2. **Mock AI 分流**：模拟分类、摘要、风险等级、置信度、建议回复与输出校验
3. **process API**：驱动 `received → processing → awaiting_review / failed`
4. **review API**：批准 / 修改后批准 / 拒绝 / 人工接管
5. **异常处理与提醒**（图 4）：安全重试、`failed` 状态、超时提醒（模拟通知）
6. **发送功能**：发送前检查与结果记录（模拟）；届时再定义 `sent` / `sending` 等状态
7. **n8n 工作流**：`n8n/` 下工作流 JSON 导出与导入说明
8. **可观测性与就绪探针**：`/ready`、结构化日志、请求 ID、统一异常处理
9. **数据层扩展**：tickets、review_records、send_records、error_logs 等表与迁移
10. **安全加固**：鉴权、审计日志、限流、敏感数据脱敏

## 已知限制与风险（演示阶段）

- API 无鉴权、无速率限制，仅适合本地演示
- `subject` / `body` 允许为空字符串；未限制请求体大小与正文长度
- 状态校验仅在 Python 层完成，数据库未设置 CHECK/ENUM；直接 SQL 写库可以绕过状态转换校验
- 测试清理 fixture 固定只允许数据库名 `ai_support_test`；其他名称（包括开发库）会被拒绝并终止测试
- 本阶段未对 `ai_support` 执行 `0002` 迁移，开发库仍停留在 `0001`（迁移验证仅在测试库完成）
- 并发验证为单进程多线程 + 单 PostgreSQL 实例，未做多实例部署与压力测试
- 未实现 `/ready`、结构化日志、监控与告警
- CI 配置未在 GitHub 上实际运行验证
