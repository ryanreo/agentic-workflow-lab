@echo off
rem Workflowww launcher - uses Python on PATH, or the bundled runtime.
setlocal
set "PY=python"
where python >nul 2>nul
if not errorlevel 1 goto :found

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
  goto :found
)

set "PY=C:\Users\osage\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

:found

if /i "%~1"=="demo" (
  "%PY%" "%~dp0scripts\run_demo.py" %2 %3
  exit /b %errorlevel%
)

if /i "%~1"=="eval" (
  "%PY%" "%~dp0scripts\run_eval.py" %2
  exit /b %errorlevel%
)

echo Usage: run.cmd demo ^<agent^> [openai^|deepseek]   ^|   run.cmd eval [openai^|deepseek]
echo Agents: pipeline_doctor, document_extractor, deep_researcher, qa_agent
exit /b 1
