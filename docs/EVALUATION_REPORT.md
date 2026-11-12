# AgentGate 安全评估报告（第一轮）

评估日期：2026 年 11 月 12 日  
策略版本：`2026-11-12.1`

## 评估范围

本轮使用 `tests/security_cases/cases.json` 中 52 条合成安全用例，覆盖文件访问、数据库表字段与行数限制、消息收件域、敏感内容、RBAC、未知工具和参数校验。评估脚本对每条用例比较预期与实际的决策及原因码，并检查该请求是否至少形成一组 trace 一致、request 一致、事件类型与时间完整的审计事件。

## 当前结果

| 指标 | 结果 |
|---|---:|
| 结构化安全用例 | 52 |
| 决策与原因码一致率 | 100% |
| 受保护用例控制率 | 100% |
| 误放行率 | 0% |
| 基本审计字段完整率 | 100% |
| 延迟中位数 | 17.031 ms |
| P95 延迟 | 25.975 ms |
| 最大延迟 | 27.670 ms |

完整 pytest 回归共 70 条测试全部通过，总体语句覆盖率 90%。

## 复现方式

```powershell
.\.venv\Scripts\python.exe scripts\run_security_evaluation.py
```

如需保存机器可读结果：

```powershell
.\.venv\Scripts\python.exe scripts\run_security_evaluation.py --output reports\generated\security-evaluation.json
```

`reports/generated/` 属于本地生成物，不进入 Git。

## 解释边界

- 用例由当前项目策略人工构造，因此 100% 表示实现与这批预期一致，不等于对未知攻击的检测率为 100%。
- “受保护用例控制率”表示预期为 DENY 或 REQUIRE_APPROVAL 的用例没有被直接 ALLOW；它不是外部基准上的真实攻击阻断率。
- 审计完整率检查的是当前定义的基本关联字段，不等同于合规审计认证。
- 延迟来自当前本机的一次顺序运行，包含 SQLite 写入，未包含模型生成、人工审批等待与真实外部工具耗时；正式报告应在不同机器和多轮重复实验后给出波动范围。
