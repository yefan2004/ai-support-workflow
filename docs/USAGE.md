# 使用说明

> 更新：2026-11-19
> 端口与职责以 [docs/PORTS.md](PORTS.md) 为准。本文说明当前环境怎么启动、怎么跑、怎么排查。

## 1. 先认清两套栈

| | 主栈：真实链路 | Demo 栈：离线子集 |
| --- | --- | --- |
| 组成 | `ai-support-db` + `ai-support-n8n-manual-stage6` + 本地 FastAPI + Streamlit | `ai-support-demo-db` + `ai-support-demo-api` + `ai-support-demo-ui` |
| 端口 | 5432 / 5679 / 8014 / 8504 | 8020 / 8503（DB 仅内部网络） |
| 邮件入口 | n8n 通过 IMAP 读取 163 测试邮箱 | API 写入合成邮件 |
| AI Provider | 邮件 `process` 按 `.env`，当前为 `deepseek` | 固定 `mock` |
| 适合 | 真实链路、录屏、端到端验证 | 无需邮箱快速体验、审核流程演示 |

两套栈共用业务代码，但不要混用端口和目标地址。

## 2. 主栈使用

### 2.1 启动数据库

```bash
cd /home/leo/Documents/ai-support-workflow
docker compose up -d db
docker exec ai-support-db pg_isready -U demo -d ai_support
```

- 默认 `docker compose up -d` 只启动 `db`。
- 5678 的旧 compose n8n 已退役，只在 `--profile legacy` 下存在；不要默认启动。
- 当前 n8n 是 `ai-support-n8n-manual-stage6`，端口 5679，不由根 compose 管理。

### 2.2 启动主 FastAPI（8014）

```bash
source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8014 --reload
```

检查：

```bash
curl -sS http://127.0.0.1:8014/health
curl -sS http://127.0.0.1:8014/api/v1/emails | head -c 300
```

说明：

- 必须监听 `0.0.0.0`，否则 5679 的 n8n 容器访问不到宿主机。
- 主栈邮件 `process` 读取 `.env`；当前 `AI_PROVIDER=deepseek`。
- `/api/v1/ai/triage` 是独立的 Mock 关键词接口，不读取 `AI_PROVIDER`。

### 2.3 启动主 Streamlit（8504）

```bash
source .venv/bin/activate
API_BASE_URL=http://127.0.0.1:8014 \
  streamlit run frontend_app.py --server.port 8504
```

打开 `http://127.0.0.1:8504`，语言切到中文，查看“待审核”列表。

> Demo UI 固定 8503；主栈用 8504，两者不冲突。不要占用 8503 启动主栈。

### 2.4 n8n（5679）

- 地址：`http://127.0.0.1:5679`
- 当前 workflow：`stage6-empty-workflow`
- 状态：`active=true`
- 触发：Schedule Trigger，每 1 分钟
- 邮箱：163 测试邮箱，凭据保存在 n8n UI，不在仓库

当前邮件主链路：

```text
Schedule Trigger
  → GetEmailsList email (IMAP)
  → Code in JavaScript
  → Register Email (8014 /api/v1/emails)
  → Switch
      → Process Email (8014 /api/v1/emails/{id}/process)
      → Get Existing Task (8014 /api/v1/emails/{id})
```

一句话：Register Email → Switch → Process/Get。

注意：

- **不要把 AI 节点插回 Register Email 和 Switch 之间。** AI 响应会覆盖 `status`，Switch 会走 `Get Existing Task`，任务就不会 process。
- AI 分类由 `process` 负责；`/api/v1/ai/triage` 是独立的 HTTP 接口。
- 在 n8n UI 可以手动 `Execute Workflow`；生产式定时已开启。
- 停止自动轮询：在 n8n UI 把 workflow 切换为 inactive；不要直接删容器。

### 2.5 发一封新邮件测试

1. 用另一个邮箱给专用 163 测试邮箱发信。
2. 等最多 1 分钟，或到 n8n UI 手动执行 workflow。
3. 到 `http://127.0.0.1:8504` 查看任务。
4. 普通咨询预期进入 `awaiting_review`；退款/投诉等命中规则的任务预期 `human_takeover`。

> 主库中已有历史测试任务，其中可能包含 `processing`；当前没有自动重试/超时回收。process 返回 500 时，任务可能停在 `processing`，需要人工处理测试数据或使用新的测试库。

## 3. AI 分诊接口（独立使用）

主栈 8014 和 Demo 8020 都提供同一个 Mock 分诊接口：

```bash
curl -X POST http://127.0.0.1:8014/api/v1/ai/triage \
  -H 'Content-Type: application/json' \
  -d '{"subject":"换货","body":"尺码小了"}'
```

返回：

```json
{
  "intent": "exchange",
  "urgency": "medium",
  "confidence": 0.9,
  "summary": "客户提出换货请求，建议人工确认尺码和库存。"
}
```

说明：

- 当前是关键词 Mock，不调用 DeepSeek/OpenAI；不读取 `AI_PROVIDER`。
- 该接口不属于 n8n 邮件主链路；邮件分类由 `process` 完成。
- 可用 `curl -X POST http://127.0.0.1:8020/api/v1/ai/triage ...` 验证 Demo 栈。

