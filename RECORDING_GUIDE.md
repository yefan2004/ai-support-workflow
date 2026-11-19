# 90 秒录屏指南：真实 IMAP 全链路

> 端口与 workflow 状态以 [docs/PORTS.md](docs/PORTS.md) 为准：n8n 5679、主 API 8014、Demo API 8020、Demo UI 8503、主 Streamlit 8504。

## 录屏目标

用**主栈**录制一条真实链路：

```text
真实邮件 → n8n IMAP → FastAPI 登记/规则/AI → Streamlit 人工审核 → 通过 / 退款拦截
```

Demo 栈不在画面里展开，只在结尾用一句“无需邮箱的离线审核子集”带过。

> 录屏主线是主栈。不要花时间解释“Demo 为什么没有 n8n”。

---

## 一、录屏前检查清单

### 1. 确认主栈 n8n 容器和端口

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}' | grep -E 'n8n|postgres'
```

当前只保留一个 n8n：

- `ai-support-n8n-manual-stage6`：5679（唯一保留）

5678 已退役，容器已删除；根 compose 的 n8n 仅在 `--profile legacy` 下可用。录屏只使用 5679。

检查项：

- [ ] 主栈 n8n UI 可以打开（5679）
- [ ] workflow 已激活（`active=true`）
- [ ] IMAP Credentials 已配置；录屏时不要打开 Credentials 页面
- [ ] workflow 主链路是 Register Email → Switch → Process/Get，邮件节点指向 `http://172.17.0.1:8014`
- [ ] AI 分类由 `/api/v1/emails/{id}/process` 负责；独立的 `/api/v1/ai/triage` 不在邮件主链路里

### 2. 启动 / 确认 PostgreSQL

如果主栈数据库还没有启动：

```bash
docker compose up -d db
docker compose ps
```

n8n 5679 是现有手动容器，**不要**再用 `docker compose up -d n8n` 启动第二个；只确认主库：

```bash
docker exec ai-support-db pg_isready -U demo -d ai_support
```

- [ ] 返回 `accepting connections`
- [ ] 5432 没有被其他服务占用

### 3. 启动 FastAPI（8014）

```bash
source .venv/bin/activate

# 首次运行且没有 .env 时：
# cp .env.example .env

alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8014
```

必须监听 `0.0.0.0`。如果只监听 `127.0.0.1`，n8n 容器访问不到宿主机的 FastAPI。

另开终端检查：

```bash
curl -sS http://127.0.0.1:8014/health
curl -sS http://127.0.0.1:8014/api/v1/emails | head -c 300
```

- [ ] health 返回 `{"status":"ok",...}`
- [ ] 列表接口返回 JSON（空列表也可以，说明数据库连通）
- [ ] 8014 没有被其他进程占用

### 4. 启动 Streamlit（8504）

先确认 8014 / 8504 的占用情况：

```bash
ss -ltnp | grep -E ':(8014|8504)\b' || true
```

```bash
source .venv/bin/activate
API_BASE_URL=http://127.0.0.1:8014 \
  streamlit run frontend_app.py --server.port 8504
```

- [ ] 打开 http://127.0.0.1:8504
- [ ] 语言切换到中文
- [ ] 能看到“待审核”列表
- [ ] 页面没有“无法连接后端”提示

Demo UI 固定 8503，主栈用 8504，两者不冲突，不需要停 Demo UI。

### 5. 检查 n8n → FastAPI 连通性

```bash
# 当前唯一保留的 n8n 容器
N8N_CONTAINER=ai-support-n8n-manual-stage6

# 容器默认网关就是宿主机地址（Linux Docker Engine 常见为 172.17.0.1）
HOST_IP=$(docker exec "$N8N_CONTAINER" sh -c "ip route | awk '/default/ {print \$3; exit}'")

echo "n8n=$N8N_CONTAINER host_ip=$HOST_IP"
docker exec "$N8N_CONTAINER" wget -qO- "http://$HOST_IP:8014/health"
```

- [ ] 返回 `{"status":"ok",...}`
- [ ] `$HOST_IP` 已填入 n8n workflow 的 HTTP Request URL（或对应环境变量）
- [ ] 如果失败，先检查 FastAPI 是否监听 `0.0.0.0:8014`
- [ ] 如果失败，检查宿主机防火墙 / 安全组是否放行 8014
- [ ] 不要把 `localhost` 填进 workflow；它指向 n8n 容器自身

如果使用 Docker Desktop，通常可以解析 `host.docker.internal`：

```bash
docker exec "$N8N_CONTAINER" wget -qO- http://host.docker.internal:8014/health
```

Linux Docker Engine 默认不一定能解析这个域名，以上面的网关 IP 为准。

### 6. 邮箱与测试数据

- [ ] 使用专用 163 测试邮箱，不接入真实客户邮箱
- [ ] 从另一个邮箱发信到测试邮箱
- [ ] 普通邮件主题：`[RECORDING] 产品咨询 - 48V 供电`
- [ ] 普通邮件正文：`请问这款伺服电机支持 48V 供电吗？`
- [ ] 退款邮件主题：`[RECORDING] 退款申请`
- [ ] 退款邮件正文：`客户要求退款，请协助处理。`
- [ ] 录屏前使用干净的测试库；如果旧任务较多，新任务会按更新时间出现在列表最上面
- [ ] n8n Schedule Trigger 轮询间隔较长时，录屏中手动点“Execute Workflow”，不要假装自动触发

### 7. AI Provider 与画面准备

