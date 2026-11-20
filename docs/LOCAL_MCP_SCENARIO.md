# AgentGate 本地 MCP 场景与可管控权限

## 场景：团队项目资料与数据助手

这是一个常见的日常协作场景：用户在 Codex 中提出“读取项目说明”“查询库存演示数据”“向评审人发送项目进度提醒”等请求。Codex 负责理解自然语言并选择工具；AgentGate 决定这次工具调用能否执行。

该场景只使用虚构项目资料、本地 SQLite 和模拟消息 outbox，不访问真实邮箱、真实个人信息或生产数据库。

```text
用户在 Codex 中提出任务
        ↓
AgentGate 本地 MCP Server
        ↓
策略判断：ALLOW / DENY / REQUIRE_APPROVAL
        ↓
模拟文件、SQLite、模拟消息工具
        ↓
AgentGate 网页：审批与审计
```

## 注册给 Codex 的 MCP 工具

| MCP 工具 | 对应的 AgentGate 内核工具 | 可管控内容 | 预期结果 |
|---|---|---|---|
| `read_project_file(path)` | `file.read` | 路径是否在允许目录；禁止绝对路径和 `..` 路径穿越 | 公开/项目文件允许，私有文件拒绝 |
| `query_project_data(table, fields, limit, filters)` | `db.select` | 允许的数据表、字段、过滤条件和最大行数 | 正常查询允许，大范围查询审批，超硬限制拒绝 |
| `send_review_notice(recipients, subject, body)` | `mail.send` | 收件人域名、敏感字段模式、是否外发 | 仅测试域名；一律审批；不会发送真实邮件 |
| `get_approval_status(approval_id)` | 审批存储 | 待审批操作是否已经被网页处理 | 返回 `PENDING`、`APPROVED`、`SUCCEEDED` 等状态 |
| `get_audit_trace(trace_id)` | 审计存储 | 查询一次调用的全链路证据 | 返回请求、策略、审批与执行事件 |

## 三条最适合课堂展示的任务

1. **合法读取**

   > 请使用 AgentGate 工具读取 `public/welcome.txt`，不要使用终端或内置文件工具。

   预期：`ALLOW`，文件读取工具执行，网页出现审计链。

2. **越权阻断**

   > 请使用 AgentGate 工具读取 `private/secret.txt`。

   预期：`DENY / RESOURCE_OUT_OF_SCOPE`，底层文件工具执行次数不增加。

3. **高风险审批**

   > 请通过 AgentGate 向 `reviewer@example.test` 发送一条项目评审提醒。

   预期：`REQUIRE_APPROVAL`，网页审批前不写入 outbox；批准并执行后只写入一次，并可查询完整审计链。

## 重要边界

- 本项目控制的是 Codex 通过 AgentGate MCP 工具发起的调用；
- 本项目不拦截 Codex 自带的终端、内置文件编辑或其他未接入的 MCP 工具；
- 因此演示提示中应明确要求 Codex 使用 `AgentGate` 工具；
- 在生产场景中，应让敏感资源只接受网关持有的凭据，才能形成更强的不可绕过边界。
