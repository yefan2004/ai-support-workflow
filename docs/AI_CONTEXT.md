# AI 交接说明（当前事实）

> 更新时间：2026-11-19
> 给其他 AI / 开发者的第一手上下文。端口以 [PORTS.md](PORTS.md) 为准，操作步骤见 [USAGE.md](USAGE.md)。

## 0. 一句话理解

这是一个 **AI 辅助邮件分诊 + 人工审核** 项目，不是自动回复系统：

- 主栈跑真实链路：163 测试邮箱 → n8n 5679 → FastAPI 8014 → PostgreSQL 5432 → Streamlit 8504。
- Demo 栈跑离线审核子集：FastAPI 8020 + Streamlit 8503 + 内部 PostgreSQL。
- AI 只生成分类、摘要和草稿；人工点批准；系统没有发送邮件能力。
- 当前 `/api/v1/ai/triage` 是关键词 Mock，不等于真实的 DeepSeek 分诊。

## 1. 当前运行环境

| 端口 | 服务 | 说明 |
| --- | --- | --- |
| 5432 | `ai-support-db` | 主库 `ai_support` / `ai_support_test` |
| 5679 | `ai-support-n8n-manual-stage6` | 唯一保留的 n8n |
| 8014 | 主 FastAPI（本机 uvicorn `--reload`） | 主库 API |
| 8020 | `ai-support-demo-api` | Demo API，固定 Mock，绑定 `127.0.0.1` |
| 8503 | `ai-support-demo-ui` | Demo Streamlit |
| 8504 | 主 Streamlit（录制时启动） | 主库审核台，当前未启动 |
| 内部 5432 | `ai-support-demo-db` | Demo 专用库，仅内部网络 |

已退役：

- 5678 的 `n8n` 与 `ai-support-n8n` 容器已删除；根 `docker-compose.yml` 的 n8n 服务用 `profiles: ["legacy"]`，默认不启动。
- 8000、8011–8018、8502 是已清理的历史 e2e 残留端口。

## 2. 代码地图

| 文件 | 作用 |
| --- | --- |
| `app/main.py` | FastAPI 入口；`ai` router 在这里加一次 `/api/v1` 前缀 |
| `app/api/routes/ai.py` | `POST /ai/triage` → 最终路径 `/api/v1/ai/triage`；Mock + exchange |
| `app/api/routes/emails.py` | 登记、列表、详情、process、review |
| `app/services/triage.py` | 规则检查 → Provider → 状态流转 |
| `app/services/review.py` | approve / reject / takeover |
| `app/services/rules.py` | 关键词风险规则 |
| `app/providers/ai/` | Mock / DeepSeek Provider |
| `app/db/models.py` | `EmailTask` + 去重唯一约束 |
| `frontend_app.py` | 双语 Streamlit 审核台 |
| `docker-compose.yml` | 主库；n8n 为 legacy profile |
| `docker-compose.demo.yml` | Demo 三件套 |
| `n8n/workflows/` | 只有早期 Webhook 草稿；真实 workflow 在 n8n UI / 5679 数据卷 |

## 3. 当前 n8n workflow

5679 只有一个 workflow：

```text
name: stage6-empty-workflow
active: true
```

链路：

```text
Schedule Trigger (1 min)
  → GetEmailsList email (IMAP)
  → Code in JavaScript
  → Register Email (http://172.17.0.1:8014/api/v1/emails)
  → Switch
      → Process Email (http://172.17.0.1:8014/api/v1/emails/{id}/process)
      → Get Existing Task (http://172.17.0.1:8014/api/v1/emails/{id})
```

关键点：

- **AI 节点已从邮件主链路移除。** 之前 AI 节点位于 Register 和 Switch 之间，AI 响应覆盖了 `status`，导致 Switch 始终走 `Get Existing Task`，任务不会 process。
- `/api/v1/ai/triage` 是独立接口，不参与邮件主链路；邮件分类由 `process` 负责。
- 如果重建 workflow，保持 `Register Email → Switch → Process/Get`。
- workflow 每分钟执行一次；要停止轮询，在 n8n UI 切换 inactive。

## 4. AI Provider 口径

- 主栈 8014：邮件 `process` 读取 `.env`，当前 `AI_PROVIDER=deepseek`。
- Demo 8020：`docker-compose.demo.yml` 固定 `AI_PROVIDER=mock`，不读取宿主 `.env`。
- `/api/v1/ai/triage`：8014 和 8020 都是独立的 Mock 关键词接口，不读取 `AI_PROVIDER`。
- 不要把“Demo 是 Mock”误解为“主栈也是 Mock”。

## 5. 已验证 / 未验证

本会话已验证：

- `14 passed, 1 warning`：AI 分诊、health、UI 等不依赖数据库的测试。
- 8014、8020、5679 的健康检查通过。
- n8n 5679 的 workflow 已激活，`n8n list:workflow --active=true` 能看到它。
- n8n 邮件链路已能走到 Process（修复前会卡在 Switch）。
- 合成邮件在临时 18014 实例上 process 成功，返回 `awaiting_review`。
- `/api/v1/ai/triage` 对“换货/尺码小了”返回 `exchange`。

历史记录、本次未重跑：

- 真实 163 IMAP 曾读取 7 封测试邮件。
- 隔离 pytest 历史记录为 257 passed / 1 warning / 0 failed / 0 skipped。
- DeepSeek 只做过有限合成数据联调。

## 6. 已知问题

- 已有测试任务在 `/process` 返回过 500，并停留在 `processing`；当前没有自动重试或 `processing` 超时回收。
- 主库中已有历史测试任务，可能包含多个 `processing`；这不代表新邮件一定失败，但演示前应使用干净测试库或清理测试数据。
- workflow 已激活，但真实 7 封链路的“当前可复现性”没有重新跑完整验证；不要把历史 7 封当成当前结果。
- 无邮件发送、无生产鉴权、无分页、无多租户、无发件人字段、无草稿历史。
- 不宣称生产稳定性；DeepSeek 启用后邮件内容会发给第三方。

## 7. 常用命令

```bash
# 主 API
curl -fsS http://127.0.0.1:8014/health

# Demo API
curl -fsS http://127.0.0.1:8020/health

# n8n
curl -fsS http://127.0.0.1:5679/healthz
docker exec ai-support-n8n-manual-stage6 n8n list:workflow --active=true

# n8n 容器 → 主 API
docker exec ai-support-n8n-manual-stage6 \
  wget -qO- http://172.17.0.1:8014/health

# AI 分诊
curl -X POST http://127.0.0.1:8014/api/v1/ai/triage \
  -H 'Content-Type: application/json' \
  -d '{"subject":"换货","body":"尺码小了"}'
```

## 8. 给其他 AI 的约束

- 不要假设主栈是 Mock；先检查 `.env` 和 `AI_PROVIDER`。
- 不要把 n8n 指向 Demo 8020；主栈 n8n 应指向 8014。
- 不要把 AI 节点插回 Register 和 Switch 之间。
- 不要使用 `/api/v1/ai_triage` 或 `/api/v1/api/v1/...`。
- 不要声称邮件已发送；`approved` 只代表人工审核通过。
- 不要把历史 7 封 / 257 当作本次重跑结果。
- 不要提交 `.env`、IMAP 授权码、API Key；不要把真实客户邮件用于公开演示。

## 9. 相关文档

- [端口与职责](PORTS.md)
- [使用说明](USAGE.md)
- [录屏指南](../RECORDING_GUIDE.md)
- [项目 README](../README.md)
- [早期 n8n Webhook 草稿说明](n8n-integration.md)
- [项目路线图](PROJECT_ROADMAP.md)
