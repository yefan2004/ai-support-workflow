# n8n 集成（阶段 6 第一小块）

> 状态：**待导入验证的 n8n 工作流草稿**。
> JSON 能被静态解析，不代表已成功导入 n8n、节点参数已兼容当前 n8n、表达式已执行、错误分支已验证、Webhook 已可访问，或 n8n 已能访问 FastAPI。

## 当前范围

目标链路：

```text
测试 JSON
  → n8n Webhook
  → POST /api/v1/emails
  → 根据登记响应的 status 分支
  → 必要时调用 process 或 GET
  → 返回统一 JSON
```

本阶段只使用现有 FastAPI 和 Mock AI，不接入真实邮箱、DeepSeek、OpenAI、Claude 或 Slack，不发送邮件，不调用 review API，不自动 approve，不新增状态、数据库表、模型或迁移。

## 文件

```text
n8n/workflows/06_test_webhook_triage.json   最小工作流草稿
examples/n8n/normal-product-question.json   合成普通咨询示例
examples/n8n/refund-request.json            合成退款示例
docs/n8n-integration.md                     详细 API 契约、错误分支和网络说明
```

没有 duplicate 示例文件。重复测试时重复发送 `normal-product-question.json`，保持相同的 `mailbox_id` 和 `message_id`。

## API 字段

登记请求只能包含四个字段：

```json
{
  "mailbox_id": "test@example.com",
  "message_id": "<stage6-demo-001@example.com>",
  "subject": "示例主题",
  "body": "示例正文（合成数据）"
}
```

- `task_id` 来自登记响应的 `id`；
- 不发送 `from`、`to`、`test_case` 或其他未定义字段；
- 首次登记通常返回 `201`、`status=received`；
- 重复登记返回 `200`、`duplicate=true`，`status` 是已有任务当前状态，不保证仍为 `received`；
- 不因 `duplicate=true` 创建新任务，也不宣称 exactly-once。

## 状态分支

| 登记响应的 status | 动作 |
| --- | --- |
| `received` | 调用一次 process |
| `processing` / `awaiting_review` / `approved` / `rejected` / `human_takeover` / `failed` | 不调用 process，调用一次 GET |
| 未知值 | 停止后续 API 调用，返回 `UNKNOWN_TASK_STATUS` 和 `manual_inspection` |

`duplicate=true` 也按上述状态分支处理：`received` 仍调用一次 process；其他已知状态只调用 GET。未知状态不调用 process。

## 错误与重试边界

- process `409`：保留 `task_id` 和 `duplicate`，返回 `PROCESSING_CONFLICT`，不自动重试，不循环调用；
- process `502`：返回 `PROVIDER_FAILURE`，保留 API `detail` 和 `task`（如有），不重试；
- process `503`：返回 `DATABASE_OR_SERVICE_UNAVAILABLE`，任务状态可能不确定，不自动重试；提示人工 GET；
- process `500`：返回 `UNEXPECTED_PROCESSING_ERROR`，任务可能仍为 `processing`，不自动重试；
- process/GET 网络错误或超时：返回 `NETWORK_ERROR`，`api_status=null`，不伪造 FastAPI 状态码，不自动重试；
- GET `404`：`TASK_NOT_FOUND`；GET `503`：`QUERY_UNAVAILABLE`；
- API 没有 `Retry-After`，不要自行发明等待时间；
- 不实现自动重试、processing 超时回收或 exactly-once。

## 状态语义

- `awaiting_review`：等待人工审核；
- `human_takeover`：需要人工接管；
- `approved`：审核已批准，但**不表示邮件已发送**；
- `rejected`：审核拒绝；
- `processing`：仍在处理或查询到处理中；
- `failed`：处理失败。

禁止声称邮件已发送、通知已发送、人工已收到、已完成外部投递或发送成功。当前没有真实发送能力。

## 数据与安全

- API 返回可能包含邮件正文和草稿；只能使用合成测试数据；
- 当前没有生产级鉴权；
- 不修改 `ai_support`，不执行迁移，不运行数据库测试；
- 联调必须显式使用 `ai_support_test`，不要依赖当前已有 uvicorn 进程；
- 不把密码、完整连接串、`.env` 或真实邮件内容放入工作流或 Git。

## n8n 与网络限制

- 当前 Compose 只有 `db` 和 `n8n`，没有 FastAPI service；
- n8n 容器内的 `localhost` 指向 n8n 容器自身，不是宿主机；
- `FASTAPI_BASE_URL` 只是配置设计，实际注入方式尚未验证；
- Linux Docker Engine 默认不一定能解析 `host.docker.internal`；可能需要 `extra_hosts`、宿主机网关 IP，或将 FastAPI 加入 Compose；
- FastAPI 通常需要监听容器可访问的地址，并确认防火墙；
- 当前使用 `n8nio/n8n:latest`，版本未固定；节点字段、错误处理选项、Switch/Respond to Webhook 行为和表达式都需要导入后验证；
- 不能假设 n8n 已能访问 FastAPI，也不能假设 Webhook 已可访问。

## 测试数据与预期

- `normal-product-question.json`：基于当前 Mock AI/规则，首次提交的**预期**是 `awaiting_review`；未联调验证。
- `refund-request.json`：正文包含退款请求，**预期**是 `human_takeover`；表示人工接管，不表示已发送通知或邮件；未联调验证。

## 验证状态

本轮只做了静态检查：JSON 可解析、无真实凭据、无 Gmail/Outlook/DeepSeek/OpenAI/Claude/Slack/邮件发送节点、无 review/approve/自动重试逻辑、登记字段只有四个、保留 `task_id`/`duplicate`、`received` 才调用 process、其他已知状态调用 GET、未知状态停止、409 不进入重试循环、示例为合成数据。

**静态检查不等于错误分支已通过实际联调验证。** 后续需要在受控测试环境中单独验证 404、409、502、503、网络超时、重复提交、n8n 导入兼容性、Webhook 可访问性和 n8n 到 FastAPI 的网络路径。完整说明见 `docs/n8n-integration.md`。
