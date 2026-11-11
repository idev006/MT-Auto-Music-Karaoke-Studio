@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\run.ps1" %*
exit /b %errorlevel%
