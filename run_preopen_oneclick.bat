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
set "LLM_LIMIT=1"
if not "%~2"=="" set "LLM_LIMIT=%~2"

set "COMMON_ARGS=--with-source-fetch --llm-limit %LLM_LIMIT%"
if not "%~1"=="" (
  set "COMMON_ARGS=--date %~1 %COMMON_ARGS%"
)

set "LIVE_LLM_FLAG="
if defined MOONSHOT_API_KEY (
  set "LIVE_LLM_FLAG=--with-live-llm"
)

echo [TradingSystem] Starting one-click preopen pipeline...
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
echo [TradingSystem] Preopen summaries:
dir /b /o:-d outputs\preopen\preopen_summary_*.md 2>nul
echo.
echo [TradingSystem] Editable holdings file:
echo workspace\portfolio\current_holdings.json
echo.
pause
