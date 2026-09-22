@echo off

REM ============================================
REM Accept the work order argument
REM ============================================
set WO=%2

REM ============================================
REM Set paths
REM ============================================
set "OIOL2_HOME=D:\xpf\oiol2"
set "PY32=D:\Python32\python.exe"

if not exist "%PY32%" (
    echo ERROR: 32-bit Python not found at %PY32% 1>&2
    exit /b 1
)

if not exist "%OIOL2_HOME%\src\oiol2\main.py" (
    echo ERROR: oiol2 package not found at %OIOL2_HOME%\src\oiol2\main.py 1>&2
    exit /b 1
)

REM ============================================
REM Move to required working directory
REM Set the working directory
REM ============================================
cd /d "%OIOL2_HOME%"
set "PYTHONPATH=%OIOL2_HOME%\src"

REM ============================================
REM Execute Python point file generator
REM ============================================
"%PY32%" -m oiol2.main --wo %WO%

REM ============================================
REM Capture Python exit code
REM ============================================
set EXITCODE=%ERRORLEVEL%

REM ============================================
REM Return same exit code to calling process
REM ============================================
endlocal & exit /b %EXITCODE%