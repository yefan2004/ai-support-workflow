# n8n 集成说明（阶段 6 第一小块）

> 状态：**待导入验证的 n8n 工作流草稿**。
> 工作流 JSON 可以被静态解析，不等于已成功导入 n8n、节点参数已兼容当前 n8n、表达式已执行、HTTP 错误分支已验证，也不等于 Webhook 已可访问或 n8n 已能访问 FastAPI。

## 1. 阶段 6 第一小块的严格范围

目标链路：

```text
测试 JSON
  → n8n Webhook
  → POST /api/v1/emails
  → 根据登记响应的 status 分支
  → 必要时调用 process 或 GET
  → 返回统一 JSON
```

本阶段包含：

- 一个最小 n8n Webhook 工作流草稿；
- 登记、process、GET 三个现有 FastAPI 接口的调用编排；
- 登记后的状态分支；
- 统一的成功/失败响应结构；
- 两个合成测试 JSON；
- 静态 JSON 与内容检查。

本阶段明确不包含：

- Gmail、Outlook 或其他真实邮箱；
- DeepSeek、OpenAI、Claude 或其他真实 AI；
- Slack、真实通知或邮件发送；
- 调用 review API、自动 approve；
- 新增状态、数据库表、数据库模型或 Alembic 迁移；
- 修改 `app/` 下的业务代码；
- 自动重试、processing 超时回收；
- 端到端 exactly-once；
- 对 `ai_support` 的任何写入、迁移或清理。

## 2. 本次文件

```text
n8n/workflows/06_test_webhook_triage.json   工作流草稿
n8n/README.md                               更新后的 n8n 使用说明
docs/n8n-integration.md                     本文件
examples/n8n/normal-product-question.json   合成普通咨询示例
examples/n8n/refund-request.json            合成退款示例
```

没有新增 `duplicate` 示例文件。重复提交测试直接重复发送 `normal-product-question.json`，并保持相同的 `mailbox_id` 和 `message_id`。

## 3. 实际 API 契约

### 3.1 登记：`POST {FASTAPI_BASE_URL}/api/v1/emails`

请求 JSON **只能包含**以下四个字段：

```json
{
  "mailbox_id": "test@example.com",
  "message_id": "<stage6-demo-001@example.com>",
  "subject": "示例主题",
  "body": "示例正文（合成数据）"
}
```

- `mailbox_id`：必填，非空字符串；
- `message_id`：必填，非空字符串；
- `subject`：可选，缺省空字符串；
- `body`：可选，缺省空字符串；
- 不发送 `from`、`to`、`test_case` 或其他未在 API schema 中定义的字段。

成功响应（`EmailTaskResponse`）包含：

- `id`：任务 ID；
- `duplicate`：是否重复登记；
- `status`：当前任务状态；
- 以及 `mailbox_id`、`message_id`、`subject`、`body`、`created_at`、`updated_at`。

首次创建返回 `201`，`status` 通常为 `received`。重复登记返回 `200`，`duplicate=true`，`status` 是已有任务当前状态，不保证仍是 `received`。**task_id 来自响应的 `id`，API 没有 `task_id` 字段。**

登记阶段可能的错误：

- `422`：字段缺失或空白；不调用 process/GET；
- `500`：登记 API 未预期错误；不猜测任务是否创建；
- `503`：登记路径当前没有专门的 503 响应映射；如出现，按服务不可用处理，不猜测任务是否创建；
- 网络错误或超时：不自动再次提交，不猜测任务是否创建。

### 3.2 处理：`POST {FASTAPI_BASE_URL}/api/v1/emails/{id}/process`

- 路径参数是登记响应的 `id`；
- **无请求体**；
- 只在登记响应 `status` 为 `received` 时调用一次；
- 不启用自动重试。

成功返回 `200`，响应是完整的 `EmailTaskDetail`，包含 `status`、`category`、`summary`、`risk_level`、`risk_reason`、`draft_body`、`requires_human`、`processed_at`、`failure_reason`、审核字段及时间字段。

最终状态可能是：

- `awaiting_review`：普通结果且存在可审核草稿，等待人工审核；
- `human_takeover`：规则命中、高风险、退款/投诉、无可用草稿等，需要人工接管。

错误/冲突：

- `404`：任务不存在；
- `409`：当前为 `processing`、终态，或最终写回冲突；不自动重试；
- `502`：Provider 预期错误或输出无效，任务已标记 `failed`；不自动重试；
- `503`：数据库操作失败，任务状态可能不确定；不自动重试；
- `500`：未预期处理错误；任务可能仍为 `processing`；
- 网络错误或超时：不伪造 API 状态码，不自动重试。

代码中没有 `Retry-After` 或其他重试提示头。

### 3.3 查询：`GET {FASTAPI_BASE_URL}/api/v1/emails/{id}`

