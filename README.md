# AgentGate

AgentGate 是《信息安全工程实践》课程项目，当前定位是一个**本地 MCP Server**：它把受控文件、数据查询和模拟消息工具提供给 Codex，并在每一次工具调用真正执行前进行独立、确定、可测试的安全判断。

项目不把大语言模型生成的工具调用视为授权。所有调用必须经过请求规范化、权限与策略判定，并根据风险进入允许、拒绝或人工审批流程；只有通过检查的请求才能由受控执行器调用本地模拟工具。关键阶段形成可关联、脱敏的审计事件。

## 当前状态

截至 2026 年 11 月 20 日，安全核心、本地演示网页和本地 MCP 接入层均已可以运行。当前实现包括请求规范化、五角色策略、ALLOW/DENY/REQUIRE_APPROVAL 三态决策、三类本地模拟工具、SQLite 审批与审计、审批摘要绑定、单次凭证、篡改与重放阻断，以及审计不可用时的 fail closed。网页可以构造演示请求、展示策略解释、处理待审批任务并查看审计时间线；Codex 也可通过本地 MCP 工具调用相同的安全内核。

当前测试基线为 85 个测试全部通过，总体语句覆盖率 92%。其中包含 52 条结构化安全用例；第一轮本地评估得到决策与原因码一致率 100%、受保护用例控制率 100%、基本审计字段完整率 100%、误放行率 0%，网关 P95 延迟 25.975 ms。FastAPI 已提供请求提交、审批查询与处理、批准后执行、近期审计和 trace 查询接口；网页与完整 HTTP 审批执行流程已经验证。SQLite 持久化幂等控制会复用相同请求的既有结果，并拒绝同一幂等键对应不同参数或并发处理中请求。这些结果只描述当前合成用例和本机运行，不代表生产级安全结论。

GitHub Actions 会在 `main` 推送和 Pull Request 上使用 Python 3.11、3.12 运行测试，要求总体覆盖率不低于 90%，并检查前端 JavaScript 语法。

## 推荐实现范围

- Python 3.11+
- Pydantic 数据模型
- SQLite 状态与审计存储
- pytest 自动化测试
- 规则化请求生成器作为必选入口
- 可选的模型 Tool Calling 适配器
- 文件读取、结构化数据库查询、模拟消息发送三类本地工具
- ALLOW、DENY、REQUIRE_APPROVAL 三态决策
- 审批摘要绑定、过期控制、单次凭证和重放防护
- 按 `trace_id` 与 `request_id` 查询的脱敏审计链

## 项目资料

- [新手使用指南](docs/USER_GUIDE.md)
- [实施路线图](docs/PROJECT_PLAN.md)
- [证据边界与待确认决策](docs/BASELINE_AND_DECISIONS.md)
- [原始材料管理约定](references/README.md)
- [实现状态](docs/IMPLEMENTATION_STATUS.md)
- [当前安全评估报告](docs/EVALUATION_REPORT.md)
- [课堂演示指南](docs/DEMO_GUIDE.md)
- [本地 Codex MCP 接入指南](docs/LOCAL_MCP_GUIDE.md)
- [本地 MCP 场景与权限设计](docs/LOCAL_MCP_SCENARIO.md)
- [协作开发说明](CONTRIBUTING.md)

## 安全边界

本项目只连接本地模拟资源，不使用真实邮箱、生产数据库、云资源、真实个人信息或具有实际外部副作用的服务。模型接入不属于核心验收前置条件。

## 最简单的本地运行方式

Windows 第一次使用时双击：

```text
setup-agentgate.cmd
```

然后双击，将 AgentGate 注册给本机 Codex：

```text
register-agentgate-mcp.cmd
```

以后进行网页演示或需要处理人工审批时，再双击：

```text
start-agentgate.cmd
```

然后浏览器访问 `http://127.0.0.1:8010/`。详细操作和故障处理见[新手使用指南](docs/USER_GUIDE.md)。

## 在 Codex 中使用 AgentGate MCP

### 这台电脑上已经做了什么

本项目的 MCP Server 不是部署到互联网，而是 Codex 在需要工具时启动的一个本地 Python 程序。我在当前电脑上执行了下面这条命令：

```powershell
codex mcp add agentgate --env "AGENTGATE_PROJECT_ROOT=C:\BUPT\2026大四\AgentGate" -- "C:\BUPT\2026大四\AgentGate\.venv\Scripts\python.exe" -m agentgate.mcp_server
```

它把一条配置保存到当前 Windows 用户的 Codex 配置中：

