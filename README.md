# AgentGate

AgentGate 是《信息安全工程实践》课程项目，目标是在智能体与外部工具之间建立一个独立、确定、可测试的安全控制层。

项目不把大语言模型生成的工具调用视为授权。所有调用必须经过请求规范化、权限与策略判定，并根据风险进入允许、拒绝或人工审批流程；只有通过检查的请求才能由受控执行器调用本地模拟工具。关键阶段形成可关联、脱敏的审计事件。

## 当前状态

截至 2026 年 11 月 12 日，安全核心的第一版已经可以运行并通过自动化测试。当前实现包括请求规范化、五角色策略、ALLOW/DENY/REQUIRE_APPROVAL 三态决策、三类本地模拟工具、SQLite 审批与审计、审批摘要绑定、单次凭证、篡改与重放阻断，以及审计不可用时的 fail closed。

当前测试基线为 70 个测试全部通过，总体语句覆盖率 90%。其中包含 52 条结构化安全用例；当前本地评估得到决策与原因码一致率 100%、受保护用例控制率 100%、基本审计字段完整率 100%、误放行率 0%，网关 P95 延迟 25.975 ms。FastAPI 已提供请求提交、审批、批准后执行和审计链查询接口，并通过真实 Uvicorn 健康检查。这些结果只描述当前合成用例和本机单次运行，不代表生产级安全结论；轻量展示页面和自然语言端到端场景仍待完成。

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

- [实施路线图](docs/PROJECT_PLAN.md)
- [证据边界与待确认决策](docs/BASELINE_AND_DECISIONS.md)
- [原始材料管理约定](references/README.md)
- [实现状态](docs/IMPLEMENTATION_STATUS.md)
- [当前安全评估报告](docs/EVALUATION_REPORT.md)

## 安全边界

本项目只连接本地模拟资源，不使用真实邮箱、生产数据库、云资源、真实个人信息或具有实际外部副作用的服务。模型接入不属于核心验收前置条件。

## 本地运行

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,api]"
.\.venv\Scripts\python.exe -m pytest --cov=agentgate --cov-report=term-missing
.\.venv\Scripts\python.exe scripts\run_demo.py
.\.venv\Scripts\python.exe scripts\run_security_evaluation.py
.\.venv\Scripts\python.exe -m uvicorn agentgate.server:app --host 127.0.0.1 --port 8010
```

演示脚本依次运行公开文件读取、越权文件阻断、模拟消息审批和审批后执行，并输出完整审计链。运行数据写入 `data/runtime/`，不会进入 Git。

API 启动后可访问 `http://127.0.0.1:8010/docs` 查看交互式接口文档，或访问 `/health` 检查服务和策略版本。

