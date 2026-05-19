@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    set "KEY=%%A"
    set "VAL=%%B"
    if not "!KEY!"=="" if /I not "!KEY:~0,1!"=="#" (
      set "!KEY!=!VAL!"
    )
  )
)

set "PYTHON_CMD=python"
set "LLM_MODE=stable"
if not "%~2"=="" set "LLM_MODE=%~2"

set "COMMON_ARGS=--with-source-fetch --strict-market-date --llm-mode %LLM_MODE%"
if not "%~1"=="" set "COMMON_ARGS=--date %~1 %COMMON_ARGS%"
if not "%~3"=="" set "COMMON_ARGS=%COMMON_ARGS% --llm-limit %~3"

set "LIVE_LLM_FLAG="
if defined MOONSHOT_API_KEY (
  set "LIVE_LLM_FLAG=--with-live-llm"
)

echo [TradingSystem] Starting one-click preopen pipeline...
echo [TradingSystem] Refreshing live account state...
%PYTHON_CMD% scripts\run_refresh_live_state.py
if errorlevel 1 (
  echo.
  echo [TradingSystem] Live account refresh failed.
  pause
  exit /b 1
)

echo.
echo [TradingSystem] Command: %PYTHON_CMD% scripts\run_assistant_pipeline.py %COMMON_ARGS% %LIVE_LLM_FLAG%
echo.

%PYTHON_CMD% scripts\run_assistant_pipeline.py %COMMON_ARGS% %LIVE_LLM_FLAG%
if errorlevel 1 (
  echo.
  echo [TradingSystem] Pipeline failed.
  pause
  exit /b 1
)

echo.
echo [TradingSystem] Pipeline completed.
echo [TradingSystem] Trading execution sheets:
dir /b /o:-d outputs\trade_execution\trade_execution_*.md 2>nul
echo.
echo [TradingSystem] Full preopen summaries:
dir /b /o:-d outputs\preopen\preopen_summary_*.md 2>nul
echo.
echo [TradingSystem] Editable holdings file:
echo workspace\portfolio\current_holdings.json
echo [TradingSystem] System trade log:
echo workspace\portfolio\system_trade_log.json
echo.
pause
