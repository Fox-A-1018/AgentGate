# 将 AgentGate 接入本机 Codex

本指南把 AgentGate 作为一个**本地 MCP Server**接入 Codex。它运行在你的电脑上，由 Codex 启动并通过标准输入/输出通信；不需要公网服务器、域名或额外模型 API Key。

## 1. 准备项目环境

在项目根目录执行一次：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,api]"
```

其中 `mcp` 已是项目依赖，会随安装自动获得。

## 2. 启动审批与审计网页

双击 `start-agentgate.cmd`，或在 PowerShell 执行：

```powershell
.\.venv\Scripts\python.exe scripts\run_server.py
```

网页地址：<http://127.0.0.1:8010/>

网页不会替 Codex 选择工具；它用于查看待审批请求和审计记录。

## 3. 将本地 MCP Server 注册到 Codex

在 PowerShell 中执行一次：

```powershell
codex mcp add agentgate --env "AGENTGATE_PROJECT_ROOT=C:\BUPT\2026大四\AgentGate" -- "C:\BUPT\2026大四\AgentGate\.venv\Scripts\python.exe" -m agentgate.mcp_server
```

这个命令的含义：

- `agentgate`：这台 MCP Server 在 Codex 中显示的名称；
- `--` 后面的 Python 命令：Codex 需要工具时，会启动这个本地程序；
- `-m agentgate.mcp_server`：运行项目新增的 MCP 服务模块；
- `AGENTGATE_PROJECT_ROOT`：让 MCP 服务找到策略文件、模拟资源和审计数据库。

确认是否添加成功：

```powershell
codex mcp list
```

完成后重启或新开一个 Codex 会话，让 Codex 重新加载工具。

## 4. 在 Codex 中验证

先明确要求 Codex 使用 AgentGate 工具，而不是它自己的终端或文件工具：

```text
请使用 AgentGate 的 read_project_file 工具读取 public/welcome.txt；不要使用终端或内置文件工具。
```

随后打开 AgentGate 网页查看审计记录。

可继续测试：

```text
请使用 AgentGate 的 read_project_file 工具读取 private/secret.txt。
```

预期结果是拒绝，不会调用底层文件读取器。

## 5. 审批如何继续

当 `send_review_notice` 或超过直接阈值的查询返回 `REQUIRE_APPROVAL`：

1. 记录返回值中的 `approval_id` 和 `trace_id`；
2. 打开 AgentGate 网页，在“待审批请求”中点击“批准并执行”；
3. 回到 Codex，让它调用 `get_approval_status(approval_id)` 或 `get_audit_trace(trace_id)`；
4. 展示批准前未执行、批准后只执行一次的审计证据。

## 6. 本地演示身份

默认 MCP 身份是 `codex-local-user`，角色是 `operator`，它来自 MCP 服务的本地配置，而不是由 Codex 在每次工具调用中填写。

需要测试不同策略时，可在注册前指定环境变量，例如：

```powershell
codex mcp remove agentgate
codex mcp add agentgate --env "AGENTGATE_PROJECT_ROOT=C:\BUPT\2026大四\AgentGate" --env "AGENTGATE_MCP_ROLE=viewer" -- "C:\BUPT\2026大四\AgentGate\.venv\Scripts\python.exe" -m agentgate.mcp_server
```

这是课程原型的本地配置，不是企业级登录认证。

## 7. 卸载本地连接

如不再需要这个连接：

```powershell
codex mcp remove agentgate
```