- [ ] 主栈 `.env` 当前是 `AI_PROVIDER=deepseek`；Demo 固定 `mock`，不要混用
- [ ] 如果使用 Mock，草稿是通用模板；如果使用 DeepSeek，确保 Key 已配置，但不要出现在画面
- [ ] 浏览器缩放到 110%–125%，关闭无关标签和通知
- [ ] 布局建议：左侧 n8n，右侧 Streamlit，邮箱窗口按需出现
- [ ] 终端里不要显示 `.env`、API Key、IMAP 授权码
- [ ] 不要在镜头前修改 Docker 配置或数据库结构

---

## 二、90 秒逐字稿

> 语速约 4–5 字/秒；`[]` 内是操作，引号内是口播。

### 0:00–0:08 开场

“这是一套 AI 邮件分诊与人工审核系统：真实邮件进 n8n，FastAPI 分类并生成草稿，最后交给人审批。”

[画面：Streamlit 审核台 + n8n workflow 各一半]

### 0:08–0:20 主栈

“现在跑的是主栈：n8n 通过 IMAP 读取 163 测试邮箱，FastAPI 分类，Streamlit 审核。这条链路已经用 7 封真实测试邮件跑通。”

[画面：n8n IMAP workflow；鼠标划过 IMAP 节点和 HTTP Request 节点，不展开凭据]

### 0:20–0:28 发真实邮件

“我从另一个邮箱发一封产品咨询邮件到测试邮箱。”

[画面：邮件客户端发送 `[RECORDING] 产品咨询 - 48V 供电`]

### 0:28–0:38 n8n 拉取

“n8n 读取这封邮件，清洗字段后调用 FastAPI 登记。”

[画面：n8n 点击 Execute Workflow；执行成功后展示节点绿色状态]

### 0:38–0:50 Streamlit 出现

“刷新审核台，新任务已经出现。打开详情：原始邮件、AI 摘要、风险等级和回复草稿都在这里。”

[画面：刷新 Streamlit；点开新任务；展示原文、摘要、风险、草稿]

### 0:50–1:00 人工审核

“草稿可以直接改。确认没问题，点击「通过」。”

[画面：在草稿框里做一个小修改；点击中文界面的“通过”按钮]

### 1:00–1:10 强调不发送

“通过只代表人工审核完成，系统不会自动发送邮件；发送仍由业务系统控制。”

[画面：状态变为“已通过”；不要出现“已发送”字样]

### 1:10–1:25 退款拦截

“再发一封退款邮件。退款属于高风险，规则引擎直接转人工接管，AI 不会被调用。”

[画面：发送 `[RECORDING] 退款申请`；n8n 手动执行；Streamlit 出现“人工接管”，没有 AI 草稿]

### 1:25–1:30 收尾

“主栈负责真实 IMAP 全链路；Demo 栈是不需要邮箱的离线审核子集。”

[画面：回到总览，停留在人工接管任务]

---

## 三、录制时不要说的话 / 不要做的事

- 不要说“邮件已发送”“已通知客户”“已完成外部投递”——当前没有发送能力。
- 不要把 `approved` 说成 `sent`；只说“人工审核通过”。
- 不要宣称生产级稳定性、生产级鉴权或规模化验证。
- 不要展示 `.env`、API Key、IMAP 授权码、真实客户邮件。
- 不要花时间解释“Demo 为什么没有 n8n”；一句“Demo 是离线审核子集”带过。
- 不要在镜头前修改 Docker 配置、数据库结构或测试数据。
- 不要用剪辑伪造“自动触发”或“AI 已发送”；等待时间可以剪掉，但因果顺序不能变。

## 四、失败兜底

| 现象 | 检查 |
| --- | --- |
| n8n 执行失败 / 网络错误 | 运行 `docker exec ... wget .../health`；确认 FastAPI 监听 `0.0.0.0:8014`；确认 workflow URL 不是 `localhost` |
| Streamlit 没有新任务 | 看 n8n 执行结果；用 `GET /api/v1/emails` 查任务；刷新页面 |
| 8504 被占用 | 换 8505；不要占用 Demo 的 8503 |
| 没有 AI 草稿 | 换普通产品 / 订单咨询；检查规则是否命中；Mock 对部分类别不生成草稿 |
| 退款没有拦截 | 主题或正文包含“退款”或 `refund`；检查规则关键词 |
| 数据库错误 | 执行 `alembic upgrade head`；检查 `.env` 的 `DATABASE_URL`；确认主栈 db 健康 |
| Process Email 500 / 任务 processing | 检查 8014 日志与 DeepSeek 配置；当前 process 错误不会自动重试，任务可能停留 processing |
| 5678 又出现 | 检查是否有人执行了 `docker compose --profile legacy up -d n8n`；默认不要启动 |
| 录屏时长超 90 秒 | 剪掉 n8n 等待和页面加载；保留发信、任务出现、审核、退款拦截四个因果点 |

## 五、录制完成检查

- [ ] 画面里能看出是主栈：n8n（5679）+ FastAPI（8014）+ Streamlit（8504）
- [ ] n8n workflow 已激活；链路为 Register Email → Switch → Process/Get
- [ ] 普通邮件完整走完：发信 → n8n → `awaiting_review` → 人工“通过”
- [ ] 退款邮件走到“人工接管”，没有 AI 草稿
- [ ] 全程没有出现“已发送 / Sent”
- [ ] 没有泄露凭据、真实客户数据或 `.env`
- [ ] Demo 只作为“离线审核子集”一句带过，没有展开解释
- [ ] 成片 90 秒左右，因果顺序清楚

---

**一句话口径：** 主栈负责真实 IMAP 全链路；Demo 栈负责无需邮箱的离线审核子集。两者共用同一套业务代码和审核流程。
