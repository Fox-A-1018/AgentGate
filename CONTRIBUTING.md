# AgentGate 协作开发说明

## 第一次运行

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,api]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\run_server.py
```

浏览器打开 `http://127.0.0.1:8010/`。所有运行数据保存在 `data/runtime/`，不会提交到 Git。

## 推荐协作流程

1. 从最新 `main` 创建独立分支，例如 `feature/identity-mapping`。
2. 一次分支只解决一个明确问题，不混入无关格式化或文档改写。
3. 提交前运行完整测试和 JavaScript 语法检查：

   ```powershell
   .\.venv\Scripts\python.exe -m pytest --cov=agentgate --cov-report=term
   node --check src\agentgate\web\app.js
   ```

4. 推送分支并创建 Pull Request，由另一名组员检查后再合并。
5. Pull Request 说明应包含：问题、实现方式、测试证据、是否改变安全边界。

## 分支建议

- `feature/*`：新功能。
- `fix/*`：缺陷修复。
- `test/*`：测试与实验。
- `docs/*`：文档和汇报材料。

不要提交 `.venv/`、`data/runtime/`、真实个人数据、真实密钥、DOCX/PDF 原材料或真实外部服务凭证。

## 当前安全边界

- 页面中的用户和角色是本地演示数据，尚未接入真实身份认证。
- 文件、数据库和消息工具全部是本地模拟工具。
- 当前评估结果只对应仓库内合成用例，不应被描述为生产级安全认证。
