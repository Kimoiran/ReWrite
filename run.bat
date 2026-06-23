@echo off
cd /d "%~dp0"
title ReWrite

:: Check venv
if not exist ".venv\Scripts\python.exe" (
    echo [First run] Creating virtual environment...
    :: Try to find normal Python (not Anaconda) to avoid DLL conflicts
    for %%p in (
        "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "C:\Program Files\Python313\python.exe"
        "C:\Program Files\Python312\python.exe"
        "C:\Program Files\Python311\python.exe"
    ) do (
        if exist %%p (
            "%%~p" -m venv .venv
            if not errorlevel 1 goto deps
        )
    )
    :: Fallback to system python
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create venv. Make sure Python >= 3.10 is installed.
        echo Download from: https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

:deps
echo [Check] Verifying dependencies...
.venv\Scripts\python.exe -c "import PySide6" 2>nul
if errorlevel 1 (
    echo [First run] Installing dependencies...
    .venv\Scripts\pip.exe install -r requirements.txt
    if errorlevel 1 (
        .venv\Scripts\pip.exe install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
    )
)

:: Ensure works/ exists
if not exist "works\" mkdir works

:: Launch
echo [Launch] Starting ReWrite...
.venv\Scripts\python.exe src\main.py
if errorlevel 1 (
    echo Launch failed (code: %errorlevel%)
    pause
)
