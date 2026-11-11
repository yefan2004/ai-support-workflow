# n8n 工作流（占位）

本目录用于存放 n8n 工作流 JSON 导出文件，供本地 n8n 实例导入。

## 规划中的工作流（本阶段未实现）

1. `email-ingest-workflow.json`：定时/Webhook 拉取测试邮箱邮件 → 调用后端 API 登记 → 去重判定（对应图 1）。
2. `triage-workflow.json`：规则检查 → 调用模拟 AI 分流接口 → 输出校验 → 进入待审核（对应图 2）。
3. `review-send-workflow.json`：人工审核结果回调 → 发送前检查 → 记录发送结果（对应图 3）。
4. `exception-alert-workflow.json`：错误重试与人工提醒（对应图 4）。

> 注意：本阶段不接入真实邮箱、Slack 或任何 AI 服务，不包含真实凭据。
