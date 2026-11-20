@echo off
setlocal
cd /d "%~dp0"

echo ==================================================
echo Register AgentGate as a local Codex MCP server
echo ==================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] The project .venv environment was not found.
  echo Run setup-agentgate.cmd first.
  pause
  exit /b 1
)

where codex >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Codex CLI was not found on PATH.
  echo Open Codex Desktop once, then retry from a new terminal.
  pause
  exit /b 1
)

call codex mcp get agentgate >nul 2>nul
if not errorlevel 1 (
  echo [INFO] AgentGate is already registered for this Codex account.
  echo Verify it with: codex mcp get agentgate
  echo To register a different project path, first run: codex mcp remove agentgate
  pause
  exit /b 0
)

call codex mcp add agentgate --env "AGENTGATE_PROJECT_ROOT=%CD%" -- "%CD%\.venv\Scripts\python.exe" -m agentgate.mcp_server
if errorlevel 1 (
  echo [ERROR] AgentGate MCP registration failed. Review the error above.
  pause
  exit /b 1
)

echo.
echo [DONE] AgentGate is registered.
echo Open a new Codex local chat, then ask it to use AgentGate tools.
echo Verify in a terminal with: codex mcp get agentgate
pause
