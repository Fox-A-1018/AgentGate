@echo off
setlocal
cd /d "%~dp0"

echo ==================================================
echo AgentGate first-time setup
echo ==================================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python launcher py.exe was not found.
  echo Install Python 3.11 or newer and enable Add Python to PATH.
  pause
  exit /b 1
)

py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3.11 or newer is required.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/2] Creating the project .venv environment...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create .venv.
    pause
    exit /b 1
  )
) else (
  echo [1/2] Existing .venv found. Reusing it.
)

echo [2/2] Installing AgentGate dependencies...
".venv\Scripts\python.exe" -m pip install -e ".[dev,api]"
if errorlevel 1 (
  echo [ERROR] Dependency installation failed. Check the network and retry.
  pause
  exit /b 1
)

echo.
echo [DONE] AgentGate is ready.
echo Use start-agentgate.cmd for future launches.
pause
