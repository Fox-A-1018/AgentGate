@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] The .venv environment was not found.
  echo Run setup-agentgate.cmd first.
  pause
  exit /b 1
)

echo ==================================================
echo AgentGate is starting
echo ==================================================
echo Dashboard: http://127.0.0.1:8010/
echo API docs:  http://127.0.0.1:8010/docs
echo.
echo Keep this window open. Press Ctrl+C to stop.
echo ==================================================
echo.

".venv\Scripts\python.exe" scripts\run_server.py %*
if errorlevel 1 (
  echo.
  echo [ERROR] AgentGate failed to start. Review the error above.
  pause
  exit /b 1
)
