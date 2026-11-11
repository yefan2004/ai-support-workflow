# AI 客服邮件分流与人工审核（Demo）

> ## ⚠️ 演示项目声明
>
> **本项目仅用于学习与技术演示，不可直接用于生产环境。**
>
> - 不包含真实 AI 模型调用（AI 分流为后续阶段，且仅做模拟）
> - 不接入真实邮箱（Gmail / Outlook）与 Slack
> - 不包含任何真实密钥，所有默认账号口令仅用于本地演示
> - 未实现鉴权、审计、限流、数据加密与合规能力
> - 当前仅实现邮件任务登记与数据库去重，其余流程尚未实现

基于 **FastAPI + PostgreSQL + n8n** 的 AI 辅助客服邮件分流与人工审核流程骨架。业务流程参考 `架构图/` 下的四张流程图：

1. 邮件接入与去重（本阶段已实现登记与去重，未接入真实邮箱）
2. 规则检查与 AI 分流（未实现）
3. 人工审核与回复发送（未实现）
4. 异常处理与人工提醒（未实现）

## 当前阶段范围

### 阶段 1（已完成）：项目骨架

- [x] 目录结构、FastAPI 应用入口、`GET /health`
- [x] PostgreSQL 的 Docker Compose 配置、`.env.example`、`.gitignore`
- [x] 基础 README、pytest 基础测试、GitHub Actions CI

### 阶段 2（本阶段已完成）：邮件任务登记与数据库去重

- [x] SQLAlchemy 2.0 ORM 模型 `email_tasks`
- [x] Alembic 迁移（含可回滚的 downgrade）
- [x] `mailbox_id + message_id` 数据库唯一约束
- [x] `POST /api/v1/emails`：首次创建（201，`status=received`），重复提交返回已有任务（200，`duplicate=true`）
- [x] 必填字段校验（缺失/空白返回 422）
- [x] 并发唯一约束冲突处理（回滚后复用已提交记录）
- [x] PostgreSQL 集成测试（含真实 8 线程并发）
- [x] CI 增加 PostgreSQL 服务与迁移步骤

**本阶段明确不包含**：真实 AI 调用、n8n 工作流、人工审核、回复发送、Slack、真实邮箱接入、鉴权体系。

## 技术栈

| 组件 | 用途 | 当前状态 |
| --- | --- | --- |
| Python 3.10+ / FastAPI | HTTP API | 已启用（健康检查 + 邮件登记） |
| PostgreSQL 16 | 业务数据存储 | 已接入（`email_tasks` 表） |
| SQLAlchemy 2.0 + Alembic | ORM 与数据库迁移 | 已启用 |
| psycopg 3 | PostgreSQL 驱动 | 已启用 |
| pytest / httpx | 自动化测试 | 14 个测试 |
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
│   ├── core/                       # 后续：日志、异常处理
│   ├── db/
│   │   ├── base.py                 # SQLAlchemy DeclarativeBase
│   │   ├── models.py               # email_tasks 模型与唯一约束
│   │   └── session.py              # 引擎、Session、get_db 依赖
│   ├── schemas/emails.py           # 请求/响应 Pydantic 模型
│   └── services/email_tasks.py     # 登记与数据库去重服务
├── alembic/
│   ├── env.py                      # 从 DATABASE_URL 读取连接
│   └── versions/0001_create_email_tasks.py
├── tests/
│   ├── conftest.py                 # PostgreSQL 测试 fixture
│   ├── test_emails.py              # 邮件登记/去重测试
│   └── test_health.py
├── n8n/                            # 后续：n8n 工作流 JSON 占位
├── 架构图/                          # 业务流程图（01-04，未改动）
├── .github/workflows/ci.yml        # CI（含 PostgreSQL 服务）
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

### 2. 安装依赖并执行迁移

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

> 本机若缺少 `python3-venv`，请先安装 `python3-venv`，或使用其他隔离环境工具（如 uv）。
> 迁移连接串来自 `DATABASE_URL`；未设置 `.env` 时使用 `app/config.py` 中的本地演示默认值。

### 3. 启动 API

```bash
uvicorn app.main:app --reload
```

- 健康检查：`GET http://127.0.0.1:8000/health`
- 接口文档：http://127.0.0.1:8000/docs

### 4. 登记邮件任务（示例）

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

### 5. 运行测试

