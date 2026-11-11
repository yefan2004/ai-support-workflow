# AI 客服邮件分流与人工审核（Demo）

> ## ⚠️ 演示项目声明
>
> **本项目仅用于学习与技术演示，不可直接用于生产环境。**
>
> - 不包含真实 AI 模型调用（后续阶段仅做模拟分类）
> - 不接入真实邮箱（Gmail / Outlook）与 Slack
> - 不包含任何真实密钥，所有默认账号口令仅用于本地演示
> - 未实现完整的鉴权、审计、限流、数据加密与合规能力

基于 **FastAPI + PostgreSQL + n8n** 的 AI 辅助客服邮件分流与人工审核流程骨架。业务流程参考 `架构图/` 下的四张流程图：

1. 邮件接入与去重
2. 规则检查与 AI 分流
3. 人工审核与回复发送
4. 异常处理与人工提醒

## 当前阶段范围

本阶段只搭建骨架，已完成：

- [x] 目录结构（按后续四大流程预留模块）
- [x] FastAPI 应用入口（`app/main.py`）
- [x] `GET /health` 健康检查接口
- [x] PostgreSQL 的 Docker Compose 配置（附带本地 n8n）
- [x] `.env.example`（纯演示值，无真实密钥）
- [x] `.gitignore`
- [x] README（含演示声明）
- [x] pytest 基础测试
- [x] GitHub Actions CI

**明确不包含**：真实 AI 调用、真实邮箱/Slack 接入、业务数据模型与迁移、n8n 工作流 JSON、人工审核界面。

## 技术栈

| 组件 | 用途 | 当前状态 |
| --- | --- | --- |
| Python 3.10+ / FastAPI | HTTP API | 已启用（仅健康检查） |
| PostgreSQL 16 | 业务数据存储 | Docker Compose 已配置，应用暂未连接 |
| n8n | 邮件接入与流程编排 | Docker Compose 已配置，工作流待实现 |
| pytest / httpx | 自动化测试 | 已启用 |

## 目录结构

```text
ai-support-workflow/
├── app/
│   ├── main.py              # FastAPI 应用入口
│   ├── config.py            # 基于 pydantic-settings 的配置
│   ├── api/routes/health.py # GET /health
│   ├── core/                # 后续：日志、异常处理
│   ├── db/                  # 后续：SQLAlchemy 模型与迁移
│   ├── schemas/             # 后续：Pydantic 模型
│   └── services/            # 后续：接入/规则/分流/审核/发送/告警
├── tests/test_health.py     # 基础测试
├── n8n/                     # 后续：n8n 工作流 JSON 占位
├── 架构图/                   # 业务流程图（01-04）
├── .github/workflows/ci.yml # GitHub Actions CI
├── docker-compose.yml       # PostgreSQL + n8n（本地演示）
├── requirements.txt
├── pyproject.toml           # 项目元数据与 pytest 配置
├── .env.example
└── README.md
```

## 本地运行

### 1. 启动数据库与 n8n（可选，本阶段接口不依赖数据库）

```bash
cp .env.example .env   # 可选，使用演示默认值
docker compose up -d
```

- PostgreSQL：`localhost:5432`（用户/密码/库名默认均为演示值，见 `.env.example`）
- n8n：http://localhost:5678 （本地演示未开启登录鉴权）

> 生产环境必须启用 n8n 鉴权、修改数据库口令，并限制端口暴露范围。

### 2. 启动 API

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

验证：

```bash
curl http://127.0.0.1:8000/health
```

预期输出：

```json
{"status":"ok","app":"AI Support Workflow","version":"0.1.0","environment":"local"}
```

接口文档：http://127.0.0.1:8000/docs

### 3. 运行测试

```bash
pytest -v
```

### 本地验证结果（2026-11-11）

- 环境：Python 3.10.12、FastAPI 0.162.4、Starlette 1.7.0、pydantic 2.14.3
- `pytest -v`：**4 passed**（0.51s）
- `uvicorn app.main:app` + `curl http://127.0.0.1:8000/health`：HTTP 200，返回体与预期一致
- `docker compose config -q`：语法校验通过（未实际启动容器）

## 配置说明

配置通过环境变量或 `.env` 读取（见 `app/config.py` 与 `.env.example`），默认值全部为本地演示配置：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_NAME` | `AI Support Workflow` | 应用名称 |
| `APP_ENV` | `local` | 运行环境标识 |
| `APP_VERSION` | `0.1.0` | 版本号 |
| `DATABASE_URL` | `postgresql://demo:demo@localhost:5432/ai_support` | 本地演示连接串 |

`.env` 已被 `.gitignore` 忽略，请勿提交真实密钥。

## CI

`.github/workflows/ci.yml` 在 push 到 `main` 及 Pull Request 时：

1. 安装 `requirements.txt` 依赖；
2. 在 Python 3.10 / 3.11 / 3.12 上运行 `pytest -v`。

本阶段测试不依赖 PostgreSQL，因此 CI 未启动数据库服务。

## 计划中的状态流转（后续阶段）

```text
received → triaged → pending_review → approved → sent
                                    ↘ rejected
                                    ↘ takeover（人工接管）
                     ↘ failed / send_uncertain（异常分支）
```

## 后续待实现模块

1. **数据层**：SQLAlchemy 模型（emails、tickets、review_records、send_records、error_logs）、Alembic 迁移、`/ready` 就绪探针
2. **邮件接入与去重**（图 1）：n8n 邮件 Webhook、邮件登记、去重判定
3. **规则与 AI 分流**（图 2）：高风险规则检查、模拟 AI 分类（类别/摘要/风险/置信度/建议回复）、输出校验
4. **人工审核与发送**（图 3）：审核 API（批准/修改后批准/拒绝/接管）、发送前检查、发送结果记录（模拟）
5. **异常处理与提醒**（图 4）：安全重试、failed/send_uncertain 状态、超时提醒（模拟 Slack/邮件通知）
6. **n8n 工作流**：`n8n/` 下工作流 JSON 导出与导入说明
7. **安全加固**：鉴权、审计日志、限流、敏感数据脱敏
