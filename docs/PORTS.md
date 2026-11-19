# 端口与职责（唯一权威表）

> 更新：2026-11-19
> 本表是当前环境的唯一端口口径。README、录屏指南、历史文档与本表冲突时，以本表为准。
> 具体启动/使用步骤见 [USAGE.md](USAGE.md)；给其他 AI 的交接说明见 [AI_CONTEXT.md](AI_CONTEXT.md)。

## 当前端口

| 端口 | 服务 | 职责 | 访问地址 | 状态 |
| --- | --- | --- | --- | --- |
| 5432 | `ai-support-db` | 主库 `ai_support` / `ai_support_test` | `localhost:5432` | healthy |
| 5679 → 容器 5678 | `ai-support-n8n-manual-stage6` | **唯一保留的 n8n**，工作流编排 | `http://127.0.0.1:5679` | Up |
| 8014 | 主 FastAPI（`uvicorn --reload`） | 主库 API：`/api/v1/emails`、`/api/v1/ai/triage` | `http://127.0.0.1:8014` | Up |
| 8020 → 容器 8000 | `ai-support-demo-api` | 离线 Demo API，固定 Mock | `http://127.0.0.1:8020` | healthy |
| 8503 → 容器 8501 | `ai-support-demo-ui` | 离线 Demo 审核台 | `http://127.0.0.1:8503` | healthy |
| 8504 | 主 Streamlit（录制时启动） | 主库审核台，避免与 Demo UI 抢 8503 | `http://127.0.0.1:8504` | 未启动 |
| 内部 5432 | `ai-support-demo-db` | Demo 专用库 `ai_support_demo` | 仅 `ai-support-demo_default` 网络 | healthy |

### 已退役 / 已清理

- **5678**：旧的 `n8n` 与 `ai-support-n8n` 容器已删除；根 `docker-compose.yml` 的 n8n 服务改为 `profiles: ["legacy"]`，默认不启动。需要临时启用时才用：
  ```bash
  docker compose --profile legacy up -d n8n
  ```
- **8000、8011–8018、8502**：2026-11-19 已清理的 `/tmp` e2e 残留进程，不要再作为服务地址使用。
- 数据卷未删除：`n8n_data`、`ai-support-workflow_n8n_data` 仍保留，避免误删历史数据。

## AI Provider 口径

- **主栈 8014**：邮件 `process` 由 `.env` 控制，当前为 `AI_PROVIDER=deepseek`。
- **Demo 8020**：compose 固定 `AI_PROVIDER=mock`，不读取宿主 `.env`，不传 DeepSeek Key。
- **`/api/v1/ai/triage`**：目前 8014 和 8020 都是独立的 Mock 关键词路由，不读取 `AI_PROVIDER`；真实模型接入是后续工作。
- 两套栈不要混用同一条链路。

## 5679 当前 workflow 状态（重要）

当前 5679 只有一个 workflow：

```text
name: stage6-empty-workflow
active: true
```

连接顺序：

```text
Schedule Trigger (1 min)
  → GetEmailsList email (IMAP)
  → Code in JavaScript
  → Register Email (POST http://172.17.0.1:8014/api/v1/emails)
  → Switch
      → Process Email
      → Get Existing Task
```

说明：

- workflow 已激活，Schedule Trigger 每分钟运行一次。
- AI 节点已从邮件主链路移除；邮件分类由 `/api/v1/emails/{id}/process` 负责。
- `/api/v1/ai/triage` 是独立的 Mock HTTP 接口，不属于邮件主链路；不要把 AI 节点插回 Register Email 和 Switch 之间，否则 AI 响应会覆盖 `status`，Switch 会走错分支。
- 7 封邮件是历史记录，当前 workflow 仍可重新读取 INBOX；已有测试任务中可能包含 `processing`，process 错误不会自动重试或自动回收。
- 如果要在 n8n UI 重建 workflow，保持：Register Email → Switch → Process/Get。

## n8n → FastAPI 的最终 URL

- **Docker 中的 n8n（当前 5679 容器）**：
  ```text
  邮件主链路：http://172.17.0.1:8014/api/v1/emails
  邮件处理：  http://172.17.0.1:8014/api/v1/emails/{id}/process
  独立 AI：   http://172.17.0.1:8014/api/v1/ai/triage
  ```
- **本机运行的 n8n**：
  ```text
  邮件主链路：http://127.0.0.1:8014/api/v1/emails
  邮件处理：  http://127.0.0.1:8014/api/v1/emails/{id}/process
  独立 AI：   http://127.0.0.1:8014/api/v1/ai/triage
  ```
- 不要使用 `http://demo-api:8000/ai/triage`，也不要使用 `/api/v1/ai_triage`。

## 快速核对

```bash
ss -ltnp | grep -E ':(5432|5679|8014|8020|8503|8504)\b'
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
docker exec ai-support-n8n-manual-stage6 \
  wget -qO- http://172.17.0.1:8014/health
```

预期 5679、5432、8014、8020、8503 存在；8504 仅在启动主 Streamlit 时出现；5678 不应出现。