- 只读，不修改任务状态；
- 用于登记响应为其他已知状态时获取当前详情；
- 成功返回 `200` 和完整 `EmailTaskDetail`；
- 包含正文、分类结果、风险信息、草稿和审核信息；
- `404`：任务不存在；
- `503`：查询不可用；
- 其他错误或网络错误：返回统一失败结构，不自动重试。

## 4. 工作流节点顺序与字段映射

节点顺序：

```text
Webhook
  → Build Register Body
  → Register Email
  → Normalize Register
  → Branch by Register Status
      ├─ process → Process Task → Normalize Process or Query → Respond to Webhook
      ├─ query   → Get Task     → Normalize Process or Query → Respond to Webhook
      └─ stop    → Respond to Webhook
```

| 节点 | 作用 | 方法与 URL / 数据 |
| --- | --- | --- |
| `Webhook` | 接收测试 JSON | `POST /webhook/test-webhook-triage`（生产路径；测试模式使用 `/webhook-test/...`） |
| `Build Register Body` | 构造登记请求 | 从 Webhook 的 `$json.body` 读取四个字段，`subject`/`body` 缺省为空字符串 |
| `Register Email` | 登记 | `POST {FASTAPI_BASE_URL}/api/v1/emails`；JSON body 只有四个 API 字段 |
| `Normalize Register` | 读取 `id`、`duplicate`、`status` | 根据登记状态设置 `process` / `query` / `stop` 分支 |
| `Branch by Register Status` | 分支 | `received` → process；其他已知状态 → query；未知状态 → stop |
| `Process Task` | 处理 | `POST {FASTAPI_BASE_URL}/api/v1/emails/{id}/process`；无请求体；只调用一次 |
| `Get Task` | 查询 | `GET {FASTAPI_BASE_URL}/api/v1/emails/{id}`；只调用一次 |
| `Normalize Process or Query` | 统一响应 | 保留 `task_id`、`duplicate`、上游 HTTP 状态和错误信息 |
| `Respond to Webhook` | 返回 JSON | 成功直接返回 `EmailTaskDetail`；失败返回统一错误结构 |

登记请求字段映射必须严格保持为：

```text
mailbox_id  <- Webhook body.mailbox_id
message_id  <- Webhook body.message_id
subject     <- Webhook body.subject，缺省 ""
body        <- Webhook body.body，缺省 ""
```

`FASTAPI_BASE_URL` 只是配置设计，当前尚未实际验证注入方式。建议由 n8n 环境变量或工作流固定配置提供，不要从 Webhook 请求体接受 base URL。

## 5. 登记状态、duplicate 与统一响应

### 5.1 状态分支

| 登记响应的 `status` | 后续动作 |
| --- | --- |
| `received` | 调用一次 `POST /api/v1/emails/{id}/process`；不调用 GET |
| `processing` | 不调用 process；调用一次 `GET /api/v1/emails/{id}` |
| `awaiting_review` | 不调用 process；调用一次 GET |
| `approved` | 不调用 process；调用一次 GET |
| `rejected` | 不调用 process；调用一次 GET |
| `human_takeover` | 不调用 process；调用一次 GET |
| `failed` | 不调用 process；调用一次 GET |
| 未知值 | 停止后续 API 调用，返回 `UNKNOWN_TASK_STATUS`，不调用 process/GET |

未知状态的响应示例（字段为工作流统一结构）：

```json
{
  "ok": false,
  "stage": "register",
  "task_id": 123,
  "duplicate": false,
  "api_status": 200,
  "result": null,
  "error": {
    "code": "UNKNOWN_TASK_STATUS",
    "message": "The registration response contains an unknown task status"
  },
  "next_action": "manual_inspection"
}
```

不得猜测未知状态的含义，也不得调用 process。

### 5.2 duplicate 处理

- `duplicate=true` 且 `status=received`：仍按 `received` 规则调用一次 process；
- `duplicate=true` 且 `status` 为其他已知状态：只调用一次 GET；
- 不因 `duplicate=true` 创建新任务；
- 不宣称 exactly-once；
- 不因状态变化循环调用任何 API。

### 5.3 统一响应

成功响应至少保留：

```json
{
  "ok": true,
  "stage": "process",
  "task_id": 123,
  "duplicate": false,
  "api_status": 200,
  "result": { "...": "FastAPI 实际返回的 EmailTaskDetail" },
  "error": null,
  "next_action": "human_review"
}
```

失败响应至少保留同样的八个字段；`result` 为 `null`，`error` 包含稳定错误码和说明。`task_id`、`duplicate` 在已知时保留。

`next_action` 映射：