```bash
pytest -v
```

测试需要可用的 PostgreSQL 且已执行迁移：

- 数据库不可用时，数据库相关用例会被跳过（不会伪装成通过）；
- 数据库可用但未迁移时，测试会失败并提示先执行 `alembic upgrade head`。

> ⚠️ 测试会在每个用例前后清空 `email_tasks` 表。请使用本地演示库；如需独立测试库，可设置 `TEST_DATABASE_URL`。

> 本机 ROS 的 `PYTHONPATH` 可能干扰 pytest 插件加载，可改用：
> `env -u PYTHONPATH .venv/bin/python -m pytest -v`

### 本地验证结果（2026-11-11，阶段 2）

- 环境：Python 3.10.12、FastAPI 0.162.4、SQLAlchemy 2.0.57、Alembic 1.20.1、psycopg 3.3.8、PostgreSQL 16（Docker）
- `alembic upgrade head`：成功创建 `email_tasks` 表与唯一约束
- `alembic downgrade base` → `alembic upgrade head`：回滚与重建均成功
- `pytest -v`：**14 passed**（0.47s），含真实 8 线程并发用例；该并发用例额外重复运行 5 次均通过
- 真实 HTTP（uvicorn + curl）：首次提交 201；重复提交 200 且 `duplicate=true`；缺少 `message_id` 返回 422
- 说明：以上均为本地单机验证，未进行多实例部署、压力测试，也未实际触发 GitHub Actions

## 配置说明

配置通过环境变量或 `.env` 读取（见 `app/config.py` 与 `.env.example`），默认值全部为本地演示配置：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_NAME` | `AI Support Workflow` | 应用名称 |
| `APP_ENV` | `local` | 运行环境标识 |
| `APP_VERSION` | `0.1.0` | 版本号 |
| `DATABASE_URL` | `postgresql+psycopg://demo:demo@localhost:5432/ai_support` | SQLAlchemy 连接串（psycopg 3 驱动） |
| `TEST_DATABASE_URL` | 未设置（复用 `DATABASE_URL`） | 测试专用连接串（可选） |

`.env` 已被 `.gitignore` 忽略，请勿提交真实密钥。

## CI

`.github/workflows/ci.yml` 在 push 到 `main` 及 Pull Request 时，在 Python 3.10 / 3.11 / 3.12 上：

1. 启动 PostgreSQL 16 服务（演示凭据，仅 CI 使用）；
2. 安装 `requirements.txt` 依赖；
3. 执行 `alembic upgrade head`；
4. 运行 `pytest -v`（含数据库集成测试）。

> 以上为 CI 配置说明；本次本地开发未实际触发 GitHub Actions 运行。

## 计划中的状态流转（后续阶段）

```text
received → triaged → pending_review → approved → sent
                                    ↘ rejected
                                    ↘ takeover（人工接管）
                     ↘ failed / send_uncertain（异常分支）
```

## 后续待实现模块

已完成：邮件任务登记与数据库去重（`email_tasks`、`POST /api/v1/emails`）。

待实现：

1. **规则与 AI 分流**（图 2）：高风险规则检查、模拟 AI 分类（类别/摘要/风险/置信度/建议回复）、输出校验
2. **人工审核与发送**（图 3）：审核 API（批准/修改后批准/拒绝/接管）、发送前检查、发送结果记录（模拟）
3. **异常处理与提醒**（图 4）：安全重试、failed/send_uncertain 状态、超时提醒（模拟 Slack/邮件通知）
4. **n8n 工作流**：`n8n/` 下工作流 JSON 导出与导入说明
5. **可观测性与就绪探针**：`/ready`、结构化日志、请求 ID、统一异常处理
6. **数据层扩展**：tickets、review_records、send_records、error_logs 等表与迁移
7. **安全加固**：鉴权、审计日志、限流、敏感数据脱敏

## 已知限制与风险（演示阶段）

- API 无鉴权、无速率限制，仅适合本地演示
- `subject` / `body` 允许为空字符串；未限制请求体大小与正文长度
- 测试会在每个用例前后清空 `email_tasks` 表，请勿指向包含真实数据的数据库
- 并发验证为单进程多线程 + 单 PostgreSQL 实例，未做多实例部署与压力测试
- 未实现 `/ready`、结构化日志、监控与告警
- CI 配置未在 GitHub 上实际运行验证