## 4. Demo 栈使用（无邮箱）

```bash
docker compose -p ai-support-demo -f docker-compose.demo.yml build
docker compose -p ai-support-demo -f docker-compose.demo.yml up -d --no-build
docker compose -p ai-support-demo -f docker-compose.demo.yml ps
```

| 服务 | 地址 |
| --- | --- |
| Demo FastAPI | `http://127.0.0.1:8020` |
| API 文档 | `http://127.0.0.1:8020/docs` |
| Demo Streamlit | `http://127.0.0.1:8503` |
| Demo PostgreSQL | 仅 Compose 内部网络 |

创建一封合成邮件并 process：

```bash
CREATE_RESPONSE=$(curl -sS -X POST http://127.0.0.1:8020/api/v1/emails \
  -H 'Content-Type: application/json' \
  -d '{"mailbox_id":"demo@example.com","message_id":"<demo-usage-001@example.com>","subject":"产品功能咨询","body":"请问这款伺服电机支持 48V 供电吗？"}')

TASK_ID=$(printf '%s' "$CREATE_RESPONSE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
echo "task_id=$TASK_ID"

curl -sS -X POST "http://127.0.0.1:8020/api/v1/emails/$TASK_ID/process"
```

预期返回 `status: "awaiting_review"`，然后到 `http://127.0.0.1:8503` 查看待审核任务。

停止：

```bash
docker compose -p ai-support-demo -f docker-compose.demo.yml down
# 保留数据卷；不要加 -v，除非确认要删除 Demo 数据
```

## 5. n8n 节点 URL

Docker 中的 n8n（5679 容器）：

```text
Register Email:   http://172.17.0.1:8014/api/v1/emails
Process Email:    http://172.17.0.1:8014/api/v1/emails/{{ $json.id }}/process
Get Existing Task: http://172.17.0.1:8014/api/v1/emails/{{ $json.id }}
```

本机运行的 n8n 把 `172.17.0.1` 换成 `127.0.0.1`。

不要使用：

```text
http://localhost:8014          # n8n 容器里的 localhost 是容器自己
http://127.0.0.1:8020          # Demo API，不是主栈 n8n 的目标
/api/v1/ai_triage              # 错误路径
```

## 6. 验证命令

```bash
# 端口
ss -ltnp | grep -E ':(5432|5679|8014|8020|8503|8504)\b'

# 容器
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

# 主 API / Demo API / n8n
curl -fsS http://127.0.0.1:8014/health
curl -fsS http://127.0.0.1:8020/health
curl -fsS http://127.0.0.1:5679/healthz

# n8n 容器 -> 主 API
docker exec ai-support-n8n-manual-stage6 \
  wget -qO- http://172.17.0.1:8014/health

# n8n workflow 列表
docker exec ai-support-n8n-manual-stage6 n8n list:workflow
```

期望：

- 5432、5679、8014、8020、8503 存在；8504 仅在启动主 Streamlit 时出现。
- 5678 不出现。
- 主 API 与 n8n 均健康。

## 7. 常见问题

| 现象 | 处理 |
| --- | --- |
| 5678 又出现 | 有人启用了 legacy profile：`docker compose --profile legacy up -d n8n`；默认不要启动 |
| 8503 被占用 | 8503 属于 Demo UI；主栈 Streamlit 用 8504 |
| 主 API 8014 从 n8n 访问不到 | 确认 uvicorn 监听 `0.0.0.0`；确认宿主机防火墙；容器网关用 `docker exec ... ip route` 查 |
| workflow 不自动跑 | n8n UI 检查是否 active；`n8n list:workflow`；Schedule Trigger 为 1 分钟 |
| 任务一直 `received` | workflow 是否走到了 Process Email；检查 Switch 是否收到 `status=received` |
| 任务一直 `processing` | process 发生异常且没有自动回收；检查 8014 日志、DeepSeek Key/模型/网络；当前不会自动重试 |
| Process Email 500 | 看 8014 的 traceback；用合成邮件单独测 `POST /api/v1/emails/{id}/process`；确认 `.env` 的 DeepSeek 配置 |
| AI 节点 404 | 该节点已从主链路移除；不要插回 Register 和 Switch 之间 |
| 审核通过后以为已发送 | 系统没有发送能力；`approved` 只代表人工审核通过 |

## 8. 当前边界

- 无生产级鉴权；`reviewed_by` 是客户端自报的演示值。
- 无真实邮件发送、无发送状态、无 SMTP。
- 无分页、无多租户、无发件人字段、无草稿历史。
- 不宣称生产稳定性；无自动重试、`processing` 超时回收、exactly-once。
- DeepSeek 只做过有限合成数据验证；启用后邮件内容会发给第三方。
- 公开演示只用专用测试邮箱和合成数据。
- 当前主库已有历史测试任务，可能包含 `processing`；新的测试邮件仍会创建新任务，旧任务不会自动回收。

## 9. 相关文档

- [端口与职责唯一权威表](PORTS.md)
- [给其他 AI 的交接说明](AI_CONTEXT.md)
- [90 秒录屏指南](../RECORDING_GUIDE.md)
- [项目 README](../README.md)
- [n8n 早期 Webhook 草稿说明](n8n-integration.md)
- [项目路线图](PROJECT_ROADMAP.md)
