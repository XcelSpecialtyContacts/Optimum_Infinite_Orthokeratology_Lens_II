@echo off

REM ============================================
REM Accept the work order argument
REM ============================================
set WO=%2

REM ============================================
REM Move to required working directory
REM ============================================
cd /d D:\oiol2

REM ============================================
REM Execute Python point file generator
REM ============================================
D:\Python32\python.exe -m oiol2.main --wo %WO%

REM ============================================
REM Capture Python exit code
REM ============================================
set EXITCODE=%ERRORLEVEL%

REM ============================================
REM Return same exit code to calling process
REM ============================================
exit /b %EXITCODE%