- 名称：`agentgate`；
- 启动程序：本项目 `.venv` 中的 Python；
- 启动模块：`agentgate.mcp_server`；
- 项目位置：`C:\BUPT\2026大四\AgentGate`。

当 Codex 想使用 AgentGate 工具时，它会启动这条本地命令；该程序再调用项目中的策略、审批、执行和审计内核。它不会上传项目文件，也不会替你开启公网端口。

### 同学如何在自己的电脑上复现

每位同学都必须在**自己的电脑**完成一次以下操作，不能直接复用你的 MCP 配置，因为每个人的项目目录和 Python 环境都不同。

1. 获取项目代码：

   ```powershell
   git clone https://github.com/Fox-A-1018/AgentGate.git
   cd AgentGate
   ```

2. 双击 `setup-agentgate.cmd`，等待虚拟环境和依赖安装完成。
3. 双击 `register-agentgate-mcp.cmd`。
4. 新开一个 Codex 本地会话，令 Codex 重新读取 MCP 配置。
5. 如需查看审批和审计网页，再双击 `start-agentgate.cmd`，访问 <http://127.0.0.1:8010/>。

`register-agentgate-mcp.cmd` 实际执行的就是 `codex mcp add`；它会自动使用该同学自己项目所在的绝对路径，因此同学不必手动修改复杂命令。

### 如何确认注册成功

最可靠的确认方式是在 PowerShell 输入：

```powershell
codex mcp get agentgate
```

看到以下三项即表示注册成功：

```text
enabled: true
transport: stdio
args: -m agentgate.mcp_server
```

也可以列出全部已注册服务：

```powershell
codex mcp list
```

Codex 桌面版与该用户的 Codex 配置共享 MCP 设置。不同版本的桌面界面中工具面板位置可能不同，因此不要只依赖某个菜单是否显示；真正的验证是新开本地会话后，让 Codex 实际调用一次 AgentGate 工具。工具调用记录中出现 `read_project_file`、`query_project_data` 或 `send_review_notice`，并且网页出现对应审计记录，才表示连接与功能都正常。

### 注册后要做什么

在一个新的 Codex 本地会话中，先输入：

```text
请使用 AgentGate 的 read_project_file 工具读取 public/welcome.txt；不要使用终端或内置文件工具。
```

预期：Codex 调用 `read_project_file`，AgentGate 返回 `ALLOW`，网页审计时间线记录本次调用。

然后输入：

```text
请使用 AgentGate 的 read_project_file 工具读取 private/secret.txt。
```

预期：AgentGate 返回 `DENY / RESOURCE_OUT_OF_SCOPE`，底层文件工具不执行。

最后输入：

```text
请通过 AgentGate 的 send_review_notice 工具，向 reviewer@example.test 发送一条项目评审提醒。
```

预期：返回 `REQUIRE_APPROVAL`。打开网页批准后，再让 Codex 调用 `get_approval_status` 或 `get_audit_trace` 查看结果。

### 修改代码后需要重新注册吗？

通常**不需要**。注册信息只保存“用哪个 Python 启动哪个模块”，不是代码副本；项目采用可编辑安装，下一次 Codex 启动 AgentGate MCP 子进程时会读取最新源码。

| 你改动了什么 | 需要做什么 |
|---|---|
| 改策略、工具实现、MCP 工具说明或普通 Python 源码 | 新开 Codex 会话；如已有工具进程，重启 Codex 更稳妥 |
| 改了 `pyproject.toml` 或新增依赖 | 再运行一次 `setup-agentgate.cmd`，然后重启 Codex |
| 改了项目所在目录、删除/重建了 `.venv` | 双击 `register-agentgate-mcp.cmd`；若提示已存在，先运行 `codex mcp remove agentgate` 再重新注册 |
| 修改了网页 | 重新启动 `start-agentgate.cmd`，浏览器按 `Ctrl + F5` |

如需删除本机注册：

```powershell
codex mcp remove agentgate
```

## 手动命令方式

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,api]"
.\.venv\Scripts\python.exe -m pytest --cov=agentgate --cov-report=term-missing
.\.venv\Scripts\python.exe scripts\run_demo.py
.\.venv\Scripts\python.exe scripts\run_security_evaluation.py
.\.venv\Scripts\python.exe scripts\run_server.py
```

演示脚本依次运行公开文件读取、越权文件阻断、模拟消息审批和审批后执行，并输出完整审计链。运行数据写入 `data/runtime/`，不会进入 Git。

服务启动后访问 `http://127.0.0.1:8010/` 使用演示网页；访问 `/docs` 查看交互式接口文档，或访问 `/health` 检查服务和策略版本。