| 任务状态 | `next_action` | 含义 |
| --- | --- | --- |
| `awaiting_review` | `human_review` | 等待人工审核 |
| `human_takeover` | `human_takeover` | 需要人工接管 |
| `approved` | `approved_not_sent` | 审核已批准，但**不表示邮件已发送** |
| `rejected` | `rejected` | 审核拒绝 |
| `processing` | `processing` | 仍在处理或查询到处理中 |
| `failed` | `failed` | 处理失败 |
| 其他/未知 | `manual_inspection` | 人工检查 |

禁止在响应或文档中声称：邮件已发送、通知已发送、人工已收到、已完成外部投递、发送成功。当前系统没有发送能力。

如果 process 返回 `409`：

- 保留 `task_id` 和 `duplicate`；
- 返回 `api_status=409`；
- 返回 `PROCESSING_CONFLICT` 错误；
- 不自动重试；
- 不循环调用 process；
- 如需要后续动作，只能提示人工通过 GET 查询。

## 6. 错误分支设计

以下为静态设计，**不代表已经通过实际联调验证**。

### 6.1 登记阶段

| 情况 | 设计行为 |
| --- | --- |
| `201` | 新建任务，读取 `id`、`duplicate`、`status` |
| `200` | 可能是重复登记，读取 `id`、`duplicate`、`status` |
| `422` | `VALIDATION_ERROR`，不调用 process/GET |
| `500` | `REGISTER_FAILED`，不猜测任务是否创建 |
| `503` | `REGISTER_UNAVAILABLE`，不猜测任务是否创建 |
| 网络错误/超时 | `NETWORK_ERROR`，不自动再次提交 |

### 6.2 process 阶段

| 情况 | 设计行为 |
| --- | --- |
| `200` | 返回任务详情，按 `result.status` 设置 `next_action` |
| `404` | `TASK_NOT_FOUND`，不重试 |
| `409` | `PROCESSING_CONFLICT`，不重试 |
| `502` | `PROVIDER_FAILURE`，保留 API `detail`；如响应包含 `task`，保留 `task`；不重试 |
| `503` | `DATABASE_OR_SERVICE_UNAVAILABLE`，提示状态可能不确定；不重试 |
| `500` | `UNEXPECTED_PROCESSING_ERROR`，任务可能仍为 `processing`；不重试 |
| 网络错误/超时 | `NETWORK_ERROR`，`api_status=null`，不伪造 FastAPI 状态码；不重试 |

### 6.3 GET 阶段

| 情况 | 设计行为 |
| --- | --- |
| `200` | 返回当前任务详情，按 `result.status` 设置 `next_action` |
| `404` | `TASK_NOT_FOUND`，不重试 |
| `503` | `QUERY_UNAVAILABLE`，不重试 |
| 其他 HTTP 错误 | `QUERY_HTTP_ERROR`，返回统一失败结构 |
| 网络错误/超时 | `NETWORK_ERROR`，`api_status=null`，不重试 |

### 6.4 重试边界

- 不实现自动重试；
- 409 不得进入无限重试；
- 502 后任务通常已是 `failed`，再次 process 会得到 409，不是重试入口；
- 503 后任务状态不确定，正确动作是人工/调用方 GET 查询，不是自动重试；
- 500 后任务可能仍为 `processing`，没有自动回收；
- 网络超时不自动再次提交登记；
- API 没有 `Retry-After`，不要自行发明等待时间。

## 7. 状态语义与外部发送

- `awaiting_review`：等待人工审核；不是已发送。
- `human_takeover`：需要人工接管；不是已发送。
- `approved`：审核已批准；**不代表邮件已发送**。
- `rejected`：审核拒绝；不代表外部系统已收到通知。
- `processing`：仍在处理或查询到处理中。
- `failed`：处理失败；不代表已重试或已恢复。

当前没有真实邮箱、真实 AI、Slack 或邮件发送能力。任何“已发送”“已通知”“人工已收到”“外部投递完成”的表述都不准确。


## 8. n8n 与 FastAPI 的访问地址、兼容性

- 当前 Compose 只有 `db` 和 `n8n`，**没有 FastAPI service**。
- n8n 容器中的 `localhost` 指向 n8n 容器自身，不是宿主机；不能写 `http://localhost:8000` 去访问宿主机 FastAPI。
- 当前 Compose 没有 `extra_hosts`；Linux Docker Engine 默认不一定能解析 `host.docker.internal`。后续可能需要 `extra_hosts: ["host.docker.internal:host-gateway"]`、宿主机网关 IP，或把 FastAPI 加入 Compose。上述都尚未验证。
- 按 uvicorn 默认行为，README 中的启动命令通常只监听 `127.0.0.1`；容器访问宿主机 FastAPI 时，需要 FastAPI 监听可被容器访问的地址（例如 `0.0.0.0`），并确认防火墙。
- `FASTAPI_BASE_URL` 只是配置设计，尚未实际验证注入方式。使用 n8n 环境变量时，还需要确认 n8n 是否允许 `$env` 访问；也可以在工作流配置节点中固定本地地址，但不要把地址从 Webhook 输入中接受。
- 当前 Compose 使用 `n8nio/n8n:latest`，版本未固定：
  - 工作流 JSON 的节点字段、HTTP Request 的错误处理选项、`Never Error` 的输出结构、Switch 节点版本、Respond to Webhook 的响应码表达式，均需要后续导入验证；
  - 不能宣称当前节点参数已兼容当前 n8n；
  - 不能宣称表达式已在 n8n 中执行过；
  - 不能宣称 Webhook 已可访问，或 n8n 已能访问 FastAPI。
