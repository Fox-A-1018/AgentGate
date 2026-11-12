# AgentGate 使用指南

本指南面向第一次接触 Python 项目的同学。日常使用不需要手动激活 `.venv`，也不需要记住复杂命令。

## 1. 第一次使用

### 第一步：确认项目位置

当前项目目录应为：

```text
C:\BUPT\2026大四\AgentGate
```

进入该目录后，可以看到：

```text
setup-agentgate.cmd
start-agentgate.cmd
README.md
src
tests
```

### 第二步：初始化环境

双击：

```text
setup-agentgate.cmd
```

它会自动完成两件事：

1. 创建项目专用的 `.venv` Python 环境；
2. 安装 AgentGate、FastAPI 和测试依赖。

第一次安装需要联网，通常需要几分钟。看到 `[DONE] AgentGate is ready.` 后即可关闭窗口。

如果 `.venv` 已经存在，脚本会直接复用，不会重复创建。

## 2. 以后每次启动

双击：

```text
start-agentgate.cmd
```

看到以下提示表示服务已经启动：

```text
Uvicorn running on http://127.0.0.1:8010
```

保持这个命令窗口开启，然后在 Chrome 或 Edge 中访问：

```text
http://127.0.0.1:8010/
```

重要说明：关闭启动窗口或按 `Ctrl + C` 后，网页服务就会停止。

## 3. 网页怎么使用

页面主要由四部分组成。

### 3.1 系统状态

页面上方会显示：

- 网关是否正常运行；
- 当前策略版本；
- 待审批请求数量；
- 最近审计事件数量。

右上角出现“网关运行正常”，说明页面已经成功连接后端。

### 3.2 构造工具调用

页面提供四个预设场景。

#### 正常放行

Viewer 读取公开文件 `public/welcome.txt`。

预期结果：

```text
ALLOW
```

表示角色、工具和文件路径都符合策略，系统会执行文件读取。

#### 越权阻断

Viewer 尝试读取 `private/secret.txt`。

预期结果：

```text
DENY / RESOURCE_OUT_OF_SCOPE
```

表示目标文件超出 Viewer 的授权目录，底层文件工具不会执行。

#### 阈值审批

Analyst 对 `inventory` 表发起超过直接执行阈值的查询。

预期结果：

```text
REQUIRE_APPROVAL
```

请求不会立即查询，而是进入页面下方的待审批队列。

#### 人工审批

Operator 尝试发送一条模拟消息。

预期结果：

```text
REQUIRE_APPROVAL
```

本项目不会发送真实邮件。批准后只会向 `data/runtime/outbox.jsonl` 写入一条本地模拟记录。

### 3.3 策略判定

提交请求后，右侧会显示：

- `ALLOW`：允许并执行；
- `DENY`：拒绝，不执行工具；
- `REQUIRE_APPROVAL`：等待人工审批；
- 风险等级；
- 原因码；
- `trace_id`；
- 工具执行结果。

原因码用于解释系统为什么作出该决定，例如：

- `ALLOWED`：请求符合策略；
- `RESOURCE_OUT_OF_SCOPE`：资源超出授权范围；
- `APPROVAL_REQUIRED`：需要人工审批；
- `SENSITIVE_DATA_DETECTED`：发现敏感数据模式；
- `IDEMPOTENCY_CONFLICT`：同一个防重键被用于不同请求。

### 3.4 审批和审计

当请求进入待审批队列后，可以：

- 点击“批准并执行”：生成一次性凭证并执行原始请求；
- 点击“拒绝”：终止请求，不执行工具。

审计时间线会记录请求、策略判定、审批和执行结果。点击“查看审计链”可以只查看当前请求的完整过程。

## 4. 如何停止

回到运行 AgentGate 的命令窗口，按：

```text
Ctrl + C
```

终端停止后，`http://127.0.0.1:8010/` 将无法继续访问，这是正常现象。

## 5. 常用地址

| 用途 | 地址 |
|---|---|
| 演示网页 | `http://127.0.0.1:8010/` |
| API 交互文档 | `http://127.0.0.1:8010/docs` |
| 健康检查 | `http://127.0.0.1:8010/health` |

这些地址只能在启动 AgentGate 的本机访问，不是公网网站。

## 6. 常见问题

### 页面无法打开

确认启动窗口仍然开启，并且终端显示：

```text
Uvicorn running on http://127.0.0.1:8010
```

如果终端已经关闭，重新双击 `start-agentgate.cmd`。

### 页面只有空白背景

1. 在启动窗口按 `Ctrl + C`；
2. 重新双击 `start-agentgate.cmd`；
3. 回到浏览器按 `Ctrl + F5`；
4. 仍有问题时访问 `http://127.0.0.1:8010/?refresh=1`。

### 提示端口被占用

说明另一个程序正在使用 8010 端口。可以先寻找之前打开的 AgentGate 窗口并按 `Ctrl + C`，或者使用 PowerShell运行：

```powershell
.\.venv\Scripts\python.exe scripts\run_server.py --port 8011
```

然后访问：

```text
http://127.0.0.1:8011/
```

### 提示没有 `.venv`

双击 `setup-agentgate.cmd`，等待初始化完成后再启动。

### Python 安装失败或找不到 `py`

安装 Python 3.11 或更高版本，并在安装界面勾选 `Add Python to PATH`。安装完成后重新打开项目目录并运行初始化脚本。

### 想重新开始演示

运行数据保存在：

```text
data\runtime
```

不要在服务运行时修改该目录。确需重置时，先停止服务，将 `data\runtime` 重命名为 `runtime-backup`，再次启动后系统会创建新的运行数据。

## 7. 手动命令方式

如果不想使用 `.cmd` 文件，也可以在项目目录打开 PowerShell。

第一次安装：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,api]"
```

日常启动：

```powershell
.\.venv\Scripts\python.exe scripts\run_server.py
```

这里不需要先执行 `Activate.ps1`，因为命令直接指定了 `.venv` 中的 Python。

## 8. 组员第一次获取项目

组员获得仓库访问权限后执行：

```powershell
git clone https://github.com/Fox-A-1018/AgentGate.git
cd AgentGate
```

然后双击 `setup-agentgate.cmd`，以后使用 `start-agentgate.cmd` 启动。

项目的 `.venv`、运行数据库和课程原始 DOCX/PDF 不会上传到 GitHub，每位组员都需要在自己的电脑上初始化环境。

## 9. 安全边界

- 当前页面身份和角色属于本地演示数据，不是生产级登录系统；
- 文件、数据库和消息操作全部使用本地模拟资源；
- 系统不会发送真实邮件，也不会连接真实生产数据库；
- 当前测试结果只证明仓库内测试场景，不代表生产级安全认证。