- 宿主机访问 n8n Webhook 的常见地址是 `http://localhost:5678/webhook/test-webhook-triage`；测试模式是 `/webhook-test/test-webhook-triage`。这是 n8n 约定，尚未在本项目验证。
- 当前 n8n 未启用登录鉴权（`N8N_BASIC_AUTH_ACTIVE=false`），仅适合本地演示；没有生产级鉴权。

## 9. 合成测试数据与预期

### 9.1 普通产品咨询

`examples/n8n/normal-product-question.json`：

```json
{
  "mailbox_id": "test@example.com",
  "message_id": "<stage6-normal-product-001@example.com>",
  "subject": "产品功能咨询",
  "body": "这是一封合成测试邮件：请问产品有哪些功能？价格如何？"
}
```

基于当前 Mock AI 和现有规则，首次提交的**预期**是进入 `awaiting_review`。这只是静态推理，尚未实际联调验证。

### 9.2 退款请求

`examples/n8n/refund-request.json`：

```json
{
  "mailbox_id": "test@example.com",
  "message_id": "<stage6-refund-request-001@example.com>",
  "subject": "退款申请",
  "body": "这是一封合成测试邮件：客户要求退款，请协助处理。"
}
```

基于当前规则，**预期**进入 `human_takeover`；这表示人工接管，不表示已发送通知或邮件。尚未实际联调验证。

### 9.3 重复提交

没有单独的 duplicate 示例文件。重复测试时：

- 再次发送 `normal-product-question.json`；
- 保持相同的 `mailbox_id` 和 `message_id`；
- 登记响应预期为 `200`、`duplicate=true`；
- 若状态为 `received`，工作流仍调用一次 process；若为其他已知状态，只调用 GET；
- 不因重复登记创建新任务；
- 不宣称 exactly-once。

### 9.4 数据安全

GET 和 process 的响应可能包含邮件正文和草稿。只能使用合成测试数据；不要发送真实客户数据、真实邮件正文、真实凭据或个人信息。

## 10. 数据库安全、限制与验证状态

### 10.1 数据库安全

- 不修改 `ai_support`；
- 不执行迁移；
- 不运行数据库测试；
- 测试或联调必须显式使用 `ai_support_test`；
- API 进程没有数据库名保护，启动前必须显式设置正确的 `DATABASE_URL`；
- 不要依赖当前已有的 uvicorn 进程，它的实际数据库连接未知；
- 不把密码、完整数据库连接串或 `.env` 提交到 Git；
- 不把数据库连接串写入 n8n 工作流。

### 10.2 当前限制

- 没有生产级鉴权、审计、限流、加密或合规能力；
- 没有真实邮箱、真实 AI、Slack 或邮件发送；
- 没有自动重试、processing 超时回收；
- 不承诺 exactly-once；
- 进程中断或数据库提交确认失败时，任务状态可能不确定；
- 规则和 Mock AI 基于关键词，可能误判或漏判。

### 10.3 验证状态

本轮只做了静态检查：

- JSON 可以解析；
- 工作流中只有 Webhook、Code、HTTP Request、Switch、Respond to Webhook 节点；
- 没有 Gmail、Outlook、DeepSeek、OpenAI、Claude、Slack 或邮件发送节点；
- 没有 review、approve 或自动重试逻辑；
- 登记请求只包含四个 API 字段；
- 工作流保留 `task_id` 和 `duplicate`；
- `received` 才调用 process，其他已知状态调用 GET，未知状态停止；
- 409 不进入重试循环；
- 示例数据为合成数据。

**静态 JSON 检查不等于错误分支已经通过实际联调验证。** 后续需要在受控测试环境中单独验证：

- 404、409、502、503；
- 网络超时；
- 重复提交；
- n8n 导入和节点参数兼容性；
- Webhook 可访问性；
- n8n 容器到 FastAPI 的网络路径；
- 实际数据库目标为 `ai_support_test`。

在完成这些验证前，工作流只能称为“待导入验证的 n8n 工作流草稿”。